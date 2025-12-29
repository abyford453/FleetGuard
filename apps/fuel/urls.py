from django.urls import path
from . import views

app_name = "fuel"

urlpatterns = [
    # Sidebar expects: {% url 'fuel:list' %}
    path("", views.fuel_list, name="list"),
    path("alerts/", views.fuel_alerts, name="alerts"),
    path("new/", views.fuel_create, name="fuel_create"),
    path("<int:pk>/edit/", views.fuel_update, name="fuel_update"),
    path("<int:pk>/delete/", views.fuel_delete, name="fuel_delete"),
]
