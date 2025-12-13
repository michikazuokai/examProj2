# studentVesion.yaml

## 概要
- 学生の試験バージョン（A/B）割当定義
- exam2 システム専用

## 構造
fsyear:
  nenji:
    version:
      - studentNo

## 注意
- 欠席・退学者は YAML に含めない
- 再ロード時は StudentExamVersion が再生成される