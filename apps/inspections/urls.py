from django.urls import path
from . import views

app_name = "inspections"

urlpatterns = [
    # Sidebar expects: {% url 'inspections:list' %}
    path("", views.inspection_list, name="list"),
    path("new/", views.inspection_create, name="inspection_create"),
    path("<int:pk>/", views.inspection_detail, name="inspection_detail"),
    path("<int:pk>/edit/", views.inspection_update, name="inspection_update"),
    path("<int:pk>/delete/", views.inspection_delete, name="inspection_delete"),

    # Alerts
    path("alerts/", views.alert_list, name="alerts"),
    path("alerts/<int:pk>/edit/", views.alert_update, name="alert_update"),
    path("alerts/<int:pk>/ack/", views.alert_ack, name="alert_ack"),
    path("alerts/<int:pk>/assign_to_me/", views.alert_assign_to_me, name="alert_assign_to_me"),
    path("alerts/<int:pk>/close/", views.alert_close, name="alert_close"),
]
