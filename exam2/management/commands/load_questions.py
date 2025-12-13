# exam2/management/commands/load_questions.py
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from exam2.models import Subject, Exam, Question


class Command(BaseCommand):
    help = "指定 subjectNo の JSON から Question を作成する"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)
        parser.add_argument(
            "--json",
            type=str,
            default=None,
            help="JSON ファイルパス（省略時は answers_<subjectNo>.json）",
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]

        # ------------------------
        # JSON パス決定
        # ------------------------
        if options["json"]:
            json_path = Path(options["json"])
        else:
            json_path = Path(
                f"/Volumes/NBPlan/TTC/examtools/work/answers_{subjectNo}.json"
            )

        if not json_path.exists():
            raise CommandError(f"JSON ファイルが見つかりません: {json_path}")

        self.stdout.write(f"JSON 読み込み: {json_path}")

        # ------------------------
        # Subject / Exam 取得
        # ------------------------
        subject = Subject.objects.filter(subjectNo=subjectNo).first()
        if not subject:
            raise CommandError(f"Subject が存在しません: {subjectNo}")

        # Exam は subject + fsyear + term + version
        exams = {
            e.version: e
            for e in Exam.objects.filter(subject=subject)
        }

        if not exams:
            raise CommandError("Exam が存在しません（先に load_subject_base.py を実行してください）")

        # ------------------------
        # JSON 読み込み
        # ------------------------
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        versions = data.get("versions", [])

        total_created = 0

        # ========================
        # version ループ（A/B）
        # ========================
        for vdata in versions:
            version = vdata["version"]

            if version not in exams:
                self.stdout.write(
                    self.style.WARNING(f"Exam が見つかりません: version={version}（skip）")
                )
                continue

            exam = exams[version]
            questions = vdata["questions"]

            # ------------------------
            # 基準 height
            # ------------------------
            base_height = questions[0]["height"]

            self.stdout.write(f"\n--- Exam {version} ---")

            # ========================
            # 行（gyo）ループ
            # questions[1] 以降が問題本体
            # ========================
            for gyo_idx, qblock in enumerate(questions[1:], start=1):
                widths = qblock["width"]
                labels = qblock["label"]
                answers = qblock["answer"]
                heights = qblock["height"]
                points = qblock["point"]
                koumokus = qblock["koumoku"]

                count = len(labels)

                # 安全チェック
                if not all(len(lst) == count for lst in
                           [widths, answers, heights, points, koumokus]):
                    raise CommandError(
                        f"配列長不一致: version={version}, gyo={gyo_idx}"
                    )

                for i in range(count):
                    q = Question.objects.create(
                        exam=exam,
                        q_no=labels[i],
                        bunrui=koumokus[i],
                        points=points[i],
                        answer=answers[i],
                        width=int(widths[i]),
                        height=int(heights[i] / base_height),
                        gyo=gyo_idx,
                        retu=i + 1,
                    )
                    total_created += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Exam {version}: Question 作成完了"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n=== Question 作成総数: {total_created} ==="
            )
        )