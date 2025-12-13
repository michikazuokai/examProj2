from django.core.management.base import BaseCommand
from exam2.models import (
    Subject, Exam,
    StudentExamVersion, ExamAdjust
)

class Command(BaseCommand):
    help = "ExamAdjust を作成する（adjust=0）"

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
            self.stdout.write(self.style.ERROR("Exam が存在しません"))
            return

        created_count = 0

        for exam in exams:
            sev_list = StudentExamVersion.objects.filter(exam=exam)
            if not sev_list.exists():
                self.stdout.write(
                    self.style.WARNING(f"StudentExamVersion がありません: Exam {exam.id}")
                )
                continue

            for sev in sev_list:
                _, created = ExamAdjust.objects.get_or_create(
                    exam=exam,
                    student=sev.student,
                    defaults={"adjust": 0}
                )
                if created:
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"ExamAdjust 作成完了: {created_count} 件")
        )