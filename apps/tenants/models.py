from django.conf import settings
from django.db import models
from django.utils.text import slugify

class Tenant(models.Model):
    # Identity
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Preferences v1 (tenant-scoped settings)
    UNITS_DISTANCE_MILES = "miles"
    UNITS_DISTANCE_KM = "km"
    UNITS_DISTANCE_CHOICES = [
        (UNITS_DISTANCE_MILES, "Miles"),
        (UNITS_DISTANCE_KM, "Kilometers"),
    ]

    UNITS_FUEL_GALLONS = "gallons"
    UNITS_FUEL_LITERS = "liters"
    UNITS_FUEL_CHOICES = [
        (UNITS_FUEL_GALLONS, "Gallons"),
        (UNITS_FUEL_LITERS, "Liters"),
    ]

    # Alerts / defaults
    default_inspection_due_days = models.PositiveIntegerField(default=30)
    inspection_alert_days_before = models.PositiveIntegerField(default=7)

    maintenance_alert_miles_before = models.PositiveIntegerField(default=500)
    maintenance_alert_days_before = models.PositiveIntegerField(default=14)

    units_distance = models.CharField(
        max_length=10, choices=UNITS_DISTANCE_CHOICES, default=UNITS_DISTANCE_MILES
    )
    units_fuel = models.CharField(
        max_length=10, choices=UNITS_FUEL_CHOICES, default=UNITS_FUEL_GALLONS
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:150] or "tenant"
            slug = base
            i = 2
            while Tenant.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class TenantMembership(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_USER = "user"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_USER, "User"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tenant", "user")

    def __str__(self):
        return f"{self.user} → {self.tenant} ({self.role})"
