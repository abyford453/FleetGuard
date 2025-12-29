from django import forms
from apps.tenants.models import Tenant

class TenantSettingsForm(forms.ModelForm):
    """
    Tenant-scoped settings editor.
    Editable: name + preference fields.
    Locked: slug (routing) and created_at.
    """
    class Meta:
        model = Tenant
        fields = [
            "name",
            "default_inspection_due_days",
            "inspection_alert_days_before",
            "maintenance_alert_miles_before",
            "maintenance_alert_days_before",
            "units_distance",
            "units_fuel",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Organization name",
                "autocomplete": "organization",
            }),
            "default_inspection_due_days": forms.NumberInput(attrs={"min": 1, "step": 1}),
            "inspection_alert_days_before": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "maintenance_alert_miles_before": forms.NumberInput(attrs={"min": 0, "step": 50}),
            "maintenance_alert_days_before": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }

    def clean(self):
        cleaned = super().clean()
        due = cleaned.get("default_inspection_due_days")
        lead = cleaned.get("inspection_alert_days_before")
        if due is not None and lead is not None and lead > due:
            self.add_error(
                "inspection_alert_days_before",
                "Alert days cannot be greater than default inspection due days."
            )
        return cleaned

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

class TenantInviteCreateForm(forms.Form):
    email = forms.EmailField(required=False, help_text="Optional (useful if you later email invites).")
    role = forms.ChoiceField(choices=(("user","User"),("admin","Admin")), initial="user")
    expires_in_days = forms.IntegerField(min_value=1, max_value=365, initial=7, help_text="How many days until the invite expires.")

