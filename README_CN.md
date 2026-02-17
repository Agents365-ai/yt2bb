# yt2bb - YouTube 视频转 Bilibili

一个 Claude Code 技能，用于将 YouTube 视频转制成带双语字幕（英文/中文）的 Bilibili 视频。

## 功能

- **下载** YouTube 视频 (yt-dlp)
- **转录** 音频 (OpenAI Whisper)
- **校对** 交互式校对字幕
- **翻译** 使用 Claude 翻译成中文
- **合并** 双语字幕（英文在上，中文在下）
- **烧录** 使用 FFmpeg 将字幕嵌入视频
- **播放列表** 支持进度追踪
- **断点续传** 支持中断恢复

## 安装

本技能专为 [Claude Code](https://claude.ai/claude-code) 设计。克隆到 skills 目录：

```bash
git clone https://github.com/Agents365-ai/yt2bb.git ~/.claude/skills/yt2bb
```

### 依赖

```bash
pip install openai-whisper
brew install ffmpeg yt-dlp
```

## 使用方法

### 通过 Claude Code

```
/yt2bb https://www.youtube.com/watch?v=VIDEO_ID
```

### 工作流程

| 步骤 | 操作 | 输出 |
|------|------|------|
| 1 | 下载视频 | `{slug}.mp4` |
| 2 | Whisper 转录 | `{slug}_en.srt` |
| 3 | 交互式校对 | `{slug}_en.srt`（修订版）|
| 4 | 翻译成中文 | `{slug}_zh.srt` |
| 5 | 合并双语字幕 | `{slug}_bilingual.srt` |
| 6 | 烧录字幕 | `{slug}_bilingual.mp4` |

### 输出结构

```
{video-slug}/
├── {slug}.mp4                  # 下载的视频
├── {slug}_en.srt               # 英文字幕
├── {slug}_zh.srt               # 中文字幕
├── {slug}_bilingual.srt        # 双语字幕
├── {slug}_bilingual.mp4        # 最终输出
└── .tmp/                       # 临时文件
```

## 工具脚本

```bash
# 合并英文和中文字幕
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py merge en.srt zh.srt output.srt

# 检查工作流状态
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py status ./video-dir

# 检查播放列表进度
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py playlist-progress ./playlist-dir

# 从标题生成 slug
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py slugify "视频标题"
```

## 字幕样式

烧录的字幕使用：
- 字体：PingFang SC (macOS) / Microsoft YaHei (Windows)
- 颜色：黄色字体，黑色描边
- 位置：底部居中，边距 30px

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)

## 支持

<div align="center">

如果这个项目对你有帮助，欢迎请我喝杯咖啡！

| 微信支付 | 支付宝 |
|:-------:|:------:|
| <img src="images/wechat-pay.png" width="200" alt="微信支付"> | <img src="images/alipay.png" width="200" alt="支付宝"> |

</div>

---

**探索未至之境**

[![GitHub](https://img.shields.io/badge/GitHub-Agents365--ai-blue?logo=github)](https://github.com/Agents365-ai)
[![Bilibili](https://img.shields.io/badge/Bilibili-441831884-pink?logo=bilibili)](https://space.bilibili.com/441831884)
