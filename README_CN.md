# yt2bb - YouTube 视频转 Bilibili

[English](README.md)

一个 Claude Code 技能，将 YouTube 视频转制成带双语（中英）硬字幕的 Bilibili 视频。

兼容 **Claude Code**、**OpenClaw**、**Hermes Agent**、**Pi (pi-mono)**，并可被 **SkillsMP** 索引。

## 工作流程

```
YouTube → yt-dlp → whisper → 校验 → 翻译 → 合并 → ffmpeg → 发布信息 → Bilibili
```

| 步骤 | 工具 | 输出 |
|------|------|------|
| 下载 | `yt-dlp` | `.mp4` |
| 转录 | `whisper` | `_{lang}.srt` |
| 校验修复 | `srt_utils.py` | `_{lang}.srt`（修复）|
| 翻译 | AI | `_zh.srt` |
| 合并 | `srt_utils.py` | `_bilingual.srt` |
| 烧录 | `ffmpeg` | `_bilingual.mp4` |
| 发布信息 | AI | `publish_info.md` |

## 使用方法

```
/yt2bb https://www.youtube.com/watch?v=VIDEO_ID
```

## 安装

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

### 前置依赖

- Python 3
- [ffmpeg](https://ffmpeg.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [openai-whisper](https://github.com/openai/whisper)
- Chrome 浏览器需登录 YouTube 帐号（yt-dlp 自动提取 cookies）

## 工具脚本

```bash
# 检测平台并推荐 whisper 后端和模型
python3 srt_utils.py check-whisper

# 合并英文和中文字幕
python3 srt_utils.py merge en.srt zh.srt output.srt

# 校验时间轴问题
python3 srt_utils.py validate input.srt

# 修复时间轴重叠
python3 srt_utils.py fix input.srt output.srt

# 转为带样式的 ASS 字幕（预设: clean, cinema, glow）
python3 srt_utils.py to_ass bilingual.srt bilingual.ass --preset clean
python3 srt_utils.py to_ass bilingual.srt bilingual.ass --style-file custom.ass

# 从标题生成 slug
python3 srt_utils.py slugify "视频标题"
```

所有子命令支持 `--format json` 输出结构化数据，方便 AI Agent 调用。`merge` 和 `to_ass` 支持 `--dry-run` 预检输入而不写入文件。

## 许可证

MIT 许可证

## 支持

如果这个项目对你有帮助，欢迎支持作者：

<table>
  <tr>
    <td align="center">
      <img src="https://raw.githubusercontent.com/Agents365-ai/images_payment/main/qrcode/wechat-pay.png" width="180" alt="微信支付">
      <br>
      <b>微信支付</b>
    </td>
    <td align="center">
      <img src="https://raw.githubusercontent.com/Agents365-ai/images_payment/main/qrcode/alipay.png" width="180" alt="支付宝">
      <br>
      <b>支付宝</b>
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
