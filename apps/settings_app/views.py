from __future__ import annotations

from functools import wraps
import secrets
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from apps.tenants.models import TenantMembership, TenantAuditEvent, TenantInvite
from .forms import TenantSettingsForm, TenantUserCreateForm, TenantInviteCreateForm


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
    tenant = getattr(request, "tenant", None)
    if not tenant or target.tenant_id != tenant.id:
        return (False, "Member not in this tenant.")
    if target.user_id == request.user.id:
        return (False, "You cannot remove yourself.")
    if target.role == TenantMembership.ROLE_ADMIN and _tenant_admin_count(tenant) <= 1:
        return (False, "You cannot remove the last admin for this tenant.")
    return (True, "")


def _can_demote_admin(tenant, target: TenantMembership, desired_role: str) -> tuple[bool, str]:
    if desired_role not in (TenantMembership.ROLE_ADMIN, TenantMembership.ROLE_USER):
        return (False, "Invalid role selection.")
    if target.role == TenantMembership.ROLE_ADMIN and desired_role == TenantMembership.ROLE_USER:
        if _tenant_admin_count(tenant) <= 1:
            return (False, "You cannot demote the last admin for this tenant.")
    return (True, "")


def _model_field_names(model) -> set[str]:
    return {f.name for f in model._meta.get_fields() if hasattr(f, "name")}


def _pick_field(model, candidates: list[str]) -> str | None:
    names = _model_field_names(model)
    for c in candidates:
        if c in names:
            return c
    return None


def _invite_is_expired(invite) -> bool:
    f = _pick_field(TenantInvite, ["expires_at", "expires_on", "expires"])
    if not f:
        return False
    val = getattr(invite, f, None)
    if not val:
        return False
    now = timezone.now()
    try:
        return val <= now
    except Exception:
        return False


def _invite_is_revoked(invite) -> bool:
    f_dt = _pick_field(TenantInvite, ["revoked_at"])
    if f_dt and getattr(invite, f_dt, None):
        return True
    f_bool = _pick_field(TenantInvite, ["revoked", "is_revoked"])
    if f_bool and bool(getattr(invite, f_bool, False)):
        return True
    return False


def _invite_is_used(invite) -> bool:
    f_dt = _pick_field(TenantInvite, ["accepted_at", "used_at"])
    if f_dt and getattr(invite, f_dt, None):
        return True
    f_bool = _pick_field(TenantInvite, ["used", "is_used", "accepted"])
    if f_bool and bool(getattr(invite, f_bool, False)):
        return True
    return False


@login_required
def index(request):
    tenant = getattr(request, "tenant", None)
    membership = _get_membership(request)
    is_admin = _is_tenant_admin(membership)

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
            "desc": "Manage tenant members and access roles.",
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
            "title": "Invite Links",
            "desc": "Create and manage invite links for this tenant.",
            "items": [
                {"label": "Scope", "value": "Tenant-scoped"},
                {"label": "Visibility", "value": "Admins manage / Users accept"},
            ],
            "cta": {
                "label": "Manage invites",
                "enabled": bool(tenant) and is_admin,
                "url": reverse("settings_app:invites_list") if (tenant and is_admin) else None,
                "hint": "Admin only" if tenant and not is_admin else "Create/revoke invite links",
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
    ]

    return render(
        request,
        "settings_app/index.html",
        {
            "tenant": tenant,
            "sections": sections,
            "user_display": request.user.get_username(),
            "membership": membership,
            "is_admin": is_admin,
            "member_count": member_count,
            "admin_count": admin_count,
            "your_role": your_role,
        },
    )


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

    for r in rows:
        if r["user"].id == request.user.id:
            r["can_change_role"] = False
            r["change_role_reason"] = "You cannot change your own role"

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
def user_add(request):
    """
    Admin-only: create a Django user and attach tenant membership with selected role.
    """
    tenant = getattr(request, "tenant", None)
    User = get_user_model()

    if request.method == "POST":
        form = TenantUserCreateForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"].strip()
            email = (form.cleaned_data.get("email", "") or "").strip()
            role = (form.cleaned_data.get("role") or "user").strip().lower()

            if role not in (TenantMembership.ROLE_ADMIN, TenantMembership.ROLE_USER):
                role = TenantMembership.ROLE_USER

            # Prevent accidental dup usernames
            if User.objects.filter(username=username).exists():
                form.add_error("username", "That username already exists.")
            else:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=form.cleaned_data["password1"],
                        first_name=form.cleaned_data.get("first_name", "") or "",
                        last_name=form.cleaned_data.get("last_name", "") or "",
                    )

                    TenantMembership.objects.create(
                        tenant=tenant,
                        user=user,
                        role=role,
                    )

                messages.success(request, f"User '{username}' created and added to tenant.")
                _audit(
                    request,
                    "member_added",
                    message="Added member via admin create",
                    meta={"username": username, "role": role},
                )
                return redirect("settings_app:users_list")
        messages.error(request, "Please fix the errors below.")
    else:
        form = TenantUserCreateForm()

    return render(request, "settings_app/user_add_form.html", {"tenant": tenant, "form": form})


@login_required
@tenant_admin_required
def user_remove_confirm(request, membership_id: int):
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

    if request.method == "POST":
        target_name = target.user.get_full_name() or target.user.get_username()
        removed_username = target.user.get_username()
        target.delete()
        messages.success(request, f"Removed {target_name} from the tenant.")
        _audit(request, "member_removed", message=f"Removed {target_name}", meta={"removed_user": removed_username})
        return redirect("settings_app:users_list")

    return render(request, "settings_app/user_remove_confirm.html", {"tenant": tenant, "target": target})


@login_required
@tenant_admin_required
def user_role_update(request, membership_id: int):
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

    action = (request.GET.get("action") or "").strip()
    start = (request.GET.get("start") or "").strip()  # YYYY-MM-DD
    end = (request.GET.get("end") or "").strip()      # YYYY-MM-DD

    qs = TenantAuditEvent.objects.filter(tenant=tenant).select_related("actor").order_by("-created_at")

    if action:
        qs = qs.filter(action=action)

    # Basic date filtering
    def parse_ymd(s: str):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    start_d = parse_ymd(start) if start else None
    end_d = parse_ymd(end) if end else None

    if start_d:
        qs = qs.filter(created_at__date__gte=start_d)
    if end_d:
        qs = qs.filter(created_at__date__lte=end_d)

    events = list(qs[:200])

    # Build action dropdown options from recent history (tenant scoped)
    actions = (
        TenantAuditEvent.objects
        .filter(tenant=tenant)
        .values_list("action", flat=True)
        .distinct()
    )
    actions = sorted([a for a in actions if a])

    return render(
        request,
        "settings_app/audit_log.html",
        {
            "tenant": tenant,
            "events": events,
            "action": action,
            "start": start,
            "end": end,
            "actions": actions,
        },
    )


@login_required
@tenant_admin_required
def users_invite(request):
    """
    Admin-only: generate invite token (no email sending required).
    Uses TenantInvite model but is tolerant to varying field names.
    """
    tenant = getattr(request, "tenant", None)

    token_field = _pick_field(TenantInvite, ["token", "invite_token", "key", "code"])
    email_field = _pick_field(TenantInvite, ["email", "invite_email"])
    role_field = _pick_field(TenantInvite, ["role"])
    expires_field = _pick_field(TenantInvite, ["expires_at", "expires_on", "expires"])
    created_by_field = _pick_field(TenantInvite, ["created_by", "creator", "actor"])
    created_at_field = _pick_field(TenantInvite, ["created_at"])  # usually auto

    if not token_field:
        messages.error(request, "TenantInvite model has no token field. Add a token field (token/invite_token).")
        return redirect("settings_app:invites_list")

    if request.method == "POST":
        form = TenantInviteCreateForm(request.POST)
        if form.is_valid():
            token = secrets.token_urlsafe(32)
            role = (form.cleaned_data.get("role") or "user").strip().lower()
            email = (form.cleaned_data.get("email") or "").strip()
            days = int(form.cleaned_data.get("expires_in_days") or 7)
            expires_at = timezone.now() + timedelta(days=days)

            invite = TenantInvite()
            # Required: tenant
            if "tenant" in _model_field_names(TenantInvite):
                invite.tenant = tenant

            setattr(invite, token_field, token)

            if role_field:
                setattr(invite, role_field, role)

            if email_field and email:
                setattr(invite, email_field, email)

            if expires_field:
                setattr(invite, expires_field, expires_at)

            if created_by_field:
                setattr(invite, created_by_field, request.user)

            invite.save()

            _audit(
                request,
                "invite_created",
                message="Invite created",
                meta={"token": token, "role": role, "email": email, "expires_in_days": days},
            )
            messages.success(request, "Invite link created.")
            return redirect("settings_app:invites_list")
        messages.error(request, "Please fix the errors below.")
    else:
        form = TenantInviteCreateForm()

    return render(request, "settings_app/users_invite.html", {"tenant": tenant, "form": form})


@login_required
@tenant_admin_required
def invites_list(request):
    tenant = getattr(request, "tenant", None)

    qs = TenantInvite.objects.all()
    if "tenant" in _model_field_names(TenantInvite):
        qs = qs.filter(tenant=tenant)

    qs = qs.order_by("-id")[:200]
    invites = []
    token_field = _pick_field(TenantInvite, ["token", "invite_token", "key", "code"])
    role_field = _pick_field(TenantInvite, ["role"])
    email_field = _pick_field(TenantInvite, ["email", "invite_email"])
    expires_field = _pick_field(TenantInvite, ["expires_at", "expires_on", "expires"])

    for inv in qs:
        token = getattr(inv, token_field) if token_field else ""
        invites.append(
            {
                "id": inv.id,
                "token": token,
                "role": getattr(inv, role_field) if role_field else "",
                "email": getattr(inv, email_field) if email_field else "",
                "expires_at": getattr(inv, expires_field) if expires_field else None,
                "is_revoked": _invite_is_revoked(inv),
                "is_used": _invite_is_used(inv),
                "is_expired": _invite_is_expired(inv),
                "accept_url": reverse("settings_app:invite_accept", args=[token]) if token else None,
            }
        )

    return render(request, "settings_app/invites_list.html", {"tenant": tenant, "invites": invites})


@login_required
@tenant_admin_required
def invite_revoke(request, invite_id: int):
    tenant = getattr(request, "tenant", None)

    qs = TenantInvite.objects.filter(id=invite_id)
    if "tenant" in _model_field_names(TenantInvite):
        qs = qs.filter(tenant=tenant)

    inv = qs.first()
    if not inv:
        messages.error(request, "Invite not found for this tenant.")
        return redirect("settings_app:invites_list")

    if _invite_is_used(inv):
        messages.error(request, "This invite has already been used and cannot be revoked.")
        return redirect("settings_app:invites_list")

    revoked_at_field = _pick_field(TenantInvite, ["revoked_at"])
    revoked_bool_field = _pick_field(TenantInvite, ["revoked", "is_revoked"])

    if request.method == "POST":
        if revoked_at_field:
            setattr(inv, revoked_at_field, timezone.now())
        elif revoked_bool_field:
            setattr(inv, revoked_bool_field, True)
        inv.save()

        _audit(request, "invite_revoked", message="Invite revoked", meta={"invite_id": inv.id})
        messages.success(request, "Invite revoked.")
        return redirect("settings_app:invites_list")

    # Small inline confirm
    token_field = _pick_field(TenantInvite, ["token", "invite_token", "key", "code"])
    token = getattr(inv, token_field) if token_field else ""
    return render(request, "settings_app/invite_revoke_confirm.html", {"tenant": tenant, "invite": inv, "token": token})


@login_required
def invite_accept(request, token: str):
    """
    Login required: accept a tenant invite for the current tenant.
    Protections:
      - tenant-scoped
      - cannot accept revoked/expired/used
      - cannot accept into wrong tenant (based on request.tenant filter)
      - cannot create duplicate membership
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        messages.error(request, "No active tenant selected.")
        return redirect("core:dashboard")

    token_field = _pick_field(TenantInvite, ["token", "invite_token", "key", "code"])
    if not token_field:
        messages.error(request, "Invites are not configured (missing token field).")
        return redirect("core:dashboard")

    qs = TenantInvite.objects.filter(**{token_field: token})
    if "tenant" in _model_field_names(TenantInvite):
        qs = qs.filter(tenant=tenant)

    inv = qs.first()
    if not inv:
        messages.error(request, "Invalid invite link for this tenant.")
        return redirect("core:dashboard")

    if _invite_is_revoked(inv):
        messages.error(request, "This invite link has been revoked.")
        return redirect("core:dashboard")

    if _invite_is_used(inv):
        messages.error(request, "This invite link has already been used.")
        return redirect("core:dashboard")

    if _invite_is_expired(inv):
        messages.error(request, "This invite link has expired.")
        return redirect("core:dashboard")

    # Already a member?
    if TenantMembership.objects.filter(tenant=tenant, user=request.user).exists():
        messages.info(request, "You are already a member of this tenant.")
        return redirect("settings_app:index")

    role_field = _pick_field(TenantInvite, ["role"])
    desired_role = (getattr(inv, role_field, "") or "user").strip().lower() if role_field else "user"
    if desired_role not in (TenantMembership.ROLE_ADMIN, TenantMembership.ROLE_USER):
        desired_role = TenantMembership.ROLE_USER

    if request.method == "POST":
        with transaction.atomic():
            TenantMembership.objects.create(
                tenant=tenant,
                user=request.user,
                role=desired_role,
            )

            # Mark used
            accepted_at_field = _pick_field(TenantInvite, ["accepted_at", "used_at"])
            used_bool_field = _pick_field(TenantInvite, ["used", "is_used", "accepted"])
            if accepted_at_field:
                setattr(inv, accepted_at_field, timezone.now())
            elif used_bool_field:
                setattr(inv, used_bool_field, True)
            inv.save()

        _audit(
            request,
            "invite_accepted",
            message="Invite accepted",
            meta={"username": request.user.get_username(), "role": desired_role},
        )
        messages.success(request, f"Joined tenant as {desired_role}.")
        return redirect("settings_app:index")

    return render(
        request,
        "settings_app/invite_accept.html",
        {
            "tenant": tenant,
            "token": token,
            "invite_role": desired_role,
        },
    )
