#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/.backup_settings_${TS}"

echo "📌 FleetGuard Settings: Adding Users & Roles + Admin-only enforcement (tenant-scoped)"
echo "📦 Backups will be saved to: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

need_file() {
  if [[ ! -f "$1" ]]; then
    echo "❌ Missing expected file: $1"
    exit 1
  fi
}

need_file "apps/settings_app/urls.py"
need_file "apps/settings_app/views.py"
need_file "apps/tenants/models.py"
need_file "templates/settings_app/index.html"
need_file "templates/settings_app/organization_form.html"

echo "🧾 Backing up files..."
cp -a "apps/settings_app/urls.py" "$BACKUP_DIR/urls.py"
cp -a "apps/settings_app/views.py" "$BACKUP_DIR/views.py"
if [[ -f "templates/settings_app/users_list.html" ]]; then
  cp -a "templates/settings_app/users_list.html" "$BACKUP_DIR/users_list.html"
fi

echo "✍️ Updating apps/settings_app/urls.py ..."
cat > "apps/settings_app/urls.py" <<'PY'
from django.urls import path
from . import views

app_name = "settings_app"

urlpatterns = [
    path("", views.index, name="index"),
    path("organization/", views.organization_edit, name="organization_edit"),
    path("users/", views.users_list, name="users_list"),
]
PY

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

    sections = [
        {
            "title": "Organization",
            "desc": "Basic tenant details and preferences.",
            "items": [
                {"label": "Tenant", "value": str(tenant) if tenant else "Not selected"},
                {"label": "Tenant ID", "value": getattr(tenant, "id", "—")},
            ],
            "cta": {
                "label": "Edit organization",
                "enabled": bool(tenant) and is_admin,
                "url": reverse("settings_app:organization_edit") if (tenant and is_admin) else None,
                "hint": "Admin only" if tenant and not is_admin else "Edit active tenant details",
            },
        },
        {
            "title": "Users & Roles",
            "desc": "View tenant members and access roles.",
            "items": [
                {"label": "Scope", "value": "Tenant-scoped"},
                {"label": "Role system", "value": "Admin / User"},
            ],
            "cta": {
                "label": "Manage users",
                "enabled": bool(tenant) and is_admin,
                "url": reverse("settings_app:users_list") if (tenant and is_admin) else None,
                "hint": "Admin only" if tenant and not is_admin else "Manage tenant membership (add/remove later)",
            },
        },
        {
            "title": "Billing",
            "desc": "Plan, invoices, and payment method (later).",
            "items": [
                {"label": "Status", "value": "Planned"},
                {"label": "Provider", "value": "Stripe (later)"},
            ],
            "cta": {"label": "View billing", "enabled": False, "url": None, "hint": "Coming later"},
        },
        {
            "title": "Appearance",
            "desc": "Theme preferences and UI defaults.",
            "items": [
                {"label": "Theme", "value": "Global theme.css"},
                {"label": "Per-user prefs", "value": "Planned"},
            ],
            "cta": {"label": "Customize", "enabled": False, "url": None, "hint": "Coming later"},
        },
        {
            "title": "Security",
            "desc": "Password, sessions, and audit controls (later).",
            "items": [
                {"label": "Status", "value": "Planned"},
                {"label": "Audit log", "value": "Planned"},
            ],
            "cta": {"label": "Review security", "enabled": False, "url": None, "hint": "Coming later"},
        },
    ]

    ctx = {
        "tenant": tenant,
        "sections": sections,
        "user_display": request.user.get_username(),
        "membership": membership,
        "is_admin": is_admin,
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

    rows = []
    for m in memberships:
        u = m.user
        rows.append(
            {
                "user": u,
                "name": u.get_full_name() or u.get_username(),
                "email": getattr(u, "email", ""),
                "role": m.get_role_display() if hasattr(m, "get_role_display") else m.role,
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
        },
    )
PY

echo "✍️ Creating templates/settings_app/users_list.html ..."
mkdir -p "templates/settings_app"
cat > "templates/settings_app/users_list.html" <<'HTML'
{% extends "base.html" %}
{% block page_title %}Users & Roles{% endblock %}
{% block page_subtitle %}Tenant: {{ tenant.name }}{% endblock %}

{% block content %}
<div class="card">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">
    <div>
      <div style="font-weight:800; font-size:16px; margin-bottom:4px;">Tenant Members</div>
      <div style="opacity:.85; font-size:13px;">
        This list is tenant-scoped. Adding/removing users will be enabled in a later step.
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
    Admin-only page. Future steps will add invites, role changes, removals, and audit logging.
  </div>
</div>
{% endblock %}
HTML

echo "✅ Done writing files."
echo
echo "🔎 Review changes with:"
echo "   git diff"
echo
echo "▶️ Run server:"
echo "   python manage.py runserver"
echo
echo "🧪 Quick check:"
echo "   - Settings dashboard: /settings/"
echo "   - Admin-only users list: /settings/users/"
echo "   - Admin-only org edit: /settings/organization/"
echo
echo "🧯 Backups stored at: $BACKUP_DIR"
