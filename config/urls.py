from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
    path("tenants/", include("apps.tenants.urls")),

    path("admin/", admin.site.urls),

    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),

    path("vehicles/", include("apps.fleet.urls")),
    path("maintenance/", include("apps.maintenance.urls")),
    path("fuel/", include("apps.fuel.urls")),
    path("inspections/", include("apps.inspections.urls")),
    path("documents/", include("apps.documents.urls")),
    path("reports/", include("apps.reports.urls")),
    path("settings/", include("apps.settings_app.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
