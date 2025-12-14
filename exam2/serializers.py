# exam2/serializers.py
from rest_framework import serializers
from .models import Subject, Exam, Question, Student, StudentExam, ExamAdjust


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "subjectNo", "name"]  # title を name にマッピングしている想定なら調整


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id",
            "exam",
            "q_no",   # 問題番号
            "bunrui",
            "gyo",
            "retu",
            "answer",
            "points",
            "width",
            "height",
        ]


class ExamSerializer(serializers.ModelSerializer):
    subjectNo = serializers.CharField(source="subject.subjectNo", read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "subject",
            "subjectNo",
            "title",
            "fsyear",
            "term",
            "version",
            # "target_year",
            "adjust_comment",
            "questions",
            "problem_hash",
        ]


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ["id", "stdNo", "nickname"]


class StudentExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentExam
        fields = [
            "id",
            "student",
            "exam",
            "question",
            "TF",
            "hosei",
        ]


class ExamAdjustSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAdjust
        fields = [
            "id",
            "exam",
            "stdNo",   # Student FK
            "adjust",
        ]