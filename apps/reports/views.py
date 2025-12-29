import csv
import io
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

from apps.fleet.models import Vehicle
from apps.inspections.models import Inspection, InspectionAlert
from apps.documents.models import VehicleDocument
from apps.fuel.models import FuelLog
from apps.fuel.alerts import vehicles_missing_fuel_logs, odometer_regressions


def _vehicle_label(v: Vehicle) -> str:
    label = v.unit_number or v.plate or "Vehicle"
    mm = f"{v.make} {v.model}".strip()
    if mm:
        return f"{label} ({mm})"
    return label


def _xlsx_response(wb: Workbook, filename: str) -> HttpResponse:
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)

    resp = HttpResponse(
        bio.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _autosize_columns(ws):
    for col in range(1, ws.max_column + 1):
        max_len = 0
        for row in range(1, ws.max_row + 1):
            v = ws.cell(row=row, column=col).value
            if v is None:
                continue
            v = str(v)
            if len(v) > max_len:
                max_len = len(v)
        ws.column_dimensions[get_column_letter(col)].width = min(max(12, max_len + 2), 55)


def _write_sheet(ws, title: str, headers: list[str], rows: list[list]):
    ws.title = title
    ws.append(headers)

    header_font = Font(bold=True)
    for i in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=i)
        c.font = header_font
        c.alignment = Alignment(vertical="center")

    for r in rows:
        ws.append(r)

    _autosize_columns(ws)


def _build_report_context(request):
    tenant = request.tenant
    today = timezone.localdate()

    # KPI Snapshot
    vehicle_count = Vehicle.objects.filter(tenant=tenant).count()

    open_alerts = (
        InspectionAlert.objects
        .filter(tenant=tenant)
        .exclude(status=InspectionAlert.STATUS_CLOSED)
        .count()
    )

    overdue_inspections = (
        Inspection.objects
        .filter(tenant=tenant, due_date__isnull=False, due_date__lt=today)
        .exclude(status=Inspection.STATUS_COMPLETED)
        .count()
    )

    due_soon_inspections = (
        Inspection.objects
        .filter(
            tenant=tenant,
            due_date__isnull=False,
            due_date__gte=today,
            due_date__lte=today + timedelta(days=7),
        )
        .exclude(status=Inspection.STATUS_COMPLETED)
        .count()
    )

    expired_docs = (
        VehicleDocument.objects
        .filter(tenant=tenant, expires_on__isnull=False, expires_on__lt=today)
        .count()
    )
    expiring_docs = (
        VehicleDocument.objects
        .filter(
            tenant=tenant,
            expires_on__isnull=False,
            expires_on__gte=today,
            expires_on__lte=today + timedelta(days=30),
        )
        .count()
    )

    fuel_stale_count = len(vehicles_missing_fuel_logs(tenant, days=30))
    fuel_odo_alert_count = len(odometer_regressions(tenant))

    spend_30 = (
        FuelLog.objects
        .filter(tenant=tenant, fuel_date__gte=today - timedelta(days=30))
        .aggregate(total=Coalesce(Sum("cost"), Decimal("0.00")))["total"]
    )

    # Chart data
    start_30 = today - timedelta(days=30)
    daily = (
        FuelLog.objects
        .filter(tenant=tenant, fuel_date__gte=start_30)
        .exclude(cost__isnull=True)
        .annotate(d=TruncDate("fuel_date"))
        .values("d")
        .annotate(total=Coalesce(Sum("cost"), Decimal("0.00")))
        .order_by("d")
    )
    daily_labels = [row["d"].strftime("%Y-%m-%d") for row in daily]
    daily_values = [float(row["total"]) for row in daily]

    start_12m = today - timedelta(days=365)
    monthly = (
        FuelLog.objects
        .filter(tenant=tenant, fuel_date__gte=start_12m)
        .exclude(cost__isnull=True)
        .annotate(m=TruncMonth("fuel_date"))
        .values("m")
        .annotate(total=Coalesce(Sum("cost"), Decimal("0.00")))
        .order_by("m")
    )
    monthly_labels = [row["m"].strftime("%Y-%m") for row in monthly]
    monthly_values = [float(row["total"]) for row in monthly]

    start_90 = today - timedelta(days=90)
    top = (
        FuelLog.objects
        .filter(tenant=tenant, fuel_date__gte=start_90)
        .exclude(cost__isnull=True)
        .values("vehicle_id")
        .annotate(total=Coalesce(Sum("cost"), Decimal("0.00")))
        .order_by("-total")[:8]
    )
    vehicle_map = {v.id: _vehicle_label(v) for v in Vehicle.objects.filter(tenant=tenant)}
    top_rows = [(vehicle_map.get(row["vehicle_id"], f"Vehicle #{row['vehicle_id']}"), float(row["total"])) for row in top]
    top_labels = [r[0] for r in top_rows]
    top_values = [r[1] for r in top_rows]

    return {
        "today": today,
        "vehicle_count": vehicle_count,
        "open_alerts": open_alerts,
        "overdue_inspections": overdue_inspections,
        "due_soon_inspections": due_soon_inspections,
        "expired_docs": expired_docs,
        "expiring_docs": expiring_docs,
        "fuel_stale_count": fuel_stale_count,
        "fuel_odo_alert_count": fuel_odo_alert_count,
        "spend_30": spend_30,
        "daily_labels_json": json.dumps(daily_labels),
        "daily_values_json": json.dumps(daily_values),
        "monthly_labels_json": json.dumps(monthly_labels),
        "monthly_values_json": json.dumps(monthly_values),
        "top_labels_json": json.dumps(top_labels),
        "top_values_json": json.dumps(top_values),
        "top_rows": top_rows,
    }


@login_required
def index(request):
    return render(request, "reports/index.html", _build_report_context(request))


@login_required
def print_report(request):
    # Print-friendly layout (use browser Print → Save as PDF)
    return render(request, "reports/print.html", _build_report_context(request))


# ---------------- CSV EXPORTS ----------------

@login_required
def export_fuel_csv(request):
    tenant = request.tenant
    today = timezone.localdate()
    start = today - timedelta(days=365)

    qs = (
        FuelLog.objects
        .filter(tenant=tenant, fuel_date__gte=start)
        .select_related("vehicle")
        .order_by("-fuel_date", "-created_at")
    )

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="fuel_logs_last_12_months.csv"'
    w = csv.writer(resp)
    w.writerow(["fuel_date", "vehicle", "odometer", "gallons", "cost", "vendor", "fuel_type", "notes"])

    for r in qs:
        w.writerow([r.fuel_date, _vehicle_label(r.vehicle), r.odometer or "", r.gallons, r.cost or "", r.vendor, r.fuel_type, r.notes])
    return resp


@login_required
def export_inspections_csv(request):
    tenant = request.tenant
    qs = Inspection.objects.filter(tenant=tenant).select_related("vehicle").order_by("-created_at")

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="inspections.csv"'
    w = csv.writer(resp)
    w.writerow(["created_at", "vehicle", "inspection_type", "status", "due_date", "performed_on", "notes"])

    for i in qs:
        v = getattr(i, "vehicle", None)
        w.writerow([
            getattr(i, "created_at", "").strftime("%Y-%m-%d %H:%M") if getattr(i, "created_at", None) else "",
            _vehicle_label(v) if v else "",
            getattr(i, "inspection_type", ""),
            getattr(i, "status", ""),
            getattr(i, "due_date", "") or "",
            getattr(i, "performed_on", "") or "",
            getattr(i, "notes", ""),
        ])
    return resp


@login_required
def export_documents_csv(request):
    tenant = request.tenant
    qs = VehicleDocument.objects.filter(tenant=tenant).select_related("vehicle").order_by("-uploaded_at")

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="documents.csv"'
    w = csv.writer(resp)
    w.writerow(["uploaded_at", "vehicle", "doc_type", "title", "expires_on", "file"])

    for d in qs:
        w.writerow([
            d.uploaded_at.strftime("%Y-%m-%d %H:%M") if getattr(d, "uploaded_at", None) else "",
            _vehicle_label(d.vehicle),
            d.doc_type,
            d.title,
            d.expires_on or "",
            getattr(d.file, "url", ""),
        ])
    return resp


@login_required
def export_inspection_alerts_csv(request):
    tenant = request.tenant
    qs = InspectionAlert.objects.filter(tenant=tenant).select_related("vehicle").order_by("-created_at")

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="inspection_alerts.csv"'
    w = csv.writer(resp)
    w.writerow(["created_at", "vehicle", "severity", "status", "title", "detail"])

    for a in qs:
        v = getattr(a, "vehicle", None)
        w.writerow([
            a.created_at.strftime("%Y-%m-%d %H:%M") if getattr(a, "created_at", None) else "",
            _vehicle_label(v) if v else "",
            getattr(a, "severity", ""),
            getattr(a, "status", ""),
            getattr(a, "title", ""),
            getattr(a, "detail", ""),
        ])
    return resp


# ---------------- EXCEL EXPORTS ----------------

@login_required
def export_fuel_xlsx(request):
    tenant = request.tenant
    today = timezone.localdate()
    start = today - timedelta(days=365)

    qs = (
        FuelLog.objects
        .filter(tenant=tenant, fuel_date__gte=start)
        .select_related("vehicle")
        .order_by("-fuel_date", "-created_at")
    )

    wb = Workbook()
    ws = wb.active
    rows = []
    for r in qs:
        rows.append([
            r.fuel_date,
            _vehicle_label(r.vehicle),
            r.odometer or "",
            float(r.gallons),
            float(r.cost) if r.cost is not None else "",
            r.vendor,
            r.fuel_type,
            r.notes,
        ])

    _write_sheet(ws, "Fuel Logs", ["Fuel Date", "Vehicle", "Odometer", "Gallons", "Cost", "Vendor", "Fuel Type", "Notes"], rows)
    return _xlsx_response(wb, "fuel_logs_last_12_months.xlsx")


@login_required
def export_inspections_xlsx(request):
    tenant = request.tenant
    qs = Inspection.objects.filter(tenant=tenant).select_related("vehicle").order_by("-created_at")

    wb = Workbook()
    ws = wb.active
    rows = []
    for i in qs:
        v = getattr(i, "vehicle", None)
        rows.append([
            getattr(i, "created_at", "") and i.created_at.strftime("%Y-%m-%d %H:%M") or "",
            _vehicle_label(v) if v else "",
            getattr(i, "inspection_type", ""),
            getattr(i, "status", ""),
            getattr(i, "due_date", "") or "",
            getattr(i, "performed_on", "") or "",
            getattr(i, "notes", ""),
        ])

    _write_sheet(ws, "Inspections", ["Created At", "Vehicle", "Type", "Status", "Due Date", "Performed On", "Notes"], rows)
    return _xlsx_response(wb, "inspections.xlsx")


@login_required
def export_documents_xlsx(request):
    tenant = request.tenant
    qs = VehicleDocument.objects.filter(tenant=tenant).select_related("vehicle").order_by("-uploaded_at")

    wb = Workbook()
    ws = wb.active
    rows = []
    for d in qs:
        rows.append([
            d.uploaded_at.strftime("%Y-%m-%d %H:%M") if getattr(d, "uploaded_at", None) else "",
            _vehicle_label(d.vehicle),
            d.doc_type,
            d.title,
            d.expires_on or "",
            getattr(d.file, "url", ""),
        ])

    _write_sheet(ws, "Documents", ["Uploaded At", "Vehicle", "Doc Type", "Title", "Expires On", "File"], rows)
    return _xlsx_response(wb, "documents.xlsx")


@login_required
def export_inspection_alerts_xlsx(request):
    tenant = request.tenant
    qs = InspectionAlert.objects.filter(tenant=tenant).select_related("vehicle").order_by("-created_at")

    wb = Workbook()
    ws = wb.active
    rows = []
    for a in qs:
        v = getattr(a, "vehicle", None)
        rows.append([
            a.created_at.strftime("%Y-%m-%d %H:%M") if getattr(a, "created_at", None) else "",
            _vehicle_label(v) if v else "",
            getattr(a, "severity", ""),
            getattr(a, "status", ""),
            getattr(a, "title", ""),
            getattr(a, "detail", ""),
        ])

    _write_sheet(ws, "Inspection Alerts", ["Created At", "Vehicle", "Severity", "Status", "Title", "Detail"], rows)
    return _xlsx_response(wb, "inspection_alerts.xlsx")
