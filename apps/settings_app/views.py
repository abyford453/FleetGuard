from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def _module_ctx():
    planned_features = [
        "Tenant profile settings",
        "User roles/permissions (admin vs user)",
        "Branding preferences (later)",
        "Billing hooks (later)",
    ]
    routes = [
        "/settings/ (index)",
    ]
    template_files = [
        "templates/settings_app/index.html",
    ]
    return {
        "planned_features": planned_features,
        "routes": routes,
        "template_files": template_files,
    }

@login_required
def index(request):
    return render(request, "settings_app/index.html", _module_ctx())
