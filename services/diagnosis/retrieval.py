"""Manual passage retrieval.

Two retrievers share one interface:
  VectorIndex  Titan Text Embeddings v2 over page chunks (the AI path; mirrors the Bedrock
               Knowledge Base, which uses the same model and the same page metadata).
  BM25Index    keyword ranking with no model (the non-AI baseline).
Both filter by equipment class, so an AHU case never retrieves RTU-only manuals.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
import time
from pathlib import Path

import boto3
from botocore.config import Config
import numpy as np

EMBED_MODEL = "amazon.titan-embed-text-v2:0"
TOKEN = re.compile(r"[a-z0-9]+")


def load_chunks(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class Embedder:
    def __init__(self, region: str = "us-east-2", profile: str | None = None):
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("bedrock-runtime", config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))
        self.input_tokens = 0

    def embed(self, text: str) -> np.ndarray:
        body = json.dumps({"inputText": text[:8000], "dimensions": 1024, "normalize": True})
        resp = json.loads(self.client.invoke_model(modelId=EMBED_MODEL, body=body)["body"].read())
        self.input_tokens += resp.get("inputTextTokenCount", 0)
        return np.asarray(resp["embedding"], dtype=np.float32)

    def embed_many(self, texts: list[str], per_minute: int = 55, cache: Path | None = None) -> np.ndarray:
        """Embed under the account's requests-per-minute quota; resumes from `cache` if given."""
        done = json.loads(cache.read_text()) if cache and cache.exists() else {}
        interval = 60.0 / per_minute
        for i, t in enumerate(texts):
            if str(i) in done:
                continue
            start = time.time()
            done[str(i)] = self.embed(t).tolist()
            if cache and i % 25 == 0:
                cache.write_text(json.dumps(done))
            time.sleep(max(0.0, interval - (time.time() - start)))
        if cache:
            cache.write_text(json.dumps(done))
        return np.vstack([np.asarray(done[str(i)], dtype=np.float32) for i in range(len(texts))])


class VectorIndex:
    def __init__(self, chunks: list[dict], vectors: np.ndarray, embedder: Embedder):
        self.chunks, self.vectors, self.embedder = chunks, vectors, embedder

    def search(self, query: str, equipment_class: str, k: int = 6) -> list[dict]:
        q = self.embedder.embed(query)
        allowed = np.array([equipment_class in c["classes"] for c in self.chunks])
        scores = np.where(allowed, self.vectors @ q, -np.inf)
        top = np.argsort(-scores)[:k]
        return [dict(self.chunks[i], score=float(scores[i])) for i in top if np.isfinite(scores[i])]


class BM25Index:
    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.docs = [Counter(TOKEN.findall(c["text"].lower())) for c in chunks]
        self.lens = np.array([sum(d.values()) for d in self.docs])
        self.avg = self.lens.mean()
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, equipment_class: str, k: int = 6) -> list[dict]:
        terms = TOKEN.findall(query.lower())
        scores = []
        for i, (d, ln) in enumerate(zip(self.docs, self.lens)):
            if equipment_class not in self.chunks[i]["classes"]:
                scores.append(-1.0)
                continue
            s = 0.0
            for t in terms:
                if t in d:
                    tf = d[t]
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * ln / self.avg))
            scores.append(s)
        top = np.argsort(-np.asarray(scores))[:k]
        return [dict(self.chunks[i], score=float(scores[i])) for i in top if scores[i] > 0]


class KbIndex:
    """Bedrock Knowledge Base retriever with the same interface as VectorIndex.

    KB documents start with the manual title line (pipelines/deploy/build_kb_docs.py); it is
    removed so passage text matches the page text the citation verifier checks.
    """

    def __init__(self, knowledge_base_id: str, region: str = "us-east-2", profile: str | None = None):
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("bedrock-agent-runtime",
                                     config=Config(retries={"max_attempts": 6, "mode": "adaptive"}))
        self.kb = knowledge_base_id

    def search(self, query: str, equipment_class: str, k: int = 6) -> list[dict]:
        resp = self.client.retrieve(
            knowledgeBaseId=self.kb, retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {
                "numberOfResults": k,
                "filter": {"listContains": {"key": "classes", "value": equipment_class}}}})
        out = []
        for r in resp["retrievalResults"]:
            md = r.get("metadata", {})
            text = r["content"]["text"]
            text = text.split("\n", 1)[1] if text.startswith(md.get("title", "\0")) and "\n" in text else text
            out.append({"manual_id": md.get("manual_id"), "page": int(float(md.get("page", 0))), "title": md.get("title"),
                        "match": md.get("match"), "classes": [str(c).strip('"') for c in md.get("classes") or []],
                        "text": text,
                        "score": float(r.get("score", 0.0))})
        return out
