# yt2bb - YouTube to Bilibili Video Repurposing

A Claude Code skill that repurposes YouTube videos for Bilibili with bilingual (EN/ZH) hardcoded subtitles.

Compatible with **Claude Code**, **OpenClaw**, **Hermes Agent**, and indexed by **SkillsMP**.

## Workflow

```
YouTube → yt-dlp → whisper → validate → translate → merge → ffmpeg → publish_info → Bilibili
```

| Step | Tool | Output |
|------|------|--------|
| Download | `yt-dlp` | `.mp4` |
| Transcribe | `whisper` | `_{lang}.srt` |
| Validate/Fix | `srt_utils.py` | `_{lang}.srt` (fixed) |
| Translate | Claude | `_zh.srt` |
| Merge | `srt_utils.py` | `_bilingual.srt` |
| Burn | `ffmpeg` | `_bilingual.mp4` |
| Publish Info | Claude | `publish_info.md` |

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

### Prerequisites

- Python 3
- [ffmpeg](https://ffmpeg.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [openai-whisper](https://github.com/openai/whisper)
- YouTube account logged in via Chrome browser (yt-dlp extracts cookies automatically)

## Utility Script

```bash
# Merge EN and ZH subtitles
python3 scripts/srt_utils.py merge en.srt zh.srt output.srt

# Segment Chinese text (max 20 chars per line)
python3 scripts/srt_utils.py segment zh.srt zh_segmented.srt

# Generate slug from title
python3 scripts/srt_utils.py slugify "Video Title"
```

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
