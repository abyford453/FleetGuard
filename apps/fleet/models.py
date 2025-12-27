from django.db import models
from apps.tenants.models import Tenant

class Vehicle(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="vehicles")

    unit_number = models.CharField(max_length=50, blank=True)
    vin = models.CharField(max_length=50, blank=True)
    plate = models.CharField(max_length=20, blank=True)

    year = models.PositiveIntegerField(null=True, blank=True)
    make = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=80, blank=True)
    trim = models.CharField(max_length=80, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        label = self.unit_number or self.plate or "Vehicle"
        return f"{label} ({self.make} {self.model})".strip()
