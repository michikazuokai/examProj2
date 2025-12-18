# exam2/management/commands/load_subject_base.py

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from exam2.models import Subject, Exam


class Command(BaseCommand):
    help = "JSON から Subject / Exam（A,B 等）を作成する（Phase3: Subjectにfsyear/term、Examはsubject+version）"

    # ★ デフォルト JSON 置き場
    DEFAULT_JSON_DIR = Path("/Volumes/NBPlan/TTC/examtools/work")

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str, help="対象 subjectNo（例: 1010401）")
        parser.add_argument("--json", type=str, default=None, help="JSON ファイルのパス（省略時は自動解決）")

        # 安全系（任意）
        parser.add_argument(
            "--update-subject",
            action="store_true",
            help="既存 Subject の name/nenji/term を JSON に合わせて更新する（デフォルトは更新しない）",
        )
        parser.add_argument(
            "--update-hash",
            action="store_true",
            help="既存 Exam の problem_hash が違う場合も JSON に合わせて更新する（デフォルトは空だけ補完）",
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        update_subject = options["update_subject"]
        update_hash = options["update_hash"]

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
            raise CommandError("JSON に versions が存在しません")

        if not versions[0].get("questions"):
            raise CommandError("JSON の versions[0].questions が空です")

        # -----------------------------
        # メタ情報（先頭）
        # -----------------------------
        meta = versions[0]["questions"][0]

        if (meta.get("subject") or "") != subjectNo:
            raise CommandError(f"subjectNo 不一致: 引数={subjectNo}, JSON={meta.get('subject')}")

        subject_name = meta.get("title") or ""
        nenji = int(meta.get("nenji") or 0)
        fsyear = meta.get("fsyear", None)
        if fsyear is None:
            raise CommandError("JSON に fsyear がありません（meta['fsyear']）")
        fsyear = int(fsyear)

        # term は当面 settings.TERM を正とする（Phase3: Subject.term に保存）
        term = getattr(settings, "TERM", None)
        if term is None:
            raise CommandError("settings.TERM が未設定です（term を Subject.term に保存するため必要）")
        term = int(term)

        # JSON 先頭の hash（fallback）
        meta_hash = (meta.get("metainfo") or {}).get("hash") or ""

        # -----------------------------
        # Subject 作成 or 取得（Phase3: subjectNo + fsyear）
        # -----------------------------
        subject, created = Subject.objects.get_or_create(
            subjectNo=subjectNo,
            fsyear=fsyear,
            defaults={
                "name": subject_name,
                "nenji": nenji,
                "term": term,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Subject 作成: {subjectNo} fsyear={fsyear} term={term} name={subject_name}"))
        else:
            self.stdout.write(self.style.WARNING(f"Subject 既存: {subjectNo} fsyear={fsyear} name={subject.name} term={subject.term}"))

            # 必要なら更新（安全のためオプション制）
            if update_subject:
                changed = False
                if subject_name and subject.name != subject_name:
                    subject.name = subject_name
                    changed = True
                if nenji and int(subject.nenji or 0) != nenji:
                    subject.nenji = nenji
                    changed = True
                if term and int(subject.term or 0) != term:
                    subject.term = term
                    changed = True

                if changed:
                    subject.save(update_fields=["name", "nenji", "term"])
                    self.stdout.write(self.style.SUCCESS("Subject を更新しました（--update-subject）"))

        # -----------------------------
        # Exam 作成（version ごと / Phase3: Examにfsyear/termは無い）
        # -----------------------------
        for v in versions:
            version = v.get("version")
            if not version:
                raise CommandError("versions[].version がありません")

            # version ごとの hash を優先（なければ meta_hash）
            vh = ""
            if v.get("questions"):
                vmeta = v["questions"][0]
                vh = (vmeta.get("metainfo") or {}).get("hash") or ""
            problem_hash = vh or meta_hash

            exam, e_created = Exam.objects.get_or_create(
                subject=subject,
                version=version,
                defaults={
                    "title": subject.name,
                    "problem_hash": problem_hash,
                },
            )

            if e_created:
                self.stdout.write(self.style.SUCCESS(f"Exam 作成: {subjectNo}({fsyear}) version={version}"))
            else:
                self.stdout.write(self.style.WARNING(f"Exam 既存: {subjectNo}({fsyear}) version={version}"))

                # hash 補完/更新
                if problem_hash:
                    if not exam.problem_hash:
                        exam.problem_hash = problem_hash
                        exam.save(update_fields=["problem_hash"])
                        self.stdout.write(self.style.SUCCESS("  problem_hash を補完しました（空→埋め）"))
                    elif exam.problem_hash != problem_hash:
                        if update_hash:
                            old = exam.problem_hash
                            exam.problem_hash = problem_hash
                            exam.save(update_fields=["problem_hash"])
                            self.stdout.write(self.style.SUCCESS(f"  problem_hash 更新: {old} -> {problem_hash}（--update-hash）"))
                        else:
                            self.stdout.write(self.style.WARNING("  problem_hash が一致しません（更新しません。必要なら --update-hash）"))

                # title は Subject.name を正とする（軽い補正）
                if exam.title != subject.name and subject.name:
                    exam.title = subject.name
                    exam.save(update_fields=["title"])

        self.stdout.write(self.style.SUCCESS("Subject / Exam 作成完了（Phase3）"))