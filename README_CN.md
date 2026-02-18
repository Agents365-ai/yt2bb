# yt2bb - YouTube 视频转 Bilibili

一个 Claude Code 技能，整合多个技能将 YouTube 视频转制成带双语字幕的 Bilibili 视频。

## 工作流程

```
YouTube → video-downloader → openai-whisper-guide → netflix-subtitle-processor → 翻译 → ffmpeg → Bilibili
```

| 步骤 | 使用技能 | 输出 |
|------|----------|------|
| 下载 | `video-downloader` | `.mp4` |
| 转录 | `openai-whisper-guide` | `_en.srt` |
| 验证 | `netflix-subtitle-processor` | `_en.srt`（修复）|
| 翻译 | Claude | `_zh.srt` |
| 合并 | `srt_utils.py` | `_bilingual.srt` |
| 烧录 | `ffmpeg` | `_bilingual.mp4` |

## 使用方法

```
/yt2bb https://www.youtube.com/watch?v=VIDEO_ID
```

## 安装

```bash
git clone https://github.com/Agents365-ai/yt2bb.git ~/.claude/skills/yt2bb
```

### 依赖技能

- `video-downloader` 技能
- `openai-whisper-guide` 技能
- `netflix-subtitle-processor` 技能
- `ffmpeg` 技能

## 工具脚本

```bash
# 合并英文和中文字幕（从 netflix-subtitle-processor 导入 parse_srt/write_srt）
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py merge en.srt zh.srt output.srt

# 中文断行（每行最多20字）
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py segment zh.srt zh_segmented.srt

# 从标题生成 slug
python3 ~/.claude/skills/yt2bb/scripts/srt_utils.py slugify "视频标题"
```

## 许可证

MIT 许可证

---

**探索未至之境**

[![GitHub](https://img.shields.io/badge/GitHub-Agents365--ai-blue?logo=github)](https://github.com/Agents365-ai)
[![Bilibili](https://img.shields.io/badge/Bilibili-441831884-pink?logo=bilibili)](https://space.bilibili.com/441831884)
