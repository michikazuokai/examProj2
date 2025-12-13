# exam2/management/commands/show_subject_stats.py
from django.core.management.base import BaseCommand
from django.db.models import Sum, Max
from exam2.models import (
    Subject, Exam, Question,
    StudentExam, ExamAdjust
)

class Command(BaseCommand):
    help = "指定 subject の試験・採点・調整の統計情報を表示する"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]

        subject = Subject.objects.filter(subjectNo=subjectNo).first()
        if not subject:
            self.stdout.write(self.style.ERROR("Subject が存在しません"))
            return

        exams = Exam.objects.filter(subject=subject)
        questions = Question.objects.filter(exam__in=exams)
        student_exams = StudentExam.objects.filter(exam__in=exams)
        exam_adjusts = ExamAdjust.objects.filter(exam__in=exams)

        self.stdout.write("=" * 40)
        self.stdout.write("Subject Statistics")
        self.stdout.write("=" * 40)
        self.stdout.write(f"SubjectNo : {subject.subjectNo}")
        self.stdout.write(f"Name      : {subject.name}")
        self.stdout.write(f"Nenji     : {subject.nenji}")
        self.stdout.write("-" * 40)

        versions = exams.values_list("version", flat=True).distinct()
        self.stdout.write(f"Exam count : {exams.count()}")
        self.stdout.write(f"Versions   : {', '.join(versions)}")
        self.stdout.write("-" * 40)

        q_total = questions.count()
        q_max_gyo = questions.aggregate(Max("gyo"))["gyo__max"] or 0
        q_points = questions.aggregate(Sum("points"))["points__sum"] or 0

        self.stdout.write("Questions")
        self.stdout.write(f"  Total questions : {q_total}")
        self.stdout.write(f"  Max rows (gyo)  : {q_max_gyo}")
        self.stdout.write(f"  Total points   : {q_points}")
        self.stdout.write("-" * 40)

        se_total = student_exams.count()
        se_tf = student_exams.filter(TF=1).count()
        se_hosei = student_exams.filter(hosei__gt=0).count()
        se_unscored = student_exams.filter(TF=0, hosei=0).count()

        self.stdout.write("StudentExam (Scoring)")
        self.stdout.write(f"  Records total  : {se_total}")
        self.stdout.write(f"  TF=1 exists    : {'YES' if se_tf else 'NO'} ({se_tf})")
        self.stdout.write(f"  Hosei exists   : {'YES' if se_hosei else 'NO'} ({se_hosei})")
        self.stdout.write(f"  Unscored       : {se_unscored}")
        self.stdout.write("-" * 40)

        ea_total = exam_adjusts.count()
        ea_nonzero = exam_adjusts.exclude(adjust=0).count()

        self.stdout.write("ExamAdjust")
        self.stdout.write(f"  Records total  : {ea_total}")
        self.stdout.write(
            f"  Adjust entered : {'YES' if ea_nonzero else 'NO'} ({ea_nonzero})"
        )

        self.stdout.write("=" * 40)