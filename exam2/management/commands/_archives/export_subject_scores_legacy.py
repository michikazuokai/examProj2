# exam2/management/commands/export_subject_scores_legacy.py
import json
from pathlib import Path
from django.utils import timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models

# 新DB側の Student は managed=False のままで OK（legacy も同じ student テーブル想定）
from exam2.models import Student


# =========================
# Legacy(旧スキーマ)モデル
#  - Subject に fsyear が無い
#  - Exam に fsyear/term がある（旧運用）
# =========================
class LegacySubject(models.Model):
    subjectNo = models.CharField(max_length=32)  # 実DBに合わせて
    name = models.CharField(max_length=255, blank=True, null=True)
    nenji = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "exam2_subject"
        app_label = "exam2"


class LegacyExam(models.Model):
    subject = models.ForeignKey(
        LegacySubject, on_delete=models.DO_NOTHING, db_column="subject_id", related_name="+"
    )
    fsyear = models.IntegerField()
    term = models.IntegerField()
    version = models.CharField(max_length=8)
    title = models.CharField(max_length=255, blank=True, null=True)
#    problem_hash = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "exam2_exam"
        app_label = "exam2"


class LegacyQuestion(models.Model):
    exam = models.ForeignKey(LegacyExam, on_delete=models.DO_NOTHING, db_column="exam_id", related_name="+")
    q_no = models.CharField(max_length=64, blank=True, null=True)
    gyo = models.IntegerField(blank=True, null=True)
    retu = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "exam2_question"
        app_label = "exam2"


class LegacyStudentExamVersion(models.Model):
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING, db_column="student_id", related_name="+")
    exam = models.ForeignKey(LegacyExam, on_delete=models.DO_NOTHING, db_column="exam_id", related_name="+")

    class Meta:
        managed = False
        db_table = "exam2_studentexamversion"
        app_label = "exam2"


class LegacyStudentExam(models.Model):
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING, db_column="student_id", related_name="+")
    exam = models.ForeignKey(LegacyExam, on_delete=models.DO_NOTHING, db_column="exam_id", related_name="+")
    question = models.ForeignKey(LegacyQuestion, on_delete=models.DO_NOTHING, db_column="question_id", related_name="+")
    TF = models.IntegerField()
    hosei = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "exam2_studentexam"
        app_label = "exam2"


class LegacyExamAdjust(models.Model):
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING, db_column="student_id", related_name="+")
    exam = models.ForeignKey(LegacyExam, on_delete=models.DO_NOTHING, db_column="exam_id", related_name="+")
    adjust = models.IntegerField()

    class Meta:
        managed = False
        db_table = "exam2_examadjust"
        app_label = "exam2"


class Command(BaseCommand):
    help = "Export scoring data from legacy DB to exam2/data/export/examTFdata.json (legacy->prod helper)"

    DB_ALIAS = "legacy"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)
        parser.add_argument("--fsyear", type=int, required=True)
        parser.add_argument("--term", type=int, default=getattr(settings, "TERM", None))
        parser.add_argument("--fill-missing", action="store_true")

    def handle(self, *args, **opts):
        subjectNo = opts["subjectNo"]
        fsyear = int(opts["fsyear"])
        term = opts["term"]
        fill_missing = opts["fill_missing"]

        if term is None:
            raise CommandError("term が未指定です。--term を付けるか settings.TERM を設定してください。")
        term = int(term)

        db = self.DB_ALIAS

        # 出力先
        out_dir = Path(settings.BASE_DIR) / "exam2" / "data" / "export"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "examTFdata.json"

        # legacy Subject（fsyear列が無いので subjectNo のみ）
        subject = LegacySubject.objects.using(db).filter(subjectNo=subjectNo).first()
        if not subject:
            raise CommandError(f"Legacy Subject not found: subjectNo={subjectNo}")

        # legacy Exam（fsyear/termで絞る）
        exams = list(
            LegacyExam.objects.using(db)
            .filter(subject=subject, fsyear=fsyear, term=term)
            .order_by("version")
        )
        if not exams:
            raise CommandError(f"Legacy Exam not found: subjectNo={subjectNo} fsyear={fsyear} term={term}")

        exam_by_version = {e.version: e for e in exams}

        # versionごと question_order
        exams_json = {}
        questions_by_version = {}

        for v, e in exam_by_version.items():
            q_list = list(
                LegacyQuestion.objects.using(db)
                .filter(exam=e)
                .order_by("gyo", "retu", "id")
            )
            if not q_list:
                raise CommandError(f"Legacy Question not found: exam_id={e.id} version={v}")

            questions_by_version[v] = q_list

            question_order = [
                {
                    "gyo": int(q.gyo or 0),
                    "retu": int(q.retu or 0),
                    "q_no": (q.q_no or "").strip(),
                }
                for q in q_list
            ]

            exams_json[v] = {
                "title": e.title,
                "problem_hash": "",
                "question_order": question_order,
            }

        # StudentExamVersion（学生→version確定）
        sev_qs = (
            LegacyStudentExamVersion.objects.using(db)
            .filter(exam__in=exams)
            .select_related("student", "exam")
            .order_by("student__stdNo")
        )

        students_json = {}
        total_students = 0
        total_answers = 0
        total_missing = 0

        for sev in sev_qs:
            stu = sev.student
            exam = sev.exam
            version = exam.version

            q_list = questions_by_version.get(version)
            if not q_list:
                raise CommandError(f"Unexpected version: {version} stdNo={stu.stdNo}")

            se_qs = (
                LegacyStudentExam.objects.using(db)
                .filter(student=stu, exam=exam)
            )
            se_by_qid = {se.question_id: se for se in se_qs}

            answers_arr = []
            missing = 0

            for q in q_list:
                se = se_by_qid.get(q.id)
                if se is None:
                    if fill_missing:
                        answers_arr.append({"TF": 0, "hosei": 0})
                        missing += 1
                        continue
                    raise CommandError(
                        f"Legacy StudentExam missing: stdNo={stu.stdNo} exam_id={exam.id} question_id={q.id} "
                        "(use --fill-missing)"
                    )
                answers_arr.append({"TF": int(se.TF), "hosei": int(se.hosei or 0)})

            adj = LegacyExamAdjust.objects.using(db).filter(student=stu, exam=exam).first()
            adjust_val = int(adj.adjust) if adj else 0

            students_json[str(stu.stdNo)] = {
                "nickname": stu.nickname,
                "version": version,
                "answers": answers_arr,
                "adjust": adjust_val,
            }

            total_students += 1
            total_answers += len(answers_arr)
            total_missing += missing

        subject_block = {
            "subjectNo": subjectNo,
            "subject_name": subject.name,
            "fsyear": fsyear,
            "term": term,
            "exams": exams_json,
            "students": students_json,
        }

        # JSON merge（subjects[subjectNo]置換）
        if out_path.exists():
            try:
                root = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                root = {}
        else:
            root = {}

        root.setdefault("meta", {})
        root["meta"]["exported_at"] = timezone.localtime().isoformat()
        root["meta"]["tool_version"] = "examProj2-phase3-score-legacy-fixedschema"
        root["meta"]["source_db"] = db
        root.setdefault("subjects", {})
        root["subjects"][subjectNo] = subject_block

        out_path.write_text(json.dumps(root, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Export completed (legacy schema)"))
        self.stdout.write(f"  db={db}")
        self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term={term}")
        self.stdout.write(f"  students={total_students} answers={total_answers} missing={total_missing}")
        self.stdout.write(f"  output={out_path}")