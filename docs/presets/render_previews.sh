#!/usr/bin/env bash
# Regenerate the preset preview images in docs/presets/.
#
# Renders a neutral gradient background, burns each ASS preset onto it,
# and writes one PNG per preset. Run from the repo root:
#
#   bash docs/presets/render_previews.sh
#
# Requires: ffmpeg (with the `ass` filter), python3.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$REPO_ROOT/docs/presets"
SAMPLE_SRT="$OUT_DIR/sample.srt"
TMP_BG="$(mktemp -t yt2bb_preview_bg.XXXXXX).png"
trap 'rm -f "$TMP_BG"' EXIT

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found on PATH" >&2
  exit 1
fi

# Neutral mid-tone gradient — dark blue at the top, lighter teal at the
# bottom where the subtitle block lives. Chosen so:
#   * netflix outline+shadow is clearly readable
#   * clean gray box is visibly distinct from the background
#   * glow color pop is still legible
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "gradients=size=1920x1080:c0=0x0a1420:c1=0x1e3a5f:c2=0x3a7a9b:n=3:x0=960:y0=0:x1=960:y1=1080:duration=1" \
  -frames:v 1 "$TMP_BG"

render_preset () {
  local preset="$1"
  local ass_path="$OUT_DIR/.${preset}.ass"
  local png_path="$OUT_DIR/${preset}.png"

  python3 "$REPO_ROOT/srt_utils.py" to_ass \
    "$SAMPLE_SRT" "$ass_path" \
    --preset "$preset" >/dev/null

  # Loop the background as a 2 s video so the subtitle cue is active,
  # then extract a single frame at t=1 s where the subtitle is on screen.
  ffmpeg -y -hide_banner -loglevel error \
    -loop 1 -t 2 -framerate 24 -i "$TMP_BG" \
    -vf "ass='$ass_path'" \
    -ss 1 -frames:v 1 \
    "$png_path"

  rm -f "$ass_path"
  echo "  rendered $png_path"
}

echo "Rendering preset previews:"
render_preset netflix
render_preset clean
render_preset glow
echo "Done. Commit docs/presets/*.png alongside any preset changes."
