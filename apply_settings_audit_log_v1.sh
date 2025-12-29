#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/.backup_settings_audit_${TS}"

echo "📌 FleetGuard Settings: Add tenant-scoped Audit Log v1 (admin-only, read-only)"
echo "📦 Backups: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

need_file() { [[ -f "$1" ]] || { echo "❌ Missing expected file: $1"; exit 1; }; }

need_file "apps/tenants/models.py"
need_file "apps/settings_app/urls.py"
need_file "apps/settings_app/views.py"
need_file "templates/settings_app/index.html"

cp -a "apps/tenants/models.py" "$BACKUP_DIR/tenants_models.py"
cp -a "apps/settings_app/urls.py" "$BACKUP_DIR/settings_urls.py"
cp -a "apps/settings_app/views.py" "$BACKUP_DIR/settings_views.py"
cp -a "templates/settings_app/index.html" "$BACKUP_DIR/settings_index.html"
if [[ -f "templates/settings_app/audit_log.html" ]]; then
  cp -a "templates/settings_app/audit_log.html" "$BACKUP_DIR/audit_log.html"
fi

echo "✍️ Patch 1/6: Add TenantAuditEvent model (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/tenants/models.py")
txt = p.read_text()

if "class TenantAuditEvent(models.Model):" in txt:
    print("✅ TenantAuditEvent already exists.")
else:
    # Ensure imports include JSONField (Django 4.2 has models.JSONField)
    # We'll append the model at the end for minimal risk.
    append = '''

class TenantAuditEvent(models.Model):
    """
    Tenant-scoped audit events (read-only in UI).
    Used to record membership + settings changes.
    """
    ACTION_ORG_UPDATED = "org.updated"
    ACTION_MEMBER_REMOVED = "member.removed"
    ACTION_ROLE_CHANGED = "member.role_changed"

    ACTION_CHOICES = [
        (ACTION_ORG_UPDATED, "Organization Updated"),
        (ACTION_MEMBER_REMOVED, "Member Removed"),
        (ACTION_ROLE_CHANGED, "Role Changed"),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="tenant_audit_events")
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    message = models.CharField(max_length=255, blank=True, default="")
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        who = getattr(self.actor, "username", "system")
        return f"[{self.tenant.slug}] {self.action} by {who}"
'''
    p.write_text(txt.rstrip() + "\n" + append)
    print("✅ Appended TenantAuditEvent model to apps/tenants/models.py")
PY

echo "🧱 Patch 2/6: Create migrations (makemigrations tenants)..."
python manage.py makemigrations tenants

echo "🗃 Patch 3/6: Apply migration..."
python manage.py migrate

echo "✍️ Patch 4/6: Add audit route in settings_app/urls.py (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/urls.py")
txt = p.read_text()

route_line = 'path("audit/", views.audit_log, name="audit_log"),'
if route_line in txt:
    print("✅ audit_log route already present.")
else:
    lines = txt.splitlines()
    out = []
    inserted = False
    for line in lines:
        if line.strip() == "]" and not inserted:
            out.append(f"    {route_line}")
            inserted = True
        out.append(line)

    if not inserted:
        raise SystemExit("❌ Could not find urlpatterns closing bracket. Refusing to patch urls.py.")

    p.write_text("\n".join(out) + "\n")
    print("✅ Added audit_log route.")
PY

echo "✍️ Patch 5/6: Add audit helper + audit_log view + hook into actions..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/views.py")
txt = p.read_text()

# Ensure import exists
if "from apps.tenants.models import TenantMembership" in txt and "TenantAuditEvent" not in txt:
    txt = txt.replace(
        "from apps.tenants.models import TenantMembership",
        "from apps.tenants.models import TenantMembership, TenantAuditEvent",
        1
    )

# Add helper _audit if missing
if "def _audit(" not in txt:
    insert_point = "def _is_tenant_admin"
    idx = txt.find(insert_point)
    if idx == -1:
        raise SystemExit("❌ Could not find insertion point for audit helper. Refusing to patch.")
    helper = '''

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

'''
    # Insert helper right before _is_tenant_admin definition
    txt = txt[:idx] + helper + txt[idx:]

# Add audit_log view if missing
if "def audit_log(request):" not in txt:
    txt = txt.rstrip() + '''

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
'''

# Hook: organization_edit success
needle = 'messages.success(request, "Organization settings updated.")'
if needle in txt and "_audit(request, TenantAuditEvent.ACTION_ORG_UPDATED" not in txt:
    txt = txt.replace(
        needle,
        needle + '\n            _audit(request, TenantAuditEvent.ACTION_ORG_UPDATED, message="Organization settings updated.")',
        1
    )

# Hook: user_remove_confirm POST success
needle2 = 'messages.success(request, f"Removed {target_name} from the tenant.")'
if needle2 in txt and "ACTION_MEMBER_REMOVED" not in txt:
    txt = txt.replace(
        needle2,
        needle2 + '\n        _audit(request, TenantAuditEvent.ACTION_MEMBER_REMOVED, message=f"Removed {target_name}", meta={"removed_user": target.user.get_username()})',
        1
    )

# Hook: user_role_update success
needle3 = 'messages.success(request, f"Updated role for {target_name}.")'
if needle3 in txt and "ACTION_ROLE_CHANGED" not in txt:
    txt = txt.replace(
        needle3,
        needle3 + '\n    _audit(request, TenantAuditEvent.ACTION_ROLE_CHANGED, message=f"Role changed for {target_name}", meta={"user": target.user.get_username(), "new_role": new_role})',
        1
    )

p.write_text(txt + ("\n" if not txt.endswith("\n") else ""))
print("✅ Updated views.py with audit log + hooks.")
PY

echo "✍️ Patch 6/6: Create audit template + add card to Settings index..."
mkdir -p templates/settings_app

cat > templates/settings_app/audit_log.html <<'HTML'
{% extends "base.html" %}
{% block page_title %}Audit Log{% endblock %}
{% block page_subtitle %}Tenant-scoped activity (latest first){% endblock %}

{% block content %}
<div class="card" style="margin-bottom:14px;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">
    <div>
      <div style="font-weight:850; font-size:16px; margin-bottom:4px;">{{ tenant.name }}</div>
      <div style="opacity:.8; font-size:13px;">
        Showing the latest 200 events. This log is tenant-scoped and admin-only.
      </div>
    </div>
    <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <a class="btn btn-secondary" href="{% url 'settings_app:index' %}">Back to Settings</a>
    </div>
  </div>
</div>

<div class="card">
  <div style="overflow:auto;">
    <table class="table" style="width:100%;">
      <thead>
        <tr>
          <th style="min-width:180px;">Time</th>
          <th style="min-width:160px;">Actor</th>
          <th style="min-width:180px;">Action</th>
          <th>Message</th>
        </tr>
      </thead>
      <tbody>
        {% for e in events %}
          <tr>
            <td style="opacity:.85;">{{ e.created_at|date:"Y-m-d H:i" }}</td>
            <td style="font-weight:750;">{% if e.actor %}{{ e.actor.get_username }}{% else %}system{% endif %}</td>
            <td style="font-weight:750;">{{ e.get_action_display }}</td>
            <td style="opacity:.9;">{{ e.message }}</td>
          </tr>
        {% empty %}
          <tr>
            <td colspan="4" style="opacity:.8;">No audit events yet.</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
HTML

python - <<'PY'
from pathlib import Path
p = Path("templates/settings_app/index.html")
txt = p.read_text()

# Add Audit Log section into the sections list in views.py already? Index template renders sections loop.
# So we add the "Audit Log" card via views.py by adding a section.
# But your index is driven by sections in views.py, so we'll patch views.py instead of template if needed.
print("✅ audit_log.html created. (Index uses sections from views; we will add the Audit card in the next patch if not present.)")
PY

# Add Audit card in views.py sections if missing
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/views.py")
txt = p.read_text()

if '"title": "Audit Log"' in txt:
    print("✅ Audit Log section already present in Settings dashboard.")
else:
    # Insert an Audit Log section right after Users & Roles section by locating the Users & Roles title block.
    marker = '"title": "Users & Roles"'
    idx = txt.find(marker)
    if idx == -1:
        raise SystemExit("❌ Could not find Users & Roles section marker. Refusing to patch sections list.")

    # Find end of that section dict by searching forward for '},' that closes it, then insert after.
    # We'll do a conservative insert by locating the next occurrence of "\n        }," after the Users block.
    after = txt.find("\n        },", idx)
    if after == -1:
        raise SystemExit("❌ Could not locate end of Users & Roles section. Refusing to patch.")
    after += len("\n        },")

    insert = '''
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
        },'''
    txt = txt[:after] + insert + txt[after:]
    p.write_text(txt)
    print("✅ Added Audit Log card to Settings dashboard.")
PY

echo "✅ DONE."
echo "🔎 Review: git diff | cat"
echo "✅ Validate: python manage.py check"
echo "▶️ Run: python manage.py runserver"
echo "🧯 Backups: $BACKUP_DIR"
