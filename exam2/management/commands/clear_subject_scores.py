# exam2/management/commands/clear_subject_scores.py

from django.core.management.base import BaseCommand
from exam2.models import Subject, Exam, StudentExam, ExamAdjust
from django.db import transaction

class Command(BaseCommand):
    help = "指定 subjectNo の採点結果（TF / hosei / adjust）をゼロクリアする（確認付き）"

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
            self.stdout.write(self.style.WARNING("Exam が存在しません"))
            return

        # 対象件数の事前取得
        se_qs = StudentExam.objects.filter(exam__in=exams)
        ea_qs = ExamAdjust.objects.filter(exam__in=exams)

        se_cnt = se_qs.count()
        ea_cnt = ea_qs.count()

        # ---- 確認表示 ----
        self.stdout.write("")
        self.stdout.write("===== ゼロクリア対象の確認 =====")
        self.stdout.write(f"SubjectNo : {subject.subjectNo}")
        self.stdout.write(f"科目名    : {subject.name}")
        self.stdout.write(f"年次      : {subject.nenji}")
        self.stdout.write("")
        self.stdout.write(f"対象 Exam 数        : {exams.count()}")
        self.stdout.write(f"StudentExam 件数   : {se_cnt}")
        self.stdout.write(f"ExamAdjust 件数    : {ea_cnt}")
        self.stdout.write("")
        self.stdout.write("※ レコードは削除されません。値のみ 0 にリセットされます。")
        self.stdout.write("")

        # ---- 確認入力 ----
        confirm = input("実行しますか？ (y/yes で実行): ").strip().lower()
        if confirm not in ("y", "yes"):
            self.stdout.write(self.style.WARNING("処理を中止しました。"))
            return

        # ---- 実行 ----
        with transaction.atomic():
            se_updated = se_qs.update(TF=0, hosei=0)
            ea_updated = ea_qs.update(adjust=0)

        self.stdout.write(self.style.SUCCESS(
            f"ゼロクリア完了: StudentExam={se_updated} 件, ExamAdjust={ea_updated} 件"
        ))