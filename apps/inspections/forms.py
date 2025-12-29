from django import forms
from .models import Inspection, InspectionAlert

class InspectionForm(forms.ModelForm):
    class Meta:
        model = Inspection
        fields = [
            "vehicle",
            "inspection_date",
            "due_date",
            "inspection_type",
            "status",
            "assigned_to",
            "result",
            "odometer",
            "notes",
        ]
        widgets = {
            "inspection_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if tenant is not None:
            self.fields["vehicle"].queryset = (
                self.fields["vehicle"].queryset
                .filter(tenant=tenant)
                .order_by("unit_number", "year", "make", "model")
            )

        can_assign = bool(user and user.has_perm("inspections.assign_inspections"))
        can_complete = bool(user and user.has_perm("inspections.complete_inspections"))

        if not can_assign:
            self.fields["assigned_to"].required = False
            self.fields["assigned_to"].widget = forms.HiddenInput()
            self.fields["due_date"].widget = forms.HiddenInput()
            self.fields["status"].widget = forms.HiddenInput()

        if not can_complete:
            self.fields["result"].widget = forms.HiddenInput()
            self.fields["odometer"].widget = forms.HiddenInput()
            self.fields["notes"].widget = forms.HiddenInput()


class InspectionAlertForm(forms.ModelForm):
    class Meta:
        model = InspectionAlert
        fields = ["status", "severity", "assigned_to", "title", "details"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 5}),
        }
