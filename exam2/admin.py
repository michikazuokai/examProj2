# exam2/admin.py
from django.contrib import admin
from .models import Student, Subject, Exam

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    # 一覧に出す列
    list_display = ("stdNo", "nickname", "name1", "name2", "entyear", "enrolled")
    # 一覧から検索できるように
    search_fields = ("stdNo", "nickname", "name1", "name2", "email")
    # フィルタ（必要なら）
#    list_filter = ("entyear", "enrolled", "gender")
    list_filter = ("entyear", "enrolled")   # ← entyear フィルタ
    # 並び順
    ordering = ("stdNo",)

    # 一覧で直接編集（便利：nickname/enrolled など）
    list_editable = ("nickname", "enrolled")

    # 編集画面のレイアウト（見やすさ）
    fieldsets = (
        ("基本", {"fields": ("stdNo", "nickname", "name1", "name2", "email")}),
        ("在籍情報", {"fields": ("entyear", "enrolled", "gender")}),
    )

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    # Subject は探しやすさ優先
    list_display = ("subjectNo", "fsyear", "term", "nenji", "name")
    search_fields = ("subjectNo", "name")
    list_filter = ("fsyear", "term", "nenji")
    ordering = ("-fsyear", "subjectNo", "term")

    # もし頻繁に修正するなら list_editable も可（運用に応じて）
    # list_editable = ("name",)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    # Exam は subject + version がキーなので、それが分かる表示にする
    list_display = ("id", "subject", "version")
    search_fields = ("subject__subjectNo", "subject__name")
    list_filter = ("version", "subject__fsyear", "subject__term", "subject__nenji")
    ordering = ("-subject__fsyear", "subject__subjectNo", "version")