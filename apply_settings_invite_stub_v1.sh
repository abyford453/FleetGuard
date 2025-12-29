#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/.backup_settings_invite_${TS}"

echo "📌 FleetGuard Settings: Add Invite User stub page + remove 'coming soon' wording"
echo "📦 Backups: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

need_file() { [[ -f "$1" ]] || { echo "❌ Missing expected file: $1"; exit 1; }; }

need_file "apps/settings_app/urls.py"
need_file "apps/settings_app/views.py"
need_file "templates/settings_app/index.html"
need_file "templates/settings_app/users_list.html"

cp -a "apps/settings_app/urls.py" "$BACKUP_DIR/urls.py"
cp -a "apps/settings_app/views.py" "$BACKUP_DIR/views.py"
cp -a "templates/settings_app/index.html" "$BACKUP_DIR/index.html"
cp -a "templates/settings_app/users_list.html" "$BACKUP_DIR/users_list.html"
if [[ -f "templates/settings_app/users_invite.html" ]]; then
  cp -a "templates/settings_app/users_invite.html" "$BACKUP_DIR/users_invite.html"
fi

echo "✍️ Patch 1/5: urls.py add invite stub route (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/urls.py")
txt = p.read_text()

route_line = 'path("users/invite/", views.users_invite, name="users_invite"),'
if route_line in txt:
    print("✅ users_invite route already present.")
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
        raise SystemExit("❌ Could not find urlpatterns closing bracket. Refusing to patch.")
    p.write_text("\n".join(out) + "\n")
    print("✅ Added users_invite route.")
PY

echo "✍️ Patch 2/5: views.py add users_invite view (admin-only, stub)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/views.py")
txt = p.read_text()

if "def users_invite" in txt:
    print("✅ users_invite already exists.")
else:
    append = '''

@login_required
@tenant_admin_required
def users_invite(request):
    """
    Admin-only stub for future invites.
    No emails, no tokens yet. Just a clean placeholder page.
    """
    tenant = getattr(request, "tenant", None)
    return render(request, "settings_app/users_invite.html", {"tenant": tenant})
'''
    p.write_text(txt.rstrip() + "\n" + append + "\n")
    print("✅ Added users_invite view.")
PY

echo "✍️ Patch 3/5: Create users_invite.html (clean Coming Later page)..."
mkdir -p templates/settings_app
cat > templates/settings_app/users_invite.html <<'HTML'
{% extends "base.html" %}
{% block page_title %}Invite User{% endblock %}
{% block page_subtitle %}Tenant: {{ tenant.name }}{% endblock %}

{% block content %}
<div class="card" style="margin-bottom:14px;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">
    <div>
      <div style="font-weight:850; font-size:16px; margin-bottom:4px;">Invites are not enabled yet</div>
      <div style="opacity:.85; font-size:13px; max-width:780px;">
        This screen is reserved for the future invite flow (email invites or join links). For now, users must be created by an admin and
        linked to the tenant via membership.
      </div>
    </div>
    <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <a class="btn btn-secondary" href="{% url 'settings_app:users_list' %}">Back to Users</a>
    </div>
  </div>
</div>

<div class="card">
  <div style="font-weight:800; margin-bottom:8px;">Planned invite options</div>
  <ul style="margin:0; padding-left:18px; opacity:.9;">
    <li>Email invite with one-time token</li>
    <li>Time-limited join link</li>
    <li>Default role selection (User/Admin)</li>
    <li>Audit log entries for invite + acceptance</li>
  </ul>

  <div style="margin-top:12px; opacity:.7; font-size:12px;">
    Coming later: this will be enabled once we finalize the role/permission model.
  </div>
</div>
{% endblock %}
HTML

echo "✍️ Patch 4/5: Update Settings index wording (remove 'coming soon' text where present)..."
python - <<'PY'
from pathlib import Path
p = Path("templates/settings_app/index.html")
txt = p.read_text()

# Remove a common phrase if it exists in template
# (Your current template is mostly driven by views, but this catches any leftover text.)
txt2 = txt.replace("coming soon", "planned").replace("Coming soon", "Planned")
if txt2 != txt:
    p.write_text(txt2)
    print("✅ Updated index.html wording (coming soon -> planned).")
else:
    print("ℹ️ No 'coming soon' wording found in index.html (may already be handled in views).")
PY

echo "✍️ Patch 5/5: Add disabled Invite button to users_list.html (if not present)..."
python - <<'PY'
from pathlib import Path
p = Path("templates/settings_app/users_list.html")
txt = p.read_text()

if "settings_app:users_invite" in txt:
    print("✅ Invite link already referenced in users_list.html")
else:
    # Insert a small toolbar button near the top if we find a Back to Settings button.
    marker = '{% url \'settings_app:index\' %}'
    idx = txt.find(marker)
    if idx == -1:
        print("ℹ️ Could not find Settings link marker; skipping users_list toolbar insert.")
    else:
        # Very conservative: add disabled button right after the first Back link block line.
        # We'll just append a disabled button near the top by finding first occurrence of '</a>' after the marker.
        end = txt.find("</a>", idx)
        if end == -1:
            print("ℹ️ Could not find anchor close; skipping.")
        else:
            insert = '\n      <a class="btn btn-secondary" href="{% url \'settings_app:users_invite\' %}" aria-disabled="true" onclick="return false;" title="Not enabled yet">Invite user</a>'
            txt = txt[:end+4] + insert + txt[end+4:]
            p.write_text(txt)
            print("✅ Added disabled Invite user button to users_list.html")
PY

echo "✅ DONE."
echo "🔎 Review: git diff | cat"
echo "▶️ Run: python manage.py runserver"
echo "🧯 Backups: $BACKUP_DIR"
