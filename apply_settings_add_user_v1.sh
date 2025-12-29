#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/.backup_settings_add_user_${TS}"

echo "📌 FleetGuard Settings: Add real Add User screen (admin creates user + membership)"
echo "📦 Backups: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

need_file() { [[ -f "$1" ]] || { echo "❌ Missing expected file: $1"; exit 1; }; }

need_file "apps/settings_app/urls.py"
need_file "apps/settings_app/views.py"
need_file "apps/settings_app/forms.py"
need_file "templates/settings_app/users_list.html"

cp -a "apps/settings_app/urls.py" "$BACKUP_DIR/urls.py"
cp -a "apps/settings_app/views.py" "$BACKUP_DIR/views.py"
cp -a "apps/settings_app/forms.py" "$BACKUP_DIR/forms.py"
cp -a "templates/settings_app/users_list.html" "$BACKUP_DIR/users_list.html"
if [[ -f "templates/settings_app/user_add_form.html" ]]; then
  cp -a "templates/settings_app/user_add_form.html" "$BACKUP_DIR/user_add_form.html"
fi

echo "✍️ Patch 1/5: urls.py add add-user route (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/urls.py")
txt = p.read_text()

route_line = 'path("users/add/", views.user_add, name="user_add"),'
if route_line in txt:
    print("✅ user_add route already present.")
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
    print("✅ Added user_add route.")
PY

echo "✍️ Patch 2/5: forms.py add TenantUserCreateForm (if missing)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/forms.py")
txt = p.read_text()

if "class TenantUserCreateForm" in txt:
    print("✅ TenantUserCreateForm already exists.")
else:
    insert = '''
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class TenantUserCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(choices=[("user","User"),("admin","Admin")], initial="user")
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("That username already exists.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            try:
                validate_password(p1)
            except Exception as e:
                self.add_error("password1", e)
        return cleaned
'''
    # Append at end for minimal risk
    p.write_text(txt.rstrip() + "\n" + insert + "\n")
    print("✅ Added TenantUserCreateForm.")
PY

echo "✍️ Patch 3/5: views.py add user_add view (admin-only)..."
python - <<'PY'
from pathlib import Path
p = Path("apps/settings_app/views.py")
txt = p.read_text()

if "def user_add(" in txt:
    print("✅ user_add view already exists.")
else:
    # Ensure imports
    if "from django.contrib.auth import get_user_model" not in txt:
        txt = txt.replace("from django.contrib.auth.decorators import login_required",
                          "from django.contrib.auth.decorators import login_required\nfrom django.contrib.auth import get_user_model",
                          1)
    if "from .forms import TenantSettingsForm" in txt and "TenantUserCreateForm" not in txt:
        txt = txt.replace("from .forms import TenantSettingsForm",
                          "from .forms import TenantSettingsForm, TenantUserCreateForm",
                          1)

    append = '''

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
            return redirect("settings_app:users_list")
        messages.error(request, "Please fix the errors below.")
    else:
        form = TenantUserCreateForm()

    return render(request, "settings_app/user_add_form.html", {"tenant": tenant, "form": form})
'''
    p.write_text(txt.rstrip() + "\n" + append + "\n")
    print("✅ Added user_add view.")
PY

echo "✍️ Patch 4/5: template user_add_form.html (new)..."
mkdir -p templates/settings_app
cat > templates/settings_app/user_add_form.html <<'HTML'
{% extends "base.html" %}
{% block page_title %}Add User{% endblock %}
{% block page_subtitle %}Tenant: {{ tenant.name }}{% endblock %}

{% block content %}
<div class="card" style="margin-bottom:14px;">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap;">
    <div>
      <div style="font-weight:850; font-size:16px; margin-bottom:4px;">Create a new user</div>
      <div style="opacity:.85; font-size:13px; max-width:780px;">
        This creates a Django user account and adds them to this tenant. Invites are planned later.
      </div>
    </div>
    <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
      <a class="btn btn-secondary" href="{% url 'settings_app:users_list' %}">Back to Users</a>
    </div>
  </div>
</div>

<div class="card">
  <form method="post">
    {% csrf_token %}
    <div style="display:grid; gap:12px; grid-template-columns: repeat(12, 1fr);">
      <div style="grid-column: span 6;">
        <label class="small strong">Username</label>
        {{ form.username }}
        {% if form.username.errors %}<div class="small" style="opacity:.8;">{{ form.username.errors }}</div>{% endif %}
      </div>
      <div style="grid-column: span 6;">
        <label class="small strong">Email</label>
        {{ form.email }}
        {% if form.email.errors %}<div class="small" style="opacity:.8;">{{ form.email.errors }}</div>{% endif %}
      </div>

      <div style="grid-column: span 6;">
        <label class="small strong">First name</label>
        {{ form.first_name }}
      </div>
      <div style="grid-column: span 6;">
        <label class="small strong">Last name</label>
        {{ form.last_name }}
      </div>

      <div style="grid-column: span 6;">
        <label class="small strong">Role</label>
        {{ form.role }}
      </div>
      <div style="grid-column: span 6;"></div>

      <div style="grid-column: span 6;">
        <label class="small strong">Password</label>
        {{ form.password1 }}
        {% if form.password1.errors %}<div class="small" style="opacity:.8;">{{ form.password1.errors }}</div>{% endif %}
      </div>
      <div style="grid-column: span 6;">
        <label class="small strong">Confirm password</label>
        {{ form.password2 }}
        {% if form.password2.errors %}<div class="small" style="opacity:.8;">{{ form.password2.errors }}</div>{% endif %}
      </div>
    </div>

    {% if form.non_field_errors %}<div class="small" style="opacity:.8; margin-top:10px;">{{ form.non_field_errors }}</div>{% endif %}

    <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:14px;">
      <button class="btn" type="submit">Create user</button>
    </div>
  </form>
</div>
{% endblock %}
HTML

echo "✍️ Patch 5/5: users_list.html add enabled Add User button (keep Invite)..."
python - <<'PY'
from pathlib import Path
p = Path("templates/settings_app/users_list.html")
txt = p.read_text()

# Replace "Add user (planned)" with real link button if present
txt = txt.replace(
    "Add user (planned)",
    "Add user"
)

# If there is an existing disabled Add User button, try to convert it.
# Common disabled pattern:
txt = txt.replace(
    'type="button" disabled aria-disabled="true"',
    'type="button" disabled aria-disabled="true"'
)

# Insert an Add User link if we can find the Invite user button link.
if "settings_app:users_invite" in txt and "settings_app:user_add" not in txt:
    # Insert Add user link right after Invite user link markup in top toolbar
    marker = 'href="{% url \'settings_app:users_invite\' %}"'
    idx = txt.find(marker)
    if idx != -1:
        end_a = txt.find("</a>", idx)
        if end_a != -1:
            insert = '\n      <a class="btn" href="{% url \'settings_app:user_add\' %}">Add user</a>'
            txt = txt[:end_a+4] + insert + txt[end_a+4:]
            p.write_text(txt)
            print("✅ Added Add user button to users_list.html")
        else:
            print("ℹ️ Could not find </a> after Invite link; no insert made.")
    else:
        print("ℹ️ Invite link marker not found; no insert made.")
else:
    p.write_text(txt)
    print("✅ users_list.html updated (no-op or already has add link).")
PY

echo "✅ DONE."
echo "🔎 Review: git diff | cat"
echo "✅ Validate: python manage.py check"
echo "▶️ Run: python manage.py runserver"
echo "🧯 Backups: $BACKUP_DIR"
