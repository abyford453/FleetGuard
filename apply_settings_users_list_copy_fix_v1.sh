#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/.backup_settings_users_list_copy_${TS}"

echo "📌 FleetGuard Settings: Fix Users & Roles copy + enable Invite stub link"
echo "📦 Backups: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

[[ -f "templates/settings_app/users_list.html" ]] || { echo "❌ Missing templates/settings_app/users_list.html"; exit 1; }

cp -a "templates/settings_app/users_list.html" "$BACKUP_DIR/users_list.html"

python - <<'PY'
from pathlib import Path
p = Path("templates/settings_app/users_list.html")
txt = p.read_text()

# 1) Update outdated “enabled later” messaging
txt = txt.replace(
    "Tenant-scoped membership and roles. Adding/removing users will be enabled later.",
    "Tenant-scoped membership and roles. Role changes and removals are enabled. Invites are planned."
)

# 2) Update admin-only footer note if present
txt = txt.replace(
    "Admin-only page. Next steps: invites, role changes, removals, and audit logging.",
    "Admin-only page. Enabled: role changes and member removal. Planned: invites and audit logging."
)

# 3) If Invite button was deliberately disabled (onclick return false), enable it to open the stub page.
# Common patterns we inserted earlier:
txt = txt.replace(
    'href="{% url \'settings_app:users_invite\' %}" aria-disabled="true" onclick="return false;" title="Not enabled yet">Invite user</a>',
    'href="{% url \'settings_app:users_invite\' %}" title="Invites are planned (opens details)">Invite user</a>'
)

# 4) If the button label says something like "Add User (Coming Later)", keep it but tighten copy if desired.
txt = txt.replace("Add User (Coming Later)", "Add user (planned)")

p.write_text(txt)
print("✅ Updated users_list.html copy + enabled Invite stub link (if present).")
PY

echo "✅ DONE."
echo "🔎 Review: git diff | cat"
echo "▶️ Run: python manage.py runserver"
echo "🧯 Backups: $BACKUP_DIR"
