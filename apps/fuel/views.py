from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FuelLogForm
from .models import FuelLog

@login_required
def fuel_list(request):
    tenant = request.tenant

    qs = (
        FuelLog.objects
        .filter(tenant=tenant)
        .select_related("vehicle")
        .order_by("-fuel_date", "-created_at")
    )

    q = (request.GET.get("q") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()

    if vehicle_id:
        qs = qs.filter(vehicle_id=vehicle_id)

    if q:
        qs = qs.filter(
            Q(vendor__icontains=q) |
            Q(fuel_type__icontains=q) |
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
        "fuel/list.html",
        {"logs": qs, "q": q, "vehicle_id": vehicle_id, "vehicles": vehicles},
    )

@login_required
def fuel_create(request):
    tenant = request.tenant

    if request.method == "POST":
        form = FuelLogForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.created_by = request.user
            obj.save()
            return redirect("fuel:list")
    else:
        form = FuelLogForm(tenant=tenant)

    return render(request, "fuel/form.html", {"form": form, "mode": "create"})

@login_required
def fuel_update(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(FuelLog, pk=pk, tenant=tenant)

    if request.method == "POST":
        form = FuelLogForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            form.save()
            return redirect("fuel:list")
    else:
        form = FuelLogForm(instance=obj, tenant=tenant)

    return render(request, "fuel/form.html", {"form": form, "mode": "edit", "obj": obj})

@login_required
def fuel_delete(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(FuelLog, pk=pk, tenant=tenant)

    if request.method == "POST":
        obj.delete()
        return redirect("fuel:list")

    return render(request, "fuel/form.html", {"mode": "delete", "obj": obj})
