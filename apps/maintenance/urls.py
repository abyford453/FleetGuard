from django.urls import path
from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.list_records, name="list"),
    path("new/", views.create_record, name="new"),
    path("<int:pk>/delete/", views.delete_record, name="delete"),
]
