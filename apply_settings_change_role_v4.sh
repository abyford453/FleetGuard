#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/.backup_settings_role_${TS}"

echo "📌 FleetGuard Settings: Add Change Role (admin/user) with guardrails"
echo "📦 Backups: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

need_file() { [[ -f "$1" ]] || { echo "❌ Missing expected file: $1"; exit 1; }; }

need_file "apps/settings_app/urls.py"
need_file "apps/settings_app/views.py"
need_file "templates/settings_app/users_list.html"

cp -a "apps/settings_app/urls.py" "$BACKUP_DIR/urls.py"
cp -a "apps/settings_app/views.py" "$BACKUP_DIR/views.py"
cp -a "templates/settings_app/users_list.html" "$BACKUP_DIR/users_list.html"

echo "✍️ Patch 1/3: urls.py add role route (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/urls.py")
txt = p.read_text()

route_line = 'path("users/<int:membership_id>/role/", views.user_role_update, name="user_role_update"),'

if route_line in txt:
    print("✅ Role route already present.")
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
    print("✅ Added role route to urls.py")
PY

echo "✍️ Patch 2/3: views.py add user_role_update view (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/views.py")
txt = p.read_text()

if "def user_role_update" in txt:
    print("✅ user_role_update already exists.")
else:
    append = '''

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
    return redirect("settings_app:users_list")
'''
    p.write_text(txt + append)
    print("✅ Added user_role_update view.")
PY

echo "✍️ Patch 3/3: users_list.html enable Change Role form..."
python - <<'PY'
from pathlib import Path
p = Path("templates/settings_app/users_list.html")
txt = p.read_text()

old = '''              <button class="btn btn-secondary" type="button" disabled aria-disabled="true" title="Coming later">
                Change Role
              </button>'''

if old not in txt:
    if "settings_app:user_role_update" in txt:
        print("✅ Change Role already enabled in template.")
    else:
        raise SystemExit("❌ Expected disabled Change Role button not found. Refusing to patch wrong area.")
else:
    new = '''              {% if r.user.id == request.user.id %}
                <button class="btn btn-secondary" type="button" disabled aria-disabled="true" title="You cannot change your own role">
                  Change Role
                </button>
              {% else %}
                <form method="post" action="{% url 'settings_app:user_role_update' r.membership_id %}" style="display:inline-flex; gap:8px; align-items:center; justify-content:flex-end;">
                  {% csrf_token %}
                  <select name="role" class="input" style="min-width:140px;">
                    <option value="admin" {% if r.is_admin %}selected{% endif %}>Admin</option>
                    <option value="user" {% if not r.is_admin %}selected{% endif %}>User</option>
                  </select>
                  <button class="btn btn-secondary" type="submit">Save</button>
                </form>
              {% endif %}'''
    p.write_text(txt.replace(old, new, 1))
    print("✅ Enabled Change Role form.")
PY

echo "✅ DONE."
echo "🔎 Review: git diff | cat"
echo "✅ Validate: python manage.py check"
echo "▶️ Run: python manage.py runserver"
echo "🧯 Backups: $BACKUP_DIR"
