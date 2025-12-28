from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import InspectionForm
from .models import Inspection

def _can_assign(user):
    return user.has_perm("inspections.assign_inspections")

def _can_complete(user):
    return user.has_perm("inspections.complete_inspections")

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

    if my == "1":
        qs = qs.filter(assigned_to=request.user)

    if vehicle_id:
        qs = qs.filter(vehicle_id=vehicle_id)

    if status:
        qs = qs.filter(status=status)

    if result:
        qs = qs.filter(result=result)

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
            "vehicles": vehicles,
            "result_choices": Inspection.RESULT_CHOICES,
            "status_choices": Inspection.STATUS_CHOICES,
            "can_assign": _can_assign(request.user),
            "can_complete": _can_complete(request.user),
            "today": timezone.localdate(),
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

            # Enforce assignment rules
            if not can_assign:
                # If user can't assign, it becomes "my" inspection
                obj.assigned_to = request.user
                # Keep assigned/in_progress depending on whether they can complete
                obj.status = Inspection.STATUS_IN_PROGRESS if can_complete else Inspection.STATUS_ASSIGNED

            # If user can't complete, prevent setting completed status
            if not can_complete and obj.status == Inspection.STATUS_COMPLETED:
                obj.status = Inspection.STATUS_ASSIGNED

            obj.save()
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

    # If not assign-capable, only allow editing if it's assigned to them
    if not can_assign:
        if obj.assigned_to_id != request.user.id:
            # view-only redirect
            return redirect("inspections:list")

    if request.method == "POST":
        form = InspectionForm(request.POST, instance=obj, tenant=tenant, user=request.user)
        if form.is_valid():
            updated = form.save(commit=False)

            # Enforce assignment rules
            if not can_assign:
                updated.assigned_to = obj.assigned_to or request.user
                updated.due_date = obj.due_date
                # Don't allow status changes except moving toward completion if they can complete
                updated.status = obj.status

            # Enforce completion rules
            if not can_complete:
                updated.result = obj.result
                updated.odometer = obj.odometer
                updated.notes = obj.notes
                if updated.status == Inspection.STATUS_COMPLETED:
                    updated.status = obj.status

            updated.save()
            return redirect("inspections:list")
    else:
        form = InspectionForm(instance=obj, tenant=tenant, user=request.user)

    return render(
        request,
        "inspections/form.html",
        {"form": form, "mode": "edit", "obj": obj, "can_assign": can_assign, "can_complete": can_complete},
    )

@login_required
def inspection_delete(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(Inspection, pk=pk, tenant=tenant)

    # Only assign-capable users can delete (keeps audit integrity)
    if not _can_assign(request.user):
        return redirect("inspections:list")

    if request.method == "POST":
        obj.delete()
        return redirect("inspections:list")

    return render(request, "inspections/form.html", {"mode": "delete", "obj": obj, "can_assign": True})
