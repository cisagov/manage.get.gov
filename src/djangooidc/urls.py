# coding: utf-8

from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.openid, name="openid"),
    path("callback/login/", views.login_callback, name="openid_login_callback"),
    path("logout/", views.logout, name="logout"),
    path("callback/logout/", views.logout_callback, name="openid_logout_callback"),
]
