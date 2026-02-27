"""release URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
import django_cas_ng.views


def dashboard_category_count(request):
    return JsonResponse({'code': 200, 'message': None, 'data': {
        'appModule': 0, 'db': 0, 'server': 0, 'network': 0
    }})


urlpatterns = [
    path('admin', admin.site.urls),
    path('api/', include(('api.urls', 'api'), namespace='api')),
    path('login', django_cas_ng.views.LoginView.as_view(), name='cas_ng_login'),
    path('logout/', django_cas_ng.views.LogoutView.as_view(), name='cas_ng_logout'),
]
