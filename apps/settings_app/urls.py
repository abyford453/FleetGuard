from django.urls import path
from . import views

app_name = "settings_app"

urlpatterns = [
    path("", views.index, name="index"),
    path("organization/", views.organization_edit, name="organization_edit"),

    path("users/", views.users_list, name="users_list"),
    path("users/add/", views.user_add, name="user_add"),
    path("users/<int:membership_id>/remove/", views.user_remove_confirm, name="user_remove_confirm"),
    path("users/<int:membership_id>/role/", views.user_role_update, name="user_role_update"),

    path("audit/", views.audit_log, name="audit_log"),

    # Invite links
    path("invites/", views.invites_list, name="invites_list"),
    path("invites/new/", views.users_invite, name="users_invite"),
    path("invites/<int:invite_id>/revoke/", views.invite_revoke, name="invite_revoke"),
    path("invites/accept/<str:token>/", views.invite_accept, name="invite_accept"),
]
