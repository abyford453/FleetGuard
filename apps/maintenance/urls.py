from django.urls import path
from . import views

app_name = "maintenance"

urlpatterns = [
    # Alias name to match base.html nav: {% url 'maintenance:list' %}
    path("", views.maintenance_list, name="list"),

    # Keep our explicit name too (used by redirects, etc.)
    path("", views.maintenance_list, name="maintenance_list"),

    path("new/", views.maintenance_create, name="maintenance_create"),
    path("<int:pk>/edit/", views.maintenance_update, name="maintenance_update"),
    path("<int:pk>/delete/", views.maintenance_delete, name="maintenance_delete"),
]
