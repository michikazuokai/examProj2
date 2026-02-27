# exam2/management/commands/clear_subject_runtime_data.py
# -------------------------------------------------------
# 目的：
#   ルールB（解答入力前のA/B入れ替え）向けに、
#   「実行時データ（StudentExam / ExamAdjust）」だけを対象科目・年度の範囲でクリアする。
#
# 仕様：
#   - デフォルトは dry-run（削除しない）
#   - --execute を付けたときだけ削除
#   - 安全ガード：
#       StudentExam の tf!=0 または hosei!=0 が1件でもあれば拒否（--force で上書き可能）
#       ExamAdjust が存在し、（補正値フィールドがあれば）合計が0でない場合も拒否（--force で上書き可能）
#
# 使い方：
#   python manage.py clear_subject_runtime_data 2022101 --fsyear 2025
#   python manage.py clear_subject_runtime_data 2022101 --fsyear 2025 --execute
#   python manage.py clear_subject_runtime_data 2022101 --fsyear 2025 --execute --force
#
# 注意：
#   - StudentExamVersion（SEV）は消しません（入れ替えは load_student_exam_version --clear-existing で）
#   - Questionは消しません（問題が変わる場合は clear_subject_data を使う想定）
#
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from exam2.models import Subject, Exam, StudentExam, ExamAdjust


class Command(BaseCommand):
    help = "Clear runtime data (StudentExam, ExamAdjust) for a subject/year (safe for swap before answering)."

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str, help="科目コード（subjectNo）")
        parser.add_argument("--fsyear", type=int, required=True, help="対象年度（例: 2025）")
        parser.add_argument("--dry-run", action="store_true", help="見積のみ（削除しない）")
        parser.add_argument("--execute", action="store_true", help="実際に削除します")
        parser.add_argument("--force", action="store_true", help="安全ガードを無視して削除します（非推奨）")

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        execute: bool = options["execute"]

        if dry_run and execute:
            raise CommandError("--dry-run と --execute は同時に指定できません。")
        if (not dry_run) and (not execute):
            raise CommandError("どちらかを指定してください: --dry-run または --execute")

        # …（ここで件数表示やガード判定）…

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: no deletion performed."))
            return

        # execute の場合はここに来る
        # …transaction.atomic() で delete …

# execute のときだけ transaction.atomic() で delete

    def _pick_adjust_value_field(self) -> str | None:
        """
        ExamAdjust が「補正値」を持っている場合、そのフィールド名を推定する。
        プロジェクトによって名称が違うので、よくある候補を順に探す。
        """
        candidates = ["hosei", "adjust", "delta", "point", "score", "value"]
        for name in candidates:
            try:
                ExamAdjust._meta.get_field(name)
                return name
            except Exception:
                pass
        return None

    def handle(self, *args, **options):
        subject_no: str = options["subjectNo"]
        fsyear: int = options["fsyear"]
        execute: bool = options["execute"]
        force: bool = options["force"]

        # Subject を特定
        try:
            subject = Subject.objects.get(subjectNo=subject_no, fsyear=fsyear)
        except Subject.DoesNotExist:
            raise CommandError(f"Subject not found: subjectNo={subject_no}, fsyear={fsyear}")

        exams_qs = Exam.objects.filter(subject=subject)
        exam_ids = list(exams_qs.values_list("id", flat=True))

        if not exam_ids:
            self.stdout.write(self.style.WARNING("No Exam found under this subject. Nothing to clear."))
            return

        se_qs = StudentExam.objects.filter(exam_id__in=exam_ids)
        adj_qs = ExamAdjust.objects.filter(exam_id__in=exam_ids)

        se_count = se_qs.count()
        adj_count = adj_qs.count()

        # --- 安全ガード判定（解答/採点が始まっていないか）---
        # StudentExam に tf/hosei がある前提だが、存在しない場合はスキップ
        se_tf_nonzero = None
        se_hosei_nonzero = None

        try:
            StudentExam._meta.get_field("tf")
            se_tf_nonzero = se_qs.exclude(tf=0).count()
        except Exception:
            pass

        try:
            StudentExam._meta.get_field("hosei")
            se_hosei_nonzero = se_qs.exclude(hosei=0).count()
        except Exception:
            pass

        # ExamAdjust の「合計0」判定：補正値っぽいフィールドがあれば Sum、無ければ件数で判断
        adj_value_field = self._pick_adjust_value_field()
        adj_sum = None
        if adj_value_field is not None:
            agg = adj_qs.aggregate(total=Sum(adj_value_field))
            adj_sum = agg.get("total") or 0

        # 事前表示
        self.stdout.write("=== clear_subject_runtime_data (dry-run by default) ===")
        self.stdout.write(f"subjectNo={subject_no}, fsyear={fsyear}")
        self.stdout.write(f"Exam count: {len(exam_ids)}")
        self.stdout.write(f"StudentExam rows: {se_count}")
        self.stdout.write(f"ExamAdjust rows: {adj_count}")

        if se_tf_nonzero is not None:
            self.stdout.write(f"StudentExam tf!=0 rows: {se_tf_nonzero}")
        else:
            self.stdout.write("StudentExam tf field: (not found)")

        if se_hosei_nonzero is not None:
            self.stdout.write(f"StudentExam hosei!=0 rows: {se_hosei_nonzero}")
        else:
            self.stdout.write("StudentExam hosei field: (not found)")

        if adj_value_field is not None:
            self.stdout.write(f"ExamAdjust value field: {adj_value_field}, SUM={adj_sum}")
        else:
            self.stdout.write("ExamAdjust value field: (not detected) -> using count only")

        # ガード条件
        guard_violations = []

        if se_tf_nonzero is not None and se_tf_nonzero > 0:
            guard_violations.append("StudentExam.tf has non-zero rows")
        if se_hosei_nonzero is not None and se_hosei_nonzero > 0:
            guard_violations.append("StudentExam.hosei has non-zero rows")

        # Adjust は「合計0」方針が使えるならそれで判定、無理なら存在自体で警告
        if adj_value_field is not None:
            if (adj_sum or 0) != 0:
                guard_violations.append(f"ExamAdjust.{adj_value_field} SUM is not zero")
        else:
            # “合計0” を計れないので、存在するなら一旦ガード扱い（運用上、0件が理想）
            if adj_count > 0:
                guard_violations.append("ExamAdjust rows exist (cannot sum value field)")

        if guard_violations and not force:
            msg = "Guard check failed (answering/scoring might have started):\n- " + "\n- ".join(guard_violations)
            msg += "\nUse --force to override (NOT recommended)."
            raise CommandError(msg)

        if not execute:
            self.stdout.write(self.style.WARNING("DRY-RUN: no deletion performed. Use --execute to delete."))
            return

        # --- 実削除 ---
        with transaction.atomic():
            # 依存関係により順序を付ける（一般に StudentExam / ExamAdjust はどちらでもOKだが安全に両方削除）
            deleted_adj = adj_qs.delete()
            deleted_se = se_qs.delete()

        self.stdout.write(self.style.SUCCESS("Deleted runtime data successfully."))
        self.stdout.write(f"ExamAdjust delete() result: {deleted_adj}")
        self.stdout.write(f"StudentExam delete() result: {deleted_se}")
        self.stdout.write("Next steps (typical):")
        self.stdout.write(f"  1) load_student_exam_version {subject_no} --fsyear {fsyear} --clear-existing")
        self.stdout.write(f"  2) load_student_exam {subject_no} --fsyear {fsyear}")
        self.stdout.write(f"  3) load_exam_adjust {subject_no} --fsyear {fsyear}")