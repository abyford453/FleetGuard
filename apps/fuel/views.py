from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def _module_ctx():
    planned_features = [
        "FuelLog model (tenant-owned) linked to Vehicle",
        "CRUD + basic stats (later)",
        "MPG calculations (later)",
    ]
    routes = [
        "/fuel/ (list)",
        "/fuel/new/ (create)",
        "/fuel/<id>/delete/ (delete)",
    ]
    template_files = [
        "templates/fuel/list.html",
        "templates/fuel/form.html",
        "templates/fuel/delete.html",
    ]
    return {
        "planned_features": planned_features,
        "routes": routes,
        "template_files": template_files,
    }

@login_required
def list_logs(request):
    return render(request, "fuel/list.html", _module_ctx())

@login_required
def create_log(request):
    return render(request, "fuel/form.html", _module_ctx())

@login_required
def delete_log(request, pk: int):
    ctx = _module_ctx()
    ctx["pk"] = pk
    return render(request, "fuel/delete.html", ctx)
