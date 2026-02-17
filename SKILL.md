---
name: yt2bb
description: Use when repurposing YouTube videos for Bilibili with bilingual subtitles. Handles download, transcription, translation, and subtitle burning.
---

# yt2bb - YouTube to Bilibili Video Repurposing

## Quick Start

```
/yt2bb https://www.youtube.com/watch?v=VIDEO_ID
```

## Workflow Overview

| Step | Action | Tool/Method | Output |
|------|--------|-------------|--------|
| 1 | Download | `video-downloader` skill | `{slug}.mp4` |
| 2 | Transcribe | whisper.cpp | `{slug}_en.srt` |
| 3 | Proofread | Interactive review | `{slug}_en.srt` (revised) |
| 4 | Translate | Claude interactive | `{slug}_zh.srt` |
| 5 | Merge | `srt_utils.py` | `{slug}_bilingual.srt` |
| 6 | Burn | `ffmpeg` skill | `{slug}_bilingual.mp4` |

## File Structure

### Single Video
```
{cwd}/
└── {video-slug}/
    ├── {slug}.mp4                  # Downloaded video (CORE)
    ├── {slug}_en.srt               # English transcript (CORE)
    ├── {slug}_zh.srt               # Chinese translation (CORE)
    ├── {slug}_bilingual.srt        # Merged bilingual (CORE)
    ├── {slug}_bilingual.mp4        # Final output (CORE)
    └── .tmp/                       # Temporary files
        ├── {slug}_raw.srt          # Raw whisper output
        └── {slug}_en_backup.srt    # Pre-proofread backup
```

### Playlist
```
{cwd}/
└── {playlist-name}/
    ├── 01_{video-slug-1}/
    │   └── (same structure as single video)
    ├── 02_{video-slug-2}/
    └── ...
```

## Playlist Workflow

**Detect playlist URL:**
```bash
# Check if URL contains 'list=' or '/playlist'
echo "{url}" | grep -E 'list=|/playlist'
```

**Get video list with yt-dlp:**
```bash
yt-dlp --flat-playlist --print "%(playlist_index)s %(title)s" "{playlist_url}"
```

**Create numbered directories:**
```bash
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py slugify "Video Title Here"
# Output: video-title-here
```

**Check playlist progress:**
```bash
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py playlist-progress "{playlist_dir}"
```

**Process each video:**
1. Download video to `{playlist_dir}/{NN}_{slug}/`
2. Run standard 6-step workflow for each
3. Check progress between videos

## Core Files Checklist

Before completing workflow, verify ALL core files exist:
- [ ] `{slug}.mp4` - Source video
- [ ] `{slug}_en.srt` - English subtitles
- [ ] `{slug}_zh.srt` - Chinese subtitles
- [ ] `{slug}_bilingual.srt` - Merged bilingual subtitles
- [ ] `{slug}_bilingual.mp4` - Final video with burned subtitles

## Resume Capability

If workflow is interrupted, the skill saves progress to `.yt2bb_status.json`.

**Check for resume on start:**
```bash
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py status "{cwd}/${slug}"
```

**Save progress after each step:**
```bash
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py save-status "{cwd}/${slug}" <step> <slug> [last_batch=N]
```

**Clear status after successful completion:**
```bash
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py clear-status "{cwd}/${slug}"
```

## Step-by-Step Instructions

### Step 1: Download Video

Use the `video-downloader` skill:
```
/video-downloader {youtube_url}
```

Create output directory and move video:
```bash
slug=$(echo "{video_title}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//')
mkdir -p "{cwd}/${slug}"
mv "{downloaded_video}" "{cwd}/${slug}/${slug}.mp4"
```

### Step 2: Transcribe with Whisper

```bash
cd "{cwd}/${slug}"
mkdir -p .tmp

# Run OpenAI Whisper with Netflix-style settings
whisper "{slug}.mp4" \
  --model turbo \
  --language en \
  --output_format srt \
  --output_dir .tmp \
  --max_line_width 42 \
  --max_line_count 1

# Whisper outputs {input_basename}.srt, rename to our convention
mv ".tmp/${slug}.srt" ".tmp/${slug}_raw.srt"
cp ".tmp/${slug}_raw.srt" "${slug}_en.srt"
```

**Note**: Model options: `tiny`, `base`, `small`, `medium`, `large`, `turbo` (default).
Use `large` for best accuracy, `turbo` for speed/quality balance.

### Step 3: Interactive Proofreading

1. Read the English SRT file
2. Present to user in batches of 10 entries
3. User can:
   - Accept batch as-is
   - Edit specific lines (provide line numbers and corrections)
   - Request re-transcription of specific segments
4. Save backup before editing: `cp {slug}_en.srt .tmp/{slug}_en_backup.srt`
5. Apply corrections and continue to next batch

### Step 4: Interactive Translation

1. Read proofread English SRT
2. Translate in batches of 10 entries to Chinese
3. Apply Chinese text rules:
   - Max 20 characters per line (wider glyphs)
   - Natural sentence breaks
4. Present translation for user review
5. User can accept or request revisions
6. Save as `{slug}_zh.srt`

### Step 5: Merge Bilingual Subtitles

Run the merge script:
```bash
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py merge \
  "{slug}_en.srt" \
  "{slug}_zh.srt" \
  "{slug}_bilingual.srt"
```

### Step 6: Burn Subtitles

Use the `ffmpeg` skill with these parameters:
```bash
ffmpeg -i "{slug}.mp4" \
  -vf "subtitles='{slug}_bilingual.srt':force_style='FontName=PingFang SC,FontSize=22,PrimaryColour=&H00FFFF,OutlineColour=&H000000,Outline=2,Shadow=0,Alignment=2,MarginV=30'" \
  -c:a copy \
  "{slug}_bilingual.mp4"
```

Style explanation:
- `FontName=PingFang SC` - macOS Chinese font (use "Microsoft YaHei" on Windows)
- `FontSize=22` - Readable size
- `PrimaryColour=&H00FFFF` - Yellow text (BGR format)
- `OutlineColour=&H000000` - Black outline
- `Outline=2` - 2px outline thickness
- `Alignment=2` - Bottom center
- `MarginV=30` - 30px from bottom

## Post-Workflow Verification

**CRITICAL: Before completing, run this checklist:**

```bash
cd "{cwd}/${slug}"

# Check all core files exist
echo "=== Core Files Check ==="
for f in "${slug}.mp4" "${slug}_en.srt" "${slug}_zh.srt" "${slug}_bilingual.srt" "${slug}_bilingual.mp4"; do
  if [ -f "$f" ]; then
    echo "✓ $f exists ($(du -h "$f" | cut -f1))"
  else
    echo "✗ $f MISSING!"
  fi
done
```

If any core file is missing, DO NOT proceed to cleanup. Investigate and fix first.

## Cleanup (User Choice)

After successful verification, ask user:

> All core files verified. Would you like to clean up temporary files in `.tmp/`?
> - **No** (default) - Keep temporary files for debugging
> - **Yes** - Delete `.tmp/` directory

Only if user explicitly chooses "Yes":
```bash
rm -rf "{cwd}/${slug}/.tmp"
```

## Subtitle Format Reference

### English SRT (after whisper)
```
1
00:00:01,000 --> 00:00:03,500
Hello everyone, welcome to today's video

2
00:00:03,500 --> 00:00:06,000
Today we'll talk about machine learning
```

### Chinese SRT
```
1
00:00:01,000 --> 00:00:03,500
大家好，欢迎收看今天的视频

2
00:00:03,500 --> 00:00:06,000
今天我们来聊聊机器学习
```

### Bilingual SRT (merged)
```
1
00:00:01,000 --> 00:00:03,500
Hello everyone, welcome to today's video
大家好，欢迎收看今天的视频

2
00:00:03,500 --> 00:00:06,000
Today we'll talk about machine learning
今天我们来聊聊机器学习
```

## Dependencies

- **OpenAI Whisper** - `pip install openai-whisper`
- **ffmpeg** - Via Homebrew (required by Whisper)
- **yt-dlp** - Via video-downloader skill
- **Python 3** - Standard library only for srt_utils

## Troubleshooting

### Whisper not found
```bash
pip install openai-whisper
# or with conda/mamba:
conda install -c conda-forge openai-whisper
```

### Font not found (subtitle burning)
- macOS: Use "PingFang SC"
- Windows: Use "Microsoft YaHei"
- Linux: Use "Noto Sans CJK SC"

### Subtitle timing mismatch
- Re-run Step 5 (merge) after fixing individual SRT files
- Ensure EN and ZH have same number of entries
