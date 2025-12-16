import json
from pathlib import Path
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from exam2.models import (
    Subject,
    Exam,
    Question,
    StudentExamVersion,
    StudentExam,
    ExamAdjust,
)


class Command(BaseCommand):
    help = "Export subject scoring data (StudentExam TF/hosei as array + ExamAdjust.adjust) to exam2/data/export/examTFdata.json"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str, help="Subject number (e.g. 1010401)")
        parser.add_argument(
            "--fsyear",
            type=int,
            default=getattr(settings, "FSYEAR", None),
            help="Fiscal year (default: settings.FSYEAR)",
        )
        parser.add_argument(
            "--term",
            type=int,
            default=getattr(settings, "TERM", None),
            help="Term (default: settings.TERM)",
        )
        parser.add_argument(
            "--fill-missing",
            action="store_true",
            help="If StudentExam for some questions is missing, fill TF=0,hosei=0 instead of raising error.",
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        fsyear = options["fsyear"]
        term = options["term"]
        fill_missing = options["fill_missing"]

        if fsyear is None or term is None:
            raise CommandError(
                "fsyear/term が未指定です。--fsyear/--term を指定するか settings.FSYEAR/settings.TERM を設定してください。"
            )

        # -------------------------
        # 出力先ファイル
        # -------------------------
        out_dir = Path(settings.BASE_DIR) / "exam2" / "data" / "export"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "examTFdata.json"

        # -------------------------
        # Subject / Exams 取得
        # -------------------------
        try:
            subject = Subject.objects.get(subjectNo=subjectNo)
        except Subject.DoesNotExist:
            raise CommandError(f"Subject not found: subjectNo={subjectNo}")

        exams = list(
            Exam.objects.filter(subject=subject, fsyear=fsyear, term=term).order_by("version")
        )
        if not exams:
            raise CommandError(
                f"Exam not found for subjectNo={subjectNo}, fsyear={fsyear}, term={term}"
            )

        exam_by_version = {e.version: e for e in exams}

        # -------------------------
        # version ごとの question_order を作る（＝配列の並び定義）
        # 並びは export/import の両方で必ず同じ order_by を使うこと！
        # -------------------------
        exams_json = {}
        questions_by_version = {}

        for v, e in exam_by_version.items():
            # ★ 並びの定義（重要）
            q_list = list(
                Question.objects.filter(exam=e).order_by("gyo", "retu", "id")
            )
            if not q_list:
                raise CommandError(f"Question not found for exam_id={e.id} version={v}")

            questions_by_version[v] = q_list

            question_order = []
            for q in q_list:
                question_order.append(
                    {
                        "gyo": int(q.gyo or 0),
                        "retu": int(q.retu or 0),
                        "q_no": (q.q_no or "").strip(),  # ★ 文字列のまま（重複してもOK）
                    }
                )

            exams_json[v] = {
                "title": e.title,
                "problem_hash": e.problem_hash,      # ★ hash 不一致なら import 中止の判定に使う
                "question_order": question_order,    # ★ 配列の並び定義
            }

        # -------------------------
        # StudentExamVersion から「学生→その学生のexam(version)」を確定
        # -------------------------
        sev_qs = (
            StudentExamVersion.objects.filter(
                exam__subject=subject,
                exam__fsyear=fsyear,
                exam__term=term,
            )
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

            if version not in questions_by_version:
                raise CommandError(
                    f"Unexpected version={version} for student={stu.stdNo} (exam_id={exam.id})"
                )

            q_list = questions_by_version[version]

            # StudentExam を辞書化（question_id -> record）
            se_qs = (
                StudentExam.objects.filter(student=stu, exam=exam)
                .select_related("question")
            )
            se_by_qid = {se.question_id: se for se in se_qs}

            answers_arr = []
            missing = 0

            # ★ question_order の順で answers 配列を構築（q_no に依存しない）
            for q in q_list:
                se = se_by_qid.get(q.id)
                if se is None:
                    if fill_missing:
                        answers_arr.append({"TF": 0, "hosei": 0})
                        missing += 1
                        continue
                    raise CommandError(
                        "StudentExam が不足しています。"
                        f" student={stu.stdNo} exam_id={exam.id} version={version} question_id={q.id}"
                        "（--fill-missing を付けると 0 埋めで継続します）"
                    )

                answers_arr.append(
                    {
                        "TF": int(se.TF),
                        "hosei": int(se.hosei or 0),
                    }
                )

            # ExamAdjust（無ければ0）
            adj = ExamAdjust.objects.filter(student=stu, exam=exam).first()
            adjust_val = int(adj.adjust) if adj else 0

            students_json[stu.stdNo] = {
                "nickname": stu.nickname,
                "version": version,      # A / B
                "answers": answers_arr,  # ★ 配列
                "adjust": adjust_val,
            }

            total_students += 1
            total_answers += len(answers_arr)
            total_missing += missing

        # -------------------------
        # subject ブロック（置き換え対象）
        # -------------------------
        subject_block = {
            "subjectNo": subject.subjectNo,
            "subject_name": subject.name,
            "fsyear": int(fsyear),
            "term": int(term),
            "exams": exams_json,          # version -> {hash, question_order, ...}
            "students": students_json,    # stdNo -> {version, answers[], adjust}
        }

        # -------------------------
        # 既存JSONを読み込み → subjects[subjectNo] を置換 → 保存
        # -------------------------
        if out_path.exists():
            try:
                with out_path.open("r", encoding="utf-8") as f:
                    root = json.load(f)
            except Exception:
                root = {}
        else:
            root = {}

        root.setdefault("meta", {})
        root["meta"]["exported_at"] = datetime.now(timezone.utc).isoformat()
        root["meta"]["tool_version"] = "examProj2-phase2-array"
        root.setdefault("subjects", {})

        # ★ 仕様：同一subjectNoは置き換え
        root["subjects"][subjectNo] = subject_block

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(root, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS("Export completed"))
        self.stdout.write(f"  subjectNo={subjectNo} fsyear={fsyear} term={term}")
        self.stdout.write(f"  students={total_students} answers={total_answers} missing={total_missing}")
        self.stdout.write(f"  output={out_path}")