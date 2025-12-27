from .models import Tenant, TenantMembership

class TenantMiddleware:
    """
    Sets request.tenant for authenticated users.

    Priority:
      1) session["tenant_id"] if valid membership
      2) first membership tenant
      3) if superuser, first Tenant (fallback)
      4) else None
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            # 1) session selection
            tenant_id = request.session.get("tenant_id")
            if tenant_id:
                if TenantMembership.objects.filter(user=user, tenant_id=tenant_id).exists():
                    request.tenant = Tenant.objects.filter(id=tenant_id).first()

            # 2) first membership
            if request.tenant is None:
                m = TenantMembership.objects.filter(user=user).select_related("tenant").first()
                if m:
                    request.tenant = m.tenant
                    request.session["tenant_id"] = m.tenant_id

            # 3) superuser fallback
            if request.tenant is None and user.is_superuser:
                t = Tenant.objects.first()
                if t:
                    request.tenant = t
                    request.session["tenant_id"] = t.id

        return self.get_response(request)
