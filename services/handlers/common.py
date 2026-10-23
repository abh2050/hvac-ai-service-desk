"""Shared runtime helpers for the Lambda handlers and the Fargate dispatch task."""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path

import boto3
import psycopg
import yaml

REGION = os.environ.get("AWS_REGION", "us-east-2")
APP_ROOT = Path(os.environ.get("APP_ROOT", Path(__file__).resolve().parents[2]))


@functools.lru_cache(maxsize=None)
def client(name: str):
    return boto3.client(name, region_name=REGION)


@functools.lru_cache(maxsize=None)
def param(name: str) -> str:
    return client("ssm").get_parameter(Name=name)["Parameter"]["Value"]


@functools.lru_cache(maxsize=None)
def config(name: str) -> dict:
    return yaml.safe_load((APP_ROOT / f"config/{name}.yaml").read_text())


@functools.lru_cache(maxsize=1)
def _db_secret() -> dict:
    arn = os.environ.get("DB_SECRET_ARN") or param("/uptime-desk/db/secret-arn")
    return json.loads(client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"])


def db() -> psycopg.Connection:
    s = _db_secret()
    # Aurora may be resuming from auto pause; allow time for the first connection.
    # Session time zone is the service territory's (Connecticut). Pipeline times are local wall-clock
    # times; without this, Postgres would read them as UTC and every SLA would be off by 4 or 5 hours.
    return psycopg.connect(host=s["host"], port=s.get("port", 5432), dbname=s.get("dbname", "uptime"),
                           user=s["username"], password=s["password"], autocommit=True, connect_timeout=60,
                           options="-c timezone=America/New_York")


def bucket() -> str:
    return os.environ.get("DATA_BUCKET") or param("/uptime-desk/data/bucket")


@functools.lru_cache(maxsize=1)
def catalog() -> dict:
    items = json.loads((APP_ROOT / "data/deploy/catalog.json").read_text())
    return {c["scenario_id"]: c for c in items}


def guardrail() -> dict | None:
    gid = os.environ.get("GUARDRAIL_ID")
    if not gid:
        return None
    return {"guardrailIdentifier": gid, "guardrailVersion": os.environ.get("GUARDRAIL_VERSION", "1"), "trace": "disabled"}
