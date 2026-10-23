"""Thin Bedrock Converse wrapper that records tokens, latency, and the model actually used."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import boto3
from botocore.config import Config

# USD per 1M tokens, us-east-2 on-demand. Source and check date are recorded in config/models.yaml.
PRICES = {
    "openai.gpt-oss-120b-1:0": (0.15, 0.60),
    "openai.gpt-oss-20b-1:0": (0.07, 0.30),
}


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: list[int] = field(default_factory=list)
    cost_usd: float = 0.0
    truncated: int = 0


class LLM:
    def __init__(self, model_id: str, region: str = "us-east-2", profile: str | None = None,
                 max_tokens: int = 2000, guardrail: dict | None = None):
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("bedrock-runtime", config=Config(retries={"max_attempts": 6, "mode": "adaptive"},
                                                                       read_timeout=120))
        self.model_id, self.max_tokens, self.guardrail = model_id, max_tokens, guardrail
        self.usage = Usage()

    def complete(self, system: str, user: str) -> str:
        kwargs = dict(modelId=self.model_id, system=[{"text": system}],
                      messages=[{"role": "user", "content": [{"text": user}]}],
                      inferenceConfig={"maxTokens": self.max_tokens, "temperature": 0})
        if self.guardrail:
            kwargs["guardrailConfig"] = self.guardrail
        t = time.time()
        resp = self.client.converse(**kwargs)
        self.usage.latency_ms.append(int((time.time() - t) * 1000))
        if resp.get("stopReason") == "max_tokens":
            self.usage.truncated += 1
        u = resp.get("usage", {})
        self.usage.calls += 1
        self.usage.input_tokens += u.get("inputTokens", 0)
        self.usage.output_tokens += u.get("outputTokens", 0)
        p_in, p_out = PRICES.get(self.model_id, (0.0, 0.0))
        self.usage.cost_usd += (u.get("inputTokens", 0) * p_in + u.get("outputTokens", 0) * p_out) / 1e6
        # gpt-oss returns a reasoningContent block first; only text blocks are the answer.
        return "".join(b["text"] for b in resp["output"]["message"]["content"] if "text" in b)


def parse_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
