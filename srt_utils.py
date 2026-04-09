#!/usr/bin/env python3
"""SRT utilities for yt2bb - merge bilingual subtitles."""

import argparse
import hashlib
import platform
import re
import shutil
import subprocess
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


def _run_quiet(cmd):
    """Run a command and return stdout, or None on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _detect_memory_gb():
    """Detect total system memory in GB."""
    system = platform.system()
    try:
        if system == 'Darwin':
            out = _run_quiet(['sysctl', '-n', 'hw.memsize'])
            return int(out) / (1024 ** 3) if out else None
        elif system == 'Linux':
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        return int(line.split()[1]) / (1024 ** 2)
            return None
        elif system == 'Windows':
            out = _run_quiet(['wmic', 'computersystem', 'get',
                              'TotalPhysicalMemory', '/value'])
            if out:
                for line in out.splitlines():
                    if 'TotalPhysicalMemory' in line:
                        return int(line.split('=')[1]) / (1024 ** 3)
            return None
    except (ValueError, OSError):
        return None


def _detect_gpu():
    """Detect GPU info. Returns dict with 'type', 'name', 'vram_gb'."""
    system = platform.system()
    machine = platform.machine()

    # Check NVIDIA (all platforms)
    out = _run_quiet(['nvidia-smi', '--query-gpu=name,memory.total',
                      '--format=csv,noheader,nounits'])
    if out:
        parts = out.splitlines()[0].split(', ')
        name = parts[0].strip()
        vram_mb = int(parts[1].strip()) if len(parts) > 1 else 0
        return {'type': 'cuda', 'name': name, 'vram_gb': vram_mb / 1024}

    # Apple Silicon → Metal/MPS (unified memory)
    if system == 'Darwin' and machine == 'arm64':
        chip = _run_quiet(['sysctl', '-n', 'machdep.cpu.brand_string']) or 'Apple Silicon'
        mem = _detect_memory_gb()
        return {'type': 'mps', 'name': chip, 'vram_gb': mem}

    return {'type': 'cpu', 'name': 'CPU only', 'vram_gb': 0}


def _detect_whisper_backends():
    """Check which whisper CLI backends are installed."""
    backends = {}
    for name, cmd in [('openai-whisper', 'whisper'),
                      ('mlx-whisper', 'mlx_whisper'),
                      ('whisper-ctranslate2', 'whisper-ctranslate2')]:
        backends[name] = shutil.which(cmd) is not None
    return backends


def check_whisper():
    """Detect platform/GPU/memory and recommend whisper backend + model."""
    system = platform.system()
    machine = platform.machine()
    is_apple_silicon = system == 'Darwin' and machine == 'arm64'
    mem_gb = _detect_memory_gb()
    gpu = _detect_gpu()
    backends = _detect_whisper_backends()

    # --- Model recommendation based on available memory ---
    avail_gb = gpu['vram_gb'] or mem_gb or 0
    if avail_gb >= 10:
        rec_model = 'large-v3'
        model_reason = f'{avail_gb:.0f} GB available'
    elif avail_gb >= 5:
        rec_model = 'medium'
        model_reason = f'{avail_gb:.0f} GB available (large-v3 needs ~10 GB)'
    else:
        rec_model = 'tiny'
        model_reason = f'{avail_gb:.0f} GB available (medium needs ~5 GB)'

    # --- Backend recommendation ---
    if is_apple_silicon:
        rec_backend = 'mlx-whisper'
        rec_cmd = 'mlx_whisper'
        rec_reason = 'Apple Silicon native (MLX), fastest on this platform'
        install_cmd = 'pip install mlx-whisper'
        # mlx-whisper uses HuggingFace model names
        model_flag = f'mlx-community/whisper-{rec_model}-mlx'
        example = (f'mlx_whisper "${{slug}}/${{slug}}.mp4" '
                   f'--model {model_flag} '
                   f'--language "$src_lang" '
                   f'--output-format srt --output-dir "${{slug}}"')
    elif gpu['type'] == 'cuda':
        rec_backend = 'whisper-ctranslate2'
        rec_cmd = 'whisper-ctranslate2'
        rec_reason = f'CTranslate2 + CUDA ({gpu["name"]}), ~4x faster than openai-whisper'
        install_cmd = 'pip install whisper-ctranslate2'
        model_flag = rec_model
        example = (f'whisper-ctranslate2 "${{slug}}/${{slug}}.mp4" '
                   f'--model {model_flag} '
                   f'--language "$src_lang" '
                   f'--output_format srt --output_dir "${{slug}}"')
    else:
        rec_backend = 'whisper-ctranslate2'
        rec_cmd = 'whisper-ctranslate2'
        rec_reason = 'CTranslate2, ~4x faster than openai-whisper on CPU'
        install_cmd = 'pip install whisper-ctranslate2'
        model_flag = rec_model
        example = (f'whisper-ctranslate2 "${{slug}}/${{slug}}.mp4" '
                   f'--model {model_flag} '
                   f'--language "$src_lang" '
                   f'--output_format srt --output_dir "${{slug}}"')

    # --- Print report ---
    print('=== yt2bb Whisper Environment Check ===\n')

    os_label = {'Darwin': 'macOS', 'Windows': 'Windows', 'Linux': 'Linux'}.get(system, system)
    arch_note = ' (Apple Silicon)' if is_apple_silicon else ''
    print(f'Platform:  {os_label} {machine}{arch_note}')
    print(f'Memory:    {mem_gb:.0f} GB' if mem_gb else 'Memory:    unknown')
    print(f'GPU:       {gpu["name"]}' + (f' ({gpu["vram_gb"]:.0f} GB VRAM)' if gpu['type'] == 'cuda' else ''))
    print()

    print('Installed backends:')
    any_installed = False
    for name, installed in backends.items():
        mark = '+' if installed else '-'
        print(f'  [{mark}] {name}')
        if installed:
            any_installed = True
    print()

    rec_installed = backends.get(rec_backend, False)
    print(f'Recommended:')
    print(f'  Backend:  {rec_backend} — {rec_reason}')
    print(f'  Model:    {rec_model} ({model_reason})')
    if not rec_installed:
        print(f'  Install:  {install_cmd}')
    print()
    print(f'Command:')
    print(f'  {example}')

    # Fallback note
    if not rec_installed and backends.get('openai-whisper'):
        print()
        print(f'Note: openai-whisper is already installed. You can use it as a fallback:')
        print(f'  whisper "${{slug}}/${{slug}}.mp4" --model {rec_model} '
              f'--language "$src_lang" --output_format srt --output_dir "${{slug}}"')


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
# {en_mv} / {zh_mv} = MarginV placeholders, resolved by to_ass() based on top_lang
# Preset A — Professional Clean: white text, black outline, subtle shadow
_PRESET_CLEAN = {
    'name': 'Professional Clean',
    'styles': [
        'Style: EN,{font},20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,{en_mv},1',
        'Style: ZH,{font},24,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,{zh_mv},1',
    ],
    'en_tag': '',
    'zh_tag': '',
}

# Preset B — Cinematic Box: white text on semi-transparent black box, per-line boxes
_PRESET_CINEMA = {
    'name': 'Cinematic Box',
    'styles': [
        'Style: EN,{font},18,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,3,0,0,2,10,10,{en_mv},1',
        'Style: ZH,{font},22,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,3,0,0,2,10,10,{zh_mv},1',
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
        'Style: EN,{font},20,&H00FFFFFF,&H000000FF,&H000080FF,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,10,10,{en_mv},1',
        'Style: ZH,{font},24,&H0000FFFF,&H000000FF,&H00003080,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,10,10,{zh_mv},1',
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


def _parse_ass_styles(path):
    """Extract style lines and override tags from an external ASS file.

    Reads the [V4+ Styles] section. Expects styles named 'EN' and 'ZH'.
    Returns (style_lines, en_tag, zh_tag). Tags default to '' unless the
    file contains a [yt2bb] section with en_tag / zh_tag overrides.
    """
    content = Path(path).read_text(encoding='utf-8')
    style_lines = []
    in_styles = False
    en_tag, zh_tag = '', ''
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith('[V4+ Styles]') or stripped.startswith('[V4 Styles]'):
            in_styles = True
            continue
        if stripped.startswith('[') and in_styles:
            in_styles = False
        if in_styles and stripped.startswith('Style:'):
            style_lines.append(stripped)
        # Optional [yt2bb] section for override tags like \blur
        if stripped.startswith('; en_tag='):
            en_tag = stripped.split('=', 1)[1].strip()
        if stripped.startswith('; zh_tag='):
            zh_tag = stripped.split('=', 1)[1].strip()
    if not style_lines:
        raise ValueError(f"No Style lines found in {path}")
    return style_lines, en_tag, zh_tag


def to_ass(entries, preset='clean', font='PingFang SC', resolution=(1920, 1080),
           top_lang='zh', style_file=None):
    """Convert bilingual SRT entries to a styled ASS file.

    Each bilingual entry (EN\\nZH text) is split into two separate ASS
    Dialogue lines with independent styles, enabling per-line color and
    glow effects not possible with SRT force_style.

    Args:
        entries: list of dicts from parse_srt() on a bilingual SRT
        preset: 'clean' | 'cinema' | 'glow' (ignored if style_file is set)
        font: font family name (ignored if style_file is set)
        resolution: (width, height) of target video
        top_lang: 'zh' (default) or 'en' — which language appears on top
                  (ignored if style_file is set, since styles define their own MarginV)
        style_file: path to an external .ass file whose [V4+ Styles] section
                    overrides the built-in preset. Must contain styles named 'EN' and 'ZH'.
    Returns:
        ASS file content as a string
    """
    w, h = resolution

    if style_file:
        style_lines, en_tag, zh_tag = _parse_ass_styles(style_file)
        title = f'yt2bb bilingual — custom ({Path(style_file).stem})'
    else:
        p = ASS_PRESETS[preset]
        en_tag, zh_tag = p['en_tag'], p['zh_tag']
        title = f'yt2bb bilingual — {p["name"]}'
        # Higher MarginV = higher on screen (further from bottom edge)
        top_mv, bot_mv = 70, 35
        en_mv = top_mv if top_lang == 'en' else bot_mv
        zh_mv = top_mv if top_lang == 'zh' else bot_mv
        style_lines = [s.replace('{font}', font)
                        .replace('{en_mv}', str(en_mv))
                        .replace('{zh_mv}', str(zh_mv))
                       for s in p['styles']]

    header = '\n'.join([
        '[Script Info]',
        f'Title: {title}',
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
                f"Dialogue: 0,{start},{end},EN,,0,0,0,,{en_tag}{en_text}"
            )
        if zh_text:
            dialogue_lines.append(
                f"Dialogue: 0,{start},{end},ZH,,0,0,0,,{zh_tag}{zh_text}"
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
    p_ass.add_argument('--top', choices=['zh', 'en'], default='zh',
                       help='Which language on top (default: zh)')
    p_ass.add_argument('--style-file', default=None,
                       help='External .ass file with custom [V4+ Styles] (overrides --preset/--font/--top)')

    sub.add_parser('check-whisper', help='Detect platform/GPU and recommend whisper backend + model')

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

    elif args.cmd == 'check-whisper':
        check_whisper()

    elif args.cmd == 'to_ass':
        try:
            w, h = map(int, args.res.lower().split('x'))
        except ValueError:
            print(f"Error: --res must be WxH e.g. 1920x1080, got '{args.res}'", file=sys.stderr)
            sys.exit(1)
        entries = parse_srt(args.input_srt)
        ass_content = to_ass(entries, preset=args.preset, font=args.font,
                            resolution=(w, h), top_lang=args.top,
                            style_file=args.style_file)
        Path(args.output_ass).write_text(ass_content, encoding='utf-8')
        p = ASS_PRESETS[args.preset]
        print(f"[{p['name']}] {len(entries)} entries -> {args.output_ass}")
