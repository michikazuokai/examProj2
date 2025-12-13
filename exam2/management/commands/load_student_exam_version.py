# exam2/management/commands/load_student_exam_version.py

from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps
from exam2.models import (
    Subject, Exam, Student, StudentExamVersion
)
import yaml
from pathlib import Path

'''
① subjectNo → subject
② fsyear, nenji → entyear 計算
③ entyear → student_queryset
④ subject → exam_queryset
⑤ YAML から (fsyear, nenji, version) → studentNo list
⑥
   for exam in exams:
     for student in students:
       if student.stdNo が YAML[version] に含まれる:
         StudentExamVersion 作成
'''

BASE_DIR = Path(apps.get_app_config("exam2").path)
DEFAULT_YAML = BASE_DIR / "data" / "studentVersion.yaml"

class Command(BaseCommand):
    help = "YAML に基づいて StudentExamVersion（A/B 割当）を作成する"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)
        parser.add_argument(
            "--yaml",
            type=str,
            default=str(DEFAULT_YAML),
            help="version 割当 YAML"
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        yaml_path = Path(options["yaml"])
        term = settings.TERM

        if not yaml_path.exists():
            self.stderr.write(self.style.ERROR(f"YAML が存在しません: {yaml_path}"))
            return

        # ---------- YAML 読み込み ----------
        with open(yaml_path, "r", encoding="utf-8") as f:
            version_data = yaml.safe_load(f)

        # ---------- Subject ----------
        subject = Subject.objects.filter(subjectNo=subjectNo).first()
        if not subject:
            self.stderr.write(self.style.ERROR("Subject が存在しません"))
            return

        nenji = subject.nenji

        created_count = 0

        # ---------- fsyear ループ ----------
        for fsyear_str, nenji_map in version_data.items():
            fsyear = int(fsyear_str)

            if nenji not in nenji_map:
                continue

            version_map = nenji_map[nenji]

            for version, student_list in version_map.items():
                # ---------- Exam ----------
                exam = Exam.objects.filter(
                    subject=subject,
                    fsyear=fsyear,
                    term=term,
                    version=version
                ).first()

                if not exam:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Exam が見つかりません: {subjectNo} {fsyear} {version}"
                        )
                    )
                    continue

                # ---------- StudentExamVersion ----------
                for stdNo in student_list:
                    student = Student.objects.filter(stdNo=str(stdNo)).first()
                    if not student:
                        self.stderr.write(
                            self.style.WARNING(f"Student 不存在: {stdNo}")
                        )
                        continue

                    _, created = StudentExamVersion.objects.get_or_create(
                        student=student,
                        exam=exam
                    )
                    if created:
                        created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"StudentExamVersion 作成完了: {created_count} 件"
            )
        )