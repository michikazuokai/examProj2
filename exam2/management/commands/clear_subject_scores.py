# exam2/management/commands/clear_subject_scores.py
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exam2.models import Subject, Exam, StudentExam, ExamAdjust


class Command(BaseCommand):
    help = "指定 subjectNo(+fsyear) の採点結果（TF/hosei/adjust）をゼロクリアする（確認付き）"

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
            self.stdout.write(self.style.ERROR(f"Subject が存在しません: subjectNo={subjectNo} fsyear={fsyear}"))
            return

        exams = Exam.objects.filter(subject=subject)
        if not exams.exists():
            self.stdout.write(self.style.WARNING("Exam が存在しません"))
            return

        se_qs = StudentExam.objects.filter(exam__in=exams)
        ea_qs = ExamAdjust.objects.filter(exam__in=exams)

        se_cnt = se_qs.count()
        ea_cnt = ea_qs.count()

        self.stdout.write("")
        self.stdout.write("===== ゼロクリア対象の確認 =====")
        self.stdout.write(f"SubjectNo : {subject.subjectNo}")
        self.stdout.write(f"科目名    : {subject.name}")
        self.stdout.write(f"fsyear    : {subject.fsyear}")
        self.stdout.write(f"term      : {subject.term}")
        self.stdout.write(f"年次      : {subject.nenji}")
        self.stdout.write("")
        self.stdout.write(f"対象 Exam 数       : {exams.count()}")
        self.stdout.write(f"StudentExam 件数  : {se_cnt}")
        self.stdout.write(f"ExamAdjust 件数   : {ea_cnt}")
        self.stdout.write("")
        self.stdout.write("※ レコードは削除されません。値のみ 0 にリセットされます。")
        self.stdout.write("")

        confirm = input("実行しますか？ (y/yes で実行): ").strip().lower()
        if confirm not in ("y", "yes"):
            self.stdout.write(self.style.WARNING("処理を中止しました。"))
            return

        with transaction.atomic():
            se_updated = se_qs.update(TF=0, hosei=0)
            ea_updated = ea_qs.update(adjust=0)

        self.stdout.write(self.style.SUCCESS(
            f"ゼロクリア完了: StudentExam={se_updated} 件, ExamAdjust={ea_updated} 件"
        ))