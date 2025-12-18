# exam2/management/commands/clear_subject_data.py
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exam2.models import Subject, Exam


class Command(BaseCommand):
    help = "指定 subjectNo(+fsyear) の Exam 以下を CASCADE で全削除する（Subject自体は残す）"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)
        parser.add_argument(
            "--fsyear",
            type=int,
            default=getattr(settings, "FSYEAR", None),
            help="年度（省略時: settings.FSYEAR）",
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        fsyear = options["fsyear"]
        if fsyear is None:
            raise CommandError("fsyear が未指定です。--fsyear を指定するか settings.FSYEAR を設定してください。")
        fsyear = int(fsyear)

        subject = Subject.objects.filter(subjectNo=subjectNo, fsyear=fsyear).first()
        if not subject:
            self.stdout.write(self.style.WARNING(f"Subject が存在しません: subjectNo={subjectNo} fsyear={fsyear}"))
            return

        exams = Exam.objects.filter(subject=subject)
        exam_cnt = exams.count()

        self.stdout.write("")
        self.stdout.write("===== 削除対象の確認（Exam以下CASCADE） =====")
        self.stdout.write(f"SubjectNo : {subject.subjectNo}")
        self.stdout.write(f"科目名    : {subject.name}")
        self.stdout.write(f"fsyear    : {subject.fsyear}")
        self.stdout.write(f"term      : {subject.term}")
        self.stdout.write(f"Exam件数  : {exam_cnt}")
        self.stdout.write("※ Subject 自体は削除しません。Exam 以下を削除します。")
        self.stdout.write("")

        confirm = input("実行しますか？ (y/yes で実行): ").strip().lower()
        if confirm not in ("y", "yes"):
            self.stdout.write(self.style.WARNING("処理を中止しました。"))
            return

        with transaction.atomic():
            deleted = exams.delete()  # CASCADEで Question/StudentExam/SEV/Adjust も落ちる想定
        self.stdout.write(self.style.SUCCESS(f"削除完了: subjectNo={subjectNo} fsyear={fsyear} (Exam以下CASCADE)"))
        self.stdout.write(f"  delete() result: {deleted}")