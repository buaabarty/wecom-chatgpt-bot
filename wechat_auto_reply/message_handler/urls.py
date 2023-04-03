from django.urls import path
from . import views

urlpatterns = [
    path('wechat/', views.wechat, name='wechat'),
]
