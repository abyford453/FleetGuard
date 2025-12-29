from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q

from apps.tenants.models import TenantMembership, TenantAuditEvent, TenantInvite
from .forms import TenantSettingsForm, TenantUserCreateForm


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


def _tenant_admin_count(tenant) -> int:
    return TenantMembership.objects.filter(tenant=tenant, role=TenantMembership.ROLE_ADMIN).count()

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



def _can_remove_membership(request, target: TenantMembership) -> tuple[bool, str]:
    """
    Returns (allowed, reason). Enforces tenant-scoped guardrails.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant or target.tenant_id != tenant.id:
        return (False, "Member not in this tenant.")
    if target.user_id == request.user.id:
        # allow self-removal only if another admin exists
        if target.role == TenantMembership.ROLE_ADMIN and _tenant_admin_count(tenant) <= 1:
            return (False, "You cannot remove yourself as the last admin.")
        return (False, "You cannot remove yourself.")
    if target.role == TenantMembership.ROLE_ADMIN and _tenant_admin_count(tenant) <= 1:
        return (False, "You cannot remove the last admin for this tenant.")
    return (True, "")

def _can_demote_admin(tenant, target: TenantMembership, desired_role: str) -> tuple[bool, str]:
    """
    Returns (allowed, reason) for role change, focused on last-admin protection.
    """
    if desired_role not in (TenantMembership.ROLE_ADMIN, TenantMembership.ROLE_USER):
        return (False, "Invalid role selection.")
    if target.role == TenantMembership.ROLE_ADMIN and desired_role == TenantMembership.ROLE_USER:
        if _tenant_admin_count(tenant) <= 1:
            return (False, "You cannot demote the last admin for this tenant.")
    return (True, "")
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
            "desc": "Manage tenant members and access roles. Add/remove and role changes are enabled.",
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
                {"label": "Invites", "value": "Join links + email invites"},
                {"label": "Permissions", "value": "Per-module role expansion"},
                {"label": "Audit", "value": "Export + retention controls"},
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
            _audit(request, "org_updated", message="Organization settings updated.")
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
    )

    q = (request.GET.get("q") or "").strip()
    role_filter = (request.GET.get("role") or "").strip().lower()  # admin/user/blank

    if role_filter in ("admin", "user"):
        memberships = memberships.filter(role=role_filter)

    if q:
        memberships = memberships.filter(
            Q(user__username__icontains=q)
            | Q(user__email__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )

    memberships = memberships.order_by("user__last_name", "user__first_name", "user__username")

    member_count = memberships.count()
    admin_count = memberships.filter(role=TenantMembership.ROLE_ADMIN).count()

    rows = []
    for m in memberships:
        u = m.user
        rows.append(
            {
                "user": u,
                "name": u.get_full_name() or u.get_username(),
                "email": getattr(u, "email", "") or "",
                "role": m.get_role_display(),
                "is_admin": m.role == TenantMembership.ROLE_ADMIN,
                "joined": m.created_at,
                "membership_id": m.id,
                "can_remove": True,
                "remove_reason": "",
                "can_change_role": True,
                "change_role_reason": "",
            }
        )

    # Compute action permissions for UI (tenant-scoped safety)
    for r in rows:
        # Change role: block self-role change
        if r["user"].id == request.user.id:
            r["can_change_role"] = False
            r["change_role_reason"] = "You cannot change your own role"
        else:
            r["can_change_role"] = True
            r["change_role_reason"] = ""

        # Remove: use guard helper (also blocks last-admin removal + self)
        target = TenantMembership.objects.filter(id=r["membership_id"], tenant=tenant).first()
        if not target:
            r["can_remove"] = False
            r["remove_reason"] = "Member not found"
        else:
            allowed, reason = _can_remove_membership(request, target)
            r["can_remove"] = allowed
            r["remove_reason"] = reason or ""

    return render(
        request,
        "settings_app/users_list.html",
        {
            "tenant": tenant,
            "rows": rows,
            "member_count": member_count,
            "admin_count": admin_count,
            "q": q,
            "role_filter": role_filter,
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
    allowed, reason = _can_remove_membership(request, target)
    if not allowed:
        messages.error(request, reason)
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
        _audit(request, "member_removed", message=f"Removed {target_name}", meta={"removed_user": target.user.get_username()})
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
    Admin-only: confirm and apply role changes.
    Guardrails:
      - tenant-scoped
      - cannot change own role
      - cannot demote last admin
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


    allowed, reason = _can_remove_membership(request, target)
    if not allowed:
        messages.error(request, reason)
        return redirect("settings_app:users_list")
    if target.user_id == request.user.id:
        messages.error(request, "You cannot change your own role.")
        return redirect("settings_app:users_list")

    if request.method == "POST":
        desired_role = (request.POST.get("role") or "").strip().lower()
        ok, reason = _can_demote_admin(tenant, target, desired_role)
        if not ok:
            messages.error(request, reason)
            return redirect("settings_app:users_list")

        if desired_role == target.role:
            messages.info(request, "No changes were made.")
            return redirect("settings_app:users_list")

        old = target.role
        target.role = desired_role
        target.save(update_fields=["role"])

        _audit(
            request,
            "role_changed",
            message="Role changed",
            meta={"user": target.user.get_username(), "from": old, "to": desired_role},
        )
        messages.success(request, "Role updated.")
        return redirect("settings_app:users_list")

    # GET confirm page
    return render(
        request,
        "settings_app/user_role_confirm.html",
        {
            "tenant": tenant,
            "target": target,
            "is_last_admin": (target.role == TenantMembership.ROLE_ADMIN and _tenant_admin_count(tenant) <= 1),
        },
    )


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


@login_required
@tenant_admin_required
def users_invite(request):
    """
    Admin-only stub for future invites.
    No emails, no tokens yet. Just a clean placeholder page.
    """
    tenant = getattr(request, "tenant", None)
    return render(request, "settings_app/users_invite.html", {"tenant": tenant})


@login_required
@tenant_admin_required
def user_add(request):
    tenant = getattr(request, "tenant", None)
    User = get_user_model()

    if request.method == "POST":
        form = TenantUserCreateForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data.get("email", "") or "",
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data.get("first_name", "") or "",
                last_name=form.cleaned_data.get("last_name", "") or "",
            )
            TenantMembership.objects.create(
                tenant=tenant,
                user=user,
                role=form.cleaned_data["role"],
            )
            messages.success(request, "User created and added to tenant.")
            _audit(request, "member_added", message="Member added", meta={"user": user.get_username(), "role": form.cleaned_data["role"]})
            return redirect("settings_app:users_list")
        messages.error(request, "Please fix the errors below.")
    else:
        form = TenantUserCreateForm()

    return render(request, "settings_app/user_add_form.html", {"tenant": tenant, "form": form})


@login_required
@tenant_admin_required
def invites_list(request):
    tenant = getattr(request, "tenant", None)

    # Defaults: 7-day expiry, single-use, role=user
    if request.method == "POST":
        role = request.POST.get("role") or TenantMembership.ROLE_USER
        days = int(request.POST.get("expires_days") or 7)
        max_uses = int(request.POST.get("max_uses") or 1)

        token = TenantInvite.new_token()
        expires_at = timezone.now() + timezone.timedelta(days=days) if days > 0 else None

        inv = TenantInvite.objects.create(
            tenant=tenant,
            created_by=request.user,
            token=token,
            role=role,
            expires_at=expires_at,
            max_uses=max_uses,
            is_active=True,
        )

        # Audit (if available)
        if "TenantAuditEvent" in globals():
            try:
                _audit(
                    request,
                    "invite_created",
                    message="Invite link created",
                    meta={"role": role, "max_uses": max_uses, "expires_days": days},
                )
            except Exception:
                pass

        messages.success(request, "Invite link created.")
        return redirect("settings_app:invites_list")

    invites = (
        TenantInvite.objects
        .filter(tenant=tenant)
        .select_related("created_by")
        .order_by("-created_at")[:200]
    )

    # Build absolute-ish link path for display (works on localhost and prod)
    # We'll render as relative URL so it survives domains.
    return render(request, "settings_app/invites_list.html", {"tenant": tenant, "invites": invites})


@login_required
def invite_accept(request, token):
    """
    Accept an invite link. Requires login.
    Creates membership in the invite's tenant if allowed.
    """
    inv = TenantInvite.objects.select_related("tenant").filter(token=token).first()
    if not inv:
        messages.error(request, "Invalid invite link.")
        return redirect("core:dashboard")

    # Ensure request.tenant is set to the invite tenant for this flow
    tenant = inv.tenant

    if not inv.can_use():
        messages.error(request, "This invite link is expired or no longer active.")
        return render(request, "settings_app/invite_accept.html", {"tenant": tenant, "invite": inv, "can_accept": False})

    existing = TenantMembership.objects.filter(tenant=tenant, user=request.user).first()
    if existing:
        messages.info(request, "You are already a member of this tenant.")
        return redirect("settings_app:index")

    if request.method == "POST":
        TenantMembership.objects.create(tenant=tenant, user=request.user, role=inv.role)
        inv.uses += 1
        if inv.uses >= inv.max_uses:
            inv.is_active = False
        inv.used_at = timezone.now()
        inv.save(update_fields=["uses", "is_active", "used_at"])

        # Audit (if available)
        if "TenantAuditEvent" in globals():
            try:
                _audit(
                    request,
                    "invite_accepted",
                    message="Invite link accepted",
                    meta={"role": inv.role, "user": request.user.get_username(), "tenant": tenant.slug},
                )
            except Exception:
                pass

        messages.success(request, f"You joined {tenant.name}.")
        # After joining, user will still need to select/switch tenant per your existing UI flow.
        return redirect("core:dashboard")

    return render(request, "settings_app/invite_accept.html", {"tenant": tenant, "invite": inv, "can_accept": True})

