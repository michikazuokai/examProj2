# exam2/management/commands/load_student_exam.py
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exam2.models import Subject, Question, StudentExamVersion, StudentExam


class Command(BaseCommand):
    help = "StudentExam を高速に作成（TF=0, hosei=0）(Phase3対応)"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)
        parser.add_argument("--fsyear", type=int, default=getattr(settings, "FSYEAR", None))
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        fsyear = options["fsyear"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        if fsyear is None:
            raise CommandError("fsyear が未指定です。--fsyear か settings.FSYEAR を設定してください。")
        fsyear = int(fsyear)

        try:
            subject = Subject.objects.get(subjectNo=subjectNo, fsyear=fsyear)
        except Subject.DoesNotExist:
            raise CommandError(f"Subject が存在しません: subjectNo={subjectNo} fsyear={fsyear}")

        sevs = (
            StudentExamVersion.objects
            .filter(exam__subject=subject)
            .select_related("student", "exam")
            .order_by("student__stdNo")
        )
        if not sevs.exists():
            self.stdout.write(self.style.WARNING("StudentExamVersion が 0 件です（先に load_student_exam_version を実行してください）"))
            return

        exam_ids = list(sevs.values_list("exam_id", flat=True).distinct())

        # ★ N+1問題：Question を 1回で取り、exam_id で束ねる
        questions_by_exam_id = {eid: [] for eid in exam_ids}
        for q in Question.objects.filter(exam_id__in=exam_ids).only("id", "exam_id"):
            questions_by_exam_id[q.exam_id].append(q)

        planned = 0
        for sev in sevs:
            planned += len(questions_by_exam_id.get(sev.exam_id) or [])

        if dry_run:
            self.stdout.write(self.style.SUCCESS("DRY-RUN OK"))
            self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term(DB)={subject.term}")
            self.stdout.write(f"  StudentExamVersion={sevs.count()} 件")
            self.stdout.write(f"  作成予定 StudentExam（試行数）={planned} 件")
            self.stdout.write("  ※ StudentExam に (student, exam, question) のユニーク制約がある前提です（ignore_conflicts運用）")
            return

        total_attempted = 0
        buf = []

        with transaction.atomic():
            for sev in sevs:
                q_list = questions_by_exam_id.get(sev.exam_id) or []
                if not q_list:
                    continue

                for q in q_list:
                    buf.append(StudentExam(
                        student=sev.student,
                        exam=sev.exam,
                        question=q,
                        TF=0,
                        hosei=0,
                    ))

                if len(buf) >= batch_size:
                    StudentExam.objects.bulk_create(buf, batch_size=batch_size, ignore_conflicts=True)
                    total_attempted += len(buf)
                    buf.clear()

            if buf:
                StudentExam.objects.bulk_create(buf, batch_size=batch_size, ignore_conflicts=True)
                total_attempted += len(buf)
                buf.clear()

        self.stdout.write(self.style.SUCCESS("StudentExam 作成完了（既存はスキップ）"))
        self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term(DB)={subject.term}")
        self.stdout.write(f"  attempted_inserts={total_attempted}")