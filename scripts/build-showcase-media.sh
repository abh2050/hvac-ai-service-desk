#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
media_dir="$root_dir/docs/media"
generated_dir="$media_dir/higgsfield"
source_dir="$root_dir/video/public"

mkdir -p "$media_dir"

hero_png="$media_dir/hero-sized.png"
before_png="$media_dir/before-sized.png"
ffmpeg -y -hide_banner -loglevel error \
  -i "$generated_dir/hero.png" \
  -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080" \
  "$hero_png"
cwebp -quiet -q 86 "$hero_png" -o "$media_dir/hero.webp"
rm -f "$hero_png"

ffmpeg -y -hide_banner -loglevel error \
  -i "$generated_dir/before.png" \
  -vf "scale=1600:-2" \
  "$before_png"
cwebp -quiet -q 84 "$before_png" -o "$media_dir/before.webp"
rm -f "$before_png"

ffmpeg -y -hide_banner -loglevel error \
  -loop 1 -i "$generated_dir/hero.png" -t 8 \
  -vf "scale=2048:-2,zoompan=z='min(zoom+0.00028,1.055)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=240:s=1920x1080:fps=30,format=yuv420p" \
  -an -c:v libx264 -preset slow -crf 24 -movflags +faststart "$media_dir/hero.mp4"

ffmpeg -y -hide_banner -loglevel error \
  -i "$media_dir/hero.mp4" -an -c:v libvpx-vp9 -b:v 0 -crf 34 -row-mt 1 "$media_dir/hero.webm"

export_clip() {
  local name="$1"
  local input="$2"
  local start="$3"
  local duration="$4"

  ffmpeg -y -hide_banner -loglevel error \
    -ss "$start" -i "$input" -t "$duration" \
    -an -vf "scale=1280:-2" \
    -c:v libx264 -preset slow -crf 27 -movflags +faststart "$media_dir/$name.mp4"

  ffmpeg -y -hide_banner -loglevel error \
    -i "$media_dir/$name.mp4" -an \
    -c:v libvpx-vp9 -b:v 0 -crf 37 -row-mt 1 "$media_dir/$name.webm"

  ffmpeg -y -hide_banner -loglevel error \
    -i "$media_dir/$name.mp4" -frames:v 1 -vf "scale=960:-2" \
    "$media_dir/$name-poster.png"
  cwebp -quiet -q 82 "$media_dir/$name-poster.png" -o "$media_dir/$name-poster.webp"
  rm -f "$media_dir/$name-poster.png"
}

export_clip "replay-detect" "$source_dir/rules.mp4" 0 8
export_clip "evidence" "$source_dir/evidence.mp4" 0 8
export_clip "approval-dispatch" "$source_dir/live-flow.mp4" 35 8
export_clip "assistant" "$source_dir/assistant.mp4" 8 8

palette_file="/tmp/uptime-hero-palette-$$.png"
ffmpeg -y -hide_banner -loglevel error \
  -i "$media_dir/hero.mp4" -t 5 \
  -vf "fps=8,scale=800:-2:flags=lanczos,palettegen=max_colors=96" "$palette_file"
ffmpeg -y -hide_banner -loglevel error \
  -i "$media_dir/hero.mp4" -i "$palette_file" -t 5 \
  -lavfi "fps=8,scale=800:-2:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer" \
  "$media_dir/hero.gif"
rm -f "$palette_file"

ffmpeg -y -hide_banner -loglevel error \
  -i "$media_dir/replay-detect.mp4" \
  -i "$media_dir/evidence.mp4" \
  -i "$media_dir/approval-dispatch.mp4" \
  -i "$media_dir/assistant.mp4" \
  -filter_complex "[0:v]trim=0:2,setpts=PTS-STARTPTS[v0];[1:v]trim=0:2,setpts=PTS-STARTPTS[v1];[2:v]trim=0:2,setpts=PTS-STARTPTS[v2];[3:v]trim=0:2,setpts=PTS-STARTPTS[v3];[v0][v1][v2][v3]concat=n=4:v=1:a=0,fps=8,scale=720:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer" \
  "$media_dir/walkthrough.gif"

du -ch "$media_dir"/*.{mp4,webm,webp,gif} 2>/dev/null | tail -n 1
