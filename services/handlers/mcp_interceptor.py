"""AgentCore Gateway REQUEST interceptor: put the signed-in caller's identity into every tool call.

The gateway has already validated the Cognito ID token (CUSTOM_JWT authorizer) before this runs,
so the payload is read without re-checking the signature. Any `caller_context` the MCP client
sent is discarded and replaced; the model and the client cannot choose who they are.
"""

from __future__ import annotations

import base64
import json


def claims_from(headers: dict) -> dict:
    auth = next((v for k, v in (headers or {}).items() if k.lower() == "authorization"), "")
    token = auth.split(" ", 1)[1] if auth.lower().startswith("bearer ") else auth
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except ValueError:
        return {}


def caller_from(claims: dict) -> dict | None:
    if not claims.get("sub"):
        return None
    groups = claims.get("cognito:groups") or []
    groups = groups if isinstance(groups, list) else str(groups).strip("[]").replace(",", " ").split()
    role = "manager" if "manager" in groups else "technician" if "technician" in groups else None
    if role is None:
        return None
    return {"sub": claims["sub"], "role": role, "technician_id": claims.get("custom:technician_id")}


def handler(event, _ctx):
    req = event.get("mcp", {}).get("gatewayRequest", {})
    body = dict(req.get("body") or {})
    if body.get("method") == "tools/call":
        params = dict(body.get("params") or {})
        args = dict(params.get("arguments") or {})
        args.pop("caller_context", None)                       # never trust a client-supplied identity
        caller = caller_from(claims_from(req.get("headers") or {}))
        if caller is None:
            return {"interceptorOutputVersion": "1.0", "mcp": {"transformedGatewayResponse": {
                "statusCode": 200, "body": {"jsonrpc": "2.0", "id": body.get("id"),
                                            "error": {"code": -32001, "message": "caller is not in an Uptime Desk group"}}}}}
        args["caller_context"] = caller
        params["arguments"] = args
        body["params"] = params
    return {"interceptorOutputVersion": "1.0", "mcp": {"transformedGatewayRequest": {"body": body}}}
