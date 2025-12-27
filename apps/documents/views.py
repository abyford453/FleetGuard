from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def _module_ctx():
    planned_features = [
        "VehicleDocument model (tenant-owned) linked to Vehicle",
        "Upload documents (media storage)",
        "Document types (registration, insurance, warranties, etc.)",
    ]
    routes = [
        "/documents/ (list)",
        "/documents/new/ (create)",
        "/documents/<id>/delete/ (delete)",
    ]
    template_files = [
        "templates/documents/document_list.html",
        "templates/documents/document_form.html",
        "templates/documents/document_delete.html",
    ]
    return {
        "planned_features": planned_features,
        "routes": routes,
        "template_files": template_files,
    }

@login_required
def document_list(request):
    return render(request, "documents/document_list.html", _module_ctx())

@login_required
def document_create(request):
    return render(request, "documents/document_form.html", _module_ctx())

@login_required
def document_delete(request, pk: int):
    ctx = _module_ctx()
    ctx["pk"] = pk
    return render(request, "documents/document_delete.html", ctx)
