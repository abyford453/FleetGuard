from django.urls import path
from . import views

app_name = "tenants"

urlpatterns = [
    path("select/", views.tenant_select, name="select"),
    path("create/", views.tenant_create, name="create"),
    path("set/<int:tenant_id>/", views.tenant_set, name="set"),
]
