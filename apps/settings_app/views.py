from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def index(request):
    tenant = getattr(request, "tenant", None)

    sections = [
        {
            "title": "Organization",
            "desc": "Basic tenant details and preferences.",
            "items": [
                {"label": "Tenant", "value": str(tenant) if tenant else "Not selected"},
                {"label": "Tenant ID", "value": getattr(tenant, "id", "—")},
            ],
            "cta": {"label": "Edit organization", "hint": "Coming next"},
        },
        {
            "title": "Users & Roles",
            "desc": "Manage users, roles, and access (coming soon).",
            "items": [
                {"label": "Status", "value": "Planned"},
                {"label": "Includes", "value": "Roles, permissions, invites"},
            ],
            "cta": {"label": "Manage users", "hint": "Coming soon"},
        },
        {
            "title": "Billing",
            "desc": "Plan, invoices, and payment method (later).",
            "items": [
                {"label": "Status", "value": "Planned"},
                {"label": "Provider", "value": "Stripe (later)"},
            ],
            "cta": {"label": "View billing", "hint": "Coming later"},
        },
        {
            "title": "Appearance",
            "desc": "Theme preferences and UI defaults.",
            "items": [
                {"label": "Theme", "value": "Global theme.css"},
                {"label": "Per-user prefs", "value": "Planned"},
            ],
            "cta": {"label": "Customize", "hint": "Coming later"},
        },
        {
            "title": "Security",
            "desc": "Password, sessions, and audit controls (later).",
            "items": [
                {"label": "Status", "value": "Planned"},
                {"label": "Audit log", "value": "Planned"},
            ],
            "cta": {"label": "Review security", "hint": "Coming later"},
        },
    ]

    ctx = {
        "tenant": tenant,
        "sections": sections,
        "user_display": request.user.get_username(),
    }
    return render(request, "settings_app/index.html", ctx)
