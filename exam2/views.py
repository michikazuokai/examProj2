# exam2/views.py
from django.conf import settings
from django.contrib import messages
from django.db import models, transaction
from django.db.models import Sum, Case, When, F, Value, IntegerField
from django.views import View

from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

# --- views.py 追加/置き換え用（manage_stdversion 一覧＋切替） ---
from django.db.models.functions import Coalesce
from django.db.models.expressions import ExpressionWrapper
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from exam2.forms import ManageStdVersionSubjectForm

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
    """
    GET /api/environment/
    settings の表示用（termは今後不要化してもOK）
    """
    def get(self, request, *args, **kwargs):
        return Response({
            "environment": getattr(settings, "ENVIRONMENT", ""),
            "fsyear": getattr(settings, "FSYEAR", None),
            "term": getattr(settings, "TERM", None),
        })


# =========================
# 科目一覧（index 用）
# =========================

class SubjectListAPIView(APIView):
    """
    GET /api/subjects/?fsyear=2025
    → 科目一覧（subjectNo, name, nenji, fsyear, term）
    ※ 新構造：Subject に fsyear/term がある
    """
    def get(self, request, *args, **kwargs):
        fsyear = request.GET.get("fsyear") or getattr(settings, "FSYEAR", None)
        if fsyear is None:
            return Response({"error": "fsyear が未指定です"}, status=400)

        fsyear = int(fsyear)
        subjects = Subject.objects.filter(fsyear=fsyear).order_by("subjectNo")

        data = [
            {
                "subjectNo": s.subjectNo,
                "name": s.name,
                "nenji": s.nenji,
                "fsyear": s.fsyear,
                "term": s.term,
            }
            for s in subjects
        ]
        return Response(data, status=status.HTTP_200_OK)


class ExamsOfSubjectAPIView(APIView):
    """
    GET /api/exams_of_subject/?subjectNo=1010401&fsyear=2025
    → 指定科目（年度込み）の Exam 一覧（A/B…）
    """
    def get(self, request, *args, **kwargs):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear") or getattr(settings, "FSYEAR", None)

        if not subjectNo or fsyear is None:
            return Response({"error": "subjectNo と fsyear が必要です"}, status=400)

        subject = get_object_or_404(Subject, subjectNo=subjectNo, fsyear=int(fsyear))
        exams = Exam.objects.filter(subject=subject).order_by("version")

        data = [
            {
                "id": e.id,
                "version": e.version,
                "title": e.title,
                "problem_hash": e.problem_hash,
            }
            for e in exams
        ]
        return Response(data, status=200)


class StudentsOfExamAPIView(APIView):
    """
    GET /api/students_of_exam/?exam_id=xx
    → 試験(Exam)を受けた学生（StudentExamVersionベース）
    """
    def get(self, request, *args, **kwargs):
        exam_id = request.GET.get("exam_id")
        if not exam_id:
            return Response({"error": "exam_id が必要です"}, status=400)

        sev_list = StudentExamVersion.objects.filter(exam_id=exam_id).select_related("student", "exam")

        data = [
            {
                "stdNo": sev.student.stdNo,
                "nickname": sev.student.nickname,
                "version": sev.exam.version
            }
            for sev in sev_list
        ]
        return Response(data, status=200)


class ExamsWithYearAPIView(APIView):
    """
    旧互換。必要なら残す。不要なら削除してOK。
    GET /api/exams_with_year/
    """
    def get(self, request, *args, **kwargs):
        from datetime import datetime

        current_year = datetime.now().year
        exams = Exam.objects.all().select_related("subject").order_by("subject__subjectNo", "subject__fsyear", "version")

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
    → ExamSerializer（questions含む想定）
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
    → その試験を受けた学生一覧（StudentExamベース）
    """
    def get(self, request, *args, **kwargs):
        exam_id = request.query_params.get("exam_id")
        if not exam_id:
            return Response({"error": "exam_id が必要です"}, status=400)

        exam = get_object_or_404(Exam, pk=exam_id)

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

        return qs.order_by("question__gyo", "question__retu", "question_id")


# =========================
# 試験結果（採点一覧/結果画面）
# =========================

class ExamResultAPIView(APIView):
    """
    GET /api/examresult/?wexamid=1
    → Exam1件の学生別集計（score/correction/adjust/total）
    """
    def get(self, request, *args, **kwargs):
        exam_id = request.query_params.get("wexamid")
        if not exam_id:
            return Response({"error": "wexamid が必要です"}, status=400)

        exam = get_object_or_404(Exam, pk=exam_id)

        student_exams = (
            StudentExam.objects.filter(exam=exam)
            .select_related("student", "question")
        )

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

        adjusts = ExamAdjust.objects.filter(exam=exam).select_related("student")
        adjust_map = {adj.student.id: adj.adjust for adj in adjusts}

        students_data = []
        for stu_id, d in result.items():
            base = d["score"]
            corr = d["correction"]
            adj = adjust_map.get(stu_id, 0)
            total = base + corr

            students_data.append({
                "stdNo": d["stdNo"],
                "nickname": d["nickname"],
                "score": base,
                "correction": corr,
                "adjust": adj,
                "total": total,
            })

        return Response({
            "wexamid": exam.id,
            "exam_name": exam.title,
            "fsyear": exam.subject.fsyear,   # ★ 新構造
            "term": exam.subject.term,       # ★ 新構造
            "students": students_data,
        }, status=200)


# =========================
# ExamAdjust 更新（旧：exam単位）
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
            return Response({"error": "配列で送ってください"}, status=400)

        for item in payload:
            exam_id = item.get("exam_id")
            stdNo = item.get("stdNo")
            adjust = item.get("adjust", 0)
            if not (exam_id and stdNo):
                continue

            exam = get_object_or_404(Exam, pk=exam_id)
            student = get_object_or_404(Student, stdNo=stdNo)

            obj, created = ExamAdjust.objects.get_or_create(
                exam=exam,
                student=student,
                defaults={"adjust": int(adjust)},
            )
            if not created:
                obj.adjust = int(adjust)
                obj.save(update_fields=["adjust"])

        return Response({"status": "ok"}, status=200)


# =========================
# adjust_comment（旧：exam単位）
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


# =========================
# （科目ベース）学生一覧：必要なら使う
# =========================
class StudentsOfSubjectAPIView(APIView):
    """
    GET /api/students_of_subject/?subjectNo=1010401&fsyear=2025
    ※ term パラメータは不要（あっても無視）
    """

    def get(self, request):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear") or getattr(settings, "FSYEAR", None)

        if not subjectNo or fsyear is None:
            return Response({"error": "subjectNo と fsyear が必要です"}, status=400)

        fsyear = int(fsyear)

        # ★ Subject は (subjectNo, fsyear) で特定（termはSubject側）
        subject = get_object_or_404(Subject, subjectNo=subjectNo, fsyear=fsyear)

        # 科目の指定学年
        target_nenji = subject.nenji

        # 対象学生の入学年度を計算
        entyear = fsyear - target_nenji + 1

        # 学年の学生一覧（必要なら enrolled=True など足せます）
        students = Student.objects.filter(entyear=entyear).order_by("stdNo")

        results = []

        for stu in students:
            # ★ version と exam_id を学生ごとに取得（exam__fsyear/term はもう無い）
            sev = (
                StudentExamVersion.objects.filter(
                    student=stu,
                    exam__subject=subject,
                )
                .select_related("exam")
                .order_by("exam__version")  # ★ A→B
                .first()
            )

            if not sev:
                results.append({
                    "stdNo": stu.stdNo,
                    "nickname": stu.nickname,
                    "version": "？",
                    "exam_id": None,
                    "score": 0,
                    "hosei": 0,
                    "adjust": 0,
                    "total": 0,
                })
                continue

            exam = sev.exam

            # 得点集計（points + hosei）
            agg = StudentExam.objects.filter(student=stu, exam=exam).aggregate(
                score=Sum(
                    Case(
                        When(TF=1, then=F("question__points")),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
                hosei=Sum("hosei"),
            )
            score = agg["score"] or 0
            hosei = agg["hosei"] or 0

            # adjust（無ければ 0）
            adj = ExamAdjust.objects.filter(student=stu, exam=exam).first()
            adjust_value = adj.adjust if adj else 0

            results.append({
                "stdNo": stu.stdNo,
                "nickname": stu.nickname,
                "version": exam.version,
                "exam_id": exam.id,
                "score": score,
                "hosei": hosei,
                "adjust": adjust_value,
                "total": score + hosei + adjust_value,
            })

        return Response({
            "subjectNo": subject.subjectNo,
            "subject_name": subject.name,
            "fsyear": subject.fsyear,
            "term": subject.term,   # 表示用
            "students": results,
        }, status=200)


# =========================
# （科目ベース）調整一覧：index/examadjust 共通
# =========================

class ExamAdjustSubjectAPIView(APIView):
    """
    GET /api/examadjust_subject/?subjectNo=1010401&fsyear=2025
    ※ term は Subject.term を使う（パラメータ不要、来ても無視）
    """
    def get(self, request, *args, **kwargs):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear") or getattr(settings, "FSYEAR", None)

        if not subjectNo or fsyear is None:
            return Response({"error": "subjectNo と fsyear を指定してください"}, status=400)

        subject = get_object_or_404(Subject, subjectNo=subjectNo, fsyear=int(fsyear))

        # 科目内のA/B exams（hash表示用）
        exams = list(Exam.objects.filter(subject=subject).order_by("version"))
        exams_info = {
            e.version: {
                "id": e.id,
                "title": e.title,
                "problem_hash": e.problem_hash,
            }
            for e in exams
        }

        # フロント互換用に「代表1件」も返す（従来 data.exam を参照していた場合に便利）
        representative_exam = exams[0] if exams else None
        exam_info = None
        if representative_exam:
            exam_info = {
                "id": representative_exam.id,
                "version": representative_exam.version,
                "title": representative_exam.title,
                "problem_hash": representative_exam.problem_hash,
            }

        # 学生→受験Exam(A/B) の対応（subjectで十分）
        sev_qs = (
            StudentExamVersion.objects.filter(exam__subject=subject)
            .select_related("student", "exam")
            .order_by("student__stdNo")
        )

        students_data = []

        for sev in sev_qs:
            stu = sev.student
            exam = sev.exam  # A or B

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
                hosei=Sum("hosei"),
            )

            score = score_agg["score"] or 0
            hosei = score_agg["hosei"] or 0

            adj = ExamAdjust.objects.filter(student=stu, exam=exam).first()
            adjust = adj.adjust if adj else 0

            students_data.append({
                "stdNo": stu.stdNo,
                "nickname": stu.nickname,
                "version": exam.version,
                "exam_id": exam.id,
                "score": score,
                "hosei": hosei,
                "adjust": adjust,
                "total": score + hosei + adjust,
            })

        return Response({
            "subjectNo": subject.subjectNo,
            "subject_name": subject.name,
            "fsyear": subject.fsyear,
            "term": subject.term,
            "exam": exam_info,      # ★ 互換用（代表）
            "exams": exams_info,    # ★ 推奨：版ごとA/B
            "students": students_data,
        }, status=200)


class ExamAdjustCommentSubjectAPIView(APIView):
    """
    GET/PUT
    /api/examadjustcomment_subject/?subjectNo=XXX&fsyear=YYY
    term は Subject.term を使う（パラメータ不要）
    """
    def get(self, request, *args, **kwargs):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear") or getattr(settings, "FSYEAR", None)

        if not subjectNo or fsyear is None:
            return Response({"error": "subjectNo と fsyear が必要です"}, status=400)

        subject = get_object_or_404(Subject, subjectNo=subjectNo, fsyear=int(fsyear))

        exam = Exam.objects.filter(subject=subject).order_by("version").first()
        if not exam:
            return Response({"adjust_comment": ""}, status=200)

        return Response({"adjust_comment": exam.adjust_comment or ""}, status=200)

    def put(self, request, *args, **kwargs):
        subjectNo = request.GET.get("subjectNo")
        fsyear = request.GET.get("fsyear") or getattr(settings, "FSYEAR", None)

        if not subjectNo or fsyear is None:
            return Response({"error": "subjectNo と fsyear が必要です"}, status=400)

        subject = get_object_or_404(Subject, subjectNo=subjectNo, fsyear=int(fsyear))

        comment = request.data.get("adjust_comment", "")

        for e in Exam.objects.filter(subject=subject):
            e.adjust_comment = comment
            e.save(update_fields=["adjust_comment"])

        return Response({"status": "ok", "adjust_comment": comment}, status=200)


class ExamAdjustUpdateSubjectAPIView(APIView):
    """
    POST /api/exam-adjust-update-subject/
    {
      "subjectNo": "1010401",
      "fsyear": 2025,
      "items": [
        {"stdNo": "23367001", "exam_id": 7, "adjust": 3},
        ...
      ]
    }
    term は不要（来ても無視してOK）
    """

    def post(self, request, *args, **kwargs):
        subjectNo = request.data.get("subjectNo")
        fsyear = request.data.get("fsyear") or getattr(settings, "FSYEAR", None)
        items = request.data.get("items", [])

        if not subjectNo or fsyear is None:
            return Response(
                {"error": "subjectNo と fsyear が必要です"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(items, list):
            return Response(
                {"error": "items は配列で送ってください"},
                status=status.HTTP_400_BAD_REQUEST
            )

        subject = get_object_or_404(Subject, subjectNo=subjectNo, fsyear=int(fsyear))

        with transaction.atomic():
            for item in items:
                exam_id = item.get("exam_id")
                stdNo = item.get("stdNo")
                adjust_raw = item.get("adjust", 0)

                if not exam_id or not stdNo:
                    continue

                # adjust を安全に int 化（失敗したら 0）
                try:
                    adjust = int(adjust_raw)
                except (TypeError, ValueError):
                    adjust = 0

                # UIが min=0 ならサーバも合わせる（必要なら外してください）
                if adjust < 0:
                    adjust = 0

                exam = get_object_or_404(Exam, pk=exam_id)

                # safety：別科目の exam が混ざったら弾く
                if exam.subject_id != subject.id:
                    return Response(
                        {
                            "error": f"exam_id={exam_id} は subjectNo={subjectNo}({fsyear}) に属しません",
                            "stdNo": stdNo,
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                student = get_object_or_404(Student, stdNo=stdNo)

                obj, created = ExamAdjust.objects.get_or_create(
                    exam=exam,
                    student=student,
                    defaults={"adjust": adjust},
                )
                if not created:
                    if obj.adjust != adjust:  # 無駄なUPDATE削減（任意）
                        obj.adjust = adjust
                        obj.save(update_fields=["adjust"])

        return Response({"status": "ok"}, status=status.HTTP_200_OK)
 


def _students_for_subject(subject: Subject):
    """
    subject.nenji と subject.fsyear から、対象学生を絞る。
    仮定：1年は entyear = fsyear、2年は entyear = fsyear - 1
    """
    qs = Student.objects.all().order_by("stdNo")

    # 在籍だけ（任意）
    if hasattr(Student, "enrolled"):
        qs = qs.filter(enrolled=True)

    # 年次→入学年度で絞る（entyearがある前提）
    if hasattr(Student, "entyear"):
        target_entyear = subject.fsyear - (subject.nenji - 1)
        qs = qs.filter(entyear=target_entyear)

    return qs


@staff_member_required
def manage_stdversion(request):
    """
    一覧画面：
    - GET: subject を選ぶと、その年次の学生一覧を表示
    - POST: 1学生だけ A/B を変更（痕跡があれば forceなしで拒否）
      更新対象：SEV / StudentExam / ExamAdjust の exam を新バージョン側へ揃える
      点数：Σ(TF*points) + Σ(hosei) + adjust（adjustは1件想定）
    """

    # ---------------------------
    # POST（1学生のA/B切替）
    # ---------------------------
    if request.method == "POST":
        subject_id = request.POST.get("subject_id")
        student_id = request.POST.get("student_id")
        target_version = request.POST.get("target_version")  # "A" or "B"
        force = (request.POST.get("force") == "1")

        subject = Subject.objects.filter(id=subject_id).first()
        if not subject:
            messages.error(request, "Subject が見つかりません。")
            return redirect(reverse("manage_stdversion"))

        student = Student.objects.filter(id=student_id).first()
        if not student:
            messages.error(request, "Student が見つかりません。")
            return redirect(reverse("manage_stdversion") + f"?subject={subject.id}")

        exams = list(Exam.objects.filter(subject=subject).order_by("version"))
        exam_by_version = {e.version: e for e in exams}
        if target_version not in exam_by_version:
            messages.error(request, f"変更先 version が不正です: {target_version}")
            return redirect(reverse("manage_stdversion") + f"?subject={subject.id}")

        new_exam = exam_by_version[target_version]

        # 現在割当（SEV）確認
        sev_qs = StudentExamVersion.objects.filter(student=student, exam__subject=subject).select_related("exam")
        current_version = sev_qs.first().exam.version if sev_qs.exists() else None

        if current_version == target_version:
            messages.info(request, "変更なし（すでに指定バージョンです）")
            return redirect(reverse("manage_stdversion") + f"?subject={subject.id}")

        # 既存の関連QS
        se_qs = StudentExam.objects.filter(student=student, exam__subject=subject)
        adj_qs = ExamAdjust.objects.filter(student=student, exam__subject=subject)

        # 痕跡チェック（点数が入っているか：あなたの定義）
        tf_points_expr = ExpressionWrapper(
            F("TF") * F("question__points"),
            output_field=IntegerField(),
        )
        tf_points_sum = se_qs.aggregate(total=Coalesce(Sum(tf_points_expr), Value(0)))["total"]
        hosei_sum = se_qs.aggregate(total=Coalesce(Sum("hosei"), Value(0)))["total"]
        adjust_val = adj_qs.values_list("adjust", flat=True).first() or 0
        total_score = tf_points_sum + hosei_sum + adjust_val

        # 痕跡あり & forceなし -> ここで止める
        if total_score != 0 and not force:
            messages.error(request, f"点数が入っているため更新不可（forceなし）: total={total_score}")
            return redirect(reverse("manage_stdversion") + f"?subject={subject.id}")

        # --- atomic 更新 ---
        with transaction.atomic():
            # SEV 更新/作成
            if sev_qs.exists():
                sev_qs.update(exam=new_exam)
            else:
                StudentExamVersion.objects.create(student=student, exam=new_exam)

            if force:
                # ★強制：点数・補正をゼロクリア
                se_qs.update(TF=0, hosei=0, exam=new_exam)
                # ExamAdjustは「1件だけ」前提：存在するものは0にして新examへ
                adj_qs.update(adjust=0, exam=new_exam)
            else:
                # 通常：examだけ揃える（痕跡なし前提）
                se_qs.update(exam=new_exam)
                adj_qs.update(exam=new_exam)

        # セッションの「修正済み」蓄積（あなたの既存コードがあればそのまま）
        changed = request.session.get("stdversion_changed_ids", [])
        if student.id not in changed:
            changed.append(student.id)
        request.session["stdversion_changed_ids"] = changed
        request.session.modified = True

        messages.success(request, f"更新しました: {student.stdNo} {current_version} → {target_version}" + ("（強制0クリア）" if force else ""))

        return redirect(reverse("manage_stdversion") + f"?subject={subject.id}")

    # ---------------------------
    # GET（一覧表示）
    # ---------------------------
    form = ManageStdVersionSubjectForm(request.GET or None)

    subject = None
    rows = []

    if form.is_valid():
        subject = form.cleaned_data.get("subject")

    if request.method == "GET" and request.GET.get("clear") == "1":
        request.session["stdversion_changed_ids"] = []
        request.session.modified = True

    if subject:

        # 科目が変わったら「今回修正した学生」マークを自動クリア
        last_subject_id = request.session.get("stdversion_last_subject_id")
        if last_subject_id != subject.id:
            request.session["stdversion_changed_ids"] = []
            request.session["stdversion_last_subject_id"] = subject.id
            request.session.modified = True




        # Exam(A/B)を取得（点数計算で「割当examに絞る」ため）
        exams = list(Exam.objects.filter(subject=subject).order_by("version"))
        exam_by_version = {e.version: e for e in exams}

        students = list(_students_for_subject(subject))

        # 学生→現在version（SEV）をまとめて取得
        sev_map = {}
        for sev in (
            StudentExamVersion.objects
            .filter(exam__subject=subject, student__in=students)
            .select_related("exam")
        ):
            sev_map[sev.student_id] = sev.exam.version  # "A"/"B"

        # Σ(TF*points) 用
        tf_points_expr = ExpressionWrapper(
            F("TF") * F("question__points"),
            output_field=IntegerField(),
        )

        for st in students:
            current_v = sev_map.get(st.id)  # "A" / "B" / None

            # 点数は「割当済みならその exam のみに絞る」ほうが安全
            target_exam = exam_by_version.get(current_v) if current_v else None

            if target_exam:
                se_qs = StudentExam.objects.filter(student=st, exam=target_exam)
                adj_qs = ExamAdjust.objects.filter(student=st, exam=target_exam)
            else:
                # 未割当時などの例外：subject全体で計算（運用上は未割当を減らす）
                se_qs = StudentExam.objects.filter(student=st, exam__subject=subject)
                adj_qs = ExamAdjust.objects.filter(student=st, exam__subject=subject)

            tf_points_sum = se_qs.aggregate(total=Coalesce(Sum(tf_points_expr), Value(0)))["total"]
            hosei_sum = se_qs.aggregate(total=Coalesce(Sum("hosei"), Value(0)))["total"]
            adjust_val = adj_qs.values_list("adjust", flat=True).first() or 0  # 1件想定（無ければ0）

            total_score = tf_points_sum + hosei_sum + adjust_val

            rows.append({
                "student": st,
                "current_version": current_v,
                "total_score": total_score,
            })




    changed_ids = set(request.session.get("stdversion_changed_ids", []))

    ctx = {
        "form": form,
        "subject": subject,
        "rows": rows,
        "changed_ids": changed_ids,
    }
    return render(request, "exam2/manage_stdversion.html", ctx)

 