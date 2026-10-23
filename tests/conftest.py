import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

DSN = os.environ.get("UPTIME_TEST_DSN", "postgresql://postgres:localtest@localhost:54329/uptime")


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def cfg():
    return {name: yaml.safe_load((ROOT / f"config/{name}.yaml").read_text())
            for name in ("policy", "dispatch", "sites", "technicians")}


@pytest.fixture(scope="session")
def recorded_cases():
    """Real diagnosis outputs recorded by the Gate 2 run (reports/gate-2-cases.jsonl)."""
    return [json.loads(line) for line in (ROOT / "reports/gate-2-cases.jsonl").read_text().splitlines()]


@pytest.fixture(scope="session")
def input_cases():
    """Real detection cases built from LBNL data (data/processed/gate2_cases.jsonl)."""
    path = ROOT / "data/processed/gate2_cases.jsonl"
    return {c["case_id"]: c for c in map(json.loads, path.read_text().splitlines())}


@pytest.fixture(scope="session")
def manual_pages():
    pages = {}
    for line in (ROOT / "data/processed/manual_pages.jsonl").read_text().splitlines():
        r = json.loads(line)
        pages[(r["manual_id"], r["page"])] = r["text"]
    return pages


@pytest.fixture()
def db():
    psycopg = pytest.importorskip("psycopg")
    from api import db as dbmod
    try:
        conn = dbmod.connect(DSN)
    except psycopg.OperationalError:
        pytest.skip("local Postgres container is not running")
    conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    dbmod.migrate(conn)
    dbmod.seed_config(conn, ROOT)
    yield conn
    conn.close()


@pytest.fixture()
def t0():
    return datetime(2026, 10, 26, 8, 0)   # a Monday; scenario clock, not a field time
