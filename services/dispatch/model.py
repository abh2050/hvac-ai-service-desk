"""Dispatch domain: technicians, jobs, travel model, and hard-constraint eligibility.

Travel model (stated in the README): straight-line great-circle distance from the technician's
home base to the site, divided by the average speed in config/dispatch.yaml (40 km/h), with no
road-network correction. Each visit is planned as a trip from home base; return travel is not
counted. All dispatch results are scenario model results, not field savings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import yaml

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CERT_IMPLIES = {"EPA608_UNIVERSAL": {"EPA608_II"}}


@dataclass(frozen=True)
class Site:
    site_id: str
    lat: float
    lon: float
    criticality: str
    sla_response_hours: int
    escort_required: bool
    allowed_hours: str


@dataclass(frozen=True)
class Technician:
    technician_id: str
    name: str
    lat: float
    lon: float
    certs: frozenset
    shift: str
    days: tuple
    site_access: frozenset
    escort_cleared: bool


@dataclass
class Job:
    work_order_id: str
    site_id: str
    release_at: datetime
    sla_due_at: datetime
    required_certs: tuple
    est_minutes: int
    priority: str = "P2"
    meta: dict = field(default_factory=dict)


def load_config(root: Path) -> tuple[dict[str, Site], dict[str, Technician], dict]:
    sites_cfg = yaml.safe_load((root / "config/sites.yaml").read_text())
    techs_cfg = yaml.safe_load((root / "config/technicians.yaml").read_text())
    dispatch = yaml.safe_load((root / "config/dispatch.yaml").read_text())
    sites = {s["id"]: Site(s["id"], s["lat"], s["lon"], s["criticality"], s["sla_response_hours"],
                           s["access"]["escort_required"], s["access"]["allowed_hours"])
             for s in sites_cfg["sites"]}
    techs = {t["id"]: Technician(t["id"], t["name"], t["lat"], t["lon"], frozenset(t["certs"]), t["shift"],
                                 tuple(t["days"]), frozenset(t["site_access"]), t["escort_cleared"])
             for t in techs_cfg["technicians"]}
    return sites, techs, dispatch


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def travel_minutes(tech: Technician, site: Site, speed_kmh: float) -> float:
    return haversine_km(tech.lat, tech.lon, site.lat, site.lon) / speed_kmh * 60.0


def has_certs(tech: Technician, required) -> bool:
    held = set(tech.certs)
    for c in tech.certs:
        held |= CERT_IMPLIES.get(c, set())
    return set(required) <= held


def _window(day: datetime, hhmm_range: str) -> tuple[datetime, datetime]:
    a, b = hhmm_range.split("-")
    start = day.replace(hour=int(a[:2]), minute=int(a[3:]), second=0, microsecond=0)
    end_h, end_m = int(b[:2]), int(b[3:])
    end = day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=end_h, minutes=end_m)
    if end <= start:          # overnight shift, e.g. 23:00-07:30
        end += timedelta(days=1)
    return start, end


def shift_windows(tech: Technician, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Every shift window of `tech` that overlaps [start, end)."""
    out = []
    day = (start - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        if DAY_NAMES[day.weekday()] in tech.days:
            ws, we = _window(day, tech.shift)
            if we > start and ws < end:
                out.append((ws, we))
        day += timedelta(days=1)
    return out


def site_windows(site: Site, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    out = []
    day = (start - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        if site.allowed_hours == "00:00-24:00":
            out.append((day, day + timedelta(days=1)))
        else:
            out.append(_window(day, site.allowed_hours))
        day += timedelta(days=1)
    return out


def ineligibility(tech: Technician, job: Job, site: Site) -> str | None:
    """Hard constraints other than time: return the first reason a technician cannot take a job."""
    if not has_certs(tech, job.required_certs):
        return f"missing certifications {sorted(set(job.required_certs) - set(tech.certs))}"
    if site.site_id not in tech.site_access:
        return "no site access"
    if site.escort_required and not tech.escort_cleared:
        return "not escort cleared"
    return None
