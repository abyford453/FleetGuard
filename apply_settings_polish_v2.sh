#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/.backup_settings_polish_${TS}"

echo "📌 FleetGuard Settings: UX polish + real Users/Roles stats (tenant-scoped)"
echo "📦 Backups: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

need_file() { [[ -f "$1" ]] || { echo "❌ Missing: $1"; exit 1; }; }

need_file "apps/settings_app/views.py"
need_file "templates/settings_app/index.html"
need_file "templates/settings_app/users_list.html"

echo "🧾 Backing up files..."
cp -a "apps/settings_app/views.py" "$BACKUP_DIR/views.py"
cp -a "templates/settings_app/index.html" "$BACKUP_DIR/index.html"
cp -a "templates/settings_app/users_list.html" "$BACKUP_DIR/users_list.html"

echo "✍️ Updating apps/settings_app/views.py ..."
cat > "apps/settings_app/views.py" <<'PY'
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse

from apps.tenants.models import TenantMembership
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
PY

echo "✍️ Updating templates/settings_app/index.html ..."
cat > "templates/settings_app/index.html" <<'HTML'
{% extends "base.html" %}
{% block page_title %}Settings{% endblock %}
{% block page_subtitle %}Tenant-scoped configuration and access{% endblock %}

{% block content %}
<div class="card" style="margin-bottom:14px;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">
    <div>
      <div style="font-weight:850; font-size:16px; margin-bottom:4px;">
        Signed in as <span style="opacity:.9;">{{ user_display }}</span>
      </div>
      <div style="opacity:.85; font-size:13px;">
        {% if tenant %}
          Active tenant: <span style="font-weight:800;">{{ tenant.name }}</span>
          <span style="opacity:.7;">•</span>
          Your role:
          {% if is_admin %}
            <span class="badge">Admin</span>
          {% else %}
            <span class="badge badge-muted">User</span>
          {% endif %}
        {% else %}
          No active tenant selected.
        {% endif %}
      </div>
    </div>

    {% if tenant %}
      <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
        <span class="badge badge-muted">Members: {{ member_count }}</span>
        <span class="badge badge-muted">Admins: {{ admin_count }}</span>
      </div>
    {% endif %}
  </div>
</div>

<div class="grid" style="display:grid; gap:16px; grid-template-columns: repeat(12, 1fr);">
  {% for s in sections %}
    <section class="card" style="grid-column: span 12;">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">
        <div style="min-width:240px;">
          <div style="font-weight:850; font-size:16px; margin-bottom:4px;">{{ s.title }}</div>
          <div style="opacity:.85; font-size:13px;">{{ s.desc }}</div>
        </div>

        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
          {% if s.cta.enabled and s.cta.url %}
            <a class="btn" href="{{ s.cta.url }}">{{ s.cta.label }}</a>
          {% elif s.cta.label and s.cta.label != "—" %}
            <button class="btn btn-secondary" type="button" disabled aria-disabled="true" title="{{ s.cta.hint|default:'Not enabled' }}">
              {{ s.cta.label }}
            </button>
          {% endif %}
          {% if s.cta.hint %}
            <span style="opacity:.7; font-size:12px;">{{ s.cta.hint }}</span>
          {% endif %}
        </div>
      </div>

      <div style="margin-top:12px; overflow:auto;">
        <table class="table" style="width:100%;">
          <tbody>
            {% for it in s.items %}
              <tr>
                <td style="width:220px; opacity:.8;">{{ it.label }}</td>
                <td style="font-weight:700;">{{ it.value }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </section>
  {% endfor %}
</div>
{% endblock %}
HTML

echo "✍️ Updating templates/settings_app/users_list.html ..."
cat > "templates/settings_app/users_list.html" <<'HTML'
{% extends "base.html" %}
{% block page_title %}Users & Roles{% endblock %}
{% block page_subtitle %}Tenant: {{ tenant.name }}{% endblock %}

{% block content %}
<div class="card">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">
    <div>
      <div style="font-weight:850; font-size:16px; margin-bottom:4px;">Tenant Members</div>
      <div style="opacity:.85; font-size:13px;">
        Tenant-scoped membership and roles. Adding/removing users will be enabled later.
      </div>
      <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap;">
        <span class="badge badge-muted">Members: {{ member_count }}</span>
        <span class="badge badge-muted">Admins: {{ admin_count }}</span>
      </div>
    </div>

    <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
      <a class="btn btn-secondary" href="{% url 'settings_app:index' %}">Back to Settings</a>
      <button class="btn" type="button" disabled aria-disabled="true" title="Coming later">
        Add User (Coming Later)
      </button>
    </div>
  </div>

  <div style="margin-top:14px; overflow:auto;">
    <table class="table" style="width:100%;">
      <thead>
        <tr>
          <th style="text-align:left;">Name</th>
          <th style="text-align:left;">Email</th>
          <th style="text-align:left;">Role</th>
          <th style="text-align:left;">Joined</th>
          <th style="text-align:right;">Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for r in rows %}
          <tr>
            <td style="font-weight:750;">{{ r.name }}</td>
            <td style="opacity:.9;">{{ r.email|default:"" }}</td>
            <td>
              {% if r.is_admin %}
                <span class="badge">Admin</span>
              {% else %}
                <span class="badge badge-muted">User</span>
              {% endif %}
              <span style="opacity:.75; font-size:12px; margin-left:8px;">({{ r.role }})</span>
            </td>
            <td style="opacity:.85;">{{ r.joined|date:"Y-m-d" }}</td>
            <td style="text-align:right;">
              <button class="btn btn-secondary" type="button" disabled aria-disabled="true" title="Coming later">
                Change Role
              </button>
              <button class="btn btn-danger" type="button" disabled aria-disabled="true" title="Coming later">
                Remove
              </button>
            </td>
          </tr>
        {% empty %}
          <tr>
            <td colspan="5" style="opacity:.8;">No members found for this tenant.</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div style="margin-top:12px; opacity:.75; font-size:12px;">
    Admin-only page. Next steps: invites, role changes, removals, and audit logging.
  </div>
</div>
{% endblock %}
HTML

echo "✅ Done."
echo "🔎 Review: git diff"
echo "▶️ Run: python manage.py runserver"
echo "🧯 Backups: $BACKUP_DIR"
