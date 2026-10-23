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
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("sites", "assets", "technicians")}
    return {"PhysicalResourceId": "uptime-db-init", "Data": {k: str(v) for k, v in counts.items()}}
