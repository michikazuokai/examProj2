# studentVersion.yaml

## 概要
- 学生の試験バージョン（A/B）割当定義
- exam2 システム専用
- 科目別に割当を管理する（subjectNo 単位）

## 構造（新）
```yaml
fsyear:
  nenji:
    subjectNo:
      A:
        - studentNo
      B:
        - studentNo
```

### 例
```yaml
2025:
  1:
    2022101:
      A:
        - 25367001
        - 25367002
      B:
        - 25367003
  2:
    2023101:
      A:
        - 26367001
      B:
        - 26367002
```

## 注意
- 欠席・退学者は YAML に含めない
- A/B の割当変更を行う場合は、運用手順（データロード運用手順）に従う
- 再ロード時は StudentExamVersion（SEV）が再生成される
- 
