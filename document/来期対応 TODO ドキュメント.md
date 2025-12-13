

# 📌 来期対応 TODO ドキュメント

# （Exam / Subject 再設計）



本ドキュメントは、現行システムを今期は維持したまま運用し、**来期（次バージョン）で実施すべき設計変更・対応内容を忘れないための備忘兼作業計画**です。



------

## 0. 背景と現行システムの課題



現行の `Subject` (授業科目) および `Exam` (試験) モデル設計には、実運用上の課題が複数存在します。



### 現行モデルの特徴と課題

- **`Subject` の責務不足:**
  - `Subject` は「授業科目」を表しますが、**年度・学年・期**の変化を十分に吸収できていません。
- **`Exam` の責務過多:**
  - `Exam` モデルが `subject / fsyear / term / version` を持ち、**授業の属性（年度、期）と試験の属性（バージョン）が混在**しており、責務が重くなっています。
  - 

### 実運用で発生する課題

1. 数年に一度、授業科目（`Subject`）の見直しが発生する。
2. 同一の `subjectNo` でも、年度によって実施期（`term`）、受講学年（`nenji`）、科目内容が変わる。
3. 追試、再試など、A/B 以外の多様な試験バージョンが発生する。

> 👉 **【次期方針】** 次期では `Subject` を「**年度付き授業科目**」として再定義し、授業属性と試験属性を分離します。

------

## 1. 次期モデル設計（確定方針）

### 1.1. Subject（年度付き授業科目）

**考え方:**

- `Subject` = 「その年度に実施される授業科目」。
- **年度ごとに別 Subject** として扱うことで、カリキュラム改訂・学年変更・期変更を自然に吸収します。

| **属性** | **役割**                   |
| -------- | -------------------------- |
| `fsyear` | 実施年度（**キー属性**）   |
| `term`   | 実施期（**授業の属性**）   |
| `nenji`  | 受講学年（**授業の属性**） |

**モデル定義:**

Python

```
class Subject(models.Model):
    subject_id = models.AutoField(primary_key=True)
    fsyear = models.IntegerField()              # 実施年度
    subjectNo = models.CharField(max_length=20)    # 科目コード
    subjectName = models.CharField(max_length=100) # 科目名
    term = models.IntegerField()                   # 実施期
    nenji = models.IntegerField()                  # 受講学年

    class Meta:
        unique_together = ("fsyear", "subjectNo")
        ordering = ["fsyear", "subjectNo"]

    def __str__(self):
        return f"{self.fsyear}-{self.subjectNo} {self.subjectName}"
```

### 1.2. Exam（試験バージョン）

**設計方針:**

- `Exam` は **`Subject`（年度付き授業科目）に従属**する。
- 試験の違いは `version` で表現する（例：A / B / 追試 / 再試 / 特別試験）。
- 年度・期・学年といった「授業の属性」は全て `Subject` が持つ。

**モデル定義（完成形）:**

Python

```
class Exam(models.Model):
    exam_id = models.AutoField(primary_key=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    version = models.CharField(max_length=10)  # A / B / R / etc
    adjust_comment = models.TextField(blank=True)

    class Meta:
        unique_together = ("subject", "version")
        ordering = ["subject", "version"]

    def __str__(self):
        return f"{self.subject} - {self.version}"
```

### 1.3. 既存関連モデルの構造（基本維持）

既存の関連モデルは、`Exam` を起点とする外部キーを維持します。これにより、大規模な再設計は不要となり、**外部キーの付け替えが主作業**となります。

**新しいモデル階層:**

```
Subject（年度付き授業科目）
 └── Exam（A / B / 追試）
      ├── Question
      ├── StudentExam
      ├── ExamAdjust
      └── StudentExamVersion
```

- `Question` → `exam` FK
- `StudentExam` → `student` + `exam` + `question`
- `ExamAdjust` → `exam` + `student`
- `StudentExamVersion` → `student` + `exam`

------

## 2. 現行モデル → 新モデル データ移行方針

### 2.1. 移行の基本戦略

- 破壊的変更は行わず、データは「移動」ではなく「再構成」する。
- 既存の `Exam` データを活用し、年度単位で `Subject` を分割して新規作成する。
- 既存の `Exam` は、作成された新しい `Subject` に紐付け替える。

### 2.2. 移行手順（概念）

1. 既存の `Exam` オブジェクトをすべて走査する。
2. 走査した `Exam` の `(fsyear, subjectNo)` をキーに、新しい `Subject` を `get_or_create` で新規作成する。
   - `subjectName / term / nenji` は、既存の `Exam` またはその古い `Subject` から取得する。
3. 既存の `Exam` の `subject` 外部キーを、新規作成された `Subject` に付け替える。
4. `term` と `fsyear` など、`Subject` に移動した属性を `Exam` モデルから削除する。
5. `Question`, `StudentExam` などの関連モデルの外部キーは、`Exam` が変わらないため自動的に追従する。

### 2.3. 移行スクリプト（イメージ）

Python

```
# Django Shell (manage.py shell) で実行を想定

for exam in Exam.objects.all():
    # 年度と科目コードをキーにSubjectを検索・作成
    subject, created = Subject.objects.get_or_create(
        fsyear=exam.fsyear,
        subjectNo=exam.subject.subjectNo, # 古いSubjectからsubjectNoを取得
        defaults={
            "subjectName": exam.subject.name, # 古いSubjectからnameを取得
            "term": exam.term,               # Examからtermを取得
            "nenji": exam.subject.nenji,     # 古いSubjectからnenjiを取得
        }
    )
    # Examの紐付けを変更
    exam.subject = subject
    exam.save()

# ※ 実行前に必ずデータベースのバックアップを取得してください。
```

------

## 3. 備忘：属性の移動に関する決定事項

| **属性**               | **現行モデル**   | **次期モデル**   | **理由**                                                     |
| ---------------------- | ---------------- | ---------------- | ------------------------------------------------------------ |
| **`term` (実施期)**    | `Exam` が保持    | `Subject` に移動 | 実施期は「授業科目」の属性であり、試験バージョン（A/B/追試）とは独立しているため。 |
| **`nenji` (受講学年)** | `Subject` が保持 | `Subject` が保持 | `Subject` が年度付きになることで、年度ごとに異なる `nenji` を持てるようになり、課題が解決する。 |

------

## 4. 次回再開時の TODO 一覧（チェックリスト）


	•	Subject を年度付きモデルに変更
	•	term を Exam → Subject に移動
	•	Exam を Subject 配下に再設計
	•	データ移行スクリプト作成
	•	API（subject / exam 取得）の整理
	•	フロント JS のクエリ条件修正
	•	テストデータで検証
------

## 5. 今期の運用方針（重要）
	•	今期は現行設計のまま運用を継続
	•	構造変更は行わない
	•	本ドキュメントを次期改修の設計書として保存



- 本設計は教育現場の実運用を最優先したものであり、理論より「数年使えるか」を重視している。
- 設計レビューや実装について、引き続きAI（ChatGPTなど）を活用して進めることが可能である。