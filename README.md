# yt2bb - YouTube to Bilibili Video Repurposing

A Claude Code skill for repurposing YouTube videos for Bilibili with bilingual (English/Chinese) subtitles.

## Features

- **Download** YouTube videos with yt-dlp
- **Transcribe** audio using OpenAI Whisper
- **Proofread** transcripts interactively
- **Translate** to Chinese with Claude
- **Merge** bilingual subtitles (EN on top, ZH below)
- **Burn** subtitles into video with FFmpeg
- **Playlist** support with progress tracking
- **Resume** capability for interrupted workflows

## Installation

This skill is designed for use with [Claude Code](https://claude.ai/claude-code). Clone to your skills directory:

```bash
git clone https://github.com/Agents365-ai/yt2bb.git ~/.claude/skills/yt2bb
```

### Dependencies

```bash
pip install openai-whisper
brew install ffmpeg yt-dlp
```

## Usage

### With Claude Code

```
/yt2bb https://www.youtube.com/watch?v=VIDEO_ID
```

### Workflow

| Step | Action | Output |
|------|--------|--------|
| 1 | Download video | `{slug}.mp4` |
| 2 | Transcribe with Whisper | `{slug}_en.srt` |
| 3 | Interactive proofreading | `{slug}_en.srt` (revised) |
| 4 | Translate to Chinese | `{slug}_zh.srt` |
| 5 | Merge bilingual | `{slug}_bilingual.srt` |
| 6 | Burn subtitles | `{slug}_bilingual.mp4` |

### Output Structure

```
{video-slug}/
├── {slug}.mp4                  # Downloaded video
├── {slug}_en.srt               # English transcript
├── {slug}_zh.srt               # Chinese translation
├── {slug}_bilingual.srt        # Merged bilingual
├── {slug}_bilingual.mp4        # Final output
└── .tmp/                       # Temporary files
```

## Utility Scripts

```bash
# Merge EN and ZH subtitles
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py merge en.srt zh.srt output.srt

# Check workflow status
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py status ./video-dir

# Check playlist progress
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py playlist-progress ./playlist-dir

# Generate slug from title
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py slugify "Video Title"
```

## Subtitle Style

Burned subtitles use:
- Font: PingFang SC (macOS) / Microsoft YaHei (Windows)
- Color: Yellow with black outline
- Position: Bottom center with 30px margin

## License

MIT License - see [LICENSE](LICENSE)

## Support

<div align="center">

If this project helps you, consider buying me a coffee!

| WeChat Pay | Alipay |
|:----------:|:------:|
| <img src="images/wechat-pay.png" width="200" alt="WeChat Pay"> | <img src="images/alipay.png" width="200" alt="Alipay"> |

</div>

---

**探索未至之境**

[![GitHub](https://img.shields.io/badge/GitHub-Agents365--ai-blue?logo=github)](https://github.com/Agents365-ai)
[![Bilibili](https://img.shields.io/badge/Bilibili-441831884-pink?logo=bilibili)](https://space.bilibili.com/441831884)
