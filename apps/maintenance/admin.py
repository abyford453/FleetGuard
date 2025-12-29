from django.contrib import admin
from .models import MaintenanceRecord

@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("service_date", "tenant", "vehicle", "category", "description", "vendor", "cost")
    list_filter = ("tenant", "category", "service_date")
    search_fields = ("description", "vendor", "vehicle__name", "vehicle__unit_number")
