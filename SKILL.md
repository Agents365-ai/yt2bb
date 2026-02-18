---
name: yt2bb
description: Use when repurposing YouTube videos for Bilibili with bilingual subtitles. Orchestrates video-downloader, openai-whisper-guide, netflix-subtitle-processor, and ffmpeg skills.
---

# yt2bb - YouTube to Bilibili Video Repurposing

## Quick Start

```
/yt2bb https://www.youtube.com/watch?v=VIDEO_ID
```

## Workflow

| Step | Skill | Output |
|------|-------|--------|
| 1 | `video-downloader` | `{slug}.mp4` |
| 2 | `openai-whisper-guide` | `{slug}_en.srt` |
| 3 | `netflix-subtitle-processor` | `{slug}_en.srt` (validated) |
| 4 | Claude translation | `{slug}_zh.srt` |
| 5 | `srt_utils.py merge` | `{slug}_bilingual.srt` |
| 6 | `ffmpeg` | `{slug}_bilingual.mp4` |

## Step 1: Download

Use `video-downloader` skill:
```
/video-downloader {youtube_url}
```

Create directory and move:
```bash
slug="video-name"
mkdir -p "${slug}" && mv downloaded.mp4 "${slug}/${slug}.mp4"
```

## Step 2: Transcribe

Use `openai-whisper-guide` skill:
```bash
whisper "${slug}.mp4" --model turbo --output_format srt \
  --max_line_width 42 --max_line_count 2
mv "${slug}.srt" "${slug}_en.srt"
```

## Step 3: Validate Subtitles

Use `netflix-subtitle-processor` skill:
```bash
python3 ~/.claude/skills/netflix-subtitle-processor/scripts/netflix_subs.py \
  fix "${slug}_en.srt" "${slug}_en.srt" --lang en
```

## Step 4: Translate

Interactive translation with Claude:
- Read `{slug}_en.srt`
- Translate to Chinese in batches of 10
- Max 20 chars per line for Chinese
- Save as `{slug}_zh.srt`

## Step 5: Merge

```bash
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py merge \
  "${slug}_en.srt" "${slug}_zh.srt" "${slug}_bilingual.srt"
```

## Step 6: Burn Subtitles

Use `ffmpeg` skill:
```bash
ffmpeg -i "${slug}.mp4" \
  -vf "subtitles='${slug}_bilingual.srt':force_style='FontName=PingFang SC,FontSize=22,PrimaryColour=&H00FFFF,OutlineColour=&H000000,Outline=2,MarginV=30'" \
  -c:a copy "${slug}_bilingual.mp4"
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

## Utility Commands

```bash
# Merge subtitles
srt_utils.py merge en.srt zh.srt output.srt

# Generate slug
srt_utils.py slugify "Video Title"
```

## Related Skills

- `video-downloader` - Download YouTube videos
- `openai-whisper-guide` - Transcription
- `netflix-subtitle-processor` - Subtitle validation
- `ffmpeg` - Video processing
