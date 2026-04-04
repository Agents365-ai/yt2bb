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

Six-step pipeline: download → transcribe → translate → merge → burn subtitles → generate publish info. Produces a video with hardcoded bilingual (EN/ZH) subtitles and a `publish_info.md` with Bilibili upload metadata.

## When to Use

- User provides a YouTube URL and wants a Bilibili-ready version
- User needs bilingual EN-ZH subtitles burned into video
- User wants to repurpose English video content for Chinese audience

## Quick Reference

| Step | Skill | Command | Output |
|------|-------|---------|--------|
| 1. Download | `yt-dlp` | `yt-dlp --cookies-from-browser chrome -o ...` | `{slug}.mp4` |
| 2. Transcribe | `whisper` | `whisper ... --model large-v3 --output_format srt` | `{slug}_en.srt` |
| 3. Translate | Claude | Batch translate, max 20 chars/line | `{slug}_zh.srt` |
| 4. Merge | `srt_utils.py` | `srt_utils.py merge ...` | `{slug}_bilingual.srt` |
| 5. Burn | `ffmpeg` | `ffmpeg -vf subtitles=...` | `{slug}_bilingual.mp4` |
| 6. Publish Info | Claude | Analyze video content, generate metadata | `publish_info.md` |

## Pipeline Details

### Step 1: Download

```bash
slug="video-name"  # or: slug=$(python3 scripts/srt_utils.py slugify "Video Title")
mkdir -p "${slug}"
yt-dlp --cookies-from-browser chrome -o "${slug}/${slug}.mp4" "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Step 2: Transcribe

```bash
whisper "${slug}/${slug}.mp4" \
  --model large-v3 \
  --language en \
  --word_timestamps True \
  --condition_on_previous_text False \
  --output_format srt \
  --max_line_width 42 --max_line_count 2 \
  --output_dir "${slug}"
mv "${slug}/${slug}.srt" "${slug}/${slug}_en.srt"
```

- `large-v3`: higher accuracy than `turbo` (use `turbo` if speed is priority)
- `--language en`: avoid misdetection; change if source is not English
- `--word_timestamps True`: more precise subtitle timing
- `--condition_on_previous_text False`: prevent hallucination loops

### Step 2.5: Validate & Fix (optional)

```bash
python3 scripts/srt_utils.py validate "${slug}/${slug}_en.srt"
# If issues found:
python3 scripts/srt_utils.py fix "${slug}/${slug}_en.srt" "${slug}/${slug}_en.srt"
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

### Step 6: Generate Publish Info

Based on the video content (from `{slug}_en.srt` and `{slug}_zh.srt`), generate `{slug}/publish_info.md`:

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
├── {slug}_en.srt           # English subtitles
├── {slug}_zh.srt           # Chinese subtitles
├── {slug}_bilingual.srt    # Merged bilingual
├── {slug}_bilingual.mp4    # Final output
└── publish_info.md         # Bilibili upload metadata
```

## Utility: srt_utils.py

```bash
python3 scripts/srt_utils.py merge en.srt zh.srt output.srt    # Merge bilingual
python3 scripts/srt_utils.py segment zh.srt out.srt [max=20]   # Break long lines
python3 scripts/srt_utils.py validate input.srt [max_chars=42]  # Check for issues
python3 scripts/srt_utils.py fix input.srt output.srt           # Fix timing/overlaps
python3 scripts/srt_utils.py slugify "Video Title"              # Generate slug
```

## Common Mistakes

- **Mismatched entry counts**: Merge pads with placeholders — review and fix manually
- **Long Chinese lines**: Always segment to ≤20 chars before merging
- **Font not found**: Ensure PingFang SC is installed (macOS default) or substitute
