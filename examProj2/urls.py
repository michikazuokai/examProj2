from django.contrib import admin
from django.urls import path, include
from exam2 import views   # ★ index/exam/adjust HTML 用

urlpatterns = [
    path('admin/', admin.site.urls),

    # ▼ HTML ページ（上に書くこと！）
    # index や adjust などの HTML ページ
    path('', include('exam2.urls')),

    # ▼ API（/api/ 配下に集約）
    path('api/', include('exam2.api_urls')),  # ★ API 用URLは別ファイルに分離する
]