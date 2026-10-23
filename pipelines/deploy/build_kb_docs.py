"""Write Bedrock Knowledge Base source documents: one text file per page-aligned manual chunk.

The Knowledge Base uses no chunking (each file is one chunk), so every retrieved passage carries
the same manual_id and page that the citation verifier checks. Metadata goes in the sidecar
`<file>.metadata.json` format that Bedrock Knowledge Bases read from S3.

Usage: .venv/bin/python -I pipelines/deploy/build_kb_docs.py   (writes data/kb_docs/)
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/kb_docs"


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    n = 0
    for line in (ROOT / "data/processed/manual_chunks.jsonl").read_text().splitlines():
        c = json.loads(line)
        name = c["chunk_id"].replace(":", "__") + ".txt"
        (OUT / name).write_text(c["title"] + "\n" + c["text"])
        meta = {"metadataAttributes": {
            "manual_id": c["manual_id"], "page": c["page"], "title": c["title"], "match": c["match"],
            "classes": c["classes"], "chunk_id": c["chunk_id"]}}
        (OUT / f"{name}.metadata.json").write_text(json.dumps(meta))
        n += 1
    print(f"{n} documents in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
