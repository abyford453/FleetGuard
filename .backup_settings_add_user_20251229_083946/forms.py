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
