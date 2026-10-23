"""Capture one recorded run from the live API into JSON for the static Vercel demo.

The static demo has no sign-in and no backend. It reads these files instead of calling the API, so it keeps
working after the AWS stacks are torn down. Every file is a real API response from the deployed system,
captured as the manager (and, for the assistant, as technician T01). Nothing is generated or edited, except:
  - stage costs are kept only on the two model stages (the API repeated the last cost on later stages; fixed in
    services/api/app.py, not yet redeployed when this snapshot was taken);
  - presigned S3 links to manuals are replaced with the publisher's URL from data/SOURCES.md (S3 links expire);
  - the work order queue and dispatch board keep only the captured run's work order, the labeled scenario
    week, and one blocked order on the same asset, so the queue is not ten copies of one test.

Usage: uv run python -I pipelines/deploy/snapshot_demo.py RUN_ID
Demo passwords are read from SSM into memory and never written out.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "app/static-demo/snapshot"
API = "https://9pq6z01gmc.execute-api.us-east-2.amazonaws.com"
CLIENT_ID = "4f6q9gq02n86kc2iko59u117gf"
SESSION = boto3.Session(profile_name="awsnew", region_name="us-east-2")


# Cognito SRP (the app client allows only USER_SRP_AUTH, as the browser sign-in uses). RFC 5054 3072-bit group.
N = int("FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B"
        "302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE6"
        "49286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D"
        "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183"
        "995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3"
        "970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE1"
        "17577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF", 16)
G = 2


def _pad(v: int | str) -> str:
    h = v if isinstance(v, str) else format(v, "x")
    return "0" + h if len(h) % 2 else ("00" + h if h[0] in "89abcdefABCDEF" else h)


def _h(hex_str: str) -> str:
    return hashlib.sha256(bytes.fromhex(hex_str)).hexdigest()


def token(user_param: str, password_param: str) -> str:
    ssm = SESSION.client("ssm")
    get = lambda n: ssm.get_parameter(Name=n, WithDecryption=True)["Parameter"]["Value"]  # noqa: E731
    user, password = get(user_param), get(password_param)
    idp = SESSION.client("cognito-idp")
    pool = get("/uptime-desk/cognito/user-pool-id").split("_")[1]
    a = secrets.randbits(256) % N
    big_a = pow(G, a, N)
    ch = idp.initiate_auth(ClientId=CLIENT_ID, AuthFlow="USER_SRP_AUTH",
                           AuthParameters={"USERNAME": user, "SRP_A": format(big_a, "x")})["ChallengeParameters"]
    big_b, salt, uid = int(ch["SRP_B"], 16), ch["SALT"], ch["USER_ID_FOR_SRP"]
    k = int(_h(_pad(N) + _pad(G)), 16)
    u = int(_h(_pad(big_a) + _pad(big_b)), 16)
    x = int(_h(_pad(salt) + hashlib.sha256(f"{pool}{uid}:{password}".encode()).hexdigest()), 16)
    s = pow(big_b - k * pow(G, x, N), a + u * x, N)
    prk = hmac.new(bytes.fromhex(_pad(u)), bytes.fromhex(_pad(s)), hashlib.sha256).digest()
    key = hmac.new(prk, b"Caldera Derived Key\x01", hashlib.sha256).digest()[:16]
    now = datetime.now(timezone.utc)
    stamp = f"{now:%a %b} {now.day} {now:%H:%M:%S} UTC {now.year}"
    sig = hmac.new(key, pool.encode() + uid.encode() + base64.b64decode(ch["SECRET_BLOCK"]) + stamp.encode(),
                   hashlib.sha256).digest()
    out = idp.respond_to_auth_challenge(
        ClientId=CLIENT_ID, ChallengeName="PASSWORD_VERIFIER",
        ChallengeResponses={"USERNAME": uid, "PASSWORD_CLAIM_SECRET_BLOCK": ch["SECRET_BLOCK"],
                            "PASSWORD_CLAIM_SIGNATURE": base64.b64encode(sig).decode(), "TIMESTAMP": stamp})
    return out["AuthenticationResult"]["IdToken"]


def call(tok: str, path: str, body: dict | None = None):
    req = urllib.request.Request(f"{API}{path}", method="POST" if body else "GET",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"authorization": tok, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def manual_urls() -> dict[str, str]:
    """manual_id -> publisher URL, from the manuals table in data/SOURCES.md."""
    out = {}
    for line in (ROOT / "data/SOURCES.md").read_text().splitlines():
        m = re.match(r"\| ([a-z0-9-]+)\.pdf \| [^|]+ \| (https://\S+)", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def save(rel: str, data) -> None:
    p = OUT / f"{rel}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, default=str))


def main(run_id: str) -> None:
    mgr = token("/uptime-desk/demo/manager-username", "/uptime-desk/demo/manager-password")
    tech = token("/uptime-desk/demo/technician-username", "/uptime-desk/demo/technician-password")

    run = call(mgr, f"/runs/{run_id}")
    for s in run["stages"]:      # same rule as the API fix: cost belongs only to the two model stages
        if s["stage"] not in ("DiagnoseCase", "VerifyAndDraft"):
            s.pop("model_cost_usd", None)
    wo_id = (run.get("work_order") or {}).get("work_order_id")
    if not wo_id:
        sys.exit(f"{run_id} has no work order; pick a run that reached dispatch")
    diag = call(mgr, f"/runs/{run_id}/diagnosis")
    urls = manual_urls()
    for c in diag.get("citations", []):
        c["url"] = f"{urls[c['manual_id']]}#page={c['page']}" if c["manual_id"] in urls else ""

    wos = call(mgr, "/work-orders")
    board = call(mgr, "/dispatch")
    scenario_wos = {i["work_order_id"] for i in board["assigned"] + board["escalated"] if i.get("scenario_id")}
    asset_id = next(w["asset_id"] for w in wos if w["work_order_id"] == wo_id)
    same_asset_blocked = [w for w in wos if w["asset_id"] == asset_id and w["status"] == "blocked"][:1]
    keep = {wo_id} | scenario_wos | {w["work_order_id"] for w in same_asset_blocked}
    wos = [w for w in wos if w["work_order_id"] in keep]
    board = {**board, "assigned": [i for i in board["assigned"] if i["work_order_id"] in keep],
             "escalated": [i for i in board["escalated"] if i["work_order_id"] in keep]}

    assigned_to = next((i["technician_id"] for i in board["assigned"] if i["work_order_id"] == wo_id), None)
    questions = [
        ("technician T01", tech, "What jobs do I have this week?"),
        ("technician T01", tech, f"What are the safety steps for work order {wo_id}?"),
        ("manager", mgr, f"Summarize work order {wo_id}: the fault, who it is assigned to, and its sourced safety steps."),
    ]
    answers = []
    for who, tok, q in questions:
        a = call(tok, "/assistant", {"question": q})
        answers.append({"asked_as": who, **a})

    meta = {"captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run_id": run_id, "scenario_id": run["scenario_id"],
            "work_order_id": wo_id, "assigned_to": assigned_to, "api": API,
            "note": "Real responses from the deployed system, captured for the static demo."}
    save("meta", meta)
    save("scenarios", call(mgr, "/scenarios"))
    save(f"runs/{run_id}", run)
    save(f"runs/{run_id}/trend", call(mgr, f"/runs/{run_id}/trend"))
    save(f"runs/{run_id}/diagnosis", diag)
    save("work-orders", wos)
    save("dispatch", board)
    save("assistant", answers)
    print(json.dumps({**meta, "work_orders": len(wos), "assigned": len(board["assigned"]),
                      "assistant_cost_usd": round(sum(a["cost_usd"] for a in answers), 5)}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
