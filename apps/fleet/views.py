from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def _module_ctx():
    planned_features = [
        "Vehicle model (tenant-owned) + CRUD",
        "Vehicle detail page with tabs for Maintenance, Fuel, Inspections, Documents",
        "Search/filter (unit, VIN, plate, make/model)",
        "Status (active/inactive) and optional soft delete",
    ]
    routes = [
        "/vehicles/ (list)",
        "/vehicles/new/ (create)",
        "/vehicles/<id>/ (detail)",
        "/vehicles/<id>/edit/ (update)",
        "/vehicles/<id>/delete/ (delete)",
    ]
    template_files = [
        "templates/fleet/vehicle_list.html",
        "templates/fleet/vehicle_form.html",
        "templates/fleet/vehicle_detail.html",
        "templates/fleet/vehicle_delete.html",
    ]
    return {
        "planned_features": planned_features,
        "routes": routes,
        "template_files": template_files,
    }

@login_required
def vehicle_list(request):
    return render(request, "fleet/vehicle_list.html", _module_ctx())

@login_required
def vehicle_create(request):
    return render(request, "fleet/vehicle_form.html", _module_ctx())

@login_required
def vehicle_detail(request, pk: int):
    ctx = _module_ctx()
    ctx["pk"] = pk
    return render(request, "fleet/vehicle_detail.html", ctx)

@login_required
def vehicle_update(request, pk: int):
    ctx = _module_ctx()
    ctx["pk"] = pk
    return render(request, "fleet/vehicle_form.html", ctx)

@login_required
def vehicle_delete(request, pk: int):
    ctx = _module_ctx()
    ctx["pk"] = pk
    return render(request, "fleet/vehicle_delete.html", ctx)
