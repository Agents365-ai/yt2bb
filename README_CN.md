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

# 按 Netflix Timed Text Style Guide 做 lint（阅读速度 / 时长 / 行长 / 间隔）
python3 srt_utils.py lint bilingual.srt

# 修复时间轴重叠
python3 srt_utils.py fix input.srt output.srt

# 转为带样式的 ASS 字幕（预设: netflix, clean, glow）
# 预设始终贴底显示，并会随分辨率自适应字号和边距
# `netflix` = 广电级：纯白字体 + 细黑描边 + 柔和阴影，无底框
python3 srt_utils.py to_ass bilingual.srt bilingual.ass --preset netflix
python3 srt_utils.py to_ass bilingual.srt bilingual.ass --style-file custom.ass

# 从标题生成 slug
python3 srt_utils.py slugify "视频标题"
```

所有子命令支持 `--format json` 输出结构化数据，方便 AI Agent 调用。`merge` 和 `to_ass` 支持 `--dry-run` 预检输入而不写入文件。

## 字幕预设效果预览

三套预设都在同一张 1920×1080 背景上渲染，方便直接对比字体、布局和对比度。

| 预设 | 效果图 | 适用场景 |
|---|---|---|
| `netflix` | ![netflix 预设预览](docs/presets/netflix.png) | **专业内容首选。** 纯白字体 + 细黑描边 + 柔和阴影，无底框。基于 Netflix Timed Text Style Guide。纪录片、访谈、长视频、所有"流媒体平台感"的内容都用它。 |
| `clean` | ![clean 预设预览](docs/presets/clean.png) | **可读性兜底。** 金黄色字体 + 半透明灰底框。当 `netflix` 的描边可能被花背景吃掉时选它——底框保证对比度。 |
| `glow` | ![glow 预设预览](docs/presets/glow.png) | **娱乐 / Vlog。** 黄色中文 + 白色英文 + 彩色外发光。最抢眼，也最不克制——适合高能剪辑和 B 站风格内容。 |

修改预设后，可通过以下命令重新生成预览图：

```bash
bash docs/presets/render_previews.sh
```

脚本会以 `docs/presets/sample.srt` 为样例在中性渐变背景上渲染每个预设，输出到 `docs/presets/{preset}.png`。

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
