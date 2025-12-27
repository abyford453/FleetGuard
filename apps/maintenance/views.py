from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def _module_ctx():
    planned_features = [
        "MaintenanceRecord model (tenant-owned) linked to Vehicle",
        "CRUD + list filters (vehicle, date range, service type)",
        "Due-soon reminders (later)",
        "Cost totals per vehicle (later)",
    ]
    routes = [
        "/maintenance/ (list)",
        "/maintenance/new/ (create)",
        "/maintenance/<id>/delete/ (delete)",
    ]
    template_files = [
        "templates/maintenance/list.html",
        "templates/maintenance/form.html",
        "templates/maintenance/delete.html",
    ]
    return {
        "planned_features": planned_features,
        "routes": routes,
        "template_files": template_files,
    }

@login_required
def list_records(request):
    return render(request, "maintenance/list.html", _module_ctx())

@login_required
def create_record(request):
    return render(request, "maintenance/form.html", _module_ctx())

@login_required
def delete_record(request, pk: int):
    ctx = _module_ctx()
    ctx["pk"] = pk
    return render(request, "maintenance/delete.html", ctx)
