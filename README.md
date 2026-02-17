# yt2bb - YouTube to Bilibili Video Repurposing

A Claude Code skill that orchestrates multiple skills to repurpose YouTube videos for Bilibili with bilingual subtitles.

## Workflow

```
YouTube → video-downloader → openai-whisper-guide → netflix-subtitle-processor → translate → ffmpeg → Bilibili
```

| Step | Skill Used | Output |
|------|------------|--------|
| Download | `video-downloader` | `.mp4` |
| Transcribe | `openai-whisper-guide` | `_en.srt` |
| Validate | `netflix-subtitle-processor` | `_en.srt` (fixed) |
| Translate | Claude | `_zh.srt` |
| Merge | `srt_utils.py` | `_bilingual.srt` |
| Burn | `ffmpeg` | `_bilingual.mp4` |

## Usage

```
/yt2bb https://www.youtube.com/watch?v=VIDEO_ID
```

## Installation

```bash
git clone https://github.com/Agents365-ai/yt2bb.git ~/.claude/skills/yt2bb
```

### Dependencies

- `video-downloader` skill
- `openai-whisper-guide` skill
- `netflix-subtitle-processor` skill
- `ffmpeg` skill

## Utility Script

```bash
# Merge EN and ZH subtitles
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py merge en.srt zh.srt output.srt

# Generate slug from title
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py slugify "Video Title"
```

## License

MIT License

---

**探索未至之境**

[![GitHub](https://img.shields.io/badge/GitHub-Agents365--ai-blue?logo=github)](https://github.com/Agents365-ai)
[![Bilibili](https://img.shields.io/badge/Bilibili-441831884-pink?logo=bilibili)](https://space.bilibili.com/441831884)
