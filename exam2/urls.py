from django.urls import path
from .views import (
    index_page,
    exam_page,
    examadjust_page,
    manage_stdversion,
    manage_stdversion_confirm,
    manage_stdversion_execute,
)

urlpatterns = [
    path('', index_page, name='index'),
    path('exam/', exam_page, name='exam-page'),
    path('examadjust/', examadjust_page, name='adjust-page'),
    path("manage_stdversion/",manage_stdversion,name="manage_stdversion",),
    path("manage_stdversion/<int:subject_id>/<int:student_id>/<str:target_version>/confirm/",
        manage_stdversion_confirm,name="manage_stdversion_confirm",),
    path("manage_stdversion/<int:subject_id>/<int:student_id>/<str:target_version>/execute/",
        manage_stdversion_execute,name="manage_stdversion_execute",),
]