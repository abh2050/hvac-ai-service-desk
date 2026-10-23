"""Postgres access for work orders, steps, dispatch decisions, and the audit log."""

from __future__ import annotations

import json
from pathlib import Path

import psycopg
import yaml

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=True)


def migrate(conn) -> None:
    conn.execute(SCHEMA.read_text())


def seed_config(conn, root: Path) -> None:
    """Load the configuration seed (sites, assets, technicians). It is configuration, not data."""
    sites = yaml.safe_load((root / "config/sites.yaml").read_text())
    techs = yaml.safe_load((root / "config/technicians.yaml").read_text())
    for s in sites["sites"]:
        a = s["access"]
        conn.execute("""INSERT INTO sites VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (site_id) DO NOTHING""",
                     (s["id"], s["name"], s["town"], s["lat"], s["lon"], s["criticality"], s["sla_response_hours"],
                      a["badge_required"], a["escort_required"], a["allowed_hours"]))
    for x in sites["assets"]:
        conn.execute("""INSERT INTO assets VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (asset_id) DO NOTHING""",
                     (x["id"], x["site"], x["equipment_class"], x["description"], x["lbnl_unit"], x["brick_model"]))
    for t in techs["technicians"]:
        conn.execute("""INSERT INTO technicians (technician_id, name, home, lat, lon, certs, shift, days, site_access,
                        escort_cleared) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                     (t["id"], t["name"], t["home"], t["lat"], t["lon"], t["certs"], t["shift"], t["days"],
                      t["site_access"], t["escort_cleared"]))


def save_work_order(conn, wo) -> None:
    with conn.transaction():
        conn.execute("""INSERT INTO work_orders (work_order_id, asset_id, case_id, created_at, status, status_reason,
                        priority, sla_due_at, fault_type, route, required_certs, est_minutes, compatibility_uncertain,
                        detection_disagreement, approval_deadline_at, approved_by, approved_at, edited)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (work_order_id) DO UPDATE SET status = EXCLUDED.status,
                        status_reason = EXCLUDED.status_reason, approved_by = EXCLUDED.approved_by,
                        approved_at = EXCLUDED.approved_at, edited = EXCLUDED.edited""",
                     (wo.work_order_id, wo.asset_id, wo.case_id, wo.created_at, wo.status, wo.status_reason,
                      wo.priority, wo.sla_due_at, wo.fault_type, wo.route, wo.required_certs, wo.est_minutes,
                      wo.compatibility_uncertain, wo.detection_disagreement, wo.approval_deadline_at,
                      wo.approved_by, wo.approved_at, wo.edited))
        conn.execute("DELETE FROM work_order_steps WHERE work_order_id = %s", (wo.work_order_id,))
        for s in wo.steps:
            conn.execute("""INSERT INTO work_order_steps (work_order_id, kind, seq, quote, manual_id, page, verified)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                         (wo.work_order_id, s["kind"], s["seq"], s["quote"], s["manual_id"], s["page"], s["verified"]))


def save_assignment(conn, a, method: str, decided_at, scenario_id: str | None = None) -> None:
    conn.execute("""INSERT INTO dispatch_decisions (work_order_id, decided_at, method, technician_id, runner_up_id,
                    travel_minutes, lateness_minutes, reason, scenario_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                 (a.work_order_id, decided_at, method, a.technician_id, a.runner_up_id, a.travel_min,
                  a.lateness_min, a.reason, scenario_id))
    new_status = {"assigned": "assigned", "escalated_unassigned": "escalated_unassigned",
                  "reschedule_requested": "reschedule_requested"}[a.status]
    conn.execute("UPDATE work_orders SET status = %s, status_reason = %s WHERE work_order_id = %s",
                 (new_status, a.reason, a.work_order_id))


def audit(conn, actor: str, role: str, action: str, resource: str, allowed: bool, detail: dict) -> None:
    if not allowed:
        from handlers.metrics import emit
        emit("DeniedCalls", 1, "Count", Action=action)
    conn.execute("""INSERT INTO audit_log (actor, actor_role, action, resource, allowed, detail)
                    VALUES (%s,%s,%s,%s,%s,%s)""", (actor, role, action, resource, allowed, json.dumps(detail)))
