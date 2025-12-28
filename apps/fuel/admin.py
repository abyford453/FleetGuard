from django.contrib import admin
from .models import FuelLog

@admin.register(FuelLog)
class FuelLogAdmin(admin.ModelAdmin):
    list_display = ("fuel_date", "tenant", "vehicle", "gallons", "cost", "vendor", "fuel_type", "odometer")
    list_filter = ("tenant", "fuel_type", "fuel_date")
    search_fields = ("vendor", "notes", "vehicle__vin", "vehicle__plate", "vehicle__unit_number", "vehicle__make", "vehicle__model")
