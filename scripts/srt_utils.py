#!/usr/bin/env python3
"""SRT utilities for yt2bb - merge bilingual subtitles."""

import re
import sys
from pathlib import Path


def parse_srt(path):
    """Parse SRT file into list of entry dicts."""
    content = sys.stdin.read() if path == '-' else Path(path).read_text(encoding='utf-8')
    entries = []
    for block in re.split(r'\n\n+', content.strip()):
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        m = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if not m:
            continue
        entries.append({'index': int(lines[0]), 'start': m.group(1), 'end': m.group(2),
                        'text': '\n'.join(lines[2:])})
    return entries


def write_srt(entries, path):
    """Write list of entry dicts to SRT file."""
    lines = []
    for i, e in enumerate(entries, 1):
        lines.extend([str(i), f"{e['start']} --> {e['end']}", e['text'], ''])
    output = '\n'.join(lines)
    if path == '-':
        print(output)
    else:
        Path(path).write_text(output, encoding='utf-8')

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

def time_to_ms(ts):
    """Convert SRT timestamp to milliseconds."""
    h, m, rest = ts.split(':')
    s, ms = rest.split(',')
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)

def ms_to_time(ms):
    """Convert milliseconds to SRT timestamp."""
    if ms < 0:
        ms = 0
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    ms_part = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms_part:03d}"

def fix_srt(entries, min_duration_ms=500, min_gap_ms=83):
    """Fix common SRT issues: short durations, overlaps, tiny gaps."""
    fixed = []
    for e in entries:
        e = e.copy()
        start_ms = time_to_ms(e['start'])
        end_ms = time_to_ms(e['end'])
        if end_ms - start_ms < min_duration_ms:
            end_ms = start_ms + min_duration_ms
            e['end'] = ms_to_time(end_ms)
        fixed.append(e)

    # Fix overlaps and tiny gaps
    for i in range(1, len(fixed)):
        prev_start = time_to_ms(fixed[i-1]['start'])
        prev_end = time_to_ms(fixed[i-1]['end'])
        curr_start = time_to_ms(fixed[i]['start'])
        if prev_end > curr_start - min_gap_ms:
            # Try trimming previous end first
            new_end = curr_start - min_gap_ms
            if new_end >= prev_start + min_duration_ms:
                fixed[i-1]['end'] = ms_to_time(new_end)
            else:
                # Can't trim enough — keep prev min duration, push current start forward
                new_end = prev_start + min_duration_ms
                fixed[i-1]['end'] = ms_to_time(new_end)
                new_start = new_end + min_gap_ms
                fixed[i]['start'] = ms_to_time(new_start)

    return fixed

def validate_srt(entries, max_line_chars=42, max_lines=2):
    """Validate SRT entries and report issues."""
    issues = []
    for e in entries:
        start_ms = time_to_ms(e['start'])
        end_ms = time_to_ms(e['end'])
        duration = end_ms - start_ms

        if duration < 500:
            issues.append(f"#{e['index']}: duration {duration}ms < 500ms")
        if duration > 7000:
            issues.append(f"#{e['index']}: duration {duration}ms > 7000ms")

        lines = e['text'].split('\n')
        if len(lines) > max_lines:
            issues.append(f"#{e['index']}: {len(lines)} lines (max {max_lines})")
        for line in lines:
            if len(line) > max_line_chars:
                issues.append(f"#{e['index']}: line too long ({len(line)} > {max_line_chars}): {line[:30]}...")

    # Check overlaps
    for i in range(1, len(entries)):
        prev_end = time_to_ms(entries[i-1]['end'])
        curr_start = time_to_ms(entries[i]['start'])
        if prev_end > curr_start:
            issues.append(f"#{entries[i]['index']}: overlaps previous by {prev_end - curr_start}ms")

    return issues

def slugify(title):
    """Convert title to URL-safe slug."""
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  srt_utils.py merge <en.srt> <zh.srt> <output.srt>")
        print("  srt_utils.py segment <zh.srt> <output.srt> [max_chars=20]")
        print("  srt_utils.py validate <input.srt> [max_line_chars=42]")
        print("  srt_utils.py fix <input.srt> <output.srt>")
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
    elif cmd == 'validate':
        srt_path = sys.argv[2]
        max_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 42
        entries = parse_srt(srt_path)
        issues = validate_srt(entries, max_line_chars=max_chars)
        if issues:
            print(f"Found {len(issues)} issues in {srt_path}:")
            for issue in issues:
                print(f"  {issue}")
            sys.exit(1)
        else:
            print(f"OK: {len(entries)} entries, no issues found")
    elif cmd == 'fix':
        srt_path, out_path = sys.argv[2:4]
        entries = parse_srt(srt_path)
        before = len(validate_srt(entries))
        fixed = fix_srt(entries)
        write_srt(fixed, out_path)
        after = len(validate_srt(fixed))
        print(f"Fixed {len(fixed)} entries -> {out_path} (issues: {before} -> {after})")
    elif cmd == 'slugify':
        print(slugify(' '.join(sys.argv[2:])))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
