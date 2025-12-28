from django.urls import path
from . import views

app_name = "inspections"

urlpatterns = [
    # Sidebar expects: {% url 'inspections:list' %}
    path("", views.inspection_list, name="list"),
    path("new/", views.inspection_create, name="inspection_create"),
    path("<int:pk>/edit/", views.inspection_update, name="inspection_update"),
    path("<int:pk>/delete/", views.inspection_delete, name="inspection_delete"),
]
