# 管理画面（admin）から実行できる機能と運用手順（暫定版）

このドキュメントは、今回追加・整備した **admin からの運用メニュー**と、  
**manage_stdversion（学生A/B切替）** の操作手順をまとめたものです。

---

## 1. admin トップ（運用メニュー）

admin のトップ画面に、運用メニューが表示されます（Subject/Exam/Student/manage_stdversion）。

### 1.1 Subject（科目）
- 目的：科目（subjectNo / fsyear / term / nenji / name）の一覧確認・編集
- よく使う機能
  - **検索**：subjectNo / name
  - **フィルタ**：fsyear / term / nenji
  - **編集**：科目名（name）など

### 1.2 Exam（試験）
- 目的：Subject に紐づく Exam（version=A/B）の一覧確認・編集
- よく使う機能
  - **フィルタ**：version(A/B) / Subject年度（fsyear）など
  - **検索**：subjectNo / subject名

### 1.3 Student（学生）
- 目的：学生情報の一覧確認・編集
- よく使う機能
  - **検索**：stdNo / nickname / name1 / name2 / email
  - **フィルタ**：entyear（入学年度）/ enrolled（在籍）
  - **一覧編集**：nickname / enrolled（list_editable を設定している場合）

### 1.4 manage_stdversion（学生A/B切替）
- 目的：特定の科目（Subject）に対して、学生の割当 Exam version（A/B）を **一覧で確認し、1名ずつ切り替える**
- 切替に伴い、関連データ（SEV/StudentExam/ExamAdjust）も整合するように更新します（下記参照）。

---

## 2. manage_stdversion（学生A/B切替）操作手順

### 2.1 画面を開く
- admin トップの「manage_stdversion（A/B変更）」をクリック
- 必要に応じて「← 管理画面トップへ戻る」で admin に戻れます

### 2.2 科目（Subject）を選択
- ドロップダウンから **対象科目**（subjectNo / fsyear / name）を選択
- 選択すると自動で一覧が更新されます  
  ※更新中は「読み込み中…」表示になる場合があります

### 2.3 学生一覧を確認
一覧には以下が表示されます：

- **学生**：`stdNo nickname`（1行）
- **A/B**：現在の割当（SEVから）
- **点数**：合計点（定義は 2.5 参照）
- **操作**：現在Aなら「Bに変更」、現在Bなら「Aに変更」（未割当なら「Aに設定」）

### 2.4 A/Bを切り替える（通常）
1. 対象学生の「Aに変更 / Bに変更」ボタンを押す
2. 確認ダイアログが表示されるので **OK** を押す
3. 処理後、自動的に一覧に戻ります（POST→Redirect→GET）
4. 変更した行は **色付き** になります（今回の作業で変更した学生の可視化）

### 2.5 強制変更（点数が入っている場合でも切替）
- 確認ダイアログには「強制変更（0クリア）」の説明が含まれます
- **OK を押すと force=1 として送信され、次が実行されます：**
  - StudentExam：`TF=0, hosei=0` にクリアしつつ、exam を新バージョン側へ揃える
  - ExamAdjust：`adjust=0` にクリアしつつ、exam を新バージョン側へ揃える
  - StudentExamVersion（SEV）：exam を新バージョン側へ変更（または作成）

> 注意：強制変更は「採点・補正を破棄する」操作です。実行前に確認してください。

### 2.6 変更した行の色（修正漏れ防止）
- 今回の作業でA/Bを切り替えた学生の行は、一覧で **色付き** になります
- **科目を切り替えると、前科目の色は自動的にクリア**されます（科目別に管理）
- 手動で消す場合は「今回の色をクリア（clear=1）」のリンクを利用（実装している場合）

---

## 2.7 点数の定義（合計点）
manage_stdversion の点数は次の式で計算します：

- **合計点 = Σ(TF × points) + Σ(hosei) + adjust**

使用フィールド：
- StudentExam.TF（大文字）
- Question.points
- StudentExam.hosei
- ExamAdjust.adjust（1件のみ想定）

> 重要：点数は「学生の現在割当（SEV）の exam」に紐づく StudentExam / ExamAdjust を対象に計算します。

---

## 3. 期待されるDB更新（参考）

学生1名のA/B切替で、対象科目（Subject）に関して次が整合するよう更新されます：

- StudentExamVersion（SEV）：その学生の割当 exam を A/B に変更
- StudentExam：その学生の exam を A/B 側へ揃える（force時は TF/hosei を0クリア）
- ExamAdjust：その学生の exam を A/B 側へ揃える（force時は adjust を0クリア）

---

## 4. よくある注意点
- manage_stdversion は **staff ログイン必須**です
- 強制変更は **点数・補正の破棄**なので、運用ルールを決めてから使用してください
- ボタンを押しても何も起きない場合：
  - messages 表示がテンプレにあるか
  - POSTフォームに action が付いているか（`{% url 'manage_stdversion' %}`）
  - Network で POST が飛んでいるか（F12→Network）

---

（暫定版：必要に応じて運用ルールやスクリーンショットを追記してください）
