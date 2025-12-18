# **1) 移行の全体フロー（安全順）**



## **✅ A. 事前スナップショット（必須）**

### **LegacyDBからjsonをエキスポートする**

```
python manage.py export_subject_scores_legacy 1010401  --fsyear 2025
```



### **本番DB（新）側：移行前の件数**


```
python manage.py shell -c "
from exam2.models import Subject,Exam,Question,StudentExam,StudentExamVersion,ExamAdjust
s=Subject.objects.get(subjectNo='1010401',fsyear=2025)
ex=Exam.objects.filter(subject=s)
print('NEW Exam=',ex.count())
print('NEW Q=',Question.objects.filter(exam__in=ex).count())
print('NEW SEV=',StudentExamVersion.objects.filter(exam__in=ex).count())
print('NEW SE=',StudentExam.objects.filter(exam__in=ex).count())
print('NEW Adjust=',ExamAdjust.objects.filter(exam__in=ex).count())
"
```

### **JSON 側：何人分あるか（超簡易チェック）**

```
python manage.py shell -c "
import json
p='exam2/data/export/examTFdata.json'
d=json.load(open(p,'r',encoding='utf-8'))
b=d['subjects']['1010401']
print('JSON students=',len(b.get('students',{})))
print('JSON versions=',list((b.get('exams') or {}).keys()))
"
```

------





## **✅ B. 本番DBの “器” を整える（問題・受験割当・採点行）**





> ここが揃っていないと import が失敗します（足りないものがある状態）。



破壊ありで作り直すなら（推奨：検証済みの完全再ロード）：

```
python manage.py clear_subject_data 1010401 --fsyear 2025
python manage.py load_subject_base 1010401
python manage.py load_questions 1010401 --fsyear 2025 --clear-existing --fix-qno
python manage.py load_student_exam_version 1010401 --fsyear 2025 --clear-existing
python manage.py load_student_exam 1010401 --fsyear 2025
python manage.py load_exam_adjust 1010401 --fsyear 2025
```

※ 「採点だけを移行する」なら、器が既にある前提でOKです（ただし StudentExam / ExamAdjust が無いと import で詰みます）。



------





## **✅ C. JSON → 本番DBへ採点移行（dry-run → 本実行）**







### **まず dry-run（絶対）**



```
python manage.py import_subject_scores 1010401 --fsyear 2025 --dry-run
```



### **OKなら本実行**



```
python manage.py import_subject_scores 1010401 --fsyear 2025 --fill-missing
```



- --fill-missing は、もし採点行が欠けていても作って埋めるための保険です
- hash/order mismatch が出たら、**止めるのが正解**（force は最後の手段）





------





# **2) 移行後チェック（差分が無いことを確認）**







## **✅ A. 本番DB件数チェック（移行後）**



```
python manage.py shell -c "
from exam2.models import Subject,Exam,Question,StudentExam,StudentExamVersion,ExamAdjust
s=Subject.objects.get(subjectNo='1010401',fsyear=2025)
ex=Exam.objects.filter(subject=s)
print('NEW Exam=',ex.count())
print('NEW Q=',Question.objects.filter(exam__in=ex).count())
print('NEW SEV=',StudentExamVersion.objects.filter(exam__in=ex).count())
print('NEW SE=',StudentExam.objects.filter(exam__in=ex).count())
print('NEW Adjust=',ExamAdjust.objects.filter(exam__in=ex).count())
"
```



## **✅ B. “合計点” が一致するか（超重要）**





（本番DBで、学生ごとの TF合計 + adjust 合計をざっくり確認）

```
python manage.py shell -c "
from exam2.models import Subject,Exam,StudentExam,ExamAdjust
from django.db.models import Sum
s=Subject.objects.get(subjectNo='1010401',fsyear=2025)
ex=Exam.objects.filter(subject=s)
tf=StudentExam.objects.filter(exam__in=ex).aggregate(Sum('TF'))['TF__sum'] or 0
hs=StudentExam.objects.filter(exam__in=ex).aggregate(Sum('hosei'))['hosei__sum'] or 0
ad=ExamAdjust.objects.filter(exam__in=ex).aggregate(Sum('adjust'))['adjust__sum'] or 0
print('SUM TF=',tf,' SUM hosei=',hs,' SUM adjust=',ad)
"
```



## **✅ C. ランダム数名の目視（実務で効く）**





「指定学生の先頭10問だけ TF/hosei を表示」

```
python manage.py shell -c "
from exam2.models import Student,StudentExamVersion,StudentExam
stdNo='25367001'
stu=Student.objects.get(stdNo=stdNo)
sev=StudentExamVersion.objects.select_related('exam').get(student=stu, exam__subject__subjectNo='1010401', exam__subject__fsyear=2025)
exam=sev.exam
rows=StudentExam.objects.filter(student=stu, exam=exam).select_related('question').order_by('question__gyo','question__retu')[:10]
print('stdNo=',stdNo,'version=',exam.version,'exam_id=',exam.id)
for r in rows:
    print(r.question.gyo,r.question.retu,r.question.q_no,'TF=',r.TF,'hosei=',r.hosei)
"
```



------





# **3) 失敗しやすいポイント（ここだけ覚えておく）**





- **StudentExam が未作成**だと import で「missing」になりやすい

  → load_student_exam を先に実行、または import に --fill-missing

- **Exam / Question の並びが違う**と配列がズレる

  → export/import が同じ order_by("gyo","retu","id") になっていることが必須

- **legacy と新で problem_hash 列が違う**（旧DBには無い）

  → legacy export は「旧スキーマ前提」で書く必要がある（あなたの今の流れはそれ）





------



この手順で、**「採点（TF/hosei/adjust）をJSON経由で新DBへ移す」**ところまでは安全に完了できます。

次にやるべきは、移行対象が **採点だけで十分か**（たとえば「学生割当(SEV)も旧を引き継ぐ必要があるか」）の最終確認ですが、今の運用だと **SEVはYAMLから再生成**で問題ない設計になっています。