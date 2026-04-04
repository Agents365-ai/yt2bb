---
name: yt2bb
description: Use when the user wants to repurpose a YouTube video for Bilibili, add bilingual (English-Chinese) subtitles to a video, or create hardcoded subtitle versions for Chinese platforms.
version: 2.0.0
author: Agents365-ai
license: MIT
homepage: https://github.com/Agents365-ai/yt2bb
compatibility: Requires Python 3, ffmpeg, yt-dlp, whisper (openai-whisper) on PATH. YouTube account must be logged in via Chrome browser (yt-dlp extracts cookies automatically).
allowed-tools: Bash(python3:*) Bash(ffmpeg:*) Bash(whisper:*) Bash(yt-dlp:*) Bash(git:*) Read Write Edit
metadata: {"openclaw":{"requires":{"bins":["python3","ffmpeg","yt-dlp","whisper"]}},"hermes":{"tags":["youtube","bilibili","subtitles","bilingual","video","localization"],"related_skills":["ffmpeg"]}}
---

# yt2bb — YouTube to Bilibili Video Repurposing

## Overview

Six-step pipeline: download → transcribe → translate → merge → burn subtitles → generate publish info. Produces a video with hardcoded bilingual (EN/ZH) subtitles and a `publish_info.md` with Bilibili upload metadata.

## When to Use

- User provides a YouTube URL and wants a Bilibili-ready version
- User needs bilingual EN-ZH subtitles burned into video
- User wants to repurpose English video content for Chinese audience

## Quick Reference

| Step | Tool | Command | Output |
|------|------|---------|--------|
| 0. Update | `git` | Auto-check for skill updates | — |
| 1. Download | `yt-dlp` | `yt-dlp --cookies-from-browser chrome -f ... -o ...` | `{slug}.mp4` |
| 2. Transcribe | `whisper` | `whisper --model large-v3 --language {lang} ...` | `{slug}_{lang}.srt` |
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

```bash
slug="video-name"  # or: slug=$(python3 "$SKILL_DIR/scripts/srt_utils.py" slugify "Video Title")
mkdir -p "${slug}"
yt-dlp --cookies-from-browser chrome \
  -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]" \
  -o "${slug}/${slug}.mp4" "https://www.youtube.com/watch?v=VIDEO_ID"
```

- `-f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]"`: ensure mp4 output, avoid webm

### Step 2: Transcribe

Determine source language first. Ask the user, or infer from the YouTube page/title.

```bash
src_lang="en"  # Change to ja/ko/es/etc. based on source video
whisper "${slug}/${slug}.mp4" \
  --model large-v3 \
  --language "$src_lang" \
  --word_timestamps True \
  --condition_on_previous_text False \
  --output_format srt \
  --max_line_width 40 --max_line_count 1 \
  --output_dir "${slug}"
mv "${slug}/${slug}.srt" "${slug}/${slug}_${src_lang}.srt"
```

- `large-v3`: higher accuracy than `turbo` (use `turbo` if speed is priority)
- `--language`: explicitly set to avoid misdetection; supports `en`, `ja`, `ko`, `es`, etc.
- `--word_timestamps True`: more precise subtitle timing
- `--condition_on_previous_text False`: prevent hallucination loops

### Step 2.5: Validate & Fix (optional)

```bash
python3 "$SKILL_DIR/scripts/srt_utils.py" validate "${slug}/${slug}_${src_lang}.srt"
# If issues found:
python3 "$SKILL_DIR/scripts/srt_utils.py" fix "${slug}/${slug}_${src_lang}.srt" "${slug}/${slug}_${src_lang}.srt"
```

### Step 3: Translate

Read `{slug}_{src_lang}.srt` and translate to Chinese. **Critical rules:**

1. **Keep SRT format intact** — preserve index numbers, timestamps (`-->` lines) exactly as-is
2. **1:1 entry mapping** — every source entry must produce exactly one translated entry (same count)
3. **Keep each Chinese entry on 1 line, ≤18 chars** — translate concisely; bilingual result = 2 lines total (EN + ZH)
4. **Translate in batches of 10 entries** — output each batch in valid SRT format, then continue
5. **Do NOT merge or split entries** — maintain original segmentation
6. Save as `{slug}/{slug}_zh.srt`, then run segment to enforce line length:

```bash
python3 "$SKILL_DIR/scripts/srt_utils.py" segment \
  "${slug}/${slug}_zh.srt" "${slug}/${slug}_zh.srt" 18
```

### Step 4: Merge

```bash
python3 "$SKILL_DIR/scripts/srt_utils.py" merge \
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

Based on the video content (from `{slug}_{src_lang}.srt` and `{slug}_zh.srt`), generate `{slug}/publish_info.md`:

```markdown
# 发布信息

## 来源
{YouTube URL}

## 标题（5个版本）
1. {标题1 — 悬念/反问式，引发好奇}
2. {标题2 — 数据/成就驱动，强调结果}
3. {标题3 — 争议/观点式，引发讨论}
4. {标题4 — 教程/干货式，强调实用}
5. {标题5 — 情绪/共鸣式，贴近用户}

## 标签
{10个左右逗号分隔的关键词，覆盖主题、技术、领域}

## 简介
{3-5句，概括视频核心内容和看点，吸引点击}

## 章节时间戳
00:00 {章节名}
...
```

**生成要求：**
- 标题风格符合 B 站用户习惯：口语化、有悬念、善用符号（【】、？、！）
- 标签同时覆盖中英文关键词，便于搜索
- 时间戳从 `{slug}_bilingual.srt` 中按内容主题变化点提取
- 简介要有 hook，前两句决定用户是否展开阅读

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
python3 "$SKILL_DIR/scripts/srt_utils.py" merge en.srt zh.srt output.srt    # Merge bilingual
python3 "$SKILL_DIR/scripts/srt_utils.py" segment zh.srt out.srt [max=18]   # Trim to 1 line
python3 "$SKILL_DIR/scripts/srt_utils.py" validate input.srt [max_chars=40]  # Check for issues
python3 "$SKILL_DIR/scripts/srt_utils.py" fix input.srt output.srt           # Fix timing/overlaps
python3 "$SKILL_DIR/scripts/srt_utils.py" slugify "Video Title"              # Generate slug
```

## Common Mistakes

- **Mismatched entry counts**: Merge pads with placeholders — review and fix manually
- **Long Chinese lines**: Always segment to ≤18 chars (single line) before merging
- **Font not found**: Ensure PingFang SC is installed (macOS default) or substitute
