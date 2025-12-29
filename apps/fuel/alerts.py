from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Dict, List, Tuple

from django.db.models import Max
from django.utils import timezone

from apps.fleet.models import Vehicle
from .models import FuelLog


@dataclass
class FuelAlert:
    kind: str
    vehicle_id: int
    vehicle_label: str
    detail: str


def _vehicle_label(v: Vehicle) -> str:
    label = v.unit_number or v.plate or "Vehicle"
    mm = f"{v.make} {v.model}".strip()
    if mm:
        return f"{label} ({mm})"
    return label


def vehicles_missing_fuel_logs(tenant, days: int = 30) -> List[FuelAlert]:
    """
    Vehicles that have no fuel logs in the last N days.
    """
    today = timezone.localdate()
    cutoff = today - timedelta(days=days)

    last_by_vehicle = (
        FuelLog.objects
        .filter(tenant=tenant)
        .values("vehicle_id")
        .annotate(last_date=Max("fuel_date"))
    )
    last_map: Dict[int, date] = {row["vehicle_id"]: row["last_date"] for row in last_by_vehicle if row["last_date"]}

    vehicles = list(Vehicle.objects.filter(tenant=tenant).order_by("unit_number", "year", "make", "model"))

    alerts: List[FuelAlert] = []
    for v in vehicles:
        last = last_map.get(v.id)
        if last is None:
            alerts.append(FuelAlert(
                kind="no_logs",
                vehicle_id=v.id,
                vehicle_label=_vehicle_label(v),
                detail="No fuel logs recorded yet.",
            ))
        elif last < cutoff:
            age = (today - last).days
            alerts.append(FuelAlert(
                kind="stale",
                vehicle_id=v.id,
                vehicle_label=_vehicle_label(v),
                detail=f"Last fuel log is {age} days old ({last}).",
            ))
    return alerts


def odometer_regressions(tenant) -> List[FuelAlert]:
    """
    Flags vehicles where a newer fuel log has a lower odometer than an older one.
    This catches fat-finger entries quickly. We only check vehicles with 2+ odometer logs.
    """
    alerts: List[FuelAlert] = []
    vehicles = Vehicle.objects.filter(tenant=tenant).order_by("unit_number", "year", "make", "model")

    for v in vehicles:
        logs = (
            FuelLog.objects
            .filter(tenant=tenant, vehicle=v, odometer__isnull=False)
            .order_by("fuel_date", "created_at")
            .values_list("fuel_date", "odometer")
        )
        prev_odo = None
        prev_date = None
        for d, odo in logs:
            if prev_odo is not None and odo is not None and odo < prev_odo:
                alerts.append(FuelAlert(
                    kind="odometer_regression",
                    vehicle_id=v.id,
                    vehicle_label=_vehicle_label(v),
                    detail=f"Odometer went down from {prev_odo} on {prev_date} to {odo} on {d}.",
                ))
                break
            prev_odo, prev_date = odo, d

    return alerts
