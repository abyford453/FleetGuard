from django.db import models
from apps.tenants.models import Tenant
from apps.fleet.models import Vehicle

class VehicleDocument(models.Model):
    TYPE_INSURANCE = "insurance"
    TYPE_REGISTRATION = "registration"
    TYPE_TITLE = "title"
    TYPE_WARRANTY = "warranty"
    TYPE_OTHER = "other"
    TYPE_CHOICES = [
        (TYPE_INSURANCE, "Insurance"),
        (TYPE_REGISTRATION, "Registration"),
        (TYPE_TITLE, "Title"),
        (TYPE_WARRANTY, "Warranty"),
        (TYPE_OTHER, "Other"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="vehicle_documents")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="documents")

    doc_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_OTHER)
    title = models.CharField(max_length=140, blank=True)

    file = models.FileField(upload_to="vehicle_docs/%Y/%m/")
    expires_on = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["tenant", "vehicle"]),
            models.Index(fields=["tenant", "doc_type"]),
            models.Index(fields=["tenant", "expires_on"]),
        ]

    def __str__(self):
        label = self.title or self.get_doc_type_display()
        return f"{label} - {self.vehicle}"
