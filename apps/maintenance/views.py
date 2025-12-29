from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q

from .models import MaintenanceRecord
from .forms import MaintenanceRecordForm

@login_required
def maintenance_list(request):
    tenant = request.tenant

    qs = (
        MaintenanceRecord.objects
        .filter(tenant=tenant)
        .select_related("vehicle")
        .order_by("-service_date", "-created_at")
    )

    q = (request.GET.get("q") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()

    if vehicle_id:
        qs = qs.filter(vehicle_id=vehicle_id)

    if q:
        qs = qs.filter(
            Q(description__icontains=q) |
            Q(category__icontains=q) |
            Q(vendor__icontains=q) |
            Q(vehicle__name__icontains=q) |
            Q(vehicle__unit_number__icontains=q)
        )

    vehicles = (
    tenant.vehicles.all().order_by("unit_number", "year", "make", "model")
    if hasattr(tenant, "vehicles") else None
)

    return render(
        request,
        "maintenance/list.html",
        {
            "records": qs,
            "q": q,
            "vehicle_id": vehicle_id,
            "vehicles": vehicles,
        },
    )


@login_required
def maintenance_create(request):
    tenant = request.tenant

    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.created_by = request.user
            obj.save()
            return redirect("maintenance:maintenance_list")
    else:
        form = MaintenanceRecordForm(tenant=tenant)

    return render(request, "maintenance/form.html", {"form": form, "mode": "create"})


@login_required
def maintenance_update(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(MaintenanceRecord, pk=pk, tenant=tenant)

    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            form.save()
            return redirect("maintenance:maintenance_list")
    else:
        form = MaintenanceRecordForm(instance=obj, tenant=tenant)

    return render(request, "maintenance/form.html", {"form": form, "mode": "edit", "obj": obj})


@login_required
def maintenance_delete(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(MaintenanceRecord, pk=pk, tenant=tenant)

    if request.method == "POST":
        obj.delete()
        return redirect("maintenance:maintenance_list")

    return render(request, "maintenance/form.html", {"mode": "delete", "obj": obj})
