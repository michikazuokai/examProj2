from django.core.management.base import BaseCommand
from exam2.models import Subject, Student, Exam, Question, StudentExam


class Command(BaseCommand):
    help = "指定された subjectNo / fsyear / term に対して StudentExam を一括作成する"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str, help="科目コード（例: 1010401）")
        parser.add_argument("fsyear", type=int, help="年度（例: 2025）")
        parser.add_argument("term", type=int, help="期（例: 1）")

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        fsyear = options["fsyear"]
        term = options["term"]

        try:
            subject = Subject.objects.get(subjectNo=subjectNo)
        except Subject.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Subject {subjectNo} が見つかりません"))
            return

        target_nenji = subject.nenji
        self.stdout.write(f"科目 {subjectNo} / 対象学年 {target_nenji}")

        # 対象学生（学年を計算： fsyear - entyear + 1）
        students = [
            stu for stu in Student.objects.all()
            if (fsyear - stu.entyear + 1) == target_nenji
        ]
        self.stdout.write(f"対象学生: {len(students)}名")

        # 対象 Exam（A/B/C など複数あれば全部）
        exams = Exam.objects.filter(subject=subject, fsyear=fsyear, term=term)
        self.stdout.write(f"対象試験数: {exams.count()}件")

        created_count = 0

        for exam in exams:
            self.stdout.write(f"--- Exam {exam.id} (version={exam.version}) を処理中 ---")

            questions = Question.objects.filter(exam=exam)

            for stu in students:
                for q in questions:
                    obj, created = StudentExam.objects.get_or_create(
                        student=stu,
                        exam=exam,
                        question=q,
                        defaults={"TF": 0, "hosei": 0}
                    )
                    if created:
                        created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"StudentExam 作成完了: 新規 {created_count} 件"
        ))