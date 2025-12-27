from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages

from .models import Vehicle
from .forms import VehicleForm

def _require_tenant(request):
    if getattr(request, "tenant", None) is None:
        return False
    return True

@login_required
def vehicle_list(request):
    if not _require_tenant(request):
        return redirect("tenants:select")

    tenant = request.tenant
    q = (request.GET.get("q") or "").strip()

    qs = Vehicle.objects.filter(tenant=tenant)
    if q:
        qs = qs.filter(
            Q(unit_number__icontains=q) |
            Q(vin__icontains=q) |
            Q(plate__icontains=q) |
            Q(make__icontains=q) |
            Q(model__icontains=q)
        )

    return render(request, "fleet/vehicle_list.html", {
        "vehicles": qs,
        "q": q,
        "tenant": tenant,
    })

@login_required
def vehicle_create(request):
    if not _require_tenant(request):
        return redirect("tenants:select")

    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            v = form.save(commit=False)
            v.tenant = request.tenant
            v.save()
            messages.success(request, "Vehicle created.")
            return redirect("fleet:vehicle_detail", pk=v.pk)
    else:
        form = VehicleForm()

    return render(request, "fleet/vehicle_form.html", {
        "form": form,
        "mode": "create",
        "tenant": request.tenant,
    })

@login_required
def vehicle_detail(request, pk: int):
    if not _require_tenant(request):
        return redirect("tenants:select")

    v = get_object_or_404(Vehicle, pk=pk, tenant=request.tenant)
    return render(request, "fleet/vehicle_detail.html", {
        "vehicle": v,
        "tenant": request.tenant,
    })

@login_required
def vehicle_update(request, pk: int):
    if not _require_tenant(request):
        return redirect("tenants:select")

    v = get_object_or_404(Vehicle, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = VehicleForm(request.POST, instance=v)
        if form.is_valid():
            form.save()
            messages.success(request, "Vehicle updated.")
            return redirect("fleet:vehicle_detail", pk=v.pk)
    else:
        form = VehicleForm(instance=v)

    return render(request, "fleet/vehicle_form.html", {
        "form": form,
        "mode": "edit",
        "vehicle": v,
        "tenant": request.tenant,
    })

@login_required
def vehicle_delete(request, pk: int):
    if not _require_tenant(request):
        return redirect("tenants:select")

    v = get_object_or_404(Vehicle, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        v.delete()
        messages.success(request, "Vehicle deleted.")
        return redirect("fleet:vehicle_list")

    return render(request, "fleet/vehicle_delete.html", {
        "vehicle": v,
        "tenant": request.tenant,
    })
