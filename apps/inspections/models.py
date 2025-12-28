from django.db import models
from django.conf import settings
from apps.tenants.models import Tenant
from apps.fleet.models import Vehicle

class Inspection(models.Model):
    RESULT_PASS = "pass"
    RESULT_FAIL = "fail"
    RESULT_NA = "na"
    RESULT_CHOICES = [
        (RESULT_PASS, "Pass"),
        (RESULT_FAIL, "Fail"),
        (RESULT_NA, "N/A"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="inspections")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="inspections")

    inspection_date = models.DateField()
    inspection_type = models.CharField(max_length=80, blank=True)  # Annual / Safety / Post-Trip / etc.
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default=RESULT_PASS)

    odometer = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_inspections",
    )

    class Meta:
        ordering = ["-inspection_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "inspection_date"]),
            models.Index(fields=["tenant", "vehicle"]),
            models.Index(fields=["tenant", "result"]),
        ]

    def __str__(self):
        return f"{self.vehicle} - {self.inspection_date} ({self.result})"
