import json
from pathlib import Path
from django.core.management.base import BaseCommand
from exam2.models import (
    Subject, Exam, Question,
    StudentExam, ExamAdjust
)

EXPORT_DIR = Path("exam2/data/export")
EXPORT_FILE = EXPORT_DIR / "examTFdata.json"


class Command(BaseCommand):
    help = "subject単位で StudentExam(TF/hosei) と ExamAdjust(adjust) をJSONにエクスポートする"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]

        subject = Subject.objects.filter(subjectNo=subjectNo).first()
        if not subject:
            self.stdout.write(self.style.ERROR("Subject が存在しません"))
            return

        exams = Exam.objects.filter(subject=subject)
        if not exams.exists():
            self.stdout.write(self.style.WARNING("Exam が存在しません"))
            return

        # 既存JSON読み込み
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        if EXPORT_FILE.exists():
            with open(EXPORT_FILE, "r", encoding="utf-8") as f:
                all_data = json.load(f)
        else:
            all_data = {}

        subject_data = {
            "students": {}
        }

        # Question を exam ごとに辞書化（id → q_no）
        question_map = {}
        for q in Question.objects.filter(exam__in=exams):
            question_map[q.id] = q.q_no

        # StudentExam
        student_exams = StudentExam.objects.filter(exam__in=exams).select_related(
            "student", "question"
        )

        for se in student_exams:
            stdno = se.student.stdNo
            q_no = question_map.get(se.question_id)
            if not q_no:
                continue

            stu = subject_data["students"].setdefault(stdno, {
                "answers": {},
                "adjust": 0
            })

            stu["answers"][q_no] = {
                "TF": se.TF,
                "hosei": se.hosei
            }

        # ExamAdjust
        exam_adjusts = ExamAdjust.objects.filter(exam__in=exams).select_related("student")

        for ea in exam_adjusts:
            stdno = ea.student.stdNo
            stu = subject_data["students"].setdefault(stdno, {
                "answers": {},
                "adjust": 0
            })
            stu["adjust"] = ea.adjust

        # subjectNo 単位で上書き
        all_data[subjectNo] = subject_data

        # 書き込み
        with open(EXPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(
            f"エクスポート完了: {EXPORT_FILE}（subjectNo={subjectNo} を更新）"
        ))