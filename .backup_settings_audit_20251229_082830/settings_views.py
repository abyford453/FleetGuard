from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse

from apps.tenants.models import TenantMembership, TenantAuditEvent
from .forms import TenantSettingsForm


def _get_membership(request):
    """
    Tenant-scoped membership lookup. Returns TenantMembership or None.
    """
    tenant = getattr(request, "tenant", None)
    user = getattr(request, "user", None)

    if not tenant or not user or not user.is_authenticated:
        return None

    return (
        TenantMembership.objects
        .filter(tenant=tenant, user=user)
        .select_related("tenant", "user")
        .first()
    )




def _audit(request, action: str, message: str = "", meta: dict | None = None) -> None:
    """
    Best-effort tenant-scoped audit writer. Never blocks the request.
    """
    try:
        tenant = getattr(request, "tenant", None)
        user = getattr(request, "user", None)
        if not tenant:
            return
        TenantAuditEvent.objects.create(
            tenant=tenant,
            actor=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            message=message or "",
            meta=meta or {},
        )
    except Exception:
        # Intentionally swallow audit errors (do not break main workflows)
        return

def _is_tenant_admin(membership: TenantMembership | None) -> bool:
    return bool(membership and membership.role == TenantMembership.ROLE_ADMIN)


def tenant_admin_required(view_func):
    """
    Enforces: user must be a member of the active tenant AND have admin role.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            messages.error(request, "No active tenant selected. Please select a tenant first.")
            return redirect("settings_app:index")

        membership = _get_membership(request)
        if not membership:
            messages.error(request, "You do not have access to this tenant.")
            return redirect("core:dashboard")

        if not _is_tenant_admin(membership):
            return HttpResponseForbidden("Admin access required.")

        request.tenant_membership = membership
        return view_func(request, *args, **kwargs)

    return _wrapped


@login_required
def index(request):
    tenant = getattr(request, "tenant", None)
    membership = _get_membership(request)
    is_admin = _is_tenant_admin(membership)

    # If a tenant is selected but the user isn't a member, bounce them out.
    if tenant and not membership:
        messages.error(request, "You do not have access to this tenant.")
        return redirect("core:dashboard")

    member_count = 0
    admin_count = 0
    your_role = "—"

    if tenant:
        qs = TenantMembership.objects.filter(tenant=tenant)
        member_count = qs.count()
        admin_count = qs.filter(role=TenantMembership.ROLE_ADMIN).count()
        if membership:
            your_role = membership.get_role_display()

    sections = [
        {
            "title": "Organization",
            "desc": "Tenant details and operational preferences.",
            "items": [
                {"label": "Tenant", "value": str(tenant) if tenant else "Not selected"},
                {"label": "Your role", "value": your_role if tenant else "—"},
            ],
            "cta": {
                "label": "Edit organization",
                "enabled": bool(tenant) and is_admin,
                "url": reverse("settings_app:organization_edit") if (tenant and is_admin) else None,
                "hint": "Admin only" if tenant and not is_admin else "Edit tenant preferences",
            },
        },
        {
            "title": "Users & Roles",
            "desc": "View tenant members and role access. Add/remove comes later.",
            "items": [
                {"label": "Members", "value": member_count if tenant else "—"},
                {"label": "Admins", "value": admin_count if tenant else "—"},
            ],
            "cta": {
                "label": "Manage users",
                "enabled": bool(tenant) and is_admin,
                "url": reverse("settings_app:users_list") if (tenant and is_admin) else None,
                "hint": "Admin only" if tenant and not is_admin else "View members and roles",
            },
        },
        {
            "title": "Audit Log",
            "desc": "Track tenant-scoped changes to settings and membership.",
            "items": [
                {"label": "Scope", "value": "Tenant-scoped"},
                {"label": "Visibility", "value": "Admins only"},
            ],
            "cta": {
                "label": "View audit log",
                "enabled": bool(tenant) and is_admin,
                "url": reverse("settings_app:audit_log") if (tenant and is_admin) else None,
                "hint": "Admin only" if tenant and not is_admin else "View recent activity",
            },
        },
        {
            "title": "Coming Later",
            "desc": "Planned upgrades (not enabled yet).",
            "items": [
                {"label": "Invites", "value": "Email invites / join links"},
                {"label": "Permissions", "value": "Per-module role expansion"},
                {"label": "Audit", "value": "Membership & settings change log"},
                {"label": "Branding", "value": "Logo + report headers"},
            ],
            "cta": {"label": "—", "enabled": False, "url": None, "hint": "Not enabled yet"},
        },
    ]

    ctx = {
        "tenant": tenant,
        "sections": sections,
        "user_display": request.user.get_username(),
        "membership": membership,
        "is_admin": is_admin,
        "member_count": member_count,
        "admin_count": admin_count,
        "your_role": your_role,
    }
    return render(request, "settings_app/index.html", ctx)


@login_required
@tenant_admin_required
def organization_edit(request):
    tenant = getattr(request, "tenant", None)

    if request.method == "POST":
        form = TenantSettingsForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization settings updated.")
            _audit(request, TenantAuditEvent.ACTION_ORG_UPDATED, message="Organization settings updated.")
            return redirect("settings_app:index")
        messages.error(request, "Please fix the errors below.")
    else:
        form = TenantSettingsForm(instance=tenant)

    return render(request, "settings_app/organization_form.html", {"tenant": tenant, "form": form})


@login_required
@tenant_admin_required
def users_list(request):
    tenant = getattr(request, "tenant", None)

    memberships = (
        TenantMembership.objects
        .filter(tenant=tenant)
        .select_related("user")
        .order_by("user__last_name", "user__first_name", "user__username")
    )

    member_count = memberships.count()
    admin_count = memberships.filter(role=TenantMembership.ROLE_ADMIN).count()

    rows = []
    for m in memberships:
        u = m.user
        rows.append(
            {
                "user": u,
                "name": u.get_full_name() or u.get_username(),
                "email": getattr(u, "email", ""),
                "role": m.get_role_display(),
                "is_admin": m.role == TenantMembership.ROLE_ADMIN,
                "joined": m.created_at,
                "membership_id": m.id,
                "membership_id": m.id,
            }
        )

    return render(
        request,
        "settings_app/users_list.html",
        {
            "tenant": tenant,
            "rows": rows,
            "member_count": member_count,
            "admin_count": admin_count,
        },
    )


@login_required
@tenant_admin_required
def user_remove_confirm(request, membership_id: int):
    """
    Admin-only: confirm and remove a tenant member safely.
    Guardrails:
      - tenant-scoped
      - cannot remove self
      - cannot remove last admin in tenant
    """
    tenant = getattr(request, "tenant", None)

    target = (
        TenantMembership.objects
        .select_related("user", "tenant")
        .filter(id=membership_id, tenant=tenant)
        .first()
    )
    if not target:
        messages.error(request, "Member not found for this tenant.")
        return redirect("settings_app:users_list")

    if target.user_id == request.user.id:
        messages.error(request, "You cannot remove yourself.")
        return redirect("settings_app:users_list")

    if target.role == TenantMembership.ROLE_ADMIN:
        admin_count = TenantMembership.objects.filter(
            tenant=tenant, role=TenantMembership.ROLE_ADMIN
        ).count()
        if admin_count <= 1:
            messages.error(request, "You cannot remove the last admin from the tenant.")
            return redirect("settings_app:users_list")

    if request.method == "POST":
        target_name = target.user.get_full_name() or target.user.get_username()
        target.delete()
        messages.success(request, f"Removed {target_name} from the tenant.")
        _audit(request, TenantAuditEvent.ACTION_MEMBER_REMOVED, message=f"Removed {target_name}", meta={"removed_user": target.user.get_username()})
        return redirect("settings_app:users_list")

    return render(
        request,
        "settings_app/user_remove_confirm.html",
        {
            "tenant": tenant,
            "target": target,
        },
    )


@login_required
@tenant_admin_required
def user_role_update(request, membership_id: int):
    """
    Admin-only: update a member role (admin/user), tenant-scoped.
    Guardrails:
      - POST only
      - cannot change self
      - cannot demote last admin
    """
    if request.method != "POST":
        return HttpResponseForbidden("POST required.")

    tenant = getattr(request, "tenant", None)

    target = (
        TenantMembership.objects
        .select_related("user", "tenant")
        .filter(id=membership_id, tenant=tenant)
        .first()
    )
    if not target:
        messages.error(request, "Member not found for this tenant.")
        return redirect("settings_app:users_list")

    if target.user_id == request.user.id:
        messages.error(request, "You cannot change your own role.")
        return redirect("settings_app:users_list")

    new_role = (request.POST.get("role") or "").strip()
    allowed = {TenantMembership.ROLE_ADMIN, TenantMembership.ROLE_USER}
    if new_role not in allowed:
        messages.error(request, "Invalid role selection.")
        return redirect("settings_app:users_list")

    if target.role == TenantMembership.ROLE_ADMIN and new_role == TenantMembership.ROLE_USER:
        admin_count = TenantMembership.objects.filter(
            tenant=tenant, role=TenantMembership.ROLE_ADMIN
        ).count()
        if admin_count <= 1:
            messages.error(request, "You cannot demote the last admin in the tenant.")
            return redirect("settings_app:users_list")

    if target.role == new_role:
        messages.info(request, "No changes made.")
        return redirect("settings_app:users_list")

    target.role = new_role
    target.save(update_fields=["role"])
    target_name = target.user.get_full_name() or target.user.get_username()
    messages.success(request, f"Updated role for {target_name}.")
    _audit(request, TenantAuditEvent.ACTION_ROLE_CHANGED, message=f"Role changed for {target_name}", meta={"user": target.user.get_username(), "new_role": new_role})
    return redirect("settings_app:users_list")

@login_required
@tenant_admin_required
def audit_log(request):
    tenant = getattr(request, "tenant", None)
    events = (
        TenantAuditEvent.objects
        .filter(tenant=tenant)
        .select_related("actor")
        .all()[:200]
    )
    return render(request, "settings_app/audit_log.html", {"tenant": tenant, "events": events})
