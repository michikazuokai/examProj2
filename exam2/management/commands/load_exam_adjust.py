# exam2/management/commands/load_exam_adjust.py

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exam2.models import Subject, StudentExamVersion, ExamAdjust


class Command(BaseCommand):
    help = "ExamAdjust を作成する（adjust=0）(Phase3対応)"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)

        # Phase3: Subject を (subjectNo, fsyear) で確定
        parser.add_argument(
            "--fsyear",
            type=int,
            default=getattr(settings, "FSYEAR", None),
            help="年度（省略時: settings.FSYEAR）",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="件数確認のみ（DBへ書き込まない）",
        )

        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="bulk_create の batch_size（default: 2000）",
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        fsyear = options["fsyear"]
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        if fsyear is None:
            raise CommandError("fsyear が未指定です。--fsyear か settings.FSYEAR を設定してください。")
        fsyear = int(fsyear)

        # ---- Subject（Phase3）----
        try:
            subject = Subject.objects.get(subjectNo=subjectNo, fsyear=fsyear)
        except Subject.DoesNotExist:
            raise CommandError(f"Subject が存在しません: subjectNo={subjectNo} fsyear={fsyear}")

        # ---- StudentExamVersion（このsubjectの割当）----
        sevs = (
            StudentExamVersion.objects
            .filter(exam__subject=subject)
            .select_related("student", "exam")
            .order_by("student__stdNo")
        )

        if not sevs.exists():
            self.stdout.write(self.style.WARNING("StudentExamVersion が 0 件です（先に load_student_exam_version を実行してください）"))
            return

        # ---- dry-run：作成予定件数の見積（既存は考慮しない簡易版）----
        if dry_run:
            self.stdout.write(self.style.SUCCESS("DRY-RUN OK"))
            self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term(DB)={subject.term}")
            self.stdout.write(f"  StudentExamVersion={sevs.count()} 件")
            self.stdout.write("  ExamAdjust は student×exam ごとに 1 件（既存は get_or_create でスキップ）")
            return

        created_attempted = 0
        buf = []

        with transaction.atomic():
            for sev in sevs:
                buf.append(
                    ExamAdjust(
                        exam=sev.exam,
                        student=sev.student,
                        adjust=0
                    )
                )

                if len(buf) >= batch_size:
                    # 既存スキップ運用（ユニーク制約: exam+student がある前提）
                    ExamAdjust.objects.bulk_create(buf, batch_size=batch_size, ignore_conflicts=True)
                    created_attempted += len(buf)
                    buf.clear()

            if buf:
                ExamAdjust.objects.bulk_create(buf, batch_size=batch_size, ignore_conflicts=True)
                created_attempted += len(buf)
                buf.clear()

        self.stdout.write(self.style.SUCCESS("ExamAdjust 作成完了（既存はスキップ）"))
        self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term(DB)={subject.term}")
        self.stdout.write(f"  attempted_inserts={created_attempted}（ignore_conflictsなので実作成数とは一致しない場合あり）")