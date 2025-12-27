from django.contrib import admin
from .models import Tenant, TenantMembership

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")

@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("tenant", "user", "role", "created_at")
    list_filter = ("role", "tenant")
    search_fields = ("tenant__name", "tenant__slug", "user__username", "user__email")
