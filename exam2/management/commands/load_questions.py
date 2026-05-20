# exam2/management/commands/load_questions.py
import json
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from exam2.models import Subject, Exam, Question


class Command(BaseCommand):
    help = "指定 subjectNo の JSON から Question を作成する（Phase3対応、YAML動的参照版）"

    def add_arguments(self, parser):
        parser.add_argument("subjectNo", type=str)

        parser.add_argument(
            "--json",
            type=str,
            default=None,
            help="JSON ファイルパス（省略時は YAML から自動解決）",
        )

        # Phase3: Subject を (subjectNo, fsyear) で特定
        parser.add_argument(
            "--fsyear",
            type=int,
            default=getattr(settings, "FSYEAR", None),
            help="年度（省略時は settings.FSYEAR。未設定なら自動解決を試みる）",
        )

        # 安全系
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="既存の Question を exam 単位で削除してから再作成する（推奨）",
        )

        # 暫定：q_no 置換パッチ（本来はJSON側修正が筋）
        parser.add_argument(
            "--fix-qno",
            action="store_true",
            help="既知の q_no 誤りを補正して登録する（例: 14-1① の重複修正）",
        )

    def handle(self, *args, **options):
        subjectNo = options["subjectNo"]
        fsyear_opt = options["fsyear"]
        clear_existing = options["clear_existing"]
        fix_qno = options["fix_qno"]

        # ------------------------
        # fsyear の特定
        # ------------------------
        fsyear = fsyear_opt if fsyear_opt is not None else getattr(settings, "FSYEAR", None)

        # ------------------------
        # JSON パス決定（utils.py の動的解決を利用）
        # ------------------------
        if options["json"]:
            json_path = Path(options["json"])
        else:
            if fsyear is None:
                raise CommandError(
                    "fsyear が特定できないため、YAML から JSON パスを逆引きできません。--fsyear を指定してください。"
                )

            # 5つ上の階層（/TTC）から utils.py の場所を計算してインポート
            try:
                current_file = Path(__file__).resolve()
                ttc_root = current_file.parents[4]
                ttc_utilpath = ttc_root / "@TTC" / "util"

                if str(ttc_utilpath) not in sys.path:
                    sys.path.insert(0, str(ttc_utilpath))

                import utils

                # 動的キー取得関数を使って "ans_json" を取得
                json_path = utils.get_exam_config_path(subjectNo, str(fsyear), "ans_json")
            except Exception as e:
                raise CommandError(f"utils.py を経由した YAML からのパス取得に失敗しました: {e}")

        if not json_path.exists():
            raise CommandError(f"JSON ファイルが見つかりません: {json_path}")

        self.stdout.write(f"YAML経由の動的JSON読み込み成功: {json_path}")

        # ------------------------
        # JSON 読み込み
        # ------------------------
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        versions = data.get("versions", [])
        if not versions:
            raise CommandError("JSON に versions が存在しません")

        if not versions[0].get("questions"):
            raise CommandError("JSON の versions[0].questions が空です")

        meta = versions[0]["questions"][0]
        json_subject = meta.get("subject")
        if json_subject and json_subject != subjectNo:
            raise CommandError(f"subjectNo 不一致: 引数={subjectNo}, JSON={json_subject}")

        # Subject / Exam 取得用の fsyear 確定
        fsyear = int(fsyear)

        # ------------------------
        # Subject / Exam 取得（Phase3）
        # ------------------------
        try:
            subject = Subject.objects.get(subjectNo=subjectNo, fsyear=fsyear)
        except Subject.DoesNotExist:
            raise CommandError(f"Subject が存在しません: subjectNo={subjectNo} fsyear={fsyear}")

        exams = {e.version: e for e in Exam.objects.filter(subject=subject)}
        if not exams:
            raise CommandError("Exam が存在しません（先に load_subject_base.py を実行してください）")

        def fix_label(version: str, gyo: int, retu: int, label: str) -> str:
            if not fix_qno:
                return label
            if label == "14-1①" and gyo == 6 and retu == 1:
                return "14-1②"
            return label

        total_created = 0
        total_deleted = 0

        # ========================
        # version ループ（A/B）
        # ========================
        for vdata in versions:
            version = vdata.get("version")
            if not version:
                raise CommandError("versions[].version がありません")

            if version not in exams:
                self.stdout.write(self.style.WARNING(f"Exam が見つかりません: version={version}（skip）"))
                continue

            exam = exams[version]
            questions = vdata.get("questions") or []
            if len(questions) < 2:
                raise CommandError(f"questions が不足しています: version={version}")

            if clear_existing:
                deleted, _ = Question.objects.filter(exam=exam).delete()
                total_deleted += deleted

            base_height = questions[0].get("height")
            if not base_height:
                raise CommandError(f"base height が取得できません: version={version}")

            self.stdout.write(f"\n--- Exam {version} (exam_id={exam.id}) ---")

            to_create = []

            for gyo_idx, qblock in enumerate(questions[1:], start=1):
                widths = qblock.get("width") or []
                labels = qblock.get("label") or []
                answers = qblock.get("answer") or []
                heights = qblock.get("height") or []
                points = qblock.get("point") or []
                koumokus = qblock.get("koumoku") or []

                count = len(labels)

                if not all(len(lst) == count for lst in [widths, answers, heights, points, koumokus]):
                    raise CommandError(f"配列長不一致: version={version}, gyo={gyo_idx}")

                for i in range(count):
                    retu = i + 1
                    label = str(labels[i] or "").strip()
                    label = fix_label(version, gyo_idx, retu, label)

                    try:
                        h_ratio = int(int(heights[i]) / int(base_height))
                    except Exception:
                        h_ratio = 1
                    if h_ratio <= 0:
                        h_ratio = 1

                    to_create.append(
                        Question(
                            exam=exam,
                            q_no=label,
                            bunrui=str(koumokus[i] or "").strip(),
                            points=int(points[i] or 0),
                            answer=str(answers[i] or ""),
                            width=int(widths[i] or 1),
                            height=h_ratio,
                            gyo=gyo_idx,
                            retu=retu,
                        )
                    )

            with transaction.atomic():
                Question.objects.bulk_create(to_create, batch_size=2000)
                total_created += len(to_create)

            self.stdout.write(self.style.SUCCESS(f"Exam {version}: Question 作成 {len(to_create)} 件"))

        if clear_existing:
            self.stdout.write(self.style.WARNING(f"削除総数（概算）: {total_deleted}"))

        self.stdout.write(self.style.SUCCESS(f"\n=== Question 作成総数: {total_created} ==="))