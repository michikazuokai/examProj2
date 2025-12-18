# exam2/management/commands/load_student_exam_version.py

from pathlib import Path
import yaml

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.apps import apps

from exam2.models import Subject, Exam, Student, StudentExamVersion


BASE_DIR = Path(apps.get_app_config("exam2").path)
DEFAULT_YAML = BASE_DIR / "data" / "studentVersion.yaml"


class Command(BaseCommand):
    help = "YAML に基づいて StudentExamVersion（A/B 割当）を作成する（Phase3対応）"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)

        # Phase3：Subject を (subjectNo, fsyear) で特定するので必須（settings.FSYEARで補完）
        parser.add_argument(
            "--fsyear",
            type=int,
            default=getattr(settings, "FSYEAR", None),
            help="年度（省略時: settings.FSYEAR）",
        )

        parser.add_argument(
            "--yaml",
            type=str,
            default=str(DEFAULT_YAML),
            help="version 割当 YAML（default: exam2/data/studentVersion.yaml）",
        )

        # 安全系
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="この subject の StudentExamVersion を先に削除して作り直す（推奨）",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="検証のみ（DBに書き込みしない）",
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        fsyear = options["fsyear"]
        yaml_path = Path(options["yaml"])
        clear_existing = options["clear_existing"]
        dry_run = options["dry_run"]

        if fsyear is None:
            raise CommandError("fsyear が未指定です。--fsyear を指定するか settings.FSYEAR を設定してください。")
        fsyear = int(fsyear)

        if not yaml_path.exists():
            raise CommandError(f"YAML が存在しません: {yaml_path}")

        # ---------- YAML 読み込み ----------
        with yaml_path.open("r", encoding="utf-8") as f:
            version_data = yaml.safe_load(f) or {}

        # ---------- Subject（Phase3） ----------
        try:
            subject = Subject.objects.get(subjectNo=subjectNo, fsyear=fsyear)
        except Subject.DoesNotExist:
            raise CommandError(f"Subject が存在しません: subjectNo={subjectNo} fsyear={fsyear}")

        nenji = int(subject.nenji)
        term_db = int(subject.term or 0)

        # YAML構造: version_data[fsyear][nenji][version] = [stdNo...]
        # nenjiキーが文字列の場合もあるので両対応
        # fkey = str(fsyear)
        # if fkey not in version_data:
        #     raise CommandError(f"YAML に fsyear={fsyear} のブロックがありません: {yaml_path}")

        nenji_map = version_data.get(fsyear) or version_data.get(str(fsyear)) or {}
        if not nenji_map:
            raise CommandError(f"YAML に fsyear={fsyear} のブロックがありません: {yaml_path}")
        vmap = nenji_map.get(nenji) or nenji_map.get(str(nenji))
        if not vmap:
            raise CommandError(f"YAML に nenji={nenji} のブロックがありません（fsyear={fsyear}）: {yaml_path}")

        # ---------- Exam（subject×version）を準備 ----------
        exams = {e.version: e for e in Exam.objects.filter(subject=subject)}
        if not exams:
            raise CommandError(f"Exam が存在しません（先に load_subject_base を実行）: subjectNo={subjectNo} fsyear={fsyear}")

        # 対象versionがDBに無い場合は警告
        for version in vmap.keys():
            if version not in exams:
                self.stdout.write(self.style.WARNING(f"DBに Exam がありません: version={version}（skip対象）"))

        # ---------- dry-run 検証 ----------
        if dry_run:
            missing_students = []
            used = 0
            for version, student_list in vmap.items():
                if version not in exams:
                    continue
                for stdNo in student_list or []:
                    used += 1
                    if not Student.objects.filter(stdNo=str(stdNo)).exists():
                        missing_students.append(str(stdNo))

            self.stdout.write(self.style.SUCCESS("DRY-RUN OK (validated)"))
            self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term(DB)={term_db} nenji={nenji}")
            self.stdout.write(f"  YAML students referenced={used}")
            if missing_students:
                self.stdout.write(self.style.WARNING(f"  Missing students in DB: {missing_students[:20]} ... (total {len(missing_students)})"))
            return

        # ---------- 反映 ----------
        created_count = 0
        updated_count = 0
        deleted_count = 0
        skipped_exam_count = 0
        skipped_student_count = 0

        with transaction.atomic():
            if clear_existing:
                deleted_count, _ = StudentExamVersion.objects.filter(exam__subject=subject).delete()

            for version, student_list in vmap.items():
                if version not in exams:
                    skipped_exam_count += 1
                    continue

                exam = exams[version]
                student_list = student_list or []

                for stdNo in student_list:
                    stdNo = str(stdNo)

                    student = Student.objects.filter(stdNo=stdNo).first()
                    if not student:
                        skipped_student_count += 1
                        self.stdout.write(self.style.WARNING(f"Student 不存在: {stdNo}（skip）"))
                        continue

                    # その学生のこの subject に対する既存割当を探して更新（複数あっても掃除）
                    qs = StudentExamVersion.objects.filter(student=student, exam__subject=subject)
                    # すでに同じexamなら更新しない
                    n = qs.exclude(exam=exam).update(exam=exam)
                    updated_count += n

                    if not qs.exists():
                        StudentExamVersion.objects.create(student=student, exam=exam)
                        created_count += 1

        self.stdout.write(self.style.SUCCESS("StudentExamVersion 作成/更新完了"))
        self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term(DB)={term_db} nenji={nenji}")
        if clear_existing:
            self.stdout.write(f"  deleted(existing)={deleted_count}")
        self.stdout.write(f"  created={created_count} updated={updated_count}")
        self.stdout.write(f"  skipped_exam_versions={skipped_exam_count} skipped_students={skipped_student_count}")
        self.stdout.write(f"  yaml={yaml_path}")