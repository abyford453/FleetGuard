from django.db import models
from django.conf import settings

class MaintenanceRecord(models.Model):
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="maintenance_records",
    )
    vehicle = models.ForeignKey(
        "fleet.Vehicle",
        on_delete=models.PROTECT,
        related_name="maintenance_records",
    )

    service_date = models.DateField()
    odometer = models.PositiveIntegerField(null=True, blank=True)

    category = models.CharField(max_length=60, blank=True)
    description = models.CharField(max_length=200)
    vendor = models.CharField(max_length=120, blank=True)

    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    next_due_date = models.DateField(null=True, blank=True)
    next_due_odometer = models.PositiveIntegerField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_maintenance_records",
    )

    class Meta:
        ordering = ["-service_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "service_date"]),
            models.Index(fields=["tenant", "vehicle"]),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle} - {self.description} ({self.service_date})"
