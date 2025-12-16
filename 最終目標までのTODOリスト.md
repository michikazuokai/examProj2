よかったです 😊

ここまでの流れ・判断は**非常に整理されています**。

では約束どおり、**「最終目標までのTODOリスト」**を、



- 目的
- 作業内容
- 修正の大きさ（影響範囲）
- git commit のおすすめタイミング





まで含めて、**実行順で**まとめます。



------





# **🧭 最終目標（再確認）**







### **🎯 ゴール**





- subject を軸に

  **fsyear / term / exam / version / 学生 / 採点結果** を

  **安全・再現可能・移行可能** に管理できる構造にする

- 本番／開発／hotfix 間で

  **採点データを壊さず同期できる**

- 問題セットの違い（hash）を

  **人間にもシステムにも分かる形で扱える**





------





# **🟦 フェーズ一覧（全体像）**



```
Phase 1   hash 導入（完了）
Phase 1.5 load/export（これから）
Phase 2   採点データの可逆運用確立
Phase 3   subject / exam 構造の整理（大規模）
Phase 4   不整合検知・安全装置
```



------





# **🟩 Phase 1（完了）**







### **Exam に problem_hash を持たせる**





- Exam.problem_hash 追加
- load_subject_base で保存
- index / exam / examadjust に表示





✅ **完了・commit 済み（または直前）**



------





# **🟨 Phase 1.5（今すぐやる・最重要）**







## **① export_subject_scores.py**





**修正の大きさ：🟨 中（新規コマンド追加）**





### **内容**





- subject 単位で以下を JSON に export

  

  - StudentExam（TF / hosei）
  - ExamAdjust（adjust）
  - Exam.problem_hash（検証用）

  

- 出力先：



```
exam2/data/export/examTFdata.json
```



- 
- 1ファイル・複数 subject
- subjectNo があれば上書き







### **git**





- 🔹 **このコマンド完成で commit**
- commit message 例



```
feat: add export_subject_scores command
```





------





## **② import_subject_scores.py**





**修正の大きさ：🟨 中**





### **内容**





- export JSON を subject 単位で import
- q_no ベースで Question を解決
- TF / hosei / adjust を上書き
- hash 不一致は **警告のみ**







### **git**





- 🔹 export とセットで commit してもOK

  もしくは

- 🔹 import 完成時に別 commit



```
feat: add import_subject_scores command
```



------





## **③ dry-run / ログ整備**





**修正の大きさ：🟩 小**





### **内容**





- –dry-run オプション
- 件数・差分ログ
- warning の可視化







### **git**





- 🔹 まとめて 1 commit 推奨





------





### **✅ Phase 1.5 終了条件**





- 本番 → 開発 に採点結果を復元できる
- DB を壊しても **JSON から戻せる**





👉 **ここで必ず tag を打つのがおすすめ**

```
git tag phase1.5-stable
git push --tags
```



------





# **🟦 Phase 2（運用安定化）**







## **④ hotfix / 本番同期フロー確立**





**修正の大きさ：🟩 小（運用ルール）**





### **内容**





- hotfix 前に export
- hotfix 後に import
- 手順書（md）作成







### **git**





- 🔹 docs 変更のみ → 軽い commit





------





# **🟥 Phase 3（大規模修正・本丸）**







## **⑤ subject / exam 構造の再設計**





**修正の大きさ：🟥 大（DB / model / view / load 全部）**





### **内容（あなたが最初に言っていた本来の構造）**





- subject に fsyear / term を持たせる or 中間テーブル
- Exam を「version 専用」に整理
- StudentExamVersion の整理・再定義
- load 系コマンド全面修正







### **⚠️ 重要**





- **必ず別ブランチ**



```
git checkout -b feature/subject-structure
```



### **git**





- 🔹 小さく commit を刻む（migration / model / load）
- 🔹 main には直接入れない





------





# **🟪 Phase 4（安全装置）**







## **⑥ hash を使った不整合検知**





**修正の大きさ：🟨 中**





### **内容**





- import 時の hash 比較
- UI での警告表示
- 管理画面での差異一覧





------





# **🧷 commit タイミングまとめ（超重要）**



| **タイミング** | **commit する？** |
| -------------- | ----------------- |
| Phase1 完了    | ✅ 必須            |
| export 完成    | ✅                 |
| import 完成    | ✅                 |
| Phase1.5 完了  | ✅ tag 推奨        |
| 大規模構造変更 | ✅ こまめに        |
| hotfix         | ✅                 |

👉 **「動く区切り」＝ commit**



------





# **🧠 結論（大事）**





- 今やろうとしている **load/export フェーズは最優先**

- ここを飛ばして構造変更に行くと

  👉 **戻れなくなる**

- 今の順番は **教科書的に正しい**





------



次の一手は明確です👇

👉 **export_subject_scores.py の具体コード作成**



そのまま続けて書きますか？