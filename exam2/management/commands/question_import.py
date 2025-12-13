import json
from django.core.management.base import BaseCommand
from exam2.models import Subject, Exam, Question


class Command(BaseCommand):
    help = "answer_xxxx.json から Question を生成（既存は上書き、削除しない）"

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="JSON ファイルのパス（answer_XXXX.json）",
        )

    def handle(self, *args, **options):
        json_path = options["json_path"]

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        versions = data.get("versions", [])
        if not versions:
            self.stdout.write(self.style.ERROR("versions が見つかりません"))
            return

        for version_block in versions:
            version = version_block.get("version")
            question_blocks = version_block.get("questions", [])

            if len(question_blocks) <= 1:
                continue

            # --- meta info ---
            meta = question_blocks[0]
            subjectNo = meta["subject"]
            fsyear = meta["fsyear"]
            term = int(meta["nenji"])

            # Exam を取得
            try:
                exam = Exam.objects.get(
                    subject__subjectNo=subjectNo,
                    fsyear=fsyear,
                    term=term,
                    version=version,
                )
            except Exam.DoesNotExist:
                self.stdout.write(self.style.ERROR("Exam 見つからず"))
                continue

            self.stdout.write(self.style.SUCCESS(f"Exam: {exam}"))

            # ----------- Question の登録 -----------
            for block_index, qblock in enumerate(question_blocks[1:], start=1):
                gyo = block_index

                labels = qblock["label"]
                answers = qblock["answer"]
                widths = qblock["width"]
                heights = qblock["height"]
                points = qblock["point"]
                koumokues = qblock["koumoku"]

                for idx in range(len(labels)):
                    retu = idx + 1

                    obj, created = Question.objects.get_or_create(
                        exam=exam,
                        q_no=labels[idx],
                        gyo=gyo,
                        retu=retu,
                        defaults={
                            "bunrui": koumokues[idx],
                            "points": points[idx],
                            "width": int(widths[idx]),
                            "height": int(heights[idx]),
                            "answer": answers[idx],
                        }
                    )

                    # 作成されなかった（既存があった）場合は上書き
                    if not created:
                        obj.bunrui = koumokues[idx]
                        obj.points = points[idx]
                        obj.width = int(widths[idx])
                        obj.height = int(heights[idx])
                        obj.answer = answers[idx]
                        obj.save()

                self.stdout.write(self.style.SUCCESS(f"  gyo={gyo} を更新"))

        self.stdout.write(self.style.SUCCESS("--- Question import 完了 ---"))