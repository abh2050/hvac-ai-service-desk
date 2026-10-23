"""Gate 2 statistics: Wilson 95% intervals and exact McNemar tests on paired cases.

Pairs are the same case scored two ways (AI vs rule hint, AI verified vs baseline verified).
Exact McNemar: two-sided binomial test on the discordant pairs with p = 0.5.

Usage: .venv/bin/python -I pipelines/evaluation/gate2_stats.py [cases.jsonl] [out.json]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
Z = 1.959964


def wilson(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * tail), 4)


def compare(rows, name_a, fa, name_b, fb) -> dict:
    a = [bool(fa(r)) for r in rows]
    b = [bool(fb(r)) for r in rows]
    n = len(rows)
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    p = mcnemar_exact(only_a, only_b)
    return {
        "cases": n,
        name_a: {"correct": sum(a), "rate": round(sum(a) / n, 3) if n else None, "wilson95": wilson(sum(a), n)},
        name_b: {"correct": sum(b), "rate": round(sum(b) / n, 3) if n else None, "wilson95": wilson(sum(b), n)},
        "discordant": {f"only_{name_a}": only_a, f"only_{name_b}": only_b},
        "mcnemar_exact_p": p,
        "significant_at_0.05": p < 0.05,
    }


def main():
    src = (ROOT / sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/gate-2-cases.jsonl"
    out = (ROOT / sys.argv[2]) if len(sys.argv) > 2 else ROOT / "reports/gate-2-stats.json"
    rows = [json.loads(line) for line in src.read_text().splitlines()]
    normal = [r for r in rows if not r["probe"]]
    lab = lambda r: r["label"]["fault_type"]
    segments = {"all": normal, "lab": [r for r in normal if r["source_type"] == "lab"],
                "field": [r for r in normal if r["source_type"] == "field"]}
    for key in sorted({(r["source_type"], r["family"]) for r in normal}):
        segments["/".join(key)] = [r for r in normal if (r["source_type"], r["family"]) == key]
    result = {"source": str(src.relative_to(ROOT)), "method": "exact McNemar on discordant pairs; Wilson 95% intervals",
              "proposal_vs_rule_hint": {}, "verified_ai_vs_verified_baseline": {}}
    for name, sel in segments.items():
        if not sel:
            continue
        result["proposal_vs_rule_hint"][name] = compare(
            sel, "ai_proposal", lambda r: r["ai"]["proposed"]["probable_cause"] == lab(r),
            "rule_hint", lambda r: r["rule_hint"] == lab(r))
        result["verified_ai_vs_verified_baseline"][name] = compare(
            sel, "ai_verified", lambda r: r["ai"]["final"]["probable_cause"] == lab(r),
            "baseline_verified", lambda r: r["baseline"]["probable_cause"] == lab(r))
    probes = [r for r in rows if r["probe"]]
    k = sum(r["ai"]["final"]["abstained"] for r in probes)
    result["probe_abstention"] = {"abstained": k, "probes": len(probes), "wilson95": wilson(k, len(probes))}
    cites = [v for r in normal for v in r["ai"]["verified"]["citations"]]
    k = sum(v["pass"] for v in cites)
    result["citation_support"] = {"passed": k, "checked": len(cites), "wilson95": wilson(k, len(cites))}
    out.write_text(json.dumps(result, indent=1))
    for name in ("all", "lab", "field"):
        x = result["proposal_vs_rule_hint"].get(name)
        if x:
            print(name, x["ai_proposal"], x["rule_hint"], x["discordant"], "p=", x["mcnemar_exact_p"])
        y = result["verified_ai_vs_verified_baseline"].get(name)
        if y:
            print("  verified", y["ai_verified"]["rate"], y["baseline_verified"]["rate"], y["discordant"], "p=", y["mcnemar_exact_p"])
    print(result["probe_abstention"], result["citation_support"])


if __name__ == "__main__":
    main()
