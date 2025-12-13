from django.core.management.base import BaseCommand
from exam2.models import Exam, Question, StudentExam, StudentExamVersion, Subject


class Command(BaseCommand):
    help = "StudentExamVersion をもとに StudentExam を作成（学生 × 試験 × 問題）"

    def add_arguments(self, parser):
        parser.add_argument("subject_no", type=str, help="科目コード 例: 2030402")
        parser.add_argument("fsyear", type=int, help="年度 例: 2025")
        parser.add_argument("term", type=int, help="期 例: 2")

    def handle(self, *args, **options):
        subject_no = options["subject_no"]
        fsyear = options["fsyear"]
        term = options["term"]

        # --- Subject 取得 ---
        try:
            subject = Subject.objects.get(subjectNo=subject_no)
        except Subject.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Subject {subject_no} が見つかりません"))
            return

        # --- 対象 Exam 取得（A/B/C ... すべて） ---
        exams = Exam.objects.filter(subject=subject, fsyear=fsyear, term=term)

        if not exams.exists():
            self.stderr.write(self.style.ERROR("対象 Exam がありません"))
            return

        self.stdout.write(self.style.SUCCESS(f"対象 Exam 件数: {exams.count()} 件"))

        created_count_total = 0

        for exam in exams:
            version = exam.version

            # --- この version を受ける学生を取得 ---
            sev_list = StudentExamVersion.objects.filter(exam=exam).select_related("student")
            students = [sev.student for sev in sev_list]

            self.stdout.write(self.style.SUCCESS(
                f"--- Exam {exam.id} (version={version}) ---"
            ))
            self.stdout.write(f"対象学生: {len(students)} 名")

            # --- Question 取得 ---
            questions = exam.questions.all()
            self.stdout.write(f"問題数: {questions.count()} 問")

            created_count = 0

            # --- 学生 × 問題 で StudentExam を作成 ---
            for student in students:
                for q in questions:
                    _, created = StudentExam.objects.get_or_create(
                        student=student,
                        exam=exam,
                        question=q,
                        defaults={"TF": 0, "hosei": 0}
                    )
                    if created:
                        created_count += 1

            created_count_total += created_count

            self.stdout.write(self.style.SUCCESS(
                f"→ Exam {exam.id} で新規作成 {created_count} 件"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"=== 全体で新規作成 {created_count_total} 件 完了 ==="
        ))