#!/usr/bin/env python3
"""SRT utilities for yt2bb - merge bilingual subtitles.

Agent-native CLI: all subcommands support --format json for structured output.
Exit codes: 0=success, 1=runtime error, 2=validation/data error.
"""

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

# Exit codes
EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_VALIDATION = 2


def _emit(result, fmt='text', text_fn=None):
    """Emit result as JSON or human-readable text."""
    if fmt == 'json':
        print(json.dumps(result, ensure_ascii=False))
    elif text_fn:
        text_fn(result)


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


# ---------------------------------------------------------------------------
# Whisper environment detection
# ---------------------------------------------------------------------------

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

    out = _run_quiet(['nvidia-smi', '--query-gpu=name,memory.total',
                      '--format=csv,noheader,nounits'])
    if out:
        parts = out.splitlines()[0].split(', ')
        name = parts[0].strip()
        vram_mb = int(parts[1].strip()) if len(parts) > 1 else 0
        return {'type': 'cuda', 'name': name, 'vram_gb': round(vram_mb / 1024, 1)}

    if system == 'Darwin' and machine == 'arm64':
        chip = _run_quiet(['sysctl', '-n', 'machdep.cpu.brand_string']) or 'Apple Silicon'
        mem = _detect_memory_gb()
        return {'type': 'mps', 'name': chip, 'vram_gb': round(mem, 1) if mem else None}

    return {'type': 'cpu', 'name': 'CPU only', 'vram_gb': 0}


def _detect_whisper_backends():
    """Check which whisper CLI backends are installed."""
    backends = {}
    for name, cmd in [('openai-whisper', 'whisper'),
                      ('mlx-whisper', 'mlx_whisper'),
                      ('whisper-ctranslate2', 'whisper-ctranslate2')]:
        backends[name] = shutil.which(cmd) is not None
    return backends


_WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large-v3']
_MODEL_SIZE_GB = {'tiny': 0.07, 'base': 0.14, 'small': 0.5, 'medium': 1.5, 'large-v3': 3.0}


def _detect_whisper_models():
    """Detect locally cached whisper models across all backends.

    Returns dict mapping model name to list of backends that have it cached.
    """
    home = Path.home()
    cached = {m: [] for m in _WHISPER_MODELS}

    # openai-whisper: ~/.cache/whisper/{model}.pt
    ow_cache = home / '.cache' / 'whisper'
    if ow_cache.is_dir():
        for m in _WHISPER_MODELS:
            # openai-whisper uses "large-v3.pt" or "large-v3.en.pt"
            if (ow_cache / f'{m}.pt').exists():
                cached[m].append('openai-whisper')

    # mlx-whisper: ~/.cache/huggingface/hub/models--mlx-community--whisper-{model}-mlx/
    hf_cache = home / '.cache' / 'huggingface' / 'hub'
    if hf_cache.is_dir():
        for m in _WHISPER_MODELS:
            slug = m.replace('-', '-')  # large-v3 stays large-v3
            mlx_dir = hf_cache / f'models--mlx-community--whisper-{slug}-mlx'
            if mlx_dir.is_dir():
                cached[m].append('mlx-whisper')
            # whisper-ctranslate2 / faster-whisper: Systran--faster-whisper-{model}
            ct2_dir = hf_cache / f'models--Systran--faster-whisper-{slug}'
            if ct2_dir.is_dir():
                cached[m].append('whisper-ctranslate2')

    return cached


def check_whisper():
    """Detect platform/GPU/memory and recommend whisper backend + model.

    Returns a structured dict with platform info, installed backends,
    cached models, and recommendation.
    """
    system = platform.system()
    machine = platform.machine()
    is_apple_silicon = system == 'Darwin' and machine == 'arm64'
    mem_gb = _detect_memory_gb()
    gpu = _detect_gpu()
    backends = _detect_whisper_backends()

    # Model recommendation based on available memory
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

    # Backend recommendation
    if is_apple_silicon:
        rec_backend = 'mlx-whisper'
        rec_reason = 'Apple Silicon native (MLX), fastest on this platform'
        install_cmd = 'pip install mlx-whisper'
        model_flag = f'mlx-community/whisper-{rec_model}-mlx'
        example = (f'mlx_whisper "${{slug}}/${{slug}}.mp4" '
                   f'--model {model_flag} '
                   f'--language "$src_lang" '
                   f'--output-format srt --output-dir "${{slug}}"')
    elif gpu['type'] == 'cuda':
        rec_backend = 'whisper-ctranslate2'
        rec_reason = f'CTranslate2 + CUDA ({gpu["name"]}), ~4x faster than openai-whisper'
        install_cmd = 'pip install whisper-ctranslate2'
        model_flag = rec_model
        example = (f'whisper-ctranslate2 "${{slug}}/${{slug}}.mp4" '
                   f'--model {model_flag} '
                   f'--language "$src_lang" '
                   f'--output_format srt --output_dir "${{slug}}"')
    else:
        rec_backend = 'whisper-ctranslate2'
        rec_reason = 'CTranslate2, ~4x faster than openai-whisper on CPU'
        install_cmd = 'pip install whisper-ctranslate2'
        model_flag = rec_model
        example = (f'whisper-ctranslate2 "${{slug}}/${{slug}}.mp4" '
                   f'--model {model_flag} '
                   f'--language "$src_lang" '
                   f'--output_format srt --output_dir "${{slug}}"')

    # Detect cached models
    models = _detect_whisper_models()

    # Check if recommended model is cached for recommended backend
    rec_model_cached = rec_backend in models.get(rec_model, [])
    rec_model_size = _MODEL_SIZE_GB.get(rec_model, 0)

    # Find best already-cached model (largest that fits in memory)
    best_cached = None
    for m in reversed(_WHISPER_MODELS):  # large-v3 first
        if models[m]:  # cached by any backend
            best_cached = m
            break

    # Fallback command
    fallback = None
    rec_installed = backends.get(rec_backend, False)
    if not rec_installed and backends.get('openai-whisper'):
        fallback = (f'whisper "${{slug}}/${{slug}}.mp4" --model {rec_model} '
                    f'--language "$src_lang" --output_format srt --output_dir "${{slug}}"')

    os_label = {'Darwin': 'macOS', 'Windows': 'Windows', 'Linux': 'Linux'}.get(system, system)

    return {
        'ok': True,
        'command': 'check-whisper',
        'platform': {
            'os': os_label,
            'arch': machine,
            'apple_silicon': is_apple_silicon,
            'memory_gb': round(mem_gb, 1) if mem_gb else None,
        },
        'gpu': gpu,
        'backends': backends,
        'models': {m: cached for m, cached in models.items() if cached},
        'recommendation': {
            'backend': rec_backend,
            'reason': rec_reason,
            'model': rec_model,
            'model_reason': model_reason,
            'model_cached': rec_model_cached,
            'model_download_gb': rec_model_size if not rec_model_cached else 0,
            'installed': rec_installed,
            'install': install_cmd if not rec_installed else None,
            'command': example,
        },
        'best_cached_model': best_cached,
        'fallback': fallback,
    }


def _print_check_whisper_text(result):
    """Human-readable output for check-whisper."""
    p = result['platform']
    gpu = result['gpu']
    rec = result['recommendation']

    arch_note = ' (Apple Silicon)' if p['apple_silicon'] else ''
    print(f'=== yt2bb Whisper Environment Check ===\n')
    print(f'Platform:  {p["os"]} {p["arch"]}{arch_note}')
    if p['memory_gb']:
        print(f'Memory:    {p["memory_gb"]:.0f} GB')
    else:
        print(f'Memory:    unknown')
    vram_note = f' ({gpu["vram_gb"]:.0f} GB VRAM)' if gpu['type'] == 'cuda' else ''
    print(f'GPU:       {gpu["name"]}{vram_note}')
    print()

    print('Installed backends:')
    for name, installed in result['backends'].items():
        mark = '+' if installed else '-'
        print(f'  [{mark}] {name}')
    print()

    print('Cached models:')
    models = result.get('models', {})
    if models:
        for m, cached_by in models.items():
            size = _MODEL_SIZE_GB.get(m, 0)
            print(f'  [+] {m} ({size:.1f} GB) — via {", ".join(cached_by)}')
    else:
        print('  (none)')
    print()

    download_note = ''
    if rec['model_download_gb'] > 0:
        download_note = f' — needs ~{rec["model_download_gb"]:.1f} GB download'
    print(f'Recommended:')
    print(f'  Backend:  {rec["backend"]} — {rec["reason"]}')
    print(f'  Model:    {rec["model"]} ({rec["model_reason"]}){download_note}')
    if rec['install']:
        print(f'  Install:  {rec["install"]}')
    print()
    print(f'Command:')
    print(f'  {rec["command"]}')

    best_cached = result.get('best_cached_model')
    if best_cached and best_cached != rec['model'] and rec['model_download_gb'] > 0:
        print()
        print(f'Tip: {best_cached} is already cached and can be used immediately.')

    if result['fallback']:
        print()
        print(f'Note: openai-whisper is already installed. You can use it as a fallback:')
        print(f'  {result["fallback"]}')


# ---------------------------------------------------------------------------
# ASS subtitle generation
# ---------------------------------------------------------------------------

def _srt_time_to_ass(ts):
    """Convert SRT timestamp (HH:MM:SS,mmm) to ASS format (H:MM:SS.cc)."""
    h, m, rest = ts.split(':')
    s, ms = rest.split(',')
    cs = int(ms) // 10
    return f"{int(h)}:{m}:{s}.{cs:02d}"


def _ass_escape(text):
    """Escape characters that have special meaning in ASS dialogue text."""
    return text.replace('{', r'\{').replace('}', r'\}')


# ASS color format: &HAABBGGRR  (alpha=00 is fully opaque)
# {en_mv} / {zh_mv} = MarginV placeholders, resolved by to_ass() based on top_lang
_PRESET_CLEAN = {
    'name': 'Professional Clean',
    'styles': [
        'Style: EN,{font},44,&H0000EFFF,&H000000FF,&H00000000,&H96C8C8C8,-1,0,0,0,100,100,0,0,3,0,4,2,15,15,{en_mv},1',
        'Style: ZH,{font},56,&H0000D4FF,&H000000FF,&H00000000,&H96C8C8C8,-1,0,0,0,100,100,0,0,3,0,4,2,15,15,{zh_mv},1',
    ],
    'en_tag': '',
    'zh_tag': '',
}

_PRESET_CINEMA = {
    'name': 'Cinematic Box',
    'styles': [
        'Style: EN,{font},40,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,0,4,2,15,15,{en_mv},1',
        'Style: ZH,{font},50,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,3,0,4,2,15,15,{zh_mv},1',
    ],
    'en_tag': '',
    'zh_tag': '',
}

_PRESET_GLOW = {
    'name': 'Vibrant Glow',
    'styles': [
        'Style: EN,{font},44,&H00FFFFFF,&H000000FF,&H000080FF,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,15,15,{en_mv},1',
        'Style: ZH,{font},56,&H0000FFFF,&H000000FF,&H00003080,&H00000000,-1,0,0,0,100,100,0,0,1,5,0,2,15,15,{zh_mv},1',
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
    """Extract style lines and override tags from an external ASS file."""
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
    """
    w, h = resolution

    if style_file:
        style_lines, en_tag, zh_tag = _parse_ass_styles(style_file)
        title = f'yt2bb bilingual — custom ({Path(style_file).stem})'
    else:
        p = ASS_PRESETS[preset]
        en_tag, zh_tag = p['en_tag'], p['zh_tag']
        title = f'yt2bb bilingual — {p["name"]}'
        top_mv, bot_mv = 100, 35
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='srt_utils.py',
        description='SRT utilities for yt2bb. Use --format json for agent-friendly output.',
    )
    sub = parser.add_subparsers(dest='cmd', required=True)

    # Shared --format flag
    fmt_parent = argparse.ArgumentParser(add_help=False)
    fmt_parent.add_argument('--format', choices=['text', 'json'], default='text',
                            dest='output_format',
                            help='Output format: text (human) or json (agent)')

    p_merge = sub.add_parser('merge', parents=[fmt_parent],
                             help='Merge EN and ZH SRT into bilingual SRT')
    p_merge.add_argument('en_srt')
    p_merge.add_argument('zh_srt')
    p_merge.add_argument('output_srt')
    p_merge.add_argument('--pad-missing', action='store_true',
                         help='Pad shorter list instead of failing on count mismatch')

    p_validate = sub.add_parser('validate', parents=[fmt_parent],
                                help='Validate SRT timing')
    p_validate.add_argument('input_srt')

    p_fix = sub.add_parser('fix', parents=[fmt_parent],
                           help='Fix SRT timing issues')
    p_fix.add_argument('input_srt')
    p_fix.add_argument('output_srt')

    p_slug = sub.add_parser('slugify', parents=[fmt_parent],
                            help='Convert title to URL-safe slug')
    p_slug.add_argument('title', nargs='+')

    p_ass = sub.add_parser('to_ass', parents=[fmt_parent],
                           help='Convert bilingual SRT to styled ASS (supports glow)')
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

    sub.add_parser('check-whisper', parents=[fmt_parent],
                   help='Detect platform/GPU and recommend whisper backend + model')

    args = parser.parse_args()
    fmt = args.output_format

    # --- merge ---
    if args.cmd == 'merge':
        try:
            merged = merge_bilingual(
                parse_srt(args.en_srt),
                parse_srt(args.zh_srt),
                pad_missing=args.pad_missing,
            )
        except ValueError as e:
            _emit(
                {'ok': False, 'command': 'merge',
                 'error': {'code': 'count_mismatch', 'message': str(e), 'retryable': False}},
                fmt,
                lambda r: print(f"Error: {r['error']['message']}", file=sys.stderr),
            )
            sys.exit(EXIT_VALIDATION)
        except OSError as e:
            _emit(
                {'ok': False, 'command': 'merge',
                 'error': {'code': 'io_error', 'message': str(e), 'retryable': False}},
                fmt,
                lambda r: print(f"Error: {r['error']['message']}", file=sys.stderr),
            )
            sys.exit(EXIT_RUNTIME)
        write_srt(merged, args.output_srt)
        _emit(
            {'ok': True, 'command': 'merge', 'entries': len(merged), 'output': args.output_srt},
            fmt,
            lambda r: print(f"Merged {r['entries']} entries -> {r['output']}"),
        )

    # --- validate ---
    elif args.cmd == 'validate':
        try:
            entries = parse_srt(args.input_srt)
        except OSError as e:
            _emit(
                {'ok': False, 'command': 'validate',
                 'error': {'code': 'io_error', 'message': str(e), 'retryable': False}},
                fmt,
                lambda r: print(f"Error: {r['error']['message']}", file=sys.stderr),
            )
            sys.exit(EXIT_RUNTIME)
        issues = validate_srt(entries)
        if issues:
            _emit(
                {'ok': False, 'command': 'validate', 'file': args.input_srt,
                 'entries': len(entries), 'issue_count': len(issues), 'issues': issues},
                fmt,
                lambda r: (
                    print(f"Found {r['issue_count']} issues in {r['file']}:"),
                    [print(f"  {i}") for i in r['issues']],
                ),
            )
            sys.exit(EXIT_VALIDATION)
        else:
            _emit(
                {'ok': True, 'command': 'validate', 'file': args.input_srt,
                 'entries': len(entries), 'issue_count': 0, 'issues': []},
                fmt,
                lambda r: print(f"OK: {r['entries']} entries, no issues found"),
            )

    # --- fix ---
    elif args.cmd == 'fix':
        try:
            entries = parse_srt(args.input_srt)
        except OSError as e:
            _emit(
                {'ok': False, 'command': 'fix',
                 'error': {'code': 'io_error', 'message': str(e), 'retryable': False}},
                fmt,
                lambda r: print(f"Error: {r['error']['message']}", file=sys.stderr),
            )
            sys.exit(EXIT_RUNTIME)
        before = len(validate_srt(entries))
        fixed = fix_srt(entries)
        write_srt(fixed, args.output_srt)
        after = len(validate_srt(fixed))
        _emit(
            {'ok': True, 'command': 'fix', 'entries': len(fixed), 'output': args.output_srt,
             'issues_before': before, 'issues_after': after},
            fmt,
            lambda r: print(f"Fixed {r['entries']} entries -> {r['output']} "
                            f"(issues: {r['issues_before']} -> {r['issues_after']})"),
        )

    # --- slugify ---
    elif args.cmd == 'slugify':
        title = ' '.join(args.title)
        slug = slugify(title)
        _emit(
            {'ok': True, 'command': 'slugify', 'title': title, 'slug': slug},
            fmt,
            lambda r: print(r['slug']),
        )

    # --- check-whisper ---
    elif args.cmd == 'check-whisper':
        result = check_whisper()
        _emit(result, fmt, _print_check_whisper_text)

    # --- to_ass ---
    elif args.cmd == 'to_ass':
        try:
            w, h = map(int, args.res.lower().split('x'))
        except ValueError:
            _emit(
                {'ok': False, 'command': 'to_ass',
                 'error': {'code': 'bad_resolution', 'message': f"--res must be WxH, got '{args.res}'",
                           'retryable': False}},
                fmt,
                lambda r: print(f"Error: {r['error']['message']}", file=sys.stderr),
            )
            sys.exit(EXIT_VALIDATION)
        try:
            entries = parse_srt(args.input_srt)
            ass_content = to_ass(entries, preset=args.preset, font=args.font,
                                resolution=(w, h), top_lang=args.top,
                                style_file=args.style_file)
        except (OSError, ValueError) as e:
            _emit(
                {'ok': False, 'command': 'to_ass',
                 'error': {'code': 'runtime_error', 'message': str(e), 'retryable': False}},
                fmt,
                lambda r: print(f"Error: {r['error']['message']}", file=sys.stderr),
            )
            sys.exit(EXIT_RUNTIME)
        Path(args.output_ass).write_text(ass_content, encoding='utf-8')
        preset_name = args.preset if not args.style_file else f'custom ({Path(args.style_file).stem})'
        _emit(
            {'ok': True, 'command': 'to_ass', 'entries': len(entries), 'output': args.output_ass,
             'preset': preset_name, 'top_lang': args.top},
            fmt,
            lambda r: print(f"[{r['preset']}] {r['entries']} entries -> {r['output']}"),
        )
