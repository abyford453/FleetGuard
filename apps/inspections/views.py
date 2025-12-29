from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import InspectionForm, InspectionAlertForm
from .models import Inspection, InspectionAlert

def _can_assign(user):
    return user.has_perm("inspections.assign_inspections")

def _can_complete(user):
    return user.has_perm("inspections.complete_inspections")

def _can_manage_alerts(user):
    return user.has_perm("inspections.manage_inspection_alerts") or _can_assign(user)

def _sync_alert_for_inspection(inspection: Inspection, user):
    """
    If inspection is completed+fail => create/update alert
    Otherwise if alert exists and inspection not failed => optionally close? (we won't auto-close)
    """
    if inspection.status == Inspection.STATUS_COMPLETED and inspection.result == Inspection.RESULT_FAIL:
        title = f"Inspection Failed: {inspection.inspection_type or 'Inspection'}"
        details_bits = []
        if inspection.notes:
            details_bits.append(inspection.notes.strip())
        details = "\n\n".join(details_bits).strip()

        alert, created = InspectionAlert.objects.get_or_create(
            inspection=inspection,
            defaults={
                "tenant": inspection.tenant,
                "vehicle": inspection.vehicle,
                "title": title,
                "details": details,
                "severity": InspectionAlert.SEV_MED,
                "status": InspectionAlert.STATUS_OPEN,
                "assigned_to": inspection.assigned_to,
                "created_by": user,
            },
        )

        if not created:
            # Keep alert tenant/vehicle aligned (in case vehicle changed)
            changed = False
            if alert.tenant_id != inspection.tenant_id:
                alert.tenant = inspection.tenant
                changed = True
            if alert.vehicle_id != inspection.vehicle_id:
                alert.vehicle = inspection.vehicle
                changed = True

            # Update title/details if blank or if we want latest notes reflected
            new_title = title
            new_details = details
            if alert.title != new_title:
                alert.title = new_title
                changed = True
            if new_details and alert.details != new_details:
                alert.details = new_details
                changed = True

            # If alert is closed but inspection failed again, re-open it
            if alert.status == InspectionAlert.STATUS_CLOSED:
                alert.status = InspectionAlert.STATUS_OPEN
                alert.closed_at = None
                alert.closed_by = None
                changed = True

            # Align assignment to inspection assignment if currently empty
            if alert.assigned_to_id is None and inspection.assigned_to_id is not None:
                alert.assigned_to = inspection.assigned_to
                changed = True

            if changed:
                alert.save()

        return alert
    return None

@login_required
def inspection_list(request):
    tenant = request.tenant

    qs = (
        Inspection.objects
        .filter(tenant=tenant)
        .select_related("vehicle", "assigned_to")
        .order_by("-inspection_date", "-created_at")
    )

    q = (request.GET.get("q") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()
    result = (request.GET.get("result") or "").strip()
    status = (request.GET.get("status") or "").strip()
    my = (request.GET.get("my") or "").strip()
    overdue = (request.GET.get("overdue") or "").strip()
    due_soon = (request.GET.get("due_soon") or "").strip()

    if my == "1":
        qs = qs.filter(assigned_to=request.user)

    if vehicle_id:
        qs = qs.filter(vehicle_id=vehicle_id)

    if status:
        qs = qs.filter(status=status)

    if result:
        qs = qs.filter(result=result)


    if due_soon == "1":
        today = timezone.localdate()
        soon = today + timezone.timedelta(days=7)
        qs = qs.filter(due_date__isnull=False, due_date__gte=today, due_date__lte=soon).exclude(status=Inspection.STATUS_COMPLETED)

    if overdue == "1":
        today = timezone.localdate()
        qs = qs.filter(due_date__isnull=False, due_date__lt=today).exclude(status=Inspection.STATUS_COMPLETED)

    if q:
        qs = qs.filter(
            Q(inspection_type__icontains=q) |
            Q(notes__icontains=q) |
            Q(vehicle__unit_number__icontains=q) |
            Q(vehicle__vin__icontains=q) |
            Q(vehicle__plate__icontains=q) |
            Q(vehicle__make__icontains=q) |
            Q(vehicle__model__icontains=q)
        )

    vehicles = tenant.vehicles.all().order_by("unit_number", "year", "make", "model")

    # Count open alerts for quick visibility
    open_alerts_count = InspectionAlert.objects.filter(tenant=tenant).exclude(status=InspectionAlert.STATUS_CLOSED).count()

    return render(
        request,
        "inspections/list.html",
        {
            "inspections": qs,
            "q": q,
            "vehicle_id": vehicle_id,
            "result": result,
            "status": status,
            "my": my,
            "overdue": overdue,
            "due_soon": due_soon,
            "vehicles": vehicles,
            "result_choices": Inspection.RESULT_CHOICES,
            "status_choices": Inspection.STATUS_CHOICES,
            "can_assign": _can_assign(request.user),
            "can_complete": _can_complete(request.user),
            "can_manage_alerts": _can_manage_alerts(request.user),
            "today": timezone.localdate(),
            "open_alerts_count": open_alerts_count,
        },
    )

@login_required
def inspection_create(request):
    tenant = request.tenant
    can_assign = _can_assign(request.user)
    can_complete = _can_complete(request.user)

    if request.method == "POST":
        form = InspectionForm(request.POST, tenant=tenant, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.created_by = request.user

            if not can_assign:
                obj.assigned_to = request.user
                obj.status = Inspection.STATUS_IN_PROGRESS if can_complete else Inspection.STATUS_ASSIGNED

            if not can_complete and obj.status == Inspection.STATUS_COMPLETED:
                obj.status = Inspection.STATUS_ASSIGNED

            obj.save()

            # Phase 2: create/update alert when completed+fail
            _sync_alert_for_inspection(obj, request.user)

            return redirect("inspections:list")
    else:
        form = InspectionForm(tenant=tenant, user=request.user)

    return render(
        request,
        "inspections/form.html",
        {"form": form, "mode": "create", "can_assign": can_assign, "can_complete": can_complete},
    )

@login_required
def inspection_update(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(Inspection, pk=pk, tenant=tenant)

    can_assign = _can_assign(request.user)
    can_complete = _can_complete(request.user)

    if not can_assign:
        if obj.assigned_to_id != request.user.id:
            return redirect("inspections:list")

    if request.method == "POST":
        form = InspectionForm(request.POST, instance=obj, tenant=tenant, user=request.user)
        if form.is_valid():
            updated = form.save(commit=False)

            if not can_assign:
                updated.assigned_to = obj.assigned_to or request.user
                updated.due_date = obj.due_date
                updated.status = obj.status

            if not can_complete:
                updated.result = obj.result
                updated.odometer = obj.odometer
                updated.notes = obj.notes
                if updated.status == Inspection.STATUS_COMPLETED:
                    updated.status = obj.status

            updated.save()

            # Phase 2: create/update alert when completed+fail
            _sync_alert_for_inspection(updated, request.user)

            return redirect("inspections:list")
    else:
        form = InspectionForm(instance=obj, tenant=tenant, user=request.user)

    return render(
        request,
        "inspections/form.html",
        {"form": form, "mode": "edit", "obj": obj, "can_assign": can_assign, "can_complete": can_complete},
    )


@login_required
def inspection_detail(request, pk: int):
    tenant = request.tenant
    inspection = get_object_or_404(
        Inspection.objects.select_related("vehicle", "assigned_to", "alert"),
        pk=pk,
        tenant=tenant,
    )
    return render(request, "inspections/detail.html", {"inspection": inspection})

@login_required
def inspection_delete(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(Inspection, pk=pk, tenant=tenant)

    if not _can_assign(request.user):
        return redirect("inspections:list")

    if request.method == "POST":
        obj.delete()
        return redirect("inspections:list")

    return render(request, "inspections/form.html", {"mode": "delete", "obj": obj, "can_assign": True})


# -----------------------------
# Alerts
# -----------------------------
@login_required
def alert_list(request):
    tenant = request.tenant
    qs = (
        InspectionAlert.objects
        .filter(tenant=tenant)
        .select_related("vehicle", "inspection", "assigned_to")
        .order_by("-created_at")
    )

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    severity = (request.GET.get("severity") or "").strip()
    my = (request.GET.get("my") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()

    if status:
        qs = qs.filter(status=status)
    if severity:
        qs = qs.filter(severity=severity)
    if my == "1":
        qs = qs.filter(assigned_to=request.user)
    if vehicle_id:
        qs = qs.filter(vehicle_id=vehicle_id)

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(details__icontains=q) |
            Q(vehicle__unit_number__icontains=q) |
            Q(vehicle__plate__icontains=q) |
            Q(vehicle__vin__icontains=q) |
            Q(vehicle__make__icontains=q) |
            Q(vehicle__model__icontains=q)
        )

    vehicles = tenant.vehicles.all().order_by("unit_number", "year", "make", "model")

    return render(
        request,
        "inspections/alerts.html",
        {
            "alerts": qs,
            "q": q,
            "status": status,
            "severity": severity,
            "my": my,
            "vehicle_id": vehicle_id,
            "vehicles": vehicles,
            "status_choices": InspectionAlert.STATUS_CHOICES,
            "severity_choices": InspectionAlert.SEVERITY_CHOICES,
            "can_manage_alerts": _can_manage_alerts(request.user),
        },
    )

@login_required
def alert_update(request, pk: int):
    tenant = request.tenant
    alert = get_object_or_404(InspectionAlert, pk=pk, tenant=tenant)

    if not _can_manage_alerts(request.user):
        return redirect("inspections:alerts")

    if request.method == "POST":
        form = InspectionAlertForm(request.POST, instance=alert)
        if form.is_valid():
            obj = form.save(commit=False)
            # If closing via edit screen, set closed stamps
            if obj.status == InspectionAlert.STATUS_CLOSED and alert.status != InspectionAlert.STATUS_CLOSED:
                obj.closed_at = timezone.now()
                obj.closed_by = request.user
            if obj.status != InspectionAlert.STATUS_CLOSED:
                obj.closed_at = None
                obj.closed_by = None
            obj.save()
            return redirect("inspections:alerts")
    else:
        form = InspectionAlertForm(instance=alert)

    return render(request, "inspections/alert_form.html", {"form": form, "alert": alert})

@login_required
def alert_close(request, pk: int):
    tenant = request.tenant
    alert = get_object_or_404(InspectionAlert, pk=pk, tenant=tenant)

    if not _can_manage_alerts(request.user):
        return redirect("inspections:alerts")

    if request.method == "POST":
        alert.close(request.user)

    return redirect("inspections:alerts")

@login_required
def alert_ack(request, pk: int):
    tenant = request.tenant
    alert = get_object_or_404(InspectionAlert, pk=pk, tenant=tenant)
    if not _can_manage_alerts(request.user):
        return redirect("inspections:alerts")
    if request.method == "POST":
        if alert.status == InspectionAlert.STATUS_OPEN:
            alert.status = InspectionAlert.STATUS_ACK
            alert.save(update_fields=["status"])
    return redirect("inspections:alerts")


@login_required
def alert_assign_to_me(request, pk: int):
    tenant = request.tenant
    alert = get_object_or_404(InspectionAlert, pk=pk, tenant=tenant)
    if not _can_manage_alerts(request.user):
        return redirect("inspections:alerts")
    if request.method == "POST":
        alert.assigned_to = request.user
        if alert.status == InspectionAlert.STATUS_OPEN:
            alert.status = InspectionAlert.STATUS_ACK
        alert.save(update_fields=["assigned_to", "status"])
    return redirect("inspections:alerts")
