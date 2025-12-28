from django.db import models
from django.conf import settings
from apps.tenants.models import Tenant
from apps.fleet.models import Vehicle

class FuelLog(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="fuel_logs")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="fuel_logs")

    fuel_date = models.DateField()
    odometer = models.PositiveIntegerField(null=True, blank=True)

    gallons = models.DecimalField(max_digits=7, decimal_places=3)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    vendor = models.CharField(max_length=120, blank=True)
    fuel_type = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_fuel_logs",
    )

    class Meta:
        ordering = ["-fuel_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "fuel_date"]),
            models.Index(fields=["tenant", "vehicle"]),
        ]

    def __str__(self):
        return f"{self.vehicle} - {self.fuel_date} ({self.gallons} gal)"
