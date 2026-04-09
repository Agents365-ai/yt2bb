#!/usr/bin/env python3
"""SRT utilities for yt2bb - merge bilingual subtitles."""

import argparse
import hashlib
import re
import sys
import unicodedata
from pathlib import Path


def parse_srt(path):
    """Parse SRT file into list of entry dicts. Warns on skipped malformed blocks."""
    content = sys.stdin.read() if path == '-' else Path(path).read_text(encoding='utf-8')
    entries = []
    skipped = 0
    for block in re.split(r'\n\n+', content.strip()):
        lines = block.strip().split('\n')
        if len(lines) < 3:
            skipped += 1
            continue
        m = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if not m:
            skipped += 1
            continue
        entries.append({'index': int(lines[0]), 'start': m.group(1), 'end': m.group(2),
                        'text': '\n'.join(lines[2:])})
    if skipped:
        print(f"Warning: skipped {skipped} malformed block(s) during parsing", file=sys.stderr)
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


def merge_bilingual(en_entries, zh_entries, pad_missing=False):
    """Merge EN and ZH entries into bilingual format (EN on top, ZH below).

    Raises ValueError on count mismatch unless pad_missing=True.
    """
    en_count, zh_count = len(en_entries), len(zh_entries)
    if en_count != zh_count:
        if not pad_missing:
            raise ValueError(
                f"Subtitle count mismatch: EN={en_count}, ZH={zh_count}. "
                f"Use --pad-missing to pad the shorter list instead of failing."
            )
        print(f"Warning: EN={en_count}, ZH={zh_count}. Padding shorter list.", file=sys.stderr)
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
            new_end = curr_start - min_gap_ms
            if new_end >= prev_start + min_duration_ms:
                fixed[i-1]['end'] = ms_to_time(new_end)
            else:
                new_end = prev_start + min_duration_ms
                fixed[i-1]['end'] = ms_to_time(new_end)
                new_start = new_end + min_gap_ms
                fixed[i]['start'] = ms_to_time(new_start)
                curr_end_ms = time_to_ms(fixed[i]['end'])
                if curr_end_ms < new_start + min_duration_ms:
                    fixed[i]['end'] = ms_to_time(new_start + min_duration_ms)

    return fixed


def validate_srt(entries):
    """Validate SRT entries for timing issues."""
    issues = []
    for e in entries:
        start_ms = time_to_ms(e['start'])
        end_ms = time_to_ms(e['end'])
        duration = end_ms - start_ms

        if duration < 500:
            issues.append(f"#{e['index']}: duration {duration}ms < 500ms")
        if duration > 7000:
            issues.append(f"#{e['index']}: duration {duration}ms > 7000ms")

    for i in range(1, len(entries)):
        prev_end = time_to_ms(entries[i-1]['end'])
        curr_start = time_to_ms(entries[i]['start'])
        if prev_end > curr_start:
            issues.append(f"#{entries[i]['index']}: overlaps previous by {prev_end - curr_start}ms")

    return issues


def slugify(title):
    """Convert title to URL-safe slug with Unicode transliteration fallback."""
    normalized = unicodedata.normalize('NFKD', title)
    ascii_title = normalized.encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_title.lower()).strip('-')
    if not slug:
        slug = 'video-' + hashlib.md5(title.encode()).hexdigest()[:8]
    return slug


def _srt_time_to_ass(ts):
    """Convert SRT timestamp (HH:MM:SS,mmm) to ASS format (H:MM:SS.cc)."""
    h, m, rest = ts.split(':')
    s, ms = rest.split(',')
    cs = int(ms) // 10
    return f"{int(h)}:{m}:{s}.{cs:02d}"


def _ass_escape(text):
    """Escape characters that have special meaning in ASS dialogue text."""
    # Curly braces would be interpreted as override tags
    return text.replace('{', r'\{').replace('}', r'\}')


# ASS color format: &HAABBGGRR  (alpha=00 is fully opaque)
# Preset A — Professional Clean: white text, black outline, subtle shadow
_PRESET_CLEAN = {
    'name': 'Professional Clean',
    'styles': [
        # EN line: FontSize=20, bold, white, black outline 2px, shadow 1px, bottom-align MarginV=70
        'Style: EN,{font},20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,70,1',
        # ZH line: FontSize=24, bold, white, black outline 2px, shadow 1px, bottom-align MarginV=35
        'Style: ZH,{font},24,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,35,1',
    ],
    'en_tag': '',
    'zh_tag': '',
}

# Preset B — Cinematic Box: white text on semi-transparent black box, per-line boxes
_PRESET_CINEMA = {
    'name': 'Cinematic Box',
    'styles': [
        # BorderStyle=3 = opaque box; BackColour alpha=80 → 50% transparent black
        'Style: EN,{font},18,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,3,0,0,2,10,10,70,1',
        'Style: ZH,{font},22,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,3,0,0,2,10,10,35,1',
    ],
    'en_tag': '',
    'zh_tag': '',
}

# Preset C — Vibrant Glow: colored text with blurred thick outline for outer glow effect
# EN: white text + amber outer glow (\blur5 blurs the outline into a soft halo)
# ZH: yellow text + deep-orange outer glow
_PRESET_GLOW = {
    'name': 'Vibrant Glow',
    'styles': [
        # OutlineColour &H000080FF = RGB(255,128,0) amber; Outline=5 thick; no shadow
        'Style: EN,{font},20,&H00FFFFFF,&H000000FF,&H000080FF,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,10,10,70,1',
        # PrimaryColour &H0000FFFF = RGB(255,255,0) yellow; OutlineColour &H00003080 = RGB(128,48,0) dark orange
        'Style: ZH,{font},24,&H0000FFFF,&H000000FF,&H00003080,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,10,10,35,1',
    ],
    'en_tag': r'{\blur5}',
    'zh_tag': r'{\blur5}',
}

ASS_PRESETS = {
    'clean': _PRESET_CLEAN,
    'cinema': _PRESET_CINEMA,
    'glow': _PRESET_GLOW,
}

_ASS_STYLE_FORMAT = (
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, '
    'OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
    'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, '
    'Alignment, MarginL, MarginR, MarginV, Encoding'
)


def to_ass(entries, preset='clean', font='PingFang SC', resolution=(1920, 1080)):
    """Convert bilingual SRT entries to a styled ASS file.

    Each bilingual entry (EN\\nZH text) is split into two separate ASS
    Dialogue lines with independent styles, enabling per-line color and
    glow effects not possible with SRT force_style.

    Args:
        entries: list of dicts from parse_srt() on a bilingual SRT
        preset: 'clean' | 'cinema' | 'glow'
        font: font family name (platform-specific)
        resolution: (width, height) of target video
    Returns:
        ASS file content as a string
    """
    p = ASS_PRESETS[preset]
    w, h = resolution
    style_lines = [s.replace('{font}', font) for s in p['styles']]

    header = '\n'.join([
        '[Script Info]',
        f'Title: yt2bb bilingual — {p["name"]}',
        'ScriptType: v4.00+',
        'WrapStyle: 0',
        f'PlayResX: {w}',
        f'PlayResY: {h}',
        'ScaledBorderAndShadow: yes',
        '',
        '[V4+ Styles]',
        _ASS_STYLE_FORMAT,
        '\n'.join(style_lines),
        '',
        '[Events]',
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    ])

    dialogue_lines = []
    for e in entries:
        start = _srt_time_to_ass(e['start'])
        end = _srt_time_to_ass(e['end'])
        # bilingual text is always "EN\nZH" — split on last \n so multi-line EN is preserved
        parts = e['text'].rsplit('\n', 1)
        en_text = _ass_escape(parts[0]) if parts else ''
        zh_text = _ass_escape(parts[1]) if len(parts) > 1 else ''
        if en_text:
            dialogue_lines.append(
                f"Dialogue: 0,{start},{end},EN,,0,0,0,,{p['en_tag']}{en_text}"
            )
        if zh_text:
            dialogue_lines.append(
                f"Dialogue: 0,{start},{end},ZH,,0,0,0,,{p['zh_tag']}{zh_text}"
            )

    return header + '\n' + '\n'.join(dialogue_lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='srt_utils.py')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_merge = sub.add_parser('merge', help='Merge EN and ZH SRT into bilingual SRT')
    p_merge.add_argument('en_srt')
    p_merge.add_argument('zh_srt')
    p_merge.add_argument('output_srt')
    p_merge.add_argument('--pad-missing', action='store_true',
                         help='Pad shorter list instead of failing on count mismatch')

    p_validate = sub.add_parser('validate', help='Validate SRT timing')
    p_validate.add_argument('input_srt')

    p_fix = sub.add_parser('fix', help='Fix SRT timing issues')
    p_fix.add_argument('input_srt')
    p_fix.add_argument('output_srt')

    p_slug = sub.add_parser('slugify', help='Convert title to URL-safe slug')
    p_slug.add_argument('title', nargs='+')

    p_ass = sub.add_parser('to_ass', help='Convert bilingual SRT to styled ASS (supports glow)')
    p_ass.add_argument('input_srt')
    p_ass.add_argument('output_ass')
    p_ass.add_argument('--preset', choices=['clean', 'cinema', 'glow'], default='clean',
                       help='Subtitle style preset (default: clean)')
    p_ass.add_argument('--font', default='PingFang SC',
                       help='Font family name (default: PingFang SC)')
    p_ass.add_argument('--res', default='1920x1080',
                       help='Video resolution WxH (default: 1920x1080)')

    args = parser.parse_args()

    if args.cmd == 'merge':
        try:
            merged = merge_bilingual(
                parse_srt(args.en_srt),
                parse_srt(args.zh_srt),
                pad_missing=args.pad_missing,
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        write_srt(merged, args.output_srt)
        print(f"Merged {len(merged)} entries -> {args.output_srt}")

    elif args.cmd == 'validate':
        entries = parse_srt(args.input_srt)
        issues = validate_srt(entries)
        if issues:
            print(f"Found {len(issues)} issues in {args.input_srt}:")
            for issue in issues:
                print(f"  {issue}")
            sys.exit(1)
        else:
            print(f"OK: {len(entries)} entries, no issues found")

    elif args.cmd == 'fix':
        entries = parse_srt(args.input_srt)
        before = len(validate_srt(entries))
        fixed = fix_srt(entries)
        write_srt(fixed, args.output_srt)
        after = len(validate_srt(fixed))
        print(f"Fixed {len(fixed)} entries -> {args.output_srt} (issues: {before} -> {after})")

    elif args.cmd == 'slugify':
        print(slugify(' '.join(args.title)))

    elif args.cmd == 'to_ass':
        try:
            w, h = map(int, args.res.lower().split('x'))
        except ValueError:
            print(f"Error: --res must be WxH e.g. 1920x1080, got '{args.res}'", file=sys.stderr)
            sys.exit(1)
        entries = parse_srt(args.input_srt)
        ass_content = to_ass(entries, preset=args.preset, font=args.font, resolution=(w, h))
        Path(args.output_ass).write_text(ass_content, encoding='utf-8')
        p = ASS_PRESETS[args.preset]
        print(f"[{p['name']}] {len(entries)} entries -> {args.output_ass}")
