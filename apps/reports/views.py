from django.contrib.auth.decorators import login_required
from django.shortcuts import render

def _module_ctx():
    planned_features = [
        "Summary dashboards (costs, due soon, trends)",
        "CSV export",
        "PDF export (later)",
    ]
    routes = [
        "/reports/ (index)",
    ]
    template_files = [
        "templates/reports/index.html",
    ]
    return {
        "planned_features": planned_features,
        "routes": routes,
        "template_files": template_files,
    }

@login_required
def index(request):
    return render(request, "reports/index.html", _module_ctx())
