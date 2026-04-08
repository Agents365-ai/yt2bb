---
name: yt2bb
description: Use when the user wants to repurpose a YouTube video for Bilibili, add bilingual (English-Chinese) subtitles to a video, or create hardcoded subtitle versions for Chinese platforms.
license: MIT
homepage: https://github.com/Agents365-ai/yt2bb
compatibility: Requires Python 3, ffmpeg, yt-dlp, whisper (openai-whisper) on PATH. Self-check steps that need vision are gracefully skipped if unavailable.
platforms: [macos, linux, windows]
allowed-tools: Bash(python3:*) Bash(ffmpeg:*) Bash(whisper:*) Bash(yt-dlp:*) Bash(git:*) Read Write Edit
metadata: {"openclaw":{"requires":{"bins":["python3","ffmpeg","yt-dlp","whisper"]},"emoji":"🎬","os":["darwin","linux","win32"],"install":[{"id":"brew-ffmpeg","kind":"brew","formula":"ffmpeg","bins":["ffmpeg"],"label":"Install ffmpeg via Homebrew","os":["darwin"]},{"id":"brew-ytdlp","kind":"brew","formula":"yt-dlp","bins":["yt-dlp"],"label":"Install yt-dlp via Homebrew","os":["darwin"]},{"id":"pipx-whisper","kind":"pipx","package":"openai-whisper","bins":["whisper"],"label":"Install openai-whisper via pipx"}]},"clawhub":{"requires":{"bins":["python3","ffmpeg","yt-dlp","whisper"]},"category":"media"},"hermes":{"tags":["youtube","bilibili","subtitles","bilingual","video","localization","whisper","yt-dlp"],"category":"media","requires_tools":["python3","ffmpeg","yt-dlp","whisper"],"related_skills":["ffmpeg","video-podcast-maker"]},"codex":{"requires":{"bins":["python3","ffmpeg","yt-dlp","whisper"]},"allowed-tools":["bash","read","write","edit"]},"claude-code":{"allowed-tools":"Bash(python3:*) Bash(ffmpeg:*) Bash(whisper:*) Bash(yt-dlp:*) Bash(git:*) Read Write Edit"},"skillsmp":{"topics":["claude-code","claude-code-skill","claude-skills","agent-skills","skillsmp","openclaw","openclaw-skills","skill-md","youtube","bilibili","subtitles","video"]},"author":"Agents365-ai","version":"2.1.0"}
---

# yt2bb — YouTube to Bilibili Video Repurposing

## Overview

Six-step pipeline: download → transcribe → translate → merge → burn subtitles → generate publish info. Produces a video with hardcoded bilingual (EN/ZH) subtitles and a `publish_info.md` with Bilibili upload metadata.

## When to Use

- User provides a YouTube URL (single video or playlist) and wants a Bilibili-ready version
- User needs bilingual EN-ZH subtitles burned into video
- User wants to repurpose English video content for Chinese audience

## Quick Reference

| Step | Tool | Command | Output |
|------|------|---------|--------|
| 0. Update | `git` | Auto-check for skill updates | — |
| 1. Download | `yt-dlp` | `yt-dlp --cookies-from-browser chrome -f ... -o ...` | `{slug}.mp4` |
| 2. Transcribe | `whisper` | `whisper --model medium --language {lang} ...` | `{slug}_{lang}.srt` |
| 2.5 Validate | `srt_utils.py` | `srt_utils.py validate / fix` | `{slug}_{lang}.srt` (fixed) |
| 3. Translate | Claude | SRT-aware batch translation | `{slug}_zh.srt` |
| 4. Merge | `srt_utils.py` | `srt_utils.py merge ...` | `{slug}_bilingual.srt` |
| 5. Burn | `ffmpeg` | `ffmpeg -c:v libx264 -vf subtitles=...` | `{slug}_bilingual.mp4` |
| 6. Publish | Claude | Analyze content, generate metadata | `publish_info.md` |

## Pre-flight: Auto Update

**Run this BEFORE any pipeline step.** Locates the skill directory and checks for updates. The `SKILL_DIR` variable is reused by later steps for script paths.

```bash
# Find skill directory (works across Claude Code, OpenClaw, Hermes)
SKILL_DIR="$(find ~/.claude/skills ~/.openclaw/skills ~/.hermes/skills ~/myagents/myskills -maxdepth 2 -name 'yt2bb' -type d 2>/dev/null | head -1)"
echo "yt2bb: SKILL_DIR=$SKILL_DIR"
if [ -n "$SKILL_DIR" ] && [ -d "$SKILL_DIR/.git" ]; then
  git -C "$SKILL_DIR" fetch --quiet origin main 2>/dev/null
  LOCAL=$(git -C "$SKILL_DIR" rev-parse HEAD)
  REMOTE=$(git -C "$SKILL_DIR" rev-parse origin/main 2>/dev/null)
  if [ "$LOCAL" != "$REMOTE" ]; then
    echo "yt2bb: new version available. Run: git -C $SKILL_DIR pull origin main"
  else
    echo "yt2bb: up to date."
  fi
fi
```

> **Note:** Does not auto-pull — the current session already loaded the old SKILL.md. Notify the user and let them update between sessions.

## Pipeline Details

### Step 1: Download

**Single video:**

```bash
slug="video-name"  # or: slug=$(python3 "$SKILL_DIR/srt_utils.py" slugify "Video Title")
mkdir -p "${slug}"
yt-dlp --cookies-from-browser chrome \
  -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]" \
  -o "${slug}/${slug}.mp4" "https://www.youtube.com/watch?v=VIDEO_ID"
```

**Playlist / series:**

```bash
yt-dlp --cookies-from-browser chrome \
  -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]" \
  -o "%(playlist_index)03d-%(title)s/%(playlist_index)03d-%(title)s.mp4" \
  "https://www.youtube.com/playlist?list=PLAYLIST_ID"
```

After downloading, rename each folder to a clean slug and run Steps 2–6 for each video sequentially.

- `-f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]"`: ensure mp4 output, avoid webm
- `%(playlist_index)03d`: zero-padded index to preserve playlist order

### Step 2: Transcribe

Determine source language first. Ask the user, or infer from the YouTube page/title.

```bash
src_lang="en"  # Change to ja/ko/es/etc. based on source video
whisper "${slug}/${slug}.mp4" \
  --model medium \
  --language "$src_lang" \
  --word_timestamps True \
  --condition_on_previous_text False \
  --output_format srt \
  --max_line_width 40 --max_line_count 1 \
  --output_dir "${slug}"
mv "${slug}/${slug}.srt" "${slug}/${slug}_${src_lang}.srt"
```

- `medium`: good balance of accuracy and speed (use `tiny` for quick drafts, `large-v3` only when explicitly requested)
- `--language`: explicitly set to avoid misdetection; supports `en`, `ja`, `ko`, `es`, etc.
- `--word_timestamps True`: more precise subtitle timing
- `--condition_on_previous_text False`: prevent hallucination loops

### Step 2.5: Validate & Fix (optional)

```bash
python3 "$SKILL_DIR/srt_utils.py" validate "${slug}/${slug}_${src_lang}.srt"
# If issues found:
python3 "$SKILL_DIR/srt_utils.py" fix "${slug}/${slug}_${src_lang}.srt" "${slug}/${slug}_${src_lang}.srt"
```

### Step 3: Translate

Read `{slug}_{src_lang}.srt` and translate to Chinese. **Critical rules:**

1. **Keep SRT format intact** — preserve index numbers, timestamps (`-->` lines) exactly as-is
2. **1:1 entry mapping** — every source entry must produce exactly one translated entry (same count)
3. **Keep each Chinese entry on 1 line, ≤18 chars** — translate concisely; bilingual result = 2 lines total (EN + ZH)
4. **Translate in batches of 10 entries** — output each batch in valid SRT format, then continue
5. **Do NOT merge or split entries** — maintain original segmentation
6. Save as `{slug}/{slug}_zh.srt`

### Step 4: Merge

```bash
python3 "$SKILL_DIR/srt_utils.py" merge \
  "${slug}/${slug}_${src_lang}.srt" "${slug}/${slug}_zh.srt" "${slug}/${slug}_bilingual.srt"
```

### Step 5: Burn Subtitles

```bash
ffmpeg -i "${slug}/${slug}.mp4" \
  -vf "subtitles='${slug}/${slug}_bilingual.srt':force_style='FontName=PingFang SC,FontSize=20,PrimaryColour=&H00FFFF,OutlineColour=&H000000,Outline=2,MarginV=30'" \
  -c:v libx264 -crf 23 -preset medium \
  -c:a copy "${slug}/${slug}_bilingual.mp4"
```

- `-c:v libx264 -crf 23`: good quality with reasonable file size
- `-preset medium`: balance between speed and compression (use `fast` for quicker encode)

### Step 6: Generate Publish Info

Based on the video content (from `{slug}_{src_lang}.srt` and `{slug}_zh.srt`), generate `{slug}/publish_info.md`.

All output in this file must be in **Chinese** (targeting Bilibili audience).

```markdown
# Publish Info

## Source
{YouTube URL}

## Titles (5 variants)
1. {Suspense/question style — spark curiosity}
2. {Data/achievement driven — emphasize results}
3. {Controversial/opinion style — spark discussion}
4. {Tutorial/practical style — emphasize utility}
5. {Emotional/relatable style — connect with audience}

## Tags
{~10 comma-separated keywords covering topic, technology, domain}

## Description
{3-5 sentences summarizing core content and highlights}

## Chapter Timestamps
00:00 {chapter name}
...
```

**Generation rules:**
- Title style must match Bilibili conventions: conversational tone, suspense hooks, liberal use of symbols (【】, ?, !)
- Tags should cover both Chinese and English keywords for discoverability
- Timestamps extracted from `{slug}_bilingual.srt` at topic transition points
- Description needs a strong hook — first two sentences determine whether users expand to read

## Output Structure

```
{slug}/
├── {slug}.mp4              # Source video
├── {slug}_{src_lang}.srt   # Source language subtitles
├── {slug}_zh.srt           # Chinese subtitles
├── {slug}_bilingual.srt    # Merged bilingual
├── {slug}_bilingual.mp4    # Final output
└── publish_info.md         # Bilibili upload metadata
```

## Utility: srt_utils.py

```bash
python3 "$SKILL_DIR/srt_utils.py" merge en.srt zh.srt output.srt    # Merge bilingual
python3 "$SKILL_DIR/srt_utils.py" validate input.srt                 # Check timing issues
python3 "$SKILL_DIR/srt_utils.py" fix input.srt output.srt           # Fix timing/overlaps
python3 "$SKILL_DIR/srt_utils.py" slugify "Video Title"              # Generate slug
```

## Common Mistakes

- **Mismatched entry counts**: Merge pads with placeholders — review and fix manually
- **Font not found**: Ensure PingFang SC is installed (macOS default) or substitute
