import csv
from django.core.management.base import BaseCommand
from exam2.models import Student


class Command(BaseCommand):
    help = "student テーブルを CSV にエクスポートする"

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default="student.csv",
            help="出力 CSV ファイル名（default: student.csv）"
        )

    def handle(self, *args, **options):
        outfile = options["out"]

        qs = Student.objects.all().order_by("id")

        if not qs.exists():
            self.stdout.write(self.style.WARNING("student データが存在しません"))
            return

        fields = [
            "id", "entyear", "stdNo", "email",
            "name1", "name2", "nickname",
            "gender", "COO", "enrolled"
        ]

        with open(outfile, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fields)

            for s in qs:
                writer.writerow([getattr(s, f) for f in fields])

        self.stdout.write(self.style.SUCCESS(
            f"student を CSV 出力しました: {outfile}（{qs.count()} 件）"
        ))