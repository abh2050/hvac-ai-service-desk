"""Embed manual chunks with Titan Text Embeddings v2 (resumable, quota-paced).

Usage: .venv/bin/python -I pipelines/training/embed_manuals.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))
from diagnosis.retrieval import Embedder, load_chunks  # noqa: E402

chunks = load_chunks(ROOT / "data/processed/manual_chunks.jsonl")
e = Embedder(profile="awsnew")
t = time.time()
vec = e.embed_many([c["title"] + "\n" + c["text"] for c in chunks],
                   cache=ROOT / "data/processed/manual_vectors.cache.json")
np.save(ROOT / "data/processed/manual_vectors.npy", vec)
print(json.dumps({"chunks": int(vec.shape[0]), "dims": int(vec.shape[1]), "new_input_tokens": e.input_tokens,
                  "cost_usd": round(e.input_tokens / 1e6 * 0.02, 5), "seconds": round(time.time() - t, 1)}))
