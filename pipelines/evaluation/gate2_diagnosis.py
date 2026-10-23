"""Gate 2: diagnosis against a non-AI baseline, on recorded cases.

AI path:   Titan v2 vector retrieval (top 6, class-filtered) -> gpt-oss-120b diagnosis ->
           citation verifier (trigram match on the cited page + gpt-oss-20b entailment) -> policy.
Baseline:  rule hint as the cause -> BM25 keyword retrieval -> the top passage's best sentence
           as the citation -> the same verifier.
Probes:    20 cases whose passages come from an unrelated query; the right answer is abstention.

Usage: .venv/bin/python -I pipelines/evaluation/gate2_diagnosis.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
from citation_verifier.verify import Verifier, tokens  # noqa: E402
from diagnosis import policy  # noqa: E402
from diagnosis.diagnose import ABSTAIN, COMPONENT, diagnose, propose  # noqa: E402
from diagnosis.llm import LLM  # noqa: E402
from diagnosis.retrieval import BM25Index, Embedder, VectorIndex, load_chunks  # noqa: E402

UNRELATED_QUERY = "unit dimensions weight shipping rigging clearances corner weights"
CHECK_CLAIM = "This passage gives a step to inspect, check, adjust, clean, or service the {}."
SAFETY_CLAIM = "This passage states a safety, lockout, or disconnect step to follow before servicing the equipment."


def human(fault: str | None) -> str:
    return (fault or "").replace("_", " ")


def query_for(case: dict) -> str:
    rules = "; ".join(r["description"] for r in case["detection"]["rules_fired"])
    return f"{case['equipment_class']} troubleshooting: {rules}. Possible {human(case['detection']['rule_hint'])}."


def baseline(case: dict, pool: list[dict], verifier: Verifier) -> dict:
    hint = case["detection"]["rule_hint"]
    if not hint or not pool:
        return {"probable_cause": ABSTAIN, "abstained": True, "citation": None, "verify": None}
    words = set(tokens(COMPONENT.get(hint, human(hint))))
    best, best_score = None, 0
    for p in pool:
        for sent in re.split(r"(?<=[.!?])\s+|\n", p["text"]):
            score = len(words & set(tokens(sent)))
            if score > best_score and len(tokens(sent)) >= 6:
                best, best_score = (p, " ".join(sent.split()[:40])), score
    if not best:
        return {"probable_cause": ABSTAIN, "abstained": True, "citation": None, "verify": None}
    p, quote = best
    v = verifier.check(p["manual_id"], p["page"], quote, CHECK_CLAIM.format(COMPONENT.get(hint, human(hint))))
    return {"probable_cause": hint if v["pass"] else ABSTAIN, "proposed_cause": hint, "abstained": not v["pass"],
            "citation": {"manual_id": p["manual_id"], "page": p["page"], "quote": quote}, "verify": v,
            "actionable": v["pass"]}


def run_case(case, vindex, bm25, chunks_by_class, diag_llm, verifier):
    t0 = time.time()
    cls = case["equipment_class"]
    probe = case.get("probe") == "evidence_withheld"
    proposed = propose(case, diag_llm)
    q = UNRELATED_QUERY if probe else proposed["manual_query"]
    passages = vindex.search(q, cls, k=6)
    diag = diagnose(case, passages, diag_llm, proposed)
    verified = {
        "citations": [verifier.check(c["manual_id"], c["page"], c.get("quote", ""), c.get("claim", ""))
                      for c in diag["citations"]],
        "recommended_checks": [verifier.check(c["manual_id"], c["page"], c.get("quote", ""),
                                              CHECK_CLAIM.format(COMPONENT.get(diag["probable_cause"], "equipment")))
                               for c in diag["recommended_checks"]],
        "safety_steps": [verifier.check(c["manual_id"], c["page"], c.get("quote", ""), SAFETY_CLAIM)
                         for c in diag["safety_steps"]],
    }
    final = policy.apply(diag, verified)
    ai_seconds = time.time() - t0
    t1 = time.time()
    pool = bm25.search(UNRELATED_QUERY, cls, k=6) if probe else bm25.search(
        f"{cls} {COMPONENT.get(case['detection']['rule_hint'], '')} inspect check adjust", cls, k=6)
    base = baseline(case, pool, verifier)
    return {"case_id": case["case_id"], "probe": case.get("probe"), "family": case["family"],
            "source_type": case["source_type"], "label": case["label"], "rule_hint": case["detection"]["rule_hint"],
            "model_probability_mean": case["detection"]["model_probability_mean"],
            "retrieved": [(p["manual_id"], p["page"], round(p["score"], 3)) for p in passages],
            "ai": {"final": final, "parse_ok": diag["parse_ok"], "explanation": diag.get("explanation"),
                   "proposed": {k: proposed.get(k) for k in ("probable_cause", "confidence", "component", "manual_query")},
                   "raw_citations": diag["citations"], "raw_checks": diag["recommended_checks"],
                   "raw_safety": diag["safety_steps"], "verified": verified, "seconds": round(ai_seconds, 2)},
            "baseline": {**base, "seconds": round(time.time() - t1, 2)}}


def rate(xs):
    xs = list(xs)
    return round(sum(xs) / len(xs), 3) if xs else None


def pct(xs, q):
    return round(float(np.percentile(xs, q)), 2) if xs else None


def summarize(rows, ai_usage, ent_usage, cfg_policy):
    normal = [r for r in rows if not r["probe"]]
    probes = [r for r in rows if r["probe"]]
    out = {}
    for name, sel in {"lab": [r for r in normal if r["source_type"] == "lab"],
                      "field": [r for r in normal if r["source_type"] == "field"],
                      "all": normal}.items():
        if not sel:
            continue
        ai_ans = [r for r in sel if not r["ai"]["final"]["abstained"]]
        all_cites = [v for r in sel for v in r["ai"]["verified"]["citations"]]
        out[name] = {
            "cases": len(sel),
            "ai": {
                "fault_type_accuracy": rate(r["ai"]["final"]["probable_cause"] == r["label"]["fault_type"] for r in sel),
                "accuracy_when_answered": rate(r["ai"]["final"]["probable_cause"] == r["label"]["fault_type"] for r in ai_ans),
                "proposal_accuracy": rate(r["ai"]["proposed"]["probable_cause"] == r["label"]["fault_type"] for r in sel),
                "abstention_rate": rate(r["ai"]["final"]["abstained"] for r in sel),
                "citation_support_rate": rate(v["pass"] for v in all_cites),
                "citation_deterministic_pass_rate": rate(v["deterministic_pass"] for v in all_cites),
                "citations_checked": len(all_cites),
                "actionability_rate": rate(bool(r["ai"]["final"]["recommended_checks"]) for r in ai_ans),
                "compatibility_warning_rate": rate(r["ai"]["final"]["compatibility_uncertain"] for r in ai_ans),
                "lockout_sourced_rate": rate(r["ai"]["final"]["lockout_sourced"] for r in ai_ans),
                "parse_ok_rate": rate(r["ai"]["parse_ok"] for r in sel),
            },
            "baseline": {
                "fault_type_accuracy": rate(r["baseline"]["probable_cause"] == r["label"]["fault_type"] for r in sel),
                "rule_hint_accuracy": rate(r["rule_hint"] == r["label"]["fault_type"] for r in sel),
                "abstention_rate": rate(r["baseline"]["abstained"] for r in sel),
                "citation_support_rate": rate(r["baseline"]["verify"]["pass"] for r in sel if r["baseline"]["verify"]),
                "actionability_rate": rate(r["baseline"].get("actionable", False)
                                           for r in sel if not r["baseline"]["abstained"]),
            },
        }
    out["by_family"] = {}
    for key in sorted({(r["source_type"], r["family"]) for r in normal}):
        sel = [r for r in normal if (r["source_type"], r["family"]) == key]
        out["by_family"]["/".join(key)] = {
            "cases": len(sel),
            "ai_proposal_accuracy": rate(r["ai"]["proposed"]["probable_cause"] == r["label"]["fault_type"] for r in sel),
            "rule_hint_accuracy": rate(r["rule_hint"] == r["label"]["fault_type"] for r in sel),
            "ai_final_accuracy": rate(r["ai"]["final"]["probable_cause"] == r["label"]["fault_type"] for r in sel),
            "baseline_final_accuracy": rate(r["baseline"]["probable_cause"] == r["label"]["fault_type"] for r in sel),
            "ai_abstention_rate": rate(r["ai"]["final"]["abstained"] for r in sel),
        }
    out["evidence_withheld_probes"] = {
        "cases": len(probes),
        "ai_abstention_rate": rate(r["ai"]["final"]["abstained"] for r in probes),
        "ai_llm_self_abstention_rate": rate(r["ai"]["final"]["llm_proposed_cause"] == ABSTAIN for r in probes),
        "baseline_abstention_rate": rate(r["baseline"]["abstained"] for r in probes),
    }
    secs = [r["ai"]["seconds"] for r in rows]
    n = len(rows)
    out["cost_latency"] = {
        "ai_seconds_p50": pct(secs, 50), "ai_seconds_p95": pct(secs, 95),
        "baseline_seconds_p50": pct([r["baseline"]["seconds"] for r in rows], 50),
        "diagnosis_llm": {"calls": ai_usage.calls, "input_tokens": ai_usage.input_tokens,
                          "output_tokens": ai_usage.output_tokens, "cost_usd": round(ai_usage.cost_usd, 4),
                          "truncated_replies": ai_usage.truncated},
        "entailment_llm": {"calls": ent_usage.calls, "input_tokens": ent_usage.input_tokens,
                           "output_tokens": ent_usage.output_tokens, "cost_usd": round(ent_usage.cost_usd, 4),
                           "truncated_replies": ent_usage.truncated},
        "cost_per_diagnosis_usd": round((ai_usage.cost_usd + ent_usage.cost_usd) / n, 5) if n else None,
        "query_embedding_note": "Titan v2 query embeddings at $0.02 per 1M tokens are under $0.0001 per case",
    }
    out["policy_1_would_route_to_manual_review"] = rate(
        (r["model_probability_mean"] or 0) < cfg_policy["detection"]["min_confidence"] for r in normal)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--resummarize", action="store_true",
                    help="recompute metrics from reports/gate-2-cases.jsonl without new model calls")
    args = ap.parse_args()
    if args.resummarize:
        resummarize()
        return
    started = time.time()
    models = yaml.safe_load((ROOT / "config/models.yaml").read_text())
    pol = yaml.safe_load((ROOT / "config/policy.yaml").read_text())
    chunks = load_chunks(ROOT / "data/processed/manual_chunks.jsonl")
    vectors = np.load(ROOT / "data/processed/manual_vectors.npy")
    embedder = Embedder(profile="awsnew")
    vindex = VectorIndex(chunks, vectors, embedder)
    bm25 = BM25Index(chunks)
    diag_llm = LLM("openai.gpt-oss-120b-1:0", profile="awsnew", max_tokens=models["diagnosis"]["max_tokens"])
    ent_llm = LLM("openai.gpt-oss-20b-1:0", profile="awsnew", max_tokens=models["entailment"]["max_tokens"])
    verifier = Verifier.from_jsonl(ROOT / "data/processed/manual_pages.jsonl", ent_llm,
                                   pol["diagnosis"]["deterministic_match_min_token_overlap"])
    cases = [json.loads(line) for line in (ROOT / "data/processed/gate2_cases.jsonl").read_text().splitlines()]
    if args.limit:
        cases = cases[:args.limit]
    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(lambda c: run_case(c, vindex, bm25, None, diag_llm, verifier), cases))

    summary = summarize(rows, diag_llm.usage, ent_llm.usage, pol)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    report = {"gate": 2, "name": "diagnosis", "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "git_commit": commit, "runtime_seconds": round(time.time() - started, 1), "limit": args.limit or None,
              "models": {"diagnosis": "openai.gpt-oss-120b-1:0", "entailment": "openai.gpt-oss-20b-1:0",
                         "embeddings": "amazon.titan-embed-text-v2:0 (local index; Bedrock KB pending deploy)"},
              "guardrails": "not attached (Bedrock Guardrail resource not yet deployed)",
              "categories": {"ground_truth": "LBNL fault labels", "measured": "every metric in results"},
              "results": summary}
    name = "gate-2" if not args.limit else "gate-2-smoke"
    (ROOT / f"reports/{name}.json").write_text(json.dumps(report, indent=1))
    with open(ROOT / f"reports/{name}-cases.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    print(json.dumps(summary, indent=1))


def resummarize():
    from types import SimpleNamespace
    report = json.loads((ROOT / "reports/gate-2.json").read_text())
    rows = [json.loads(line) for line in (ROOT / "reports/gate-2-cases.jsonl").read_text().splitlines()]
    pol = yaml.safe_load((ROOT / "config/policy.yaml").read_text())
    cl = report["results"]["cost_latency"]
    u = lambda d: SimpleNamespace(calls=d["calls"], input_tokens=d["input_tokens"], output_tokens=d["output_tokens"],
                                  cost_usd=d["cost_usd"], truncated=d["truncated_replies"])
    report["results"] = summarize(rows, u(cl["diagnosis_llm"]), u(cl["entailment_llm"]), pol)
    report["resummarized_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (ROOT / "reports/gate-2.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report["results"], indent=1))


if __name__ == "__main__":
    main()
