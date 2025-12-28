from django.db import models
from django.conf import settings
from apps.tenants.models import Tenant
from apps.fleet.models import Vehicle

class Inspection(models.Model):
    # Workflow status (assignment lifecycle)
    STATUS_ASSIGNED = "assigned"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_ASSIGNED, "Assigned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    # Outcome result (what happened)
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
    due_date = models.DateField(null=True, blank=True)

    inspection_type = models.CharField(max_length=80, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ASSIGNED)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_inspections",
    )

    # completion fields
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default=RESULT_PASS)
    odometer = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    completed_at = models.DateTimeField(null=True, blank=True)

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
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "assigned_to"]),
            models.Index(fields=["tenant", "result"]),
        ]
        permissions = [
            ("assign_inspections", "Can assign inspections"),
            ("complete_inspections", "Can complete inspections"),
        ]

    def save(self, *args, **kwargs):
        # Auto-set completed_at when marking completed the first time
        if self.status == self.STATUS_COMPLETED and self.completed_at is None:
            from django.utils import timezone
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.vehicle} - {self.inspection_date} ({self.status}/{self.result})"
