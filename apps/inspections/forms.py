from django import forms
from .models import Inspection

class InspectionForm(forms.ModelForm):
    class Meta:
        model = Inspection
        fields = [
            "vehicle",
            "inspection_date",
            "inspection_type",
            "result",
            "odometer",
            "notes",
        ]
        widgets = {
            "inspection_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["vehicle"].queryset = (
                self.fields["vehicle"].queryset
                .filter(tenant=tenant)
                .order_by("unit_number", "year", "make", "model")
            )
