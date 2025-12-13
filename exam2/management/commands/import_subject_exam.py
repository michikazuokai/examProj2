import json
from django.core.management.base import BaseCommand
from exam2.models import Subject, Exam


class Command(BaseCommand):
    help = "answer_xxxx.json から Subject と Exam を生成する（Question は作らない）"

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="インポートする JSON ファイルのパス（answer_XXXX.json）",
        )

    def handle(self, *args, **options):
        json_path = options["json_path"]
        self.stdout.write(self.style.WARNING(f"--- JSON 読み込み開始: {json_path} ---"))

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        versions = data.get("versions", [])
        if not versions:
            self.stdout.write(self.style.ERROR("versions 配列が見つかりません"))
            return

        for version_block in versions:
            version = version_block.get("version")  # "A", "B" など
            q_blocks = version_block.get("questions", [])

            if not q_blocks:
                self.stdout.write(self.style.ERROR(f"{version}: questions が空です"))
                continue

            # --- ★ Block 0 が Exam メタ情報 ---
            meta = q_blocks[0]

            subjectNo = meta.get("subject")
            name = meta.get("title") 
            fsyear = meta.get("fsyear")
            term = int(meta.get("nenji", 1))   # 1期、2期…
            title = meta.get("title") or ""

            # --- Subject 作成 ---
            subject, created_sub = Subject.objects.get_or_create(
                subjectNo=subjectNo,
                defaults={"name": name},
            )

            if created_sub:
                self.stdout.write(self.style.SUCCESS(f"Subject 作成: {subjectNo} / {name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Subject 存在: {subjectNo}"))

            # --- Exam 作成 ---
            exam, created_exam = Exam.objects.get_or_create(
                subject=subject,
                fsyear=fsyear,
                term=term,
                version=version,
                defaults={"title": title},
            )

            if created_exam:
                self.stdout.write(
                    self.style.SUCCESS(f"Exam 作成: {subjectNo}-{version}（{title}）")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Exam 既存: {subjectNo}-{version}（上書きなし）")
                )

        self.stdout.write(self.style.SUCCESS("--- Subject / Exam インポート完了 ---"))