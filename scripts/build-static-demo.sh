#!/usr/bin/env bash
# Build the static recorded demo (no sign-in, no backend) into build/vercel/uptime-desk for Vercel.
# It needs no AWS access: it reads app/static-demo/snapshot (captured by pipelines/deploy/snapshot_demo.py)
# and the gate reports. Vercel runs this on every push to main (see vercel.json at the repo root).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/build/vercel/uptime-desk"
cd "$REPO_ROOT/app"
npx tsc -b
mkdir -p "$OUT"
find "$OUT" -mindepth 1 -maxdepth 1 ! -name .vercel -exec rm -rf {} +    # keep the Vercel project link
VITE_STATIC=1 npx vite build --outDir "$OUT" --emptyOutDir false
cp -R static-demo/snapshot "$OUT/snapshot"
mkdir -p "$OUT/reports"
cp "$REPO_ROOT"/reports/gate-*.json "$REPO_ROOT"/reports/gate-*.md "$OUT/reports/"
echo "Built $OUT"
