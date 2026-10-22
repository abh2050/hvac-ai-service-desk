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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
import numpy as np

EMBED_MODEL = "amazon.titan-embed-text-v2:0"
TOKEN = re.compile(r"[a-z0-9]+")


def load_chunks(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class Embedder:
    def __init__(self, region: str = "us-east-2", profile: str | None = None):
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("bedrock-runtime")
        self.input_tokens = 0

    def embed(self, text: str) -> np.ndarray:
        body = json.dumps({"inputText": text[:8000], "dimensions": 1024, "normalize": True})
        resp = json.loads(self.client.invoke_model(modelId=EMBED_MODEL, body=body)["body"].read())
        self.input_tokens += resp.get("inputTextTokenCount", 0)
        return np.asarray(resp["embedding"], dtype=np.float32)

    def embed_many(self, texts: list[str], workers: int = 8) -> np.ndarray:
        with ThreadPoolExecutor(workers) as pool:
            return np.vstack(list(pool.map(self.embed, texts)))


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
