from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
from .models import Tenant, TenantMembership

@login_required
def tenant_select(request):
    memberships = TenantMembership.objects.filter(user=request.user).select_related("tenant")

    # superuser may see all tenants
    tenants = [m.tenant for m in memberships]
    if request.user.is_superuser:
        tenants = list(Tenant.objects.all())

    return render(request, "tenants/select.html", {
        "tenants": tenants,
        "current_tenant_id": request.session.get("tenant_id"),
    })

@login_required
def tenant_set(request, tenant_id: int):
    allowed = TenantMembership.objects.filter(user=request.user, tenant_id=tenant_id).exists()
    if request.user.is_superuser:
        allowed = Tenant.objects.filter(id=tenant_id).exists()

    if not allowed:
        return HttpResponseForbidden("Not allowed to access this tenant.")

    request.session["tenant_id"] = int(tenant_id)
    return redirect("core:dashboard")

@login_required
def tenant_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if name:
            tenant = Tenant.objects.create(name=name)
            TenantMembership.objects.create(
                tenant=tenant,
                user=request.user,
                role=TenantMembership.ROLE_ADMIN
            )
            request.session["tenant_id"] = tenant.id
            return redirect("core:dashboard")

    return render(request, "tenants/create.html")
