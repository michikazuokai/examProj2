# exam2/models.py
from django.db import models


class Subject(models.Model):
    subjectNo = models.CharField(max_length=20)  # ★ uniqueを外す
    fsyear = models.IntegerField(null=False)               # ★ 追加
    term = models.IntegerField(null=False)                 # ★ 追加（その年度内で変わらない前提）
    # fsyear = models.IntegerField(null=True, blank=True)
    # term   = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=100)
    nenji = models.IntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["subjectNo", "fsyear"], name="uq_subject_subjectNo_fsyear"),
        ]
        indexes = [
            models.Index(fields=["subjectNo", "fsyear"]),
        ]

    def __str__(self):
        return f"{self.subjectNo} {self.name} ({self.fsyear}年度 {self.term}期)"


class Exam(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    version = models.CharField(max_length=5)   # A/B/C

    adjust_comment = models.TextField(blank=True)

    problem_hash = models.CharField(
        max_length=32, null=True, blank=True, db_index=True,
        help_text="問題内容を一意に識別するハッシュ（answers_xxxx.json の metainfo.hash）"
    )

    class Meta:
        # subject が年度込みになるので、これでOK
        constraints = [
            models.UniqueConstraint(fields=["subject", "version"], name="uq_exam_subject_version"),
        ]
        ordering = ["subject__subjectNo", "subject__fsyear", "subject__term", "version"]

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