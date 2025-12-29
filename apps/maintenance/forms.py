from django import forms
from .models import MaintenanceRecord

class MaintenanceRecordForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = [
            "vehicle",
            "service_date",
            "odometer",
            "category",
            "description",
            "vendor",
            "cost",
            "next_due_date",
            "next_due_odometer",
            "notes",
        ]
        widgets = {
            "service_date": forms.DateInput(attrs={"type": "date"}),
            "next_due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["vehicle"].queryset = (
                self.fields["vehicle"].queryset.filter(tenant=tenant).order_by("unit_number", "year", "make", "model")
            )
