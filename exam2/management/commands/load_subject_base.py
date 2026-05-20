# exam2/management/commands/load_subject_base.py
import json
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from exam2.models import Subject, Exam


class Command(BaseCommand):
    help = "JSON から Subject / Exam を作成する（YAML自動解決版）"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str, help="対象 subjectNo（例: 1010401）")
        parser.add_argument("--json", type=str, default=None, help="JSON ファイルのパス（省略時は自動解決）")
        
        # 明示的に年度を渡したい場合のための引数（省略時は自動解決）
        parser.add_argument(
            "--fsyear",
            type=int,
            default=getattr(settings, "FSYEAR", None),
            help="年度（省略時は settings.FSYEAR。未設定なら dirinfo.yaml の fsyear から自動取得）",
        )

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
        fsyear_opt = options["fsyear"]

        # -----------------------------
        # utils.py パス設定とインポート
        # -----------------------------
        try:
            current_file = Path(__file__).resolve()
            ttc_root = current_file.parents[4]
            ttc_utilpath = ttc_root / "@TTC" / "util"

            if str(ttc_utilpath) not in sys.path:
                sys.path.insert(0, str(ttc_utilpath))

            import utils
        except Exception as e:
            raise CommandError(f"utils.py のインポートに失敗しました: {e}")

        # -----------------------------
        # fsyear の自動解決
        # -----------------------------
        if fsyear_opt is not None:
            fsyear = fsyear_opt
        else:
            try:
                # 引数にも settings にもない場合、dirinfo.yaml のトップにある現在のデフォルト値を拾う
                fsyear = int(utils.get_current_fsyear())
            except Exception as e:
                raise CommandError(f"dirinfo.yaml から fsyear を自動特定できませんでした: {e}")

        # -----------------------------
        # JSON パス決定
        # -----------------------------
        if options.get("json"):
            json_path = Path(options["json"])
        else:
            try:
                # 動的キー取得関数を使って "ans_json" のフルパスを取得
                json_path = utils.get_exam_config_path(subjectNo, str(fsyear), "ans_json")
            except Exception as e:
                raise CommandError(f"共通設定ファイル(YAML)からのパス自動取得に失敗しました: {e}")

        if not json_path.exists():
            raise CommandError(f"JSON ファイルが存在しません: {json_path}")

        self.stdout.write(f"YAML経由の動的JSON読み込み成功: {json_path}")

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

        # term は当面 settings.TERM を正とする
        term = getattr(settings, "TERM", None)
        if term is None:
            raise CommandError("settings.TERM が未設定です（term を Subject.term に保存するため必要）")
        term = int(term)

        # JSON 先頭の hash
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
        # Exam 作成（version ごと）
        # -----------------------------
        for v in versions:
            version = v.get("version")
            if not version:
                raise CommandError("versions[].version がありません")

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
                            self.stdout.write(self.style.WARNING("  problem_hash が一致しません（必要なら --update-hash）"))

                if exam.title != subject.name and subject.name:
                    exam.title = subject.name
                    exam.save(update_fields=["title"])

        self.stdout.write(self.style.SUCCESS("Subject / Exam 作成完了（Phase3）"))