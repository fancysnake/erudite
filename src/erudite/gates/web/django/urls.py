from django.contrib import admin
from django.urls import path

from erudite.gates.web.django.home import home

urlpatterns = [path("admin/", admin.site.urls), path("", home, name="home")]
