#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/.backup_settings_remove_${TS}"

echo "📌 FleetGuard Settings: Add tenant-scoped member removal (admin-only, guarded)"
echo "📦 Backups: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

need_file() { [[ -f "$1" ]] || { echo "❌ Missing expected file: $1"; exit 1; }; }

need_file "apps/settings_app/urls.py"
need_file "apps/settings_app/views.py"
need_file "templates/settings_app/users_list.html"

cp -a "apps/settings_app/urls.py" "$BACKUP_DIR/urls.py"
cp -a "apps/settings_app/views.py" "$BACKUP_DIR/views.py"
cp -a "templates/settings_app/users_list.html" "$BACKUP_DIR/users_list.html"
if [[ -f "templates/settings_app/user_remove_confirm.html" ]]; then
  cp -a "templates/settings_app/user_remove_confirm.html" "$BACKUP_DIR/user_remove_confirm.html"
fi

echo "✍️ Patch 1/4: urls.py add remove route (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/urls.py")
txt = p.read_text()

route_line = 'path("users/<int:membership_id>/remove/", views.user_remove_confirm, name="user_remove"),'

if route_line in txt:
    print("✅ Remove route already present.")
else:
    if 'path("users/", views.users_list, name="users_list"),' not in txt:
        raise SystemExit("❌ Expected users_list route not found. Refusing to patch urls.py blindly.")

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
    print("✅ Added remove route to urls.py")
PY

echo "✍️ Patch 2/4: views.py ensure users_list rows include membership_id..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/views.py")
txt = p.read_text()

# We expect rows.append dict contains '"joined": m.created_at,' from your current version.
old = '"joined": m.created_at,'
if old not in txt:
    # If already patched, proceed
    if '"membership_id": m.id' in txt:
        print("✅ membership_id already present in users_list rows.")
    else:
        raise SystemExit("❌ Could not locate rows dict marker in users_list. Refusing to patch views.py.")
else:
    txt = txt.replace(old, '"joined": m.created_at,\n                "membership_id": m.id,', 1)
    p.write_text(txt)
    print("✅ Added membership_id to users_list rows.")
PY

echo "✍️ Patch 3/4: views.py add user_remove_confirm view (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/views.py")
txt = p.read_text()

if "def user_remove_confirm" in txt:
    print("✅ user_remove_confirm already exists.")
else:
    # Append at end to minimize risk
    append = '''

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
        return redirect("settings_app:users_list")

    return render(
        request,
        "settings_app/user_remove_confirm.html",
        {
            "tenant": tenant,
            "target": target,
        },
    )
'''
    p.write_text(txt + append)
    print("✅ Added user_remove_confirm view.")
PY

echo "✍️ Patch 4/4: templates - create confirm page + enable Remove link..."

mkdir -p "templates/settings_app"
cat > "templates/settings_app/user_remove_confirm.html" <<'HTML'
{% extends "base.html" %}
{% block page_title %}Remove Member{% endblock %}
{% block page_subtitle %}Tenant: {{ tenant.name }}{% endblock %}

{% block content %}
<div class="card">
  <div style="font-weight:850; font-size:16px; margin-bottom:6px;">Confirm removal</div>
  <div style="opacity:.85; font-size:13px;">
    You are about to remove this user from the tenant. This does not delete their account—only their access to this tenant.
  </div>

  <div style="margin-top:14px; border:1px solid rgba(255,255,255,.10); background: rgba(255,255,255,.03); border-radius:14px; padding:12px;">
    <div style="font-weight:800;">{{ target.user.get_full_name|default:target.user.get_username }}</div>
    <div style="opacity:.85; margin-top:4px;">Role: <span style="font-weight:800;">{{ target.get_role_display }}</span></div>
  </div>

  <form method="post" style="margin-top:14px; display:flex; gap:10px; flex-wrap:wrap;">
    {% csrf_token %}
    <a class="btn btn-secondary" href="{% url 'settings_app:users_list' %}">Cancel</a>
    <button class="btn btn-danger" type="submit">Remove from Tenant</button>
  </form>

  <div style="margin-top:10px; opacity:.7; font-size:12px;">
    Guardrails: cannot remove yourself, cannot remove the last admin.
  </div>
</div>
{% endblock %}
HTML

python - <<'PY'
from pathlib import Path
p = Path("templates/settings_app/users_list.html")
txt = p.read_text()

# We are replacing the specific disabled "Remove" button block that exists in your current template.
old_block = '''              <button class="btn btn-danger" type="button" disabled aria-disabled="true" title="Coming later">
                Remove
              </button>'''

if old_block not in txt:
    # If already upgraded, don't fail
    if "settings_app:user_remove" in txt:
        print("✅ users_list.html already has Remove link.")
    else:
        raise SystemExit("❌ Could not find the expected disabled Remove button block. Refusing to patch the wrong thing.")
else:
    new_block = '''              {% if r.user.id == request.user.id %}
                <button class="btn btn-danger" type="button" disabled aria-disabled="true" title="You cannot remove yourself">
                  Remove
                </button>
              {% else %}
                <a class="btn btn-danger" href="{% url 'settings_app:user_remove' r.membership_id %}">Remove</a>
              {% endif %}'''
    txt = txt.replace(old_block, new_block, 1)
    p.write_text(txt)
    print("✅ Enabled Remove link with safe membership_id.")
PY

echo "✅ DONE. Review and test:"
echo "   git diff"
echo "   python manage.py check"
echo "   python manage.py runserver"
echo
echo "🧪 Test URLs:"
echo "   /settings/users/"
echo "   click Remove → confirm page → POST removes membership"
echo
echo "🧯 Backups: $BACKUP_DIR"
