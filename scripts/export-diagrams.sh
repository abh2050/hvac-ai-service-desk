#!/usr/bin/env bash
# Export every diagrams/*.drawio to PNG (2x scale) and SVG with the draw.io desktop CLI.
set -euo pipefail
cd "$(dirname "$0")/../diagrams"
for f in *.drawio; do
  drawio -x -f png -s 2 -b 20 -o "${f%.drawio}.png" "$f" >/dev/null 2>&1
  drawio -x -f svg -b 20 -o "${f%.drawio}.svg" "$f" >/dev/null 2>&1
  echo "exported ${f%.drawio}"
done
