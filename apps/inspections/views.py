from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import InspectionForm
from .models import Inspection

@login_required
def inspection_list(request):
    tenant = request.tenant

    qs = (
        Inspection.objects
        .filter(tenant=tenant)
        .select_related("vehicle")
        .order_by("-inspection_date", "-created_at")
    )

    q = (request.GET.get("q") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()
    result = (request.GET.get("result") or "").strip()

    if vehicle_id:
        qs = qs.filter(vehicle_id=vehicle_id)

    if result:
        qs = qs.filter(result=result)

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
            "vehicles": vehicles,
            "result_choices": Inspection.RESULT_CHOICES,
        },
    )

@login_required
def inspection_create(request):
    tenant = request.tenant

    if request.method == "POST":
        form = InspectionForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.created_by = request.user
            obj.save()
            return redirect("inspections:list")
    else:
        form = InspectionForm(tenant=tenant)

    return render(request, "inspections/form.html", {"form": form, "mode": "create"})

@login_required
def inspection_update(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(Inspection, pk=pk, tenant=tenant)

    if request.method == "POST":
        form = InspectionForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            form.save()
            return redirect("inspections:list")
    else:
        form = InspectionForm(instance=obj, tenant=tenant)

    return render(request, "inspections/form.html", {"form": form, "mode": "edit", "obj": obj})

@login_required
def inspection_delete(request, pk: int):
    tenant = request.tenant
    obj = get_object_or_404(Inspection, pk=pk, tenant=tenant)

    if request.method == "POST":
        obj.delete()
        return redirect("inspections:list")

    return render(request, "inspections/form.html", {"mode": "delete", "obj": obj})
