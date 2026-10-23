"""HTTP API: identity comes only from token claims; roles and ownership are enforced and audited."""

import json
from datetime import timedelta

import pytest

from conftest import DSN


@pytest.fixture()
def api(db, monkeypatch, recorded_cases, input_cases, cfg, t0):
    import psycopg
    from fastapi.testclient import TestClient
    from api import app as appmod
    from api import db as dbmod
    from api import workorders as wo_mod
    from dispatch import model as dm
    monkeypatch.setenv("ALLOW_TEST_CALLER", "1")
    monkeypatch.setattr(appmod, "db", lambda: psycopg.connect(DSN, autocommit=True))
    sites, _, dispatch = dm.load_config(appmod.__file__ and __import__("pathlib").Path(__file__).resolve().parents[1])
    r = next(x for x in recorded_cases if not x["probe"] and x["ai"]["final"].get("route") == "technician"
             and x["ai"]["final"]["lockout_sourced"])
    case = input_cases[r["case_id"]]
    asset = {a["lbnl_unit"]: a for a in cfg["sites"]["assets"]}[case["unit"]]
    wo = wo_mod.draft(r["ai"]["final"], case, asset, sites[asset["site"]], dispatch, cfg["policy"], t0, False)
    dbmod.save_work_order(db, wo)
    db.execute("""INSERT INTO dispatch_decisions (work_order_id, decided_at, method, technician_id, start_at, reason)
                  VALUES (%s, %s, 'ortools', 'T01', %s, 'test')""", (wo.work_order_id, t0, t0 + timedelta(hours=1)))
    return TestClient(appmod.app), wo.work_order_id


def claims(sub, group, tech=None):
    c = {"sub": sub, "cognito:groups": f"[{group}]"}
    if tech:
        c["custom:technician_id"] = tech
    return {"x-test-claims": json.dumps(c)}


def test_no_identity_is_rejected(api):
    client, _ = api
    assert client.get("/me").status_code == 401


def test_identity_from_claims(api):
    client, _ = api
    assert client.get("/me", headers=claims("s1", "technician", "T01")).json() == {
        "sub": "s1", "role": "technician", "technician_id": "T01"}


def test_technician_cannot_approve_and_is_audited(api, db):
    client, wid = api
    r = client.post(f"/work-orders/{wid}/approve", json={}, headers=claims("s3", "technician", "T03"))
    assert r.status_code == 403
    assert db.execute("SELECT count(*) FROM audit_log WHERE actor='s3' AND NOT allowed").fetchone()[0] == 1


def test_technician_sees_only_own_work_orders(api):
    client, wid = api
    mine = client.get("/work-orders", headers=claims("s1", "technician", "T01")).json()
    other = client.get("/work-orders", headers=claims("s3", "technician", "T03")).json()
    manager = client.get("/work-orders", headers=claims("m", "manager")).json()
    assert [w["work_order_id"] for w in mine] == [wid]
    assert other == []
    assert wid in [w["work_order_id"] for w in manager]
    assert all(s["manual_id"] and s["page"] for s in mine[0]["steps"])
