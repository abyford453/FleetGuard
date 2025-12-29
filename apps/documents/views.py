from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import VehicleDocumentForm
from .models import VehicleDocument

@login_required
def document_list(request):
    tenant = request.tenant

    qs = (
        VehicleDocument.objects
        .filter(tenant=tenant)
        .select_related("vehicle")
        .order_by("-uploaded_at")
    )

    q = (request.GET.get("q") or "").strip()
    vehicle_id = (request.GET.get("vehicle") or "").strip()
    doc_type = (request.GET.get("doc_type") or "").strip()

    expired = (request.GET.get("expired") or "").strip()
    expiring = (request.GET.get("expiring") or "").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(notes__icontains=q) |
            Q(vehicle__unit_number__icontains=q) |
            Q(vehicle__plate__icontains=q) |
            Q(vehicle__vin__icontains=q) |
            Q(vehicle__make__icontains=q) |
            Q(vehicle__model__icontains=q)
        )

    if vehicle_id:
        qs = qs.filter(vehicle_id=vehicle_id)

    if doc_type:
        qs = qs.filter(doc_type=doc_type)


    # Expiration filters
    today = timezone.localdate()
    soon = today + timezone.timedelta(days=30)

    if expired == "1":
        qs = qs.filter(expires_on__isnull=False, expires_on__lt=today)

    if expiring == "1":
        qs = qs.filter(expires_on__isnull=False, expires_on__gte=today, expires_on__lte=soon)

    vehicles = tenant.vehicles.all().order_by("unit_number", "year", "make", "model")

    return render(
        request,
        "documents/document_list.html",
        {
            "documents": qs,
            "vehicles": vehicles,
            "q": q,
            "vehicle_id": vehicle_id,
            "doc_type": doc_type,
            "doc_types": VehicleDocument.TYPE_CHOICES,
            "expired": expired,
            "expiring": expiring,
            "today": timezone.localdate(),
        },
    )

@login_required
def document_create(request):
    tenant = request.tenant

    if request.method == "POST":
        form = VehicleDocumentForm(request.POST, request.FILES, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            return redirect("documents:document_list")
    else:
        form = VehicleDocumentForm(tenant=tenant)

    return render(request, "documents/document_form.html", {"form": form, "mode": "create"})

@login_required
def document_delete(request, pk: int):
    tenant = request.tenant
    doc = get_object_or_404(VehicleDocument, pk=pk, tenant=tenant)

    if request.method == "POST":
        doc.delete()
        return redirect("documents:document_list")

    return render(request, "documents/document_form.html", {"doc": doc, "mode": "delete"})
