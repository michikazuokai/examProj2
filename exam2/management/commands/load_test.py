import sys
from pathlib import Path

# py1.py の場所を起点にする
current_file = Path(__file__).resolve()

# 5つ上の階層（/TTC）を一発で取得
ttc_root = current_file.parents[4]
ttc_utilpath = ttc_root / "@TTC" / "util"  # フォルダ名に@がある場合は含めます

# 3. sys.path は「文字列のリスト」を期待するため、str() で変換して検索パスの先頭に追加する
if str(ttc_utilpath) not in sys.path:
    sys.path.insert(0, str(ttc_utilpath))

# 4. インポートを実行する（ファイル名が utils.py の場合）
import utils

# ─── これで準備完了です ───
# 先ほど作った共通関数を呼び出す例：
try:
    ans_json_path = utils.get_exam_config_path("1020701", "2026", "ans_json")
    print(f"成功しました！ パス: {ans_json_path}")
except AttributeError:
    print("utils.py は読み込めましたが、関数名が未定義か間違っています。")