from django.contrib import admin
from .models import Inspection

@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("inspection_date", "tenant", "vehicle", "inspection_type", "result", "odometer")
    list_filter = ("tenant", "result", "inspection_date")
    search_fields = ("inspection_type", "notes", "vehicle__vin", "vehicle__plate", "vehicle__unit_number", "vehicle__make", "vehicle__model")
