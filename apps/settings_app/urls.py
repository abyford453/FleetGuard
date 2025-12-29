from django.urls import path
from . import views

app_name = "settings_app"

urlpatterns = [
    path("", views.index, name="index"),
    path("organization/", views.organization_edit, name="organization_edit"),
]
