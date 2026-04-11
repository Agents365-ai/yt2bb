# yt2bb - YouTube to Bilibili Video Repurposing

[中文文档](README_CN.md)

A Claude Code skill that repurposes YouTube videos for Bilibili with bilingual (EN/ZH) hardcoded subtitles.

Compatible with **Claude Code**, **OpenClaw**, **Hermes Agent**, **Pi (pi-mono)**, and indexed by **SkillsMP**.

## Workflow

```
YouTube → yt-dlp → whisper → validate → translate → merge → ffmpeg → publish_info → Bilibili
```

| Step | Tool | Output |
|------|------|--------|
| Download | `yt-dlp` | `.mp4` |
| Transcribe | `whisper` | `_{lang}.srt` |
| Validate/Fix | `srt_utils.py` | `_{lang}.srt` (fixed) |
| Translate | AI | `_zh.srt` |
| Merge | `srt_utils.py` | `_bilingual.srt` |
| Burn | `ffmpeg` | `_bilingual.mp4` |
| Publish Info | AI | `publish_info.md` |

## Usage

```
/yt2bb https://www.youtube.com/watch?v=VIDEO_ID
```

## Installation

### Claude Code

```bash
git clone https://github.com/Agents365-ai/yt2bb.git ~/.claude/skills/yt2bb
```

### OpenClaw

```bash
git clone https://github.com/Agents365-ai/yt2bb.git ~/.openclaw/skills/yt2bb
```

### Hermes Agent

```bash
git clone https://github.com/Agents365-ai/yt2bb.git ~/.hermes/skills/media/yt2bb
```

### Pi (pi-mono)

```bash
git clone https://github.com/Agents365-ai/yt2bb.git ~/.pi/agent/skills/yt2bb
```

### Prerequisites

- Python 3
- [ffmpeg](https://ffmpeg.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [openai-whisper](https://github.com/openai/whisper)
- YouTube account logged in via Chrome browser (yt-dlp extracts cookies automatically)

## Utility Script

```bash
# Detect platform and recommend whisper backend + model
python3 srt_utils.py check-whisper

# Merge EN and ZH subtitles
python3 srt_utils.py merge en.srt zh.srt output.srt

# Validate timing issues
python3 srt_utils.py validate input.srt

# Lint against Netflix Timed Text Style Guide (CPS, duration, line length, gaps)
python3 srt_utils.py lint bilingual.srt

# Fix timing overlaps
python3 srt_utils.py fix input.srt output.srt

# Convert to styled ASS (presets: netflix, clean, glow)
# Presets stay bottom-aligned and scale with resolution
# `netflix` = broadcast-grade: white text, thin outline, soft shadow, no box
python3 srt_utils.py to_ass bilingual.srt bilingual.ass --preset netflix
python3 srt_utils.py to_ass bilingual.srt bilingual.ass --style-file custom.ass

# Generate slug from title
python3 srt_utils.py slugify "Video Title"
```

All subcommands support `--format json` for structured agent-friendly output. `merge` and `to_ass` support `--dry-run` to validate inputs without writing files.

## Subtitle Preset Previews

All three presets rendered on the same 1920×1080 background, so you can compare typography, layout, and contrast at a glance.

| Preset | Preview | Use case |
|---|---|---|
| `netflix` | ![netflix preset preview](docs/presets/netflix.png) | **Default for professional content.** Pure white text, thin black outline, soft drop shadow, no box. Modeled on the Netflix Timed Text Style Guide. Best for documentaries, interviews, and long-form video. |
| `clean` | ![clean preset preview](docs/presets/clean.png) | **Readability safety net.** Golden-yellow text on a semi-transparent gray box. Use when `netflix`'s outline could get visually lost on busy or bright-heavy footage — the box guarantees a contrast pad. |
| `glow` | ![glow preset preview](docs/presets/glow.png) | **Entertainment / vlog.** Yellow ZH + white EN with a colored outer glow. Most eye-catching, least subtle — best for high-energy edits and B站-style content. |

To regenerate these images after changing a preset, run:

```bash
bash docs/presets/render_previews.sh
```

The script renders each preset against a neutral gradient background using the committed `docs/presets/sample.srt` fixture and writes `docs/presets/{preset}.png`.

## License

MIT License

## Support

If this project helps you, consider supporting the author:

<table>
  <tr>
    <td align="center">
      <img src="https://raw.githubusercontent.com/Agents365-ai/images_payment/main/qrcode/wechat-pay.png" width="180" alt="WeChat Pay">
      <br>
      <b>WeChat Pay</b>
    </td>
    <td align="center">
      <img src="https://raw.githubusercontent.com/Agents365-ai/images_payment/main/qrcode/alipay.png" width="180" alt="Alipay">
      <br>
      <b>Alipay</b>
    </td>
    <td align="center">
      <img src="https://raw.githubusercontent.com/Agents365-ai/images_payment/main/qrcode/buymeacoffee.png" width="180" alt="Buy Me a Coffee">
      <br>
      <b>Buy Me a Coffee</b>
    </td>
  </tr>
</table>

---

**探索未至之境**

[![GitHub](https://img.shields.io/badge/GitHub-Agents365--ai-blue?logo=github)](https://github.com/Agents365-ai)
[![Bilibili](https://img.shields.io/badge/Bilibili-441831884-pink?logo=bilibili)](https://space.bilibili.com/441831884)
