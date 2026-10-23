"""CloudFormation custom resource: create the schema and load the configuration seed into Aurora.

Runs on every deploy (idempotent). Seeds the technician roster, sites, and assets from config/,
which is configuration, not data.
"""

from __future__ import annotations

from api import db as dbmod

from .common import APP_ROOT, db


def handler(event, _ctx):
    if event.get("RequestType") == "Delete":
        return {"PhysicalResourceId": event.get("PhysicalResourceId", "uptime-db-init")}
    with db() as conn:
        dbmod.migrate(conn)
        dbmod.seed_config(conn, APP_ROOT)
        # The recorded scenario week (Gate 3 plan, a scenario model result) gives the technician
        # assistant real jobs to answer about. Loaded once; every row is tagged with its scenario id.
        import json
        import sys
        sys.path.insert(0, str(APP_ROOT / "pipelines/evaluation"))
        from gate4_seed import seed_week
        seed_week(conn, json.loads((APP_ROOT / "reports/gate-3-detail.json").read_text()))
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("sites", "assets", "technicians")}
    return {"PhysicalResourceId": "uptime-db-init", "Data": {k: str(v) for k, v in counts.items()}}
