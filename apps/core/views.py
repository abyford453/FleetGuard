from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.inspections.models import Inspection, InspectionAlert

def home(request):
    # Always send to login for now (hero page)
    return redirect("accounts:login")

@login_required
def dashboard(request):
    tenant = request.tenant
    today = timezone.localdate()
    soon = today + timezone.timedelta(days=7)

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
        .filter(tenant=tenant, due_date__isnull=False, due_date__gte=today, due_date__lte=soon)
        .exclude(status=Inspection.STATUS_COMPLETED)
        .count()
    )

    return render(
        request,
        "core/dashboard.html",
        {
            "open_alerts": open_alerts,
            "overdue_inspections": overdue_inspections,
            "due_soon_inspections": due_soon_inspections,
        },
    )
