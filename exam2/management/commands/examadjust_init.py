from django.core.management.base import BaseCommand
from exam2.models import Exam, ExamAdjust, StudentExamVersion, Subject


class Command(BaseCommand):
    help = "ExamAdjust（補正値）を初期化（version別学生 × exam）で作成）"

    def add_arguments(self, parser):
        parser.add_argument("subject_no", type=str, help="科目コード 例: 2030402")
        parser.add_argument("fsyear", type=int, help="年度 例: 2025")
        parser.add_argument("term", type=int, help="期 例: 2")

    def handle(self, *args, **options):
        subject_no = options["subject_no"]
        fsyear = options["fsyear"]
        term    = options["term"]

        # --- Subject ---
        try:
            subject = Subject.objects.get(subjectNo=subject_no)
        except Subject.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Subject {subject_no} が見つかりません"))
            return

        # --- 対象 Exam（A/B 全部） ---
        exams = Exam.objects.filter(subject=subject, fsyear=fsyear, term=term)

        if not exams.exists():
            self.stderr.write(self.style.ERROR("対象 Exam がありません"))
            return

        self.stdout.write(self.style.SUCCESS(f"対象 Exam 件数: {exams.count()}件"))

        total_created = 0

        for exam in exams:
            version = exam.version
            self.stdout.write(self.style.SUCCESS(
                f"\n--- Exam {exam.id} (version={version}) ---"
            ))

            # --- version 別に学生を取得 ---
            sev_list = StudentExamVersion.objects.filter(exam=exam)
            students = [sev.student for sev in sev_list]

            self.stdout.write(f"対象学生: {len(students)} 名")

            created_cnt = 0

            for student in students:
                _, created = ExamAdjust.objects.get_or_create(
                    exam=exam,
                    student=student,
                    defaults={"adjust": 0}
                )
                if created:
                    created_cnt += 1

            total_created += created_cnt

            self.stdout.write(self.style.SUCCESS(
                f"Exam {exam.id} で新規作成 {created_cnt} 件"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\n=== 全 Exam 合計 新規作成 {total_created} 件 完了 ==="
        ))