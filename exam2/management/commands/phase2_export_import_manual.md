# **Phase2: 採点データ export/import 運用手順書（hash不一致は中止）**





## **目的**



本番PC・開発PCの間で、**subject単位**に以下の採点データを安全に同期する。



- StudentExam: TF, hosei
- ExamAdjust: adjust





さらに、**Exam.problem_hash（A/B別）** を使って「問題セットが一致しているか」を判定し、**hashが違う場合は import を中止**する。



------





## **対象コマンド**





- export_subject_scores

  subject の採点データを JSON に書き出す（既存 subject ブロックは置換）

- import_subject_scores

  JSON を読み込み、subject の採点データを DB に反映する（hash不一致は中止）





------





## **入出力ファイル**







### **出力先（固定）**





- exam2/data/export/examTFdata.json







### **JSONの特徴**





- 1ファイルに複数 subject を格納
- subjects[subjectNo] が既にあれば **置換（上書き）**
- exams[version].problem_hash と question_order を含む（配列形式で安全に復元するため）





------





## **実行前の確認**







### **✅ 1) settings の年度・期**





--fsyear / --term を省略すると settings.FSYEAR / settings.TERM が使われます。

環境が違うPCで事故が起きやすいので、最初は明示指定推奨です。





### **✅ 2) hash が DB に入っていること**





Phase1 の結果として、Exam に problem_hash が保存されている前提です。

（画面に [80acce5] が出ているならOK）



------





## **手順A：本番PC → 開発PCに採点結果を持ってくる（基本）**







### **① 本番PCで export（subject単位）**



```
python manage.py export_subject_scores 1010401 --fsyear 2025 --term 4
```

（必要なら欠損StudentExamを0埋め）

```
python manage.py export_subject_scores 1010401 --fsyear 2025 --term 4 --fill-missing
```



### **②** 

### **exam2/data/export/examTFdata.json**

###  **を開発PCへ移動**





- USB / 共有フォルダ / scp など
- **注意：このJSONは運用データなので、原則 Git 管理しない**（後述）







### **③ 開発PCで import（subject単位）**



```
python manage.py import_subject_scores 1010401 --fsyear 2025 --term 4
```



- **hash が一致しない場合：この時点で中止（DB更新なし）**
- 成功すれば StudentExam/ExamAdjust が更新される





------





## **手順B：本番PCに「特定の学生だけ」反映したい（部分import）**





例：学生 25367001 だけ import

```
python manage.py import_subject_scores 1010401 --fsyear 2025 --term 4 --stdno 25367001
```

用途：



- 本番で個別に採点した分だけ戻したい
- 誤採点の修正だけ同期したい





注意：



- subject 全体 import と違い、更新対象が限定されます
- hash不一致チェックは **同様に実施**（不一致なら中止）





------





## **よくあるエラーと対応**







### **❌ hash不一致で中止**





原因：



- DB側の Exam.problem_hash と、JSON側の exams[version].problem_hash が一致しない
- つまり「問題セットが違う」





対応：



- **import はしない（安全側）**
- まず問題データを揃える（load系の順序を見直す／本番と同じ answers_xxxx.json を適用する 等）





------





### **❌ export/import の結果が想定より少ない**





よくある原因：



- --fsyear / --term が違う
- StudentExamVersion が揃っていない（学生とA/Bの紐付けが欠けている）
- --stdno 指定している





------





## **推奨運用（事故を減らす）**





✅ 1) 「本番に触る前」に必ずバックアップ



- db.sqlite3 のコピー、またはディレクトリ丸ごとバックアップ





✅ 2) export/import は “subject単位” で小さく



- いきなり全科目ではなく、1科目ずつ確認





✅ 3) 反映後に画面で hash を目視確認



- index / examadjust / exam の [xxxxxxx] が一致しているか





------





## **コマンド出力（表示例）**





（最終行は日本語でこういう意味）



- 対象科目・年度・期
- 更新された学生数
- 更新された StudentExam 件数
- 更新された ExamAdjust 件数
- StudentExamVersion の再整列件数（実装がある場合）





------





## **Git運用（このフェーズ完了時の commit は？）**







### **✅ 結論：**

### **commit した方がいいです**





理由：



- Phase2 の export/import は運用に直結し、後から追跡できる状態にしておくべき
- hash不一致中止など「安全仕様」は特に履歴として残す価値が高い







### **✅ commit に含めるもの**





- exam2/management/commands/export_subject_scores.py
- exam2/management/commands/import_subject_scores.py
- （必要なら）関連する README / 手順書（この md）







### **❌ commit に含めないもの（推奨）**





- exam2/data/export/examTFdata.json（運用データ）
- db.sqlite3（原則）





.gitignore 推奨例：

```
exam2/data/export/*.json
db.sqlite3
```



------



必要なら、この手順書をあなたのディレクトリ構造に合わせて「どこに置くか（document/ か exam2/data/README.md に統合か）」も含めて、**リポジトリ内の最終配置案**に整えて書き直します。