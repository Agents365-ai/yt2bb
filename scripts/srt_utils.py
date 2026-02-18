#!/usr/bin/env python3
"""SRT utilities for yt2bb - merge bilingual subtitles."""

import re
import sys
from pathlib import Path

# Import from netflix-subtitle-processor to avoid duplication
sys.path.insert(0, str(Path.home() / '.claude/skills/netflix-subtitle-processor/scripts'))
from netflix_subs import parse_srt, write_srt

def segment_chinese(text, max_chars=20):
    """Break Chinese text into lines of max_chars."""
    if len(text) <= max_chars:
        return text
    punctuation = '，。！？、；：""''）》】'
    lines, current = [], ''
    for char in text:
        current += char
        if len(current) >= max_chars or char in punctuation:
            lines.append(current.strip())
            current = ''
    if current.strip():
        lines.append(current.strip())
    return '\n'.join(lines)

def merge_bilingual(en_entries, zh_entries):
    """Merge EN and ZH entries into bilingual format (EN on top, ZH below)."""
    en_count, zh_count = len(en_entries), len(zh_entries)
    if en_count != zh_count:
        print(f"Warning: EN={en_count}, ZH={zh_count}. Padding shorter list.", file=sys.stderr)
        # Pad shorter list
        if en_count > zh_count:
            for i in range(zh_count, en_count):
                zh_entries.append({'index': i+1, 'start': en_entries[i]['start'],
                    'end': en_entries[i]['end'], 'text': '[翻译缺失]'})
        else:
            for i in range(en_count, zh_count):
                en_entries.append({'index': i+1, 'start': zh_entries[i]['start'],
                    'end': zh_entries[i]['end'], 'text': '[Translation missing]'})

    return [{'index': i, 'start': en['start'], 'end': en['end'],
             'text': f"{en['text']}\n{zh['text']}"}
            for i, (en, zh) in enumerate(zip(en_entries, zh_entries), 1)]

def slugify(title):
    """Convert title to URL-safe slug."""
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  srt_utils.py merge <en.srt> <zh.srt> <output.srt>")
        print("  srt_utils.py segment <zh.srt> <output.srt> [max_chars=20]")
        print("  srt_utils.py slugify <title>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'merge':
        en_path, zh_path, out_path = sys.argv[2:5]
        merged = merge_bilingual(parse_srt(en_path), parse_srt(zh_path))
        write_srt(merged, out_path)
        print(f"Merged {len(merged)} entries -> {out_path}")
    elif cmd == 'segment':
        zh_path, out_path = sys.argv[2:4]
        max_chars = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        entries = parse_srt(zh_path)
        for e in entries:
            e['text'] = segment_chinese(e['text'], max_chars)
        write_srt(entries, out_path)
        print(f"Segmented {len(entries)} entries -> {out_path}")
    elif cmd == 'slugify':
        print(slugify(' '.join(sys.argv[2:])))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
