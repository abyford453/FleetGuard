from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from apps.fleet.models import Vehicle
from apps.inspections.models import Inspection, InspectionAlert
from apps.documents.models import VehicleDocument
from apps.fuel.models import FuelLog
from apps.fuel.alerts import vehicles_missing_fuel_logs, odometer_regressions


@login_required
def index(request):
    tenant = request.tenant
    today = timezone.localdate()

    # Vehicles
    vehicle_count = Vehicle.objects.filter(tenant=tenant).count()

    # Inspections
    open_alerts = (
        InspectionAlert.objects
        .filter(tenant=tenant)
        .exclude(status=InspectionAlert.STATUS_CLOSED)
        .count()
    )

    overdue_inspections = (
        Inspection.objects
        .filter(tenant=tenant, due_date__isnull=False, due_date__lt=today)
        .exclude(status=Inspection.STATUS_COMPLETED)
        .count()
    )

    due_soon_inspections = (
        Inspection.objects
        .filter(tenant=tenant, due_date__isnull=False, due_date__gte=today, due_date__lte=today + timedelta(days=7))
        .exclude(status=Inspection.STATUS_COMPLETED)
        .count()
    )

    # Documents
    expired_docs = (
        VehicleDocument.objects
        .filter(tenant=tenant, expires_on__isnull=False, expires_on__lt=today)
        .count()
    )
    expiring_docs = (
        VehicleDocument.objects
        .filter(tenant=tenant, expires_on__isnull=False, expires_on__gte=today, expires_on__lte=today + timedelta(days=30))
        .count()
    )

    # Fuel alerts (simple)
    fuel_stale_count = len(vehicles_missing_fuel_logs(tenant, days=30))
    fuel_odo_alert_count = len(odometer_regressions(tenant))

    # Fuel spend (last 30 days)
    spend_30 = (
        FuelLog.objects
        .filter(tenant=tenant, fuel_date__gte=today - timedelta(days=30))
        .aggregate(total=Sum("cost"))["total"]
    ) or 0

    return render(
        request,
        "reports/index.html",
        {
            "vehicle_count": vehicle_count,
            "open_alerts": open_alerts,
            "overdue_inspections": overdue_inspections,
            "due_soon_inspections": due_soon_inspections,
            "expired_docs": expired_docs,
            "expiring_docs": expiring_docs,
            "fuel_stale_count": fuel_stale_count,
            "fuel_odo_alert_count": fuel_odo_alert_count,
            "spend_30": spend_30,
        },
    )
