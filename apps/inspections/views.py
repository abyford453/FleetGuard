from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def _module_ctx():
    planned_features = [
        "Inspection model (tenant-owned) linked to Vehicle",
        "Pass/Fail/Needs Attention status",
        "Recurring schedules/reminders (later)",
    ]
    routes = [
        "/inspections/ (list)",
        "/inspections/new/ (create)",
        "/inspections/<id>/delete/ (delete)",
    ]
    template_files = [
        "templates/inspections/list.html",
        "templates/inspections/form.html",
        "templates/inspections/delete.html",
    ]
    return {
        "planned_features": planned_features,
        "routes": routes,
        "template_files": template_files,
    }

@login_required
def inspection_list(request):
    return render(request, "inspections/list.html", _module_ctx())

@login_required
def inspection_create(request):
    return render(request, "inspections/form.html", _module_ctx())

@login_required
def inspection_delete(request, pk: int):
    ctx = _module_ctx()
    ctx["pk"] = pk
    return render(request, "inspections/delete.html", ctx)
