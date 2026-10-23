"""AgentCore Gateway interceptor and target: identity comes only from the validated token."""

import base64
import json
from types import SimpleNamespace

from handlers import mcp_interceptor


def token(claims: dict) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"Bearer {enc({'alg': 'RS256'})}.{enc(claims)}.sig"


def call(args, claims):
    event = {"mcp": {"gatewayRequest": {"headers": {"Authorization": token(claims)},
                                        "body": {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                                                 "params": {"name": "t___get_work_order", "arguments": args}}}}}
    return mcp_interceptor.handler(event, None)


def test_identity_injected_from_token():
    out = call({"work_order_id": "WO-1"}, {"sub": "s1", "cognito:groups": ["technician"], "custom:technician_id": "T01"})
    args = out["mcp"]["transformedGatewayRequest"]["body"]["params"]["arguments"]
    assert args == {"work_order_id": "WO-1", "caller_context": {"sub": "s1", "role": "technician", "technician_id": "T01"}}


def test_client_supplied_identity_is_replaced():
    spoof = {"sub": "attacker", "role": "manager", "technician_id": None}
    out = call({"work_order_id": "WO-1", "caller_context": spoof},
               {"sub": "s1", "cognito:groups": ["technician"], "custom:technician_id": "T01"})
    cc = out["mcp"]["transformedGatewayRequest"]["body"]["params"]["arguments"]["caller_context"]
    assert cc["role"] == "technician" and cc["sub"] == "s1"


def test_user_without_group_is_refused_at_the_gateway():
    out = call({"work_order_id": "WO-1"}, {"sub": "s9"})
    assert "error" in out["mcp"]["transformedGatewayResponse"]["body"]


def test_tools_list_passes_through():
    event = {"mcp": {"gatewayRequest": {"headers": {}, "body": {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}}}}
    assert mcp_interceptor.handler(event, None)["mcp"]["transformedGatewayRequest"]["body"]["method"] == "tools/list"


def test_target_fails_closed_without_identity(monkeypatch):
    from handlers import mcp_target
    ctx = SimpleNamespace(client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": "t___list_my_jobs"}))
    assert "error" in mcp_target.handler({}, ctx)


def test_target_enforces_ownership(db, recorded_cases, input_cases, cfg, t0, monkeypatch):
    import psycopg
    from conftest import DSN
    from handlers import mcp_target
    from test_mcp_tools import _seed_one
    monkeypatch.setattr(mcp_target, "db", lambda: psycopg.connect(DSN, autocommit=True))
    wo = _seed_one(db, recorded_cases, input_cases, cfg, t0, tech="T01")
    ctx = SimpleNamespace(client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": "uptime___get_work_order"}))
    other = mcp_target.handler({"work_order_id": wo.work_order_id,
                                "caller_context": {"sub": "s3", "role": "technician", "technician_id": "T03"}}, ctx)
    owner = mcp_target.handler({"work_order_id": wo.work_order_id,
                                "caller_context": {"sub": "s1", "role": "technician", "technician_id": "T01"}}, ctx)
    assert other.get("denied") is True and owner.get("found") is True
