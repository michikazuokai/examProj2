# exam2/models.py
from django.db import models


class Subject(models.Model):
    subjectNo = models.CharField(max_length=20, unique=True)  # 科目コード
    name = models.CharField(max_length=100)                   # 科目名例：情報処理Ⅰ
    nenji = models.IntegerField(default=1)               # 何年生が受講するかの年次

    def __str__(self):
        return f"{self.subjectNo} {self.name}"


class Exam(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, default=1)
    title = models.CharField(max_length=100)          # 例：情報処理Ⅰ（1期 A版）

    # 試験情報
    fsyear = models.CharField(max_length=4)           # 年度
    term = models.IntegerField()                      # 学期（1期〜n期）
    version = models.CharField(max_length=5)          # A/B/C

    # 任意で調整コメントを保持（旧 adjust_comment）
    adjust_comment = models.TextField(blank=True)

    # ★ 追加（安全）
    problem_hash = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        db_index=True,
        help_text="問題内容を一意に識別するハッシュ（answers_xxxx.json の metainfo.hash）"
    )

    class Meta:
        unique_together = ("subject", "fsyear", "term", "version")
        ordering = ["subject__subjectNo", "fsyear", "term", "version"]

    def __str__(self):
        return f"{self.subject.subjectNo}-{self.version} {self.title}"


class Question(models.Model):
    exam = models.ForeignKey(
        Exam,
        related_name='questions',
        on_delete=models.CASCADE
    )

    # 問題番号（旧 exam_code）
    q_no = models.CharField(max_length=50, default='')  
    # bunrui（分類：選択, 記述, プログラム, 単語, 図式...）
    bunrui = models.CharField(max_length=20, blank=True, default='')

    # 採点情報
    points = models.IntegerField(default=1)

    # レイアウト情報
    gyo = models.IntegerField(default=1)   # ← default を入れる
    retu = models.IntegerField(default=1)
    width = models.IntegerField(default=1)
    height = models.IntegerField(default=60)

    # 正答
    answer = models.CharField(max_length=255, default='')

    class Meta:
        ordering = ["gyo", "retu"]

    def __str__(self):
        return f"{self.q_no} ({self.exam})"

class Student(models.Model):
    id = models.IntegerField(primary_key=True)
    entyear = models.IntegerField()
    stdNo = models.CharField(max_length=8, unique=True)
    email = models.EmailField()
    name1 = models.CharField(max_length=255)
    name2 = models.CharField(max_length=255)
    nickname = models.CharField(max_length=255)
    gender = models.CharField(max_length=1)
    COO = models.CharField(max_length=50)
    enrolled = models.BooleanField(default=True)

    class Meta:
        db_table = 'student'
        managed = False

    def __str__(self):
        return f"{self.stdNo}:{self.nickname}"

class ExamAdjust(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    adjust = models.IntegerField(default=0)

    class Meta:
        unique_together = ("exam", "student")


class StudentExamVersion(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('student', 'exam')

    def __str__(self):
        return f"{self.student.stdNo} → {self.exam}"


class StudentExam(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    TF = models.IntegerField(default=0)
    hosei = models.IntegerField(default=0)

    class Meta:
        unique_together = ("student", "exam", "question")