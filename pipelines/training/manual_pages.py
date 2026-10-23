"""Split each manual PDF into page records and page-aligned chunks with page metadata.

Page numbers are 1-based PDF page indexes, so a citation opens with `#page=N` in a browser.
Each chunk carries manual_id, page, and the equipment classes the manual applies to (from the
compatibility table in data/SOURCES.md). The same JSONL feeds the local index used in Gate 2
and the Bedrock Knowledge Base metadata files.

Usage: .venv/bin/python -I pipelines/training/manual_pages.py
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUAL_DIR = ROOT / "data/raw/manuals"
OUT = ROOT / "data/processed"

# From the compatibility table in data/SOURCES.md. "class" means class match only.
MANUALS = {
    "trane-rt-svx26p-voyager-gas-electric-12-25t": {"title": "Trane RT-SVX26P-EN Voyager Gas/Electric 12.5 to 25 Tons IOM",
                                                    "classes": ["RTU"], "match": "class"},
    "trane-rt-svx21ad-precedent-gas-electric-3-10t": {"title": "Trane RT-SVX21AD-EN Precedent Gas/Electric 3 to 10 Tons IOM",
                                                      "classes": ["RTU"], "match": "class"},
    "daikin-im672-vision-ahu": {"title": "Daikin Applied IM 672-26 Vision Indoor Air Handler",
                                "classes": ["AHU-MZVAV", "AHU-SZCAV", "AHU-SZVAV"], "match": "class"},
    "trane-clch-svx08f-csaa-ahu-gas-heat": {"title": "Trane CLCH-SVX08F-EN Performance Climate Changer CSAA (gas heat)",
                                            "classes": ["AHU-MZVAV", "AHU-SZCAV", "AHU-SZVAV"], "match": "class"},
    "honeywell-jade-w7220-63-2700": {"title": "Honeywell 63-2700 JADE W7220 Economizer Module",
                                     "classes": ["RTU"], "match": "class"},
    # Added after Gate 2 run 1 for components with no coverage. Appended so earlier chunk indexes
    # (and their cached embeddings) stay valid.
    "siemens-duct-temperature-sensor-129-525": {"title": "Siemens 129-525 Duct Temperature Sensor Installation Instructions",
                                                "classes": ["RTU", "AHU-MZVAV", "AHU-SZCAV", "AHU-SZVAV"], "match": "class"},
    "jci-te6300m-duct-averaging-sensor": {"title": "Johnson Controls TE-6300M Duct Averaging Temperature Sensors Installation Instructions",
                                          "classes": ["RTU", "AHU-MZVAV", "AHU-SZCAV", "AHU-SZVAV"], "match": "class"},
    "honeywell-ml6984-ml7984-series4000": {"title": "Honeywell ML6984/ML7984 Series 4000 Direct Coupled Valve Actuators",
                                           "classes": ["AHU-MZVAV", "AHU-SZCAV", "AHU-SZVAV"], "match": "class"},
}
CHUNK_CHARS = 1800
OVERLAP = 200


def page_texts(pdf: Path) -> list[str]:
    text = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    return text.split("\f")


def clean(t: str) -> str:
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def chunks_of(text: str) -> list[str]:
    if len(text) <= CHUNK_CHARS:
        return [text]
    out, start = [], 0
    while start < len(text):
        out.append(text[start:start + CHUNK_CHARS])
        start += CHUNK_CHARS - OVERLAP
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pages, chunks = [], []
    for manual_id, meta in MANUALS.items():
        for i, raw in enumerate(page_texts(MANUAL_DIR / f"{manual_id}.pdf"), start=1):
            text = clean(raw)
            if len(text) < 40:
                continue
            pages.append({"manual_id": manual_id, "page": i, "text": text})
            for j, c in enumerate(chunks_of(text)):
                chunks.append({"chunk_id": f"{manual_id}:p{i}:c{j}", "manual_id": manual_id, "page": i,
                               "title": meta["title"], "classes": meta["classes"], "match": meta["match"], "text": c})
    (OUT / "manual_pages.jsonl").write_text("\n".join(json.dumps(p) for p in pages))
    (OUT / "manual_chunks.jsonl").write_text("\n".join(json.dumps(c) for c in chunks))
    print(f"{len(pages)} pages, {len(chunks)} chunks, {sum(len(c['text']) for c in chunks)} characters")


if __name__ == "__main__":
    main()
