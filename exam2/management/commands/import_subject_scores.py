import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exam2.models import (
    Subject, Exam, Question, Student,
    StudentExamVersion, StudentExam, ExamAdjust
)


class Command(BaseCommand):
    help = "Import subject scoring data (TF/hosei array + adjust) from exam2/data/export/examTFdata.json"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)
        parser.add_argument("--fsyear", type=int, default=getattr(settings, "FSYEAR", None))
        parser.add_argument("--json", type=str, default=None, help="Path to examTFdata.json (default: exam2/data/export/examTFdata.json)")

        # 安全系
        parser.add_argument("--dry-run", action="store_true", help="Validate only (no DB write).")
        parser.add_argument("--force-hash", action="store_true", help="Ignore problem_hash mismatch and continue.")
        parser.add_argument("--force-order", action="store_true", help="Ignore question_order mismatch and continue.")
        parser.add_argument("--fill-missing", action="store_true", help="Create missing StudentExam rows if not exist.")
        parser.add_argument("--skip-adjust", action="store_true", help="Do not import ExamAdjust.adjust.")

        # term は Subject.term を正とし、オプションで不一致検出だけ
        parser.add_argument("--term", type=int, default=None, help="Optional check: if given, must match Subject.term")

    def handle(self, *args, **opts):
        subjectNo = opts["subjectNo"]
        fsyear = opts["fsyear"]
        if fsyear is None:
            raise CommandError("fsyear が未指定です。--fsyear を指定するか settings.FSYEAR を設定してください。")
        fsyear = int(fsyear)

        # ---- JSON 読み込み ----
        if opts["json"]:
            json_path = Path(opts["json"])
        else:
            json_path = Path(settings.BASE_DIR) / "exam2" / "data" / "export" / "examTFdata.json"

        if not json_path.exists():
            raise CommandError(f"JSON not found: {json_path}")

        with json_path.open("r", encoding="utf-8") as f:
            root = json.load(f)

        subjects = root.get("subjects") or {}
        block = subjects.get(subjectNo)
        if not block:
            raise CommandError(f"subjectNo={subjectNo} not found in JSON: {json_path}")

        # ---- Subject を確定（Phase3）----
        try:
            subject = Subject.objects.get(subjectNo=subjectNo, fsyear=fsyear)
        except Subject.DoesNotExist:
            raise CommandError(f"Subject not found in DB: subjectNo={subjectNo} fsyear={fsyear}")

        term_db = int(subject.term or 0)
        term_opt = opts["term"]
        if term_opt is not None and int(term_opt) != term_db:
            raise CommandError(f"term mismatch: option={term_opt} but Subject.term={term_db} (subjectNo={subjectNo} fsyear={fsyear})")

        exams_json = block.get("exams") or {}
        students_json = block.get("students") or {}

        if not exams_json:
            raise CommandError("JSON exams is empty.")
        if not students_json:
            self.stdout.write(self.style.WARNING("JSON students is empty. (no scoring data)"))

        # ---- Exam を version で取得 ----
        exam_by_version = {}
        questions_by_version = {}

        for v, exinfo in exams_json.items():
            try:
                exam = Exam.objects.get(subject=subject, version=v)
            except Exam.DoesNotExist:
                raise CommandError(f"Exam not found in DB: subject={subjectNo}({fsyear}) version={v}")

            # hash チェック
            json_hash = exinfo.get("problem_hash") or ""
            db_hash = exam.problem_hash or ""
            if json_hash and db_hash and (json_hash != db_hash) and (not opts["force_hash"]):
                raise CommandError(
                    f"problem_hash mismatch version={v}: json={json_hash} db={db_hash}. "
                    "止めます（--force-hash で無視可能）"
                )

            exam_by_version[v] = exam

            # Question 並び（export/import共通の定義）
            q_list = list(Question.objects.filter(exam=exam).order_by("gyo", "retu", "id"))
            if not q_list:
                raise CommandError(f"No questions for exam_id={exam.id} version={v}")

            questions_by_version[v] = q_list

            # question_order チェック
            qorder = exinfo.get("question_order") or []
            if len(qorder) != len(q_list) and (not opts["force_order"]):
                raise CommandError(
                    f"question count mismatch version={v}: json={len(qorder)} db={len(q_list)} "
                    "止めます（--force-order で無視可能）"
                )

            # 並びチェック（gyo/retu/q_no）
            if qorder and len(qorder) == len(q_list) and (not opts["force_order"]):
                for i, (qo, q) in enumerate(zip(qorder, q_list)):
                    if int(qo.get("gyo", 0)) != int(q.gyo or 0) or int(qo.get("retu", 0)) != int(q.retu or 0):
                        raise CommandError(
                            f"question_order mismatch version={v} idx={i}: "
                            f"json(gyo,retu)=({qo.get('gyo')},{qo.get('retu')}) "
                            f"db=({q.gyo},{q.retu})"
                        )
                    # q_no は表示用途。違っても運用上許すならここは比較しない手もあります。
                    # 今回は「ズレ検知」のために比較（空は無視）
                    jq = (qo.get("q_no") or "").strip()
                    dq = (q.q_no or "").strip()
                    if jq and dq and jq != dq:
                        raise CommandError(
                            f"q_no mismatch version={v} idx={i}: json='{jq}' db='{dq}' "
                            "（DB側の q_no 修正 or --force-order を検討）"
                        )

        # ---- dry-run ならここで終了 ----
        if opts["dry_run"]:
            self.stdout.write(self.style.SUCCESS("DRY-RUN OK (validated). No DB writes."))
            return

        # ---- 反映（atomic）----
        updated_se = 0
        created_se = 0
        updated_adj = 0
        created_adj = 0
        updated_sev = 0
        created_sev = 0

        with transaction.atomic():
            for stdNo, sinfo in students_json.items():
                try:
                    student = Student.objects.get(stdNo=stdNo)
                except Student.DoesNotExist:
                    raise CommandError(f"Student not found in DB: stdNo={stdNo}")

                version = sinfo.get("version")
                if version not in exam_by_version:
                    raise CommandError(f"Unknown version for student={stdNo}: {version}")

                exam = exam_by_version[version]
                q_list = questions_by_version[version]

                answers = sinfo.get("answers") or []
                if len(answers) != len(q_list):
                    raise CommandError(
                        f"answers length mismatch stdNo={stdNo} version={version}: "
                        f"json={len(answers)} db_questions={len(q_list)}"
                    )

                # StudentExamVersion を (student, subject) 単位で確定させる
                sev_qs = StudentExamVersion.objects.filter(student=student, exam__subject=subject)
                if sev_qs.exists():
                    # 既存が複数でも全部更新（変な状態を一掃）
                    n = sev_qs.update(exam=exam)
                    updated_sev += n
                else:
                    StudentExamVersion.objects.create(student=student, exam=exam)
                    created_sev += 1

                # 既存 StudentExam を辞書化
                se_qs = StudentExam.objects.filter(student=student, exam=exam)
                se_by_qid = {se.question_id: se for se in se_qs}

                to_update = []
                to_create = []

                for q, a in zip(q_list, answers):
                    TF = int(a.get("TF", 0))
                    hosei = int(a.get("hosei", 0) or 0)

                    se = se_by_qid.get(q.id)
                    if se is None:
                        if not opts["fill_missing"]:
                            raise CommandError(
                                f"StudentExam missing stdNo={stdNo} exam_id={exam.id} question_id={q.id} "
                                "（--fill-missing で作成可能）"
                            )
                        to_create.append(StudentExam(student=student, exam=exam, question=q, TF=TF, hosei=hosei))
                    else:
                        if se.TF != TF or int(se.hosei or 0) != hosei:
                            se.TF = TF
                            se.hosei = hosei
                            to_update.append(se)

                if to_create:
                    StudentExam.objects.bulk_create(to_create, ignore_conflicts=False)
                    created_se += len(to_create)

                if to_update:
                    StudentExam.objects.bulk_update(to_update, ["TF", "hosei"])
                    updated_se += len(to_update)

                # ExamAdjust
                if not opts["skip_adjust"]:
                    adjust = int(sinfo.get("adjust", 0) or 0)
                    obj, created = ExamAdjust.objects.get_or_create(
                        student=student, exam=exam, defaults={"adjust": adjust}
                    )
                    if created:
                        created_adj += 1
                    else:
                        if int(obj.adjust or 0) != adjust:
                            obj.adjust = adjust
                            obj.save(update_fields=["adjust"])
                            updated_adj += 1

        self.stdout.write(self.style.SUCCESS("Import completed"))
        self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term(DB)={term_db}")
        self.stdout.write(f"  StudentExam: created={created_se} updated={updated_se}")
        self.stdout.write(f"  ExamAdjust:  created={created_adj} updated={updated_adj}")
        self.stdout.write(f"  StudentExamVersion: created={created_sev} updated={updated_sev}")
        self.stdout.write(f"  json={json_path}")