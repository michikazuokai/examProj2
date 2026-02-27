# exam2/pages_urls.py
from django.urls import path
from .views import index_page, exam_page , examadjust_page, manage_stdversion

urlpatterns = [
    path('', index_page, name='index'),
    path('exam/', exam_page, name='exam-page'),
    path('examadjust/', examadjust_page, name='adjust-page'),
    path("manage_stdversion/", manage_stdversion, name="manage_stdversion"),
]