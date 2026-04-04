---
name: yt2bb
description: Use when the user wants to repurpose a YouTube video for Bilibili, add bilingual (English-Chinese) subtitles to a video, or create hardcoded subtitle versions for Chinese platforms.
version: 1.1.0
author: Agents365-ai
license: MIT
homepage: https://github.com/Agents365-ai/yt2bb
compatibility: Requires Python 3, ffmpeg, yt-dlp, whisper (openai-whisper) on PATH. YouTube account must be logged in via Chrome browser (yt-dlp extracts cookies automatically).
allowed-tools: Bash(python3:*) Bash(ffmpeg:*) Bash(whisper:*) Bash(yt-dlp:*) Read Write Edit
metadata: {"openclaw":{"requires":{"bins":["python3","ffmpeg","yt-dlp","whisper"]}},"hermes":{"tags":["youtube","bilibili","subtitles","bilingual","video","localization"],"related_skills":["ffmpeg"]}}
---

# yt2bb — YouTube to Bilibili Video Repurposing

## Overview

Five-step pipeline: download → transcribe → translate → merge → burn subtitles. Produces a video with hardcoded bilingual (EN/ZH) subtitles ready for Bilibili upload.

## When to Use

- User provides a YouTube URL and wants a Bilibili-ready version
- User needs bilingual EN-ZH subtitles burned into video
- User wants to repurpose English video content for Chinese audience

## Quick Reference

| Step | Skill | Command | Output |
|------|-------|---------|--------|
| 1. Download | `yt-dlp` | `yt-dlp --cookies-from-browser chrome -o ...` | `{slug}.mp4` |
| 2. Transcribe | `whisper` | `whisper ... --output_format srt` | `{slug}_en.srt` |
| 3. Translate | Claude | Batch translate, max 20 chars/line | `{slug}_zh.srt` |
| 4. Merge | `srt_utils.py` | `srt_utils.py merge ...` | `{slug}_bilingual.srt` |
| 5. Burn | `ffmpeg` | `ffmpeg -vf subtitles=...` | `{slug}_bilingual.mp4` |

## Pipeline Details

### Step 1: Download

```bash
slug="video-name"  # or: slug=$(python3 scripts/srt_utils.py slugify "Video Title")
mkdir -p "${slug}"
yt-dlp --cookies-from-browser chrome -o "${slug}/${slug}.mp4" "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Step 2: Transcribe

```bash
whisper "${slug}/${slug}.mp4" --model turbo --output_format srt \
  --max_line_width 42 --max_line_count 2
mv "${slug}/${slug}.srt" "${slug}/${slug}_en.srt"
```

### Step 3: Translate

- Read `{slug}_en.srt`, translate to Chinese in batches of 10 entries
- Max 20 chars per line for Chinese (use `srt_utils.py segment` if needed)
- Save as `{slug}_zh.srt`

### Step 4: Merge

```bash
python3 scripts/srt_utils.py merge \
  "${slug}/${slug}_en.srt" "${slug}/${slug}_zh.srt" "${slug}/${slug}_bilingual.srt"
```

### Step 5: Burn Subtitles

```bash
ffmpeg -i "${slug}/${slug}.mp4" \
  -vf "subtitles='${slug}/${slug}_bilingual.srt':force_style='FontName=PingFang SC,FontSize=22,PrimaryColour=&H00FFFF,OutlineColour=&H000000,Outline=2,MarginV=30'" \
  -c:a copy "${slug}/${slug}_bilingual.mp4"
```

## Output Structure

```
{slug}/
├── {slug}.mp4              # Source video
├── {slug}_en.srt           # English subtitles
├── {slug}_zh.srt           # Chinese subtitles
├── {slug}_bilingual.srt    # Merged bilingual
└── {slug}_bilingual.mp4    # Final output
```

## Utility: srt_utils.py

```bash
python3 scripts/srt_utils.py merge en.srt zh.srt output.srt    # Merge bilingual
python3 scripts/srt_utils.py segment zh.srt out.srt [max=20]   # Break long lines
python3 scripts/srt_utils.py slugify "Video Title"              # Generate slug
```

## Common Mistakes

- **Mismatched entry counts**: Merge pads with placeholders — review and fix manually
- **Long Chinese lines**: Always segment to ≤20 chars before merging
- **Font not found**: Ensure PingFang SC is installed (macOS default) or substitute
