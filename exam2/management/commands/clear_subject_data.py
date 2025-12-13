# exam2/management/commands/clear_subject_data.py
from django.core.management.base import BaseCommand
from exam2.models import Subject

class Command(BaseCommand):
    help = "指定 subjectNo のデータを CASCADE で全削除する"

    def add_arguments(self, parser):
        parser.add_argument(
            "subjectNo",
            type=str,
            help="削除対象の subjectNo（例: 2022001）"
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]

        subject = Subject.objects.filter(subjectNo=subjectNo).first()
        if not subject:
            self.stdout.write(
                self.style.WARNING(f"Subject {subjectNo} は存在しません")
            )
            return

        # 表示用（削除前に情報を出す）
        subject_name = subject.name

        # ★ CASCADE 削除（これだけ）
        subject.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Subject {subjectNo} ({subject_name}) を CASCADE 削除しました"
            )
        )