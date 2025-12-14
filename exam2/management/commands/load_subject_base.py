# exam2/management/commands/load_subject_base.py

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from exam2.models import Subject, Exam
from django.conf import settings

class Command(BaseCommand):
    help = "JSON から Subject / Exam（A,B 等）を作成する"

    # ★ デフォルト JSON 置き場
    DEFAULT_JSON_DIR = Path(
        "/Volumes/NBPlan/TTC/examtools/work"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "subjectNo",
            type=str,
            help="対象 subjectNo（例: 2022001）"
        )
        parser.add_argument(
            "--json",
            type=str,
            help="JSON ファイルのパス（省略時は自動解決）"
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]

        # -----------------------------
        # JSON パス決定
        # -----------------------------
        if options.get("json"):
            json_path = Path(options["json"])
        else:
            json_path = self.DEFAULT_JSON_DIR / f"answers_{subjectNo}.json"

        if not json_path.exists():
            raise CommandError(f"JSON ファイルが存在しません: {json_path}")

        self.stdout.write(f"JSON 読み込み: {json_path}")

        # -----------------------------
        # JSON 読み込み
        # -----------------------------
        with json_path.open(encoding="utf-8") as f:
            data = json.load(f)

        versions = data.get("versions", [])
        if not versions:
            raise CommandError("versions が存在しません")

        # -----------------------------
        # メタ情報（questions[0]）
        # -----------------------------
        meta = versions[0]["questions"][0]

        if meta.get("subject") != subjectNo:
            raise CommandError(
                f"subjectNo 不一致: 引数={subjectNo}, JSON={meta.get('subject')}"
            )

        subject_name = meta["title"]
        nenji = int(meta["nenji"])
        fsyear = meta["fsyear"]
        problem_hash=meta["metainfo"]["hash"]

        # -----------------------------
        # Subject 作成 or 取得
        # -----------------------------
        subject, created = Subject.objects.get_or_create(
            subjectNo=subjectNo,
            defaults={
                "name": subject_name,
                "nenji": nenji,
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Subject 作成: {subjectNo} {subject_name}")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"Subject 既存: {subjectNo} {subject.name}")
            )

        # -----------------------------
        # Exam 作成（version ごと）
        # -----------------------------
        term = settings.TERM   # ← ★ 今回の唯一の term 情報源
        for v in versions:
            version = v["version"]

    # JSON の metainfo から取得済みとする
    # problem_hash = meta["hash"]

            exam, created = Exam.objects.get_or_create(
                subject=subject,
                fsyear=fsyear,
                term=term,
                version=version,
                defaults={
                    "title": subject.name,
                    "problem_hash": problem_hash,   # ★ 新規作成時のみ
                }
            )

            # ★ 既存 Exam に hash が無い場合のみ補完（安全）
            if not created and not exam.problem_hash and problem_hash:
                exam.problem_hash = problem_hash
                exam.save(update_fields=["problem_hash"])

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Exam 作成: {subjectNo} {fsyear} {version}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Exam 既存: {subjectNo} {fsyear} {version}"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Subject / Exam 作成完了"))