from django.urls import path
from . import views

app_name = "settings_app"

urlpatterns = [
    path("", views.index, name="index"),
    path("organization/", views.organization_edit, name="organization_edit"),
    path("users/", views.users_list, name="users_list"),
    path("users/<int:membership_id>/remove/", views.user_remove_confirm, name="user_remove"),
    path("users/<int:membership_id>/role/", views.user_role_update, name="user_role_update"),
]
