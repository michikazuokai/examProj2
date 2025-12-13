from django.core.management.base import BaseCommand
from exam2.models import (
    Subject, Exam, Question,
    StudentExamVersion, StudentExam
)

class Command(BaseCommand):
    help = "StudentExam を高速に作成（TF=0, hosei=0）"

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

        total_created = 0
        bulk_list = []

        for exam in exams:
            questions = list(Question.objects.filter(exam=exam))
            sevs = StudentExamVersion.objects.filter(exam=exam).select_related("student")

            if not questions or not sevs:
                continue

            for sev in sevs:
                for q in questions:
                    bulk_list.append(
                        StudentExam(
                            student=sev.student,
                            exam=exam,
                            question=q,
                            TF=0,
                            hosei=0,
                        )
                    )

            # ★ ここで一気に INSERT（メモリ節約のため分割）
            StudentExam.objects.bulk_create(
                bulk_list,
                batch_size=1000,   # ★ 重要
                ignore_conflicts=True
            )
            total_created += len(bulk_list)
            bulk_list.clear()

        self.stdout.write(
            self.style.SUCCESS(f"StudentExam 作成完了: {total_created} 件")
        )