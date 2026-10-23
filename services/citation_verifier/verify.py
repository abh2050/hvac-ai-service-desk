"""Citation verifier: deterministic text match on the cited page plus an LLM entailment check.

Both results are recorded. A citation passes only when both pass.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagnosis.llm import LLM, parse_json  # noqa: E402

WORD = re.compile(r"[a-z0-9]+")
SUPPORTED = re.compile(r"\"?supported\"?\s*:\s*(true|false)", re.I)

ENTAIL_SYSTEM = """Reasoning: low
You check citations for HVAC service records. Decide if the PAGE text supports the CLAIM.
Supported means the page states it or directly describes it. General relevance is not enough.
Reply with one JSON object: {"supported": true or false, "reason": "one sentence"}."""


def tokens(text: str) -> list[str]:
    return WORD.findall(text.lower())


def trigram_coverage(quote: str, page: str) -> float:
    q, p = tokens(quote), tokens(page)
    if len(q) < 3:
        return 1.0 if q and " ".join(q) in " ".join(p) else 0.0
    qg = {tuple(q[i:i + 3]) for i in range(len(q) - 2)}
    pg = {tuple(p[i:i + 3]) for i in range(len(p) - 2)}
    return len(qg & pg) / len(qg)


class Verifier:
    def __init__(self, pages: dict[tuple[str, int], str], entail_llm: LLM, min_overlap: float):
        self.pages, self.llm, self.min_overlap = pages, entail_llm, min_overlap

    @classmethod
    def from_jsonl(cls, path: Path, entail_llm: LLM, min_overlap: float) -> "Verifier":
        pages = {}
        for line in path.read_text().splitlines():
            r = json.loads(line)
            pages[(r["manual_id"], r["page"])] = r["text"]
        return cls(pages, entail_llm, min_overlap)

    def check(self, manual_id: str | None, page: int | None, quote: str, claim: str) -> dict:
        text = self.pages.get((manual_id, page))
        if not text or not quote:
            return {"deterministic_pass": False, "coverage": 0.0, "entailed": False,
                    "reason": "cited page not found", "pass": False}
        coverage = round(trigram_coverage(quote, text), 3)
        det = coverage >= self.min_overlap
        entailed, reason = False, "skipped: quote not on page"
        if det:
            raw = self.llm.complete(ENTAIL_SYSTEM, json.dumps({"CLAIM": claim, "PAGE": text[:6000]}))
            reply = parse_json(raw)
            if reply is not None:
                entailed = reply.get("supported") is True
                reason = reply.get("reason", "")
            else:
                m = SUPPORTED.search(raw)
                entailed = bool(m and m.group(1) == "true")
                reason = f"loose parse: {raw[:200]}" if m else f"unparseable reply: {raw[:200]!r}"
        return {"deterministic_pass": det, "coverage": coverage, "entailed": entailed, "reason": reason,
                "pass": det and entailed}
