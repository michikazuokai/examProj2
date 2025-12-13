# exam2/management/commands/load_students.py

import csv
from django.core.management.base import BaseCommand
from exam2.models import Student


class Command(BaseCommand):
    help = "CSV から student テーブルを再構築する（全削除→再ロード）"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help="読み込む student CSV ファイルのパス"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="実際にはDBを変更せず、件数と内容のみ表示する"
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="確認プロンプトを省略して実行する"
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        dry_run = options["dry_run"]
        auto_yes = options["yes"]

        # -------------------------
        # CSV 読み込み
        # -------------------------
        rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        if not rows:
            self.stdout.write(self.style.WARNING("CSV にデータがありません"))
            return

        # -------------------------
        # 現状確認
        # -------------------------
        current_count = Student.objects.count()
        new_count = len(rows)

        self.stdout.write("===================================")
        self.stdout.write(" student 再ロード")
        self.stdout.write("-----------------------------------")
        self.stdout.write(f"現在の student 件数 : {current_count}")
        self.stdout.write(f"CSV の student 件数 : {new_count}")
        self.stdout.write(f"CSV ファイル        : {csv_path}")
        self.stdout.write("===================================")

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] 実際の削除・追加は行いません"))
            return

        # -------------------------
        # 確認
        # -------------------------
        if not auto_yes:
            confirm = input("本当に student を全削除して再ロードしますか？ [y/N]: ")
            if confirm.lower() not in ("y", "yes"):
                self.stdout.write(self.style.WARNING("キャンセルしました"))
                return

        # -------------------------
        # 削除
        # -------------------------
        deleted, _ = Student.objects.all().delete()
        self.stdout.write(f"削除件数: {deleted}")

        def parse_bool(v, default=True):
            if v is None:
                return default
            v = str(v).strip().lower()
            if v in ("1", "true", "t", "yes", "y"):
                return True
            if v in ("0", "false", "f", "no", "n"):
                return False
            return default

        # -------------------------
        # 作成（bulk_create）
        # -------------------------
        students = []
        for r in rows:
            students.append(Student(
                id=int(r["id"]),
                entyear=int(r["entyear"]),
                stdNo=r["stdNo"],
                email=r["email"],
                name1=r["name1"],
                name2=r["name2"],
                nickname=r["nickname"],
                gender=r["gender"],
                COO=r["COO"],
                enrolled = parse_bool(r.get("enrolled"), default=True)
                #enrolled=bool(int(r["enrolled"])) if r["enrolled"] is not None else True,
            ))

        Student.objects.bulk_create(students)

        self.stdout.write(
            self.style.SUCCESS(f"student 再ロード完了: {len(students)} 件")
        )