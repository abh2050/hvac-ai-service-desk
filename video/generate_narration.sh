#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/video/script.md"
OUT="$ROOT/video/audio"
VOICE_ID="XrExE9yKIg1WjnnlVkGX"

mkdir -p "$OUT"
ELEVEN_KEY="$(~/.local/bin/aws ssm get-parameter \
  --name /uptime-desk/elevenlabs/api-key \
  --with-decryption \
  --profile awsnew \
  --region us-east-2 \
  --query Parameter.Value \
  --output text)"

scene_text() {
  local scene="$1"
  awk -v heading="## Scene $scene," '
    index($0, heading) == 1 { in_scene=1; next }
    in_scene && /^## Scene / { exit }
    in_scene && NF { print }
  ' "$SCRIPT"
}

for scene in 1 2 3 4 5 6; do
  target="$OUT/scene-${scene}.mp3"
  if [[ -s "$target" ]]; then
    echo "kept scene-${scene}.mp3"
    continue
  fi
  text="$(scene_text "$scene")"
  payload="$(jq -n --arg text "$text" '{
    text: $text,
    model_id: "eleven_multilingual_v2",
    voice_settings: {stability: 0.55, similarity_boost: 0.78, style: 0.18, use_speaker_boost: true}
  }')"
  curl -fsS \
    -X POST "https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}?output_format=mp3_44100_128" \
    -H "xi-api-key: ${ELEVEN_KEY}" \
    -H "Content-Type: application/json" \
    --data-binary "$payload" \
    --output "$target"
  duration="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$target")"
  echo "generated scene-${scene}.mp3 (${duration}s)"
done
