from django.urls import path
from . import views

app_name = "fuel"

urlpatterns = [
    path("", views.list_logs, name="list"),
    path("new/", views.create_log, name="new"),
    path("<int:pk>/delete/", views.delete_log, name="delete"),
]
