# exam2/views.py
from rest_framework.decorators import api_view
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.db import models
from django.db.models import Sum, Case, When, F, IntegerField
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.conf import settings

from .models import (
    Subject,
    Exam,
    Question,
    Student,
    StudentExam,
    ExamAdjust,
    StudentExamVersion,
)
from .serializers import (
    SubjectSerializer,
    ExamSerializer,
    QuestionSerializer,
    StudentSerializer,
    StudentExamSerializer,
    ExamAdjustSerializer,
)


# =========================
# HTML ページ用 View
# =========================

def index_page(request):
    """試験一覧 + 結果画面 (index.html)"""
    return render(request, "index.html")


def exam_page(request):
    """採点画面 (exam.html)"""
    return render(request, "exam.html")


def examadjust_page(request):
    """全体調整画面 (examadjust.html)"""
    return render(request, "examadjust.html")


class ExamPageView(View):
    """（旧互換） exam.html を返すだけ"""
    def get(self, request, *args, **kwargs):
        return render(request, "exam.html")


# =========================
# 環境情報
# =========================



class EnvironmentAPIView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({
            "environment": settings.ENVIRONMENT,
            "fsyear": settings.FSYEAR,
            "term": settings.TERM,
        })

# =========================
# 試験一覧（index 用）
# =========================

class SubjectListAPIView(APIView):
    """
    GET /api/subjects/
    → 科目一覧（subjectNo, name, nenji を返す）
    """

    def get(self, request, *args, **kwargs):
        subjects = Subject.objects.all().order_by("subjectNo")

        data = [
            {
                "subjectNo": s.subjectNo,
                "name": s.name,
                "nenji": s.nenji
            }
            for s in subjects
        ]

        return Response(data, status=200)


class ExamsOfSubjectAPIView(APIView):
    def get(self, request):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear")
        term = request.GET.get("term")

        subject = Subject.objects.get(subjectNo=subjectNo)

        exams = Exam.objects.filter(subject=subject, fsyear=fsyear, term=term)

        data = [
            {"id": e.id, "version": e.version, "title": e.title}
            for e in exams
        ]

        return Response(data)

class StudentsOfExamAPIView(APIView):
    def get(self, request):
        exam_id = request.GET.get("exam_id")
        sev_list = StudentExamVersion.objects.filter(exam_id=exam_id)

        data = [
            {
                "stdNo": sev.student.stdNo,
                "nickname": sev.student.nickname,
                "version": sev.exam.version
            }
            for sev in sev_list
        ]

        return Response(data)

class ExamsWithYearAPIView(APIView):
    """
    GET /api/exams_with_year/
    → {
         "current_year": 2025,
         "exams": [
           {"id": 1, "exam_code": "1010401-A", "title": "情報処理Ⅰ（1期 A版）"},
           ...
         ]
       }
    """

    def get(self, request, *args, **kwargs):
        from datetime import datetime

        current_year = datetime.now().year
        exams = Exam.objects.all().order_by("subject__subjectNo", "version")

        data = {
            "current_year": current_year,
            "exams": [
                {
                    "id": exam.id,
                    "exam_code": f"{exam.subject.subjectNo}-{exam.version}",
                    "title": exam.title,
                }
                for exam in exams
            ],
        }
        return Response(data, status=200)


# =========================
# Exam 1件取得（採点画面用）
# =========================

class ExamRetrieveAPIView(APIView):
    """
    GET /api/exams/<pk>/
    → Exam + Question 一覧
    """

    def get(self, request, pk, *args, **kwargs):
        exam = get_object_or_404(Exam, pk=pk)
        serializer = ExamSerializer(exam)
        return Response(serializer.data, status=200)


# =========================
# 学生一覧（特定 Exam の学生）
# =========================

class ExamStudentListAPIView(APIView):
    """
    GET /api/exam-students/?exam_id=1
    → その試験を受けた学生一覧
    """

    def get(self, request, *args, **kwargs):
        exam_id = request.query_params.get("exam_id")
        if not exam_id:
            return Response(
                {"error": "exam_id が必要です"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exam = get_object_or_404(Exam, pk=exam_id)
        # この Exam に StudentExam がある学生を抽出
        student_ids = (
            StudentExam.objects.filter(exam=exam)
            .values_list("student_id", flat=True)
            .distinct()
        )
        students = Student.objects.filter(id__in=student_ids).order_by("stdNo")

        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data, status=200)


# =========================
# StudentExam CRUD + フィルタ
# =========================

class StudentExamViewSet(viewsets.ModelViewSet):
    """
    /api/student-exams/
      GET: exam & student で絞り込み
      PATCH: TF / hosei 更新
    """

    queryset = StudentExam.objects.all().select_related("student", "exam", "question")
    serializer_class = StudentExamSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        exam_id = self.request.query_params.get("exam")
        student_id = self.request.query_params.get("student")
        student_stdno = self.request.query_params.get("student_stdno")

        if exam_id:
            qs = qs.filter(exam_id=exam_id)

        if student_id:
            qs = qs.filter(student_id=student_id)

        if student_stdno:
            qs = qs.filter(student__stdNo=student_stdno)

        return qs.order_by("question__gyo", "question__retu")

    def create(self, request, *args, **kwargs):
        """
        必要ならここで「Exam と Student から一括生成」を実装しても良いが、
        今回は既存データ前提でそのままにしておく。
        """
        return super().create(request, *args, **kwargs)


# =========================
# 試験結果（index & adjust 共通）
# =========================

class ExamResultAPIView(APIView):
    """
    GET /api/examresult/?wexamid=1

    → {
         "wexamid": 1,
         "exam_name": "情報処理Ⅰ（1期 A版）",
         "fsyear": "2025",
         "students": [
           {
             "stdNo": "23367001",
             "nickname": "ルオン",
             "score": 2,         # 素点 (TF=1 の points 合計)
             "correction": 0,    # 補正の合計 (hosei の合計)
             "adjust": 0,        # ExamAdjust.adjust
             "total": 2          # score + correction
           },
           ...
         ]
       }
    """

    def get(self, request, *args, **kwargs):
        exam_id = request.query_params.get("wexamid")
        if not exam_id:
            return Response({"error": "wexamid が必要です"}, status=400)

        exam = get_object_or_404(Exam, pk=exam_id)

        # この Exam に紐づく全 StudentExam
        student_exams = (
            StudentExam.objects.filter(exam=exam)
            .select_related("student", "question")
        )

        # 学生ごとに集計
        result = {}
        for se in student_exams:
            stu = se.student
            q = se.question

            base = q.points if se.TF == 1 else 0
            corr = se.hosei or 0

            if stu.id not in result:
                result[stu.id] = {
                    "stdNo": stu.stdNo,
                    "nickname": stu.nickname,
                    "score": 0,
                    "correction": 0,
                }

            result[stu.id]["score"] += base
            result[stu.id]["correction"] += corr

        # ExamAdjust を反映
        adjusts = ExamAdjust.objects.filter(exam=exam).select_related("student")
        adjust_map = {adj.student.id: adj.adjust for adj in adjusts}

        students_data = []
        for stu_id, d in result.items():
            base = d["score"]
            corr = d["correction"]
            adj = adjust_map.get(stu_id, 0)
            total = base + corr

            students_data.append(
                {
                    "stdNo": d["stdNo"],
                    "nickname": d["nickname"],
                    "score": base,
                    "correction": corr,
                    "adjust": adj,
                    "total": total,
                }
            )

        data = {
            "wexamid": exam.id,
            "exam_name": exam.title,
            "fsyear": exam.fsyear,
            "students": students_data,
        }
        return Response(data, status=200)


# =========================
# ExamAdjust 更新 API
# =========================

class ExamAdjustUpdateAPIView(APIView):
    """
    POST /api/exam-adjust-update/

    [
      {"exam_id": 1, "stdNo": "23367001", "adjust": 3},
      ...
    ]
    """

    def post(self, request, *args, **kwargs):
        payload = request.data
        if not isinstance(payload, list):
            return Response(
                {"error": "配列で送ってください"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in payload:
            exam_id = item.get("exam_id")
            stdNo = item.get("stdNo")
            adjust = item.get("adjust", 0)

            if not (exam_id and stdNo):
                continue

            exam = get_object_or_404(Exam, pk=exam_id)
            student = get_object_or_404(Student, stdNo=stdNo)

            obj, _created = ExamAdjust.objects.get_or_create(
                exam=exam,
                student=student,
                defaults={"adjust": adjust},
            )
            if not _created:
                obj.adjust = adjust
                obj.save()

        return Response({"status": "ok"}, status=200)


# =========================
# adjust_comment 用 API
# =========================

class ExamAdjustCommentAPIView(APIView):
    """
    GET /api/examadjustcomment/?wexamid=1
    PUT /api/examadjustcomment/?wexamid=1 { "adjust_comment": "..." }
    """

    def get_exam(self, request):
        exam_id = request.query_params.get("wexamid")
        if not exam_id:
            return None, Response({"error": "wexamid が必要です"}, status=400)
        exam = get_object_or_404(Exam, pk=exam_id)
        return exam, None

    def get(self, request, *args, **kwargs):
        exam, error = self.get_exam(request)
        if error:
            return error
        return Response({"adjust_comment": exam.adjust_comment or ""}, status=200)

    def put(self, request, *args, **kwargs):
        exam, error = self.get_exam(request)
        if error:
            return error

        comment = request.data.get("adjust_comment", "")
        exam.adjust_comment = comment
        exam.save(update_fields=["adjust_comment"])
        return Response({"status": "ok"}, status=200)

@api_view(["PATCH"])
def studentexam_bulk_update(request):
    """
    StudentExam の複数レコードを一括更新する
    """
    data = request.data  # [{id, TF, hosei}, ...]

    for item in data:
        obj = StudentExam.objects.get(id=item["id"])
        if "TF" in item:
            obj.TF = item["TF"]
        if "hosei" in item:
            obj.hosei = item["hosei"]
        obj.save()

    return Response({"status": "ok"})


# exam2/api_views.py
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from exam2.models import (
    Subject, Student, Exam, StudentExamVersion,
    StudentExam, ExamAdjust
)

class StudentsOfSubjectAPIView(APIView):
    def get(self, request):
        subjectNo = request.GET.get("subjectNo")
        fsyear = int(request.GET.get("fsyear"))   # ★ ここが重要！
        term = request.GET.get("term")

        subject = get_object_or_404(Subject, subjectNo=subjectNo)

        # 科目の指定学年
        target_nenji = subject.nenji

        # 対象学生の入学年度を計算
        entyear = fsyear - target_nenji + 1

        # 学年の学生一覧
        students = Student.objects.filter(entyear=entyear)

        results = []

        for stu in students:
            # ★ version と exam_id を学生ごとに取得
            sev = StudentExamVersion.objects.filter(
                student=stu,
                exam__subject=subject,
                exam__fsyear=fsyear,
                exam__term=term,
            ).first()

            version = sev.exam.version if sev else "？"
            exam_id = sev.exam.id if sev else None

            # ★ 点数（A/B 関係なく、その学生の exam_id で取る）
            total_score = (
                StudentExam.objects.filter(student=stu, exam_id=exam_id)
                .aggregate(total=models.Sum(models.F("TF") + models.F("hosei")))["total"]
                or 0
            )

            # ★ adjust（無ければ 0）
            adjust = ExamAdjust.objects.filter(student=stu, exam_id=exam_id).first()
            adjust_value = adjust.adjust if adjust else 0

            results.append({
                "stdNo": stu.stdNo,
                "name": stu.nickname,
                "version": version,
                "exam_id": exam_id,
                "score": total_score,
                "hosei": 0,
                "adjust": adjust_value,
                "total": total_score + adjust_value,
            })

        return Response({"students": results})

class ExamAdjustSubjectAPIView(APIView):
    """
    GET /api/examadjust_subject/?subjectNo=2030402&fsyear=2025&term=2

    → その科目 / 年度 / 期 に属する学生を
       A/B まとめて返す（version は表示用に含める）
    """

    def get(self, request, *args, **kwargs):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear")
        term = request.GET.get("term")

        if not (subjectNo and fsyear and term):
            return Response(
                {"error": "subjectNo, fsyear, term を指定してください"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fsyear = int(fsyear)
        term = int(term)

        subject = get_object_or_404(Subject, subjectNo=subjectNo)

        # ★ 学生と Exam(=A/B) の対応は StudentExamVersion に入っている想定
        sev_qs = StudentExamVersion.objects.filter(
            exam__subject=subject,
            exam__fsyear=fsyear,
            exam__term=term,
        ).select_related("student", "exam").order_by("student__stdNo")

        students_data = []

        for sev in sev_qs:
            stu = sev.student
            exam = sev.exam   # この exam が A or B

            # 得点集計（points + hosei）
            score_agg = StudentExam.objects.filter(
                student=stu,
                exam=exam,
            ).aggregate(
                score=Sum(
                    Case(
                        When(TF=1, then=F("question__points")),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
                hosei=Sum("hosei")
            )
            score = score_agg["score"] or 0
            hosei = score_agg["hosei"] or 0

            # adjust
            adj = ExamAdjust.objects.filter(
                student=stu,
                exam=exam,
            ).first()
            adjust = adj.adjust if adj else 0

            students_data.append({
                "stdNo": stu.stdNo,
                "nickname": stu.nickname,
                "version": exam.version,  # A / B
                "exam_id": exam.id,
                "score": score,
                "hosei": hosei,
                "adjust": adjust,
                "total": score + hosei + adjust,
            })

        return Response(
            {
                "subjectNo": subject.subjectNo,
                "subject_name": subject.name,
                "fsyear": fsyear,
                "term": term,
                "students": students_data,
            },
            status=status.HTTP_200_OK,
        )

class ExamAdjustCommentSubjectAPIView(APIView):
    """
    科目全体の adjust コメントを取得・更新する API
    GET /api/examadjustcomment_subject/?subjectNo=XXX&fsyear=YYY&term=Z
    PUT /api/examadjustcomment_subject/?subjectNo=XXX&fsyear=YYY&term=Z
    """

    def get(self, request, *args, **kwargs):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear")
        term = request.GET.get("term")

        if not (subjectNo and fsyear and term):
            return Response({"error": "subjectNo, fsyear, term が必要です"}, status=400)

        exam = (
            Exam.objects.filter(
                subject__subjectNo=subjectNo,
                fsyear=fsyear,
                term=term
            )
            .order_by("version")
            .first()
        )

        if not exam:
            return Response({"adjust_comment": ""})

        return Response({"adjust_comment": exam.adjust_comment or ""})


    def put(self, request, *args, **kwargs):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear")
        term = request.GET.get("term")

        if not (subjectNo and fsyear and term):
            return Response({"error": "subjectNo, fsyear, term が必要です"}, status=400)

        exams = Exam.objects.filter(
            subject__subjectNo=subjectNo,
            fsyear=fsyear,
            term=term
        )

        comment = request.data.get("adjust_comment", "")

        for exam in exams:
            exam.adjust_comment = comment
            exam.save(update_fields=["adjust_comment"])

        return Response({"status": "ok", "adjust_comment": comment})

class ExamAdjustUpdateSubjectAPIView(APIView):
    """
    POST /api/exam-adjust-update-subject/
    {
        "subjectNo": "2030402",
        "fsyear": 2025,
        "term": 2,
        "items": [
            {
                "stdNo": "23367001",
                "exam_id": 7,
                "adjust": 3
            },
            ...
        ]
    }
    """

    def post(self, request, *args, **kwargs):

        subjectNo = request.data.get("subjectNo")
        fsyear = request.data.get("fsyear")
        term = request.data.get("term")
        items = request.data.get("items", [])

        if not (subjectNo and fsyear and term):
            return Response(
                {"error": "subjectNo, fsyear, term が必要です"},
                status=400
            )

        for item in items:
            exam_id = item.get("exam_id")
            stdNo = item.get("stdNo")
            adjust = item.get("adjust", 0)

            if not exam_id or not stdNo:
                continue

            exam = get_object_or_404(Exam, pk=exam_id)
            student = get_object_or_404(Student, stdNo=stdNo)

            obj, created = ExamAdjust.objects.get_or_create(
                exam=exam,
                student=student,
                defaults={"adjust": adjust}
            )
            if not created:
                obj.adjust = adjust
                obj.save()

        return Response({"status": "ok"}, status=200)