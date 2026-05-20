# exam2/services.py

from dataclasses import dataclass

from django.db import transaction

from .models import (
    Subject,
    Exam,
    Question,
    Student,
    StudentExam,
    StudentExamVersion,
    ExamAdjust,
)


@dataclass
class VersionChangeResult:
    subject: Subject
    student: Student
    old_version: str | None
    new_version: str
    created_student_exam_count: int


def get_current_exam_version(subject: Subject, student: Student) -> str | None:
    """
    指定科目における学生の現在のA/B版を返す。
    未割当なら None。
    """
    sev = (
        StudentExamVersion.objects
        .filter(student=student, exam__subject=subject)
        .select_related("exam")
        .order_by("exam__version")
        .first()
    )

    if not sev:
        return None

    return sev.exam.version


def change_student_exam_version(
    *,
    subject_id: int,
    student_id: int,
    target_version: str,
) -> VersionChangeResult:
    """
    学生のA/B版を変更する。

    重要：
    StudentExam の exam だけを update しない。
    Question は Exam に属しているため、旧版の StudentExam は削除し、
    新版の Question に合わせて StudentExam を作り直す。
    """

    target_version = str(target_version).upper()

    with transaction.atomic():
        subject = Subject.objects.get(id=subject_id)
        student = Student.objects.get(id=student_id)

        new_exam = Exam.objects.get(
            subject=subject,
            version=target_version,
        )

        old_version = get_current_exam_version(subject, student)

        # 同じ版なら、データは触らず結果だけ返す
        if old_version == target_version:
            question_count = Question.objects.filter(exam=new_exam).count()

            return VersionChangeResult(
                subject=subject,
                student=student,
                old_version=old_version,
                new_version=target_version,
                created_student_exam_count=question_count,
            )

        # この科目に属するA/B試験
        subject_exams = Exam.objects.filter(subject=subject)

        # 旧データを削除
        StudentExamVersion.objects.filter(
            student=student,
            exam__in=subject_exams,
        ).delete()

        StudentExam.objects.filter(
            student=student,
            exam__in=subject_exams,
        ).delete()

        ExamAdjust.objects.filter(
            student=student,
            exam__in=subject_exams,
        ).delete()

        # 新しい版を割り当て
        StudentExamVersion.objects.create(
            student=student,
            exam=new_exam,
        )

        # 新しい版の問題に合わせて StudentExam を作り直す
        questions = list(
            Question.objects
            .filter(exam=new_exam)
            .order_by("gyo", "retu", "id")
        )

        StudentExam.objects.bulk_create([
            StudentExam(
                student=student,
                exam=new_exam,
                question=q,
                TF=0,
                hosei=0,
            )
            for q in questions
        ])

        # 試験全体補正も 0 で作り直す
        ExamAdjust.objects.create(
            student=student,
            exam=new_exam,
            adjust=0,
        )

        return VersionChangeResult(
            subject=subject,
            student=student,
            old_version=old_version,
            new_version=target_version,
            created_student_exam_count=len(questions),
        )