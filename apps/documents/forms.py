from django import forms
from .models import VehicleDocument

class VehicleDocumentForm(forms.ModelForm):
    class Meta:
        model = VehicleDocument
        fields = ["vehicle", "doc_type", "title", "file", "expires_on", "notes"]
        widgets = {
            "expires_on": forms.DateInput(attrs={"type": "date"}),
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
