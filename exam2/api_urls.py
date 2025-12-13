# exam2/api_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EnvironmentAPIView,
    ExamsWithYearAPIView,
    ExamRetrieveAPIView,
    ExamStudentListAPIView,
    ExamResultAPIView,
    ExamAdjustUpdateAPIView,
    ExamAdjustCommentAPIView,
    StudentExamViewSet,
    studentexam_bulk_update,
    SubjectListAPIView,
    ExamsOfSubjectAPIView,
    StudentsOfExamAPIView,
    StudentsOfSubjectAPIView,
    ExamAdjustSubjectAPIView,
    ExamAdjustCommentSubjectAPIView,
    ExamAdjustUpdateSubjectAPIView,
)

router = DefaultRouter()
router.register(r"student-exams", StudentExamViewSet, basename="student-exams")

urlpatterns = [
    # 共通環境
    path("environment/", EnvironmentAPIView.as_view()),

    # index 用試験一覧
    path("exams_with_year/", ExamsWithYearAPIView.as_view()),

    # Exam 1件詳細 + Question
    path("exams/<int:pk>/", ExamRetrieveAPIView.as_view()),

    # 試験ごとの学生一覧
    path("exam-students/", ExamStudentListAPIView.as_view()),

    # 試験結果（index / adjust 共通）
    path("examresult/", ExamResultAPIView.as_view()),

    # 調整値更新
    path("exam-adjust-update/", ExamAdjustUpdateAPIView.as_view()),

    # adjust_comment
    path("examadjustcomment/", ExamAdjustCommentAPIView.as_view()),

    path("student-exams/bulk_update/", studentexam_bulk_update),

    path("subjects/", SubjectListAPIView.as_view()),
    path("exams_of_subject/", ExamsOfSubjectAPIView.as_view()),
    path("students_of_exam/", StudentsOfExamAPIView.as_view()),
    path("students_of_subject/", StudentsOfSubjectAPIView.as_view()),
    path("examadjust_subject/", ExamAdjustSubjectAPIView.as_view()),
    path("examadjustcomment_subject/", ExamAdjustCommentSubjectAPIView.as_view()),
    path("exam-adjust-update-subject/", ExamAdjustUpdateSubjectAPIView.as_view()),

    # StudentExam の CRUD
    path("", include(router.urls)),

]