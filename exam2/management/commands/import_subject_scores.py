import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exam2.models import (
    Subject,
    Exam,
    Question,
    Student,
    StudentExamVersion,
    StudentExam,
    ExamAdjust,
)


class Command(BaseCommand):
    help = (
        "Import subject scoring data from exam2/data/export/examTFdata.json\n"
        "- Strict: abort if Exam.problem_hash mismatch\n"
        "- Strict: abort if question_order mismatch (DB vs JSON)\n"
        "- Apply TF/hosei by array index order (NOT by q_no)\n"
        "- Optional: import only specific students by --stdno"
    )

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str, help="Subject number (e.g. 1010401)")
        parser.add_argument(
            "--stdno",
            action="append",
            default=[],
            help="Import only this student stdNo. Can be repeated. Comma-separated also OK. e.g. --stdno 25367001 --stdno 25367002,25367003",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Do not prompt. Apply changes immediately after validation.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and show what would be updated, but do not write DB.",
        )

    # ----------------------------
    # Helpers
    # ----------------------------
    def _load_json(self, path: Path) -> dict:
        if not path.exists():
            raise CommandError(f"JSON file not found: {path}")
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise CommandError(f"Failed to read JSON: {path} ({e})")

    def _parse_stdnos(self, raw_list):
        stdnos = []
        for x in raw_list or []:
            if not x:
                continue
            parts = [p.strip() for p in str(x).split(",")]
            stdnos.extend([p for p in parts if p])
        # unique preserve order
        seen = set()
        out = []
        for s in stdnos:
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    def _norm_qno(self, qno):
        return (qno or "").strip()

    def _compare_question_order(self, version, json_order, db_questions):
        """
        json_order: list of {gyo, retu, q_no}
        db_questions: list of Question ordered by ("gyo","retu","id")
        """
        if len(json_order) != len(db_questions):
            raise CommandError(
                f"[ABORT] question count mismatch for version={version}: "
                f"JSON={len(json_order)} DB={len(db_questions)}"
            )

        for i, (j, q) in enumerate(zip(json_order, db_questions), start=1):
            j_gyo = int(j.get("gyo") or 0)
            j_retu = int(j.get("retu") or 0)
            j_qno = self._norm_qno(j.get("q_no"))

            d_gyo = int(q.gyo or 0)
            d_retu = int(q.retu or 0)
            d_qno = self._norm_qno(q.q_no)

            if (j_gyo, j_retu, j_qno) != (d_gyo, d_retu, d_qno):
                raise CommandError(
                    "[ABORT] question_order mismatch (index-based mapping would be unsafe)\n"
                    f"  version={version} index={i}\n"
                    f"  JSON: gyo={j_gyo} retu={j_retu} q_no='{j_qno}'\n"
                    f"  DB : gyo={d_gyo} retu={d_retu} q_no='{d_qno}' (question_id={q.id})"
                )

    # ----------------------------
    # Main
    # ----------------------------
    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        only_stdnos = self._parse_stdnos(options["stdno"])
        assume_yes = bool(options["yes"])
        dry_run = bool(options["dry_run"])

        json_path = Path(settings.BASE_DIR) / "exam2" / "data" / "export" / "examTFdata.json"
        root = self._load_json(json_path)

        subjects = (root or {}).get("subjects") or {}
        if subjectNo not in subjects:
            raise CommandError(f"Subject block not found in JSON: subjectNo={subjectNo}")

        block = subjects[subjectNo]

        # Basic block fields
        json_fsyear = block.get("fsyear")
        json_term = block.get("term")
        json_exams = block.get("exams") or {}
        json_students = block.get("students") or {}

        if json_fsyear is None or json_term is None:
            raise CommandError("JSON subject block must include fsyear and term")

        # DB subject
        try:
            subject = Subject.objects.get(subjectNo=subjectNo)
        except Subject.DoesNotExist:
            raise CommandError(f"DB Subject not found: subjectNo={subjectNo}")

        # ----------------------------
        # 1) Validate exams + hash + question_order
        # ----------------------------
        # Build DB exam map for this subject/fsyear/term
        db_exam_map = {}
        for version, exinfo in json_exams.items():
            if not version:
                raise CommandError("JSON exams has empty version key")

            exam = Exam.objects.filter(
                subject=subject,
                fsyear=int(json_fsyear),
                term=int(json_term),
                version=version,
            ).first()

            if not exam:
                raise CommandError(
                    f"[ABORT] DB Exam not found for subjectNo={subjectNo} fsyear={json_fsyear} term={json_term} version={version}"
                )

            # hash check (strict)
            json_hash = exinfo.get("problem_hash")
            db_hash = exam.problem_hash
            if (json_hash or None) != (db_hash or None):
                raise CommandError(
                    "[ABORT] Exam.problem_hash mismatch\n"
                    f"  subjectNo={subjectNo} fsyear={json_fsyear} term={json_term} version={version}\n"
                    f"  JSON: {json_hash}\n"
                    f"  DB : {db_hash}"
                )

            # question_order check (strict)
            json_order = exinfo.get("question_order")
            if not isinstance(json_order, list) or len(json_order) == 0:
                raise CommandError(f"[ABORT] JSON exams[{version}].question_order is missing/empty")

            db_questions = list(
                Question.objects.filter(exam=exam).order_by("gyo", "retu", "id")
            )
            if not db_questions:
                raise CommandError(f"[ABORT] DB Questions not found for exam_id={exam.id} version={version}")

            self._compare_question_order(version, json_order, db_questions)

            db_exam_map[version] = {
                "exam": exam,
                "questions": db_questions,  # ordered
            }

        # ----------------------------
        # 2) Determine target students
        # ----------------------------
        target_items = []
        for stdNo, sinfo in json_students.items():
            if only_stdnos and stdNo not in only_stdnos:
                continue
            target_items.append((stdNo, sinfo))

        if only_stdnos and len(target_items) == 0:
            raise CommandError(f"No matching students in JSON for --stdno={only_stdnos}")

        if len(target_items) == 0:
            raise CommandError("No students found in JSON subject block (or filtered out).")

        # ----------------------------
        # 3) Pre-validate students payload shape
        # ----------------------------
        for stdNo, sinfo in target_items:
            version = (sinfo.get("version") or "").strip()
            if version not in db_exam_map:
                raise CommandError(
                    f"[ABORT] JSON student version not found in exams map: stdNo={stdNo} version={version}"
                )

            answers = sinfo.get("answers")
            if not isinstance(answers, list):
                raise CommandError(f"[ABORT] JSON students[{stdNo}].answers must be an array")

            expected_len = len(db_exam_map[version]["questions"])
            if len(answers) != expected_len:
                raise CommandError(
                    "[ABORT] answers length mismatch\n"
                    f"  stdNo={stdNo} version={version}\n"
                    f"  JSON answers={len(answers)}\n"
                    f"  DB questions={expected_len}"
                )

            # validate elements
            for i, a in enumerate(answers, start=1):
                if not isinstance(a, dict):
                    raise CommandError(f"[ABORT] answers element must be object: stdNo={stdNo} index={i}")
                if "TF" not in a or "hosei" not in a:
                    raise CommandError(f"[ABORT] answers element must have TF/hosei: stdNo={stdNo} index={i}")
                try:
                    int(a.get("TF"))
                    int(a.get("hosei"))
                except Exception:
                    raise CommandError(f"[ABORT] TF/hosei must be int-castable: stdNo={stdNo} index={i}")

        # ----------------------------
        # 4) Show summary + confirm
        # ----------------------------
        self.stdout.write(self.style.WARNING("=== Import plan (validated OK so far) ==="))
        self.stdout.write(f"JSON: {json_path}")
        self.stdout.write(f"Target subjectNo={subjectNo} ({subject.name}) fsyear={json_fsyear} term={json_term}")
        self.stdout.write(f"Target students: {len(target_items)}" + (f" (filtered: {only_stdnos})" if only_stdnos else ""))
        self.stdout.write("Exam versions in JSON:")
        for v, info in json_exams.items():
            h = info.get("problem_hash")
            self.stdout.write(f"  - {v}: problem_hash={(h[:7] + '...') if h else 'None'}")

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] No DB writes will be performed."))

        if not assume_yes and not dry_run:
            ans = input("Proceed to apply changes? (y/yes to continue): ").strip().lower()
            if ans not in ("y", "yes"):
                self.stdout.write(self.style.WARNING("Aborted by user."))
                return

        # ----------------------------
        # 5) Apply
        # ----------------------------
        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run completed (all validations passed)."))
            return

        updated_students = 0
        updated_studentexams = 0
        updated_adjusts = 0
        updated_versions = 0

        with transaction.atomic():
            for stdNo, sinfo in target_items:
                version = (sinfo.get("version") or "").strip()
                exam = db_exam_map[version]["exam"]
                db_questions = db_exam_map[version]["questions"]
                answers = sinfo.get("answers") or []
                adjust_val = int(sinfo.get("adjust") or 0)

                # Student
                student = Student.objects.filter(stdNo=stdNo).first()
                if not student:
                    raise CommandError(f"[ABORT] DB Student not found: stdNo={stdNo}")

                # StudentExamVersion: align (optional but consistent)
                sev = StudentExamVersion.objects.filter(student=student, exam__subject=subject, exam__fsyear=int(json_fsyear), exam__term=int(json_term)).first()
                if sev:
                    if sev.exam_id != exam.id:
                        sev.exam = exam
                        sev.save(update_fields=["exam"])
                        updated_versions += 1
                else:
                    StudentExamVersion.objects.create(student=student, exam=exam)
                    updated_versions += 1

                # StudentExam rows (must exist)
                se_qs = list(
                    StudentExam.objects.filter(student=student, exam=exam)
                    .select_related("question")
                    .order_by("question__gyo", "question__retu", "question__id")
                )

                if len(se_qs) != len(db_questions):
                    raise CommandError(
                        "[ABORT] StudentExam count mismatch (DB incomplete?)\n"
                        f"  stdNo={stdNo} version={version} exam_id={exam.id}\n"
                        f"  DB StudentExam={len(se_qs)} DB Questions={len(db_questions)}"
                    )

                # Apply by index
                for se, a in zip(se_qs, answers):
                    se.TF = int(a["TF"])
                    se.hosei = int(a["hosei"])
                StudentExam.objects.bulk_update(se_qs, ["TF", "hosei"])
                updated_studentexams += len(se_qs)

                # ExamAdjust
                adj_obj, created = ExamAdjust.objects.get_or_create(
                    student=student,
                    exam=exam,
                    defaults={"adjust": adjust_val},
                )
                if not created and int(adj_obj.adjust or 0) != adjust_val:
                    adj_obj.adjust = adjust_val
                    adj_obj.save(update_fields=["adjust"])
                    updated_adjusts += 1
                if created and adjust_val != 0:
                    # created already has adjust set, count as updated for stats
                    updated_adjusts += 1

                updated_students += 1

        self.stdout.write(self.style.SUCCESS("インポートが完了しました"))
        self.stdout.write(f"  対象科目: {subjectNo}  年度: {json_fsyear}  期: {json_term}")
        self.stdout.write(f"  学生数={updated_students}")
        self.stdout.write(f"  採点データ更新件数={updated_studentexams}")
        self.stdout.write(f"  adjust 更新件数={updated_adjusts}")
        self.stdout.write(f"  受験バージョン紐付け変更件数={updated_versions}")