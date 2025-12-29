from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.index, name="index"),

    # Print-friendly executive report (current snapshot)
    path("print/", views.print_report, name="print_report"),

    # Custom Reports
    path("weekly/", views.weekly_report, name="weekly_report"),
    path("monthly/", views.monthly_report, name="monthly_report"),

    # CSV exports (raw)
    path("export/fuel.csv", views.export_fuel_csv, name="export_fuel_csv"),
    path("export/inspections.csv", views.export_inspections_csv, name="export_inspections_csv"),
    path("export/documents.csv", views.export_documents_csv, name="export_documents_csv"),
    path("export/inspection-alerts.csv", views.export_inspection_alerts_csv, name="export_inspection_alerts_csv"),

    # Excel exports (raw)
    path("export/fuel.xlsx", views.export_fuel_xlsx, name="export_fuel_xlsx"),
    path("export/inspections.xlsx", views.export_inspections_xlsx, name="export_inspections_xlsx"),
    path("export/documents.xlsx", views.export_documents_xlsx, name="export_documents_xlsx"),
    path("export/inspection-alerts.xlsx", views.export_inspection_alerts_xlsx, name="export_inspection_alerts_xlsx"),

    # Excel exports (custom reports)
    path("weekly/export.xlsx", views.export_weekly_xlsx, name="export_weekly_xlsx"),
    path("monthly/export.xlsx", views.export_monthly_xlsx, name="export_monthly_xlsx"),
]
