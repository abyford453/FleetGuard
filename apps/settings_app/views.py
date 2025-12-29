from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import TenantSettingsForm


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
            "cta": {
                "label": "Edit organization",
                "enabled": bool(tenant),
                "url": reverse("settings_app:organization_edit") if tenant else None,
                "hint": "Edit active tenant details",
            },
        },
        {
            "title": "Users & Roles",
            "desc": "Manage users, roles, and access (coming soon).",
            "items": [
                {"label": "Status", "value": "Planned"},
                {"label": "Includes", "value": "Roles, permissions, invites"},
            ],
            "cta": {"label": "Manage users", "enabled": False, "url": None, "hint": "Coming soon"},
        },
        {
            "title": "Billing",
            "desc": "Plan, invoices, and payment method (later).",
            "items": [
                {"label": "Status", "value": "Planned"},
                {"label": "Provider", "value": "Stripe (later)"},
            ],
            "cta": {"label": "View billing", "enabled": False, "url": None, "hint": "Coming later"},
        },
        {
            "title": "Appearance",
            "desc": "Theme preferences and UI defaults.",
            "items": [
                {"label": "Theme", "value": "Global theme.css"},
                {"label": "Per-user prefs", "value": "Planned"},
            ],
            "cta": {"label": "Customize", "enabled": False, "url": None, "hint": "Coming later"},
        },
        {
            "title": "Security",
            "desc": "Password, sessions, and audit controls (later).",
            "items": [
                {"label": "Status", "value": "Planned"},
                {"label": "Audit log", "value": "Planned"},
            ],
            "cta": {"label": "Review security", "enabled": False, "url": None, "hint": "Coming later"},
        },
    ]

    ctx = {
        "tenant": tenant,
        "sections": sections,
        "user_display": request.user.get_username(),
    }
    return render(request, "settings_app/index.html", ctx)


@login_required
def organization_edit(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        messages.error(request, "No active tenant selected. Please select a tenant first.")
        return redirect("settings_app:index")

    if request.method == "POST":
        form = TenantSettingsForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Organization settings updated.")
            return redirect("settings_app:index")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = TenantSettingsForm(instance=tenant)

    return render(request, "settings_app/organization_form.html", {"tenant": tenant, "form": form})
