#!/usr/bin/env python3
"""SRT utilities for yt2bb skill - parse, segment, merge bilingual subtitles."""

import re
import sys
import json
from pathlib import Path

def parse_srt(path):
    """Parse SRT file into list of entries: [{index, start, end, text}, ...]"""
    content = Path(path).read_text(encoding='utf-8')
    entries = []
    blocks = re.split(r'\n\n+', content.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        index = int(lines[0])
        time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if not time_match:
            continue

        entries.append({
            'index': index,
            'start': time_match.group(1),
            'end': time_match.group(2),
            'text': '\n'.join(lines[2:])
        })

    return entries

def segment_chinese(text, max_chars=20):
    """Break Chinese text into lines of max_chars. Respects punctuation breaks."""
    if len(text) <= max_chars:
        return text

    punctuation = '，。！？、；：""''）》】'
    lines = []
    current = ''

    for char in text:
        current += char
        if len(current) >= max_chars or char in punctuation:
            lines.append(current.strip())
            current = ''

    if current.strip():
        lines.append(current.strip())

    return '\n'.join(lines)

def merge_bilingual(en_entries, zh_entries, strict=False):
    """Merge EN and ZH entries into bilingual format (EN on top, ZH below).

    If strict=True, raises error when entry counts differ.
    If strict=False (default), pads shorter list with empty text.
    """
    en_count, zh_count = len(en_entries), len(zh_entries)

    if en_count != zh_count:
        msg = f"Entry count mismatch: EN={en_count}, ZH={zh_count}"
        if strict:
            raise ValueError(msg)
        else:
            print(f"Warning: {msg}. Padding shorter list.", file=sys.stderr)

        # Pad shorter list
        if en_count > zh_count:
            for i in range(zh_count, en_count):
                zh_entries.append({
                    'index': i + 1,
                    'start': en_entries[i]['start'],
                    'end': en_entries[i]['end'],
                    'text': '[翻译缺失]'
                })
        else:
            for i in range(en_count, zh_count):
                en_entries.append({
                    'index': i + 1,
                    'start': zh_entries[i]['start'],
                    'end': zh_entries[i]['end'],
                    'text': '[Translation missing]'
                })

    merged = []
    for i, (en, zh) in enumerate(zip(en_entries, zh_entries), 1):
        merged.append({
            'index': i,
            'start': en['start'],
            'end': en['end'],
            'text': f"{en['text']}\n{zh['text']}"
        })

    return merged

def write_srt(entries, path):
    """Write entries to SRT file."""
    lines = []
    for entry in entries:
        lines.append(str(entry['index']))
        lines.append(f"{entry['start']} --> {entry['end']}")
        lines.append(entry['text'])
        lines.append('')

    Path(path).write_text('\n'.join(lines), encoding='utf-8')

def verify_core_files(directory, slug):
    """Check if all core files exist. Returns (success, missing_files)."""
    core_files = [
        f"{slug}.mp4",
        f"{slug}_en.srt",
        f"{slug}_zh.srt",
        f"{slug}_bilingual.srt",
        f"{slug}_bilingual.mp4"
    ]

    directory = Path(directory)
    missing = [f for f in core_files if not (directory / f).exists()]

    return len(missing) == 0, missing

def cleanup_temp(directory):
    """Remove .tmp directory if exists."""
    tmp_dir = Path(directory) / '.tmp'
    if tmp_dir.exists():
        import shutil
        shutil.rmtree(tmp_dir)
        return True
    return False

# --- Resume capability ---

STATUS_FILE = '.yt2bb_status.json'

def load_status(directory):
    """Load workflow status from directory. Returns dict or None."""
    status_path = Path(directory) / STATUS_FILE
    if status_path.exists():
        return json.loads(status_path.read_text(encoding='utf-8'))
    return None

def save_status(directory, step, slug, **extra):
    """Save workflow status to directory."""
    status_path = Path(directory) / STATUS_FILE
    status = {'step': step, 'slug': slug, **extra}
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding='utf-8')
    return status

def clear_status(directory):
    """Remove status file after successful completion."""
    status_path = Path(directory) / STATUS_FILE
    if status_path.exists():
        status_path.unlink()
        return True
    return False

def get_resume_info(directory):
    """Get human-readable resume info. Returns (step_name, details) or None."""
    status = load_status(directory)
    if not status:
        return None

    step_names = {
        1: 'Download',
        2: 'Transcribe',
        3: 'Proofread',
        4: 'Translate',
        5: 'Merge',
        6: 'Burn'
    }
    step = status.get('step', 0)
    step_name = step_names.get(step, f'Step {step}')
    return step_name, status

# --- Playlist support ---

def slugify(title):
    """Convert title to URL-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower())
    return slug.strip('-')

def is_playlist_url(url):
    """Check if URL is a YouTube playlist."""
    return 'list=' in url or '/playlist' in url

def get_playlist_video_dirs(playlist_dir):
    """Get list of numbered video directories in playlist, sorted by number."""
    playlist_path = Path(playlist_dir)
    if not playlist_path.exists():
        return []

    dirs = []
    for d in playlist_path.iterdir():
        if d.is_dir() and re.match(r'^\d+_', d.name):
            match = re.match(r'^(\d+)_(.+)$', d.name)
            if match:
                dirs.append((int(match.group(1)), d.name, d))

    return [(name, path) for _, name, path in sorted(dirs)]

def create_playlist_dir(base_dir, playlist_name, video_title, index):
    """Create numbered directory for video in playlist. Returns path."""
    slug = slugify(video_title)
    dir_name = f"{index:02d}_{slug}"
    video_dir = Path(base_dir) / slugify(playlist_name) / dir_name
    video_dir.mkdir(parents=True, exist_ok=True)
    return video_dir

def get_playlist_progress(playlist_dir):
    """Get progress summary for playlist. Returns dict with counts."""
    dirs = get_playlist_video_dirs(playlist_dir)
    if not dirs:
        return None

    completed = 0
    in_progress = []
    not_started = []

    for name, path in dirs:
        status = load_status(path)
        slug = name.split('_', 1)[1] if '_' in name else name

        # Check if final video exists
        final_video = path / f"{slug}_bilingual.mp4"
        if final_video.exists():
            completed += 1
        elif status:
            in_progress.append((name, status.get('step', 0)))
        else:
            # Check if any work started
            if any((path / f).exists() for f in [f"{slug}.mp4", f"{slug}_en.srt"]):
                in_progress.append((name, 1))
            else:
                not_started.append(name)

    return {
        'total': len(dirs),
        'completed': completed,
        'in_progress': in_progress,
        'not_started': not_started
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  srt_utils.py merge <en.srt> <zh.srt> <output.srt> [--strict]")
        print("  srt_utils.py segment <zh.srt> <output.srt> [max_chars=20]")
        print("  srt_utils.py verify <directory> <slug>")
        print("  srt_utils.py cleanup <directory>")
        print("  srt_utils.py status <directory>              # Check resume status")
        print("  srt_utils.py save-status <directory> <step> <slug> [key=value ...]")
        print("  srt_utils.py clear-status <directory>        # Clear after completion")
        print("  srt_utils.py slugify <title>                 # Convert title to slug")
        print("  srt_utils.py playlist-progress <playlist_dir>  # Check playlist progress")
        print("")
        print("Options:")
        print("  --strict    Fail if EN/ZH entry counts differ (default: pad shorter list)")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'merge':
        # Parse args: merge <en.srt> <zh.srt> <output.srt> [--strict]
        strict = '--strict' in sys.argv
        args = [a for a in sys.argv[2:] if not a.startswith('--')]
        en_path, zh_path, out_path = args[:3]
        en_entries = parse_srt(en_path)
        zh_entries = parse_srt(zh_path)
        try:
            merged = merge_bilingual(en_entries, zh_entries, strict=strict)
            write_srt(merged, out_path)
            print(f"Merged {len(merged)} entries -> {out_path}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif cmd == 'segment':
        zh_path, out_path = sys.argv[2:4]
        max_chars = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        entries = parse_srt(zh_path)
        for e in entries:
            e['text'] = segment_chinese(e['text'], max_chars)
        write_srt(entries, out_path)
        print(f"Segmented {len(entries)} entries -> {out_path}")

    elif cmd == 'verify':
        directory, slug = sys.argv[2:4]
        success, missing = verify_core_files(directory, slug)
        if success:
            print("✓ All core files present")
            sys.exit(0)
        else:
            print("✗ Missing files:")
            for f in missing:
                print(f"  - {f}")
            sys.exit(1)

    elif cmd == 'cleanup':
        directory = sys.argv[2]
        if cleanup_temp(directory):
            print(f"✓ Cleaned up {directory}/.tmp")
        else:
            print(f"No .tmp directory found in {directory}")

    elif cmd == 'status':
        directory = sys.argv[2]
        info = get_resume_info(directory)
        if info:
            step_name, status = info
            print(f"Resume available: Step {status['step']} ({step_name})")
            print(f"  Slug: {status.get('slug', 'unknown')}")
            for k, v in status.items():
                if k not in ('step', 'slug'):
                    print(f"  {k}: {v}")
        else:
            print("No resume status found")

    elif cmd == 'save-status':
        directory, step, slug = sys.argv[2:5]
        extra = {}
        for arg in sys.argv[5:]:
            if '=' in arg:
                k, v = arg.split('=', 1)
                extra[k] = v
        save_status(directory, int(step), slug, **extra)
        print(f"Status saved: step={step}, slug={slug}")

    elif cmd == 'clear-status':
        directory = sys.argv[2]
        if clear_status(directory):
            print("Status cleared")
        else:
            print("No status file found")

    elif cmd == 'slugify':
        title = ' '.join(sys.argv[2:])
        print(slugify(title))

    elif cmd == 'playlist-progress':
        playlist_dir = sys.argv[2]
        progress = get_playlist_progress(playlist_dir)
        if not progress:
            print(f"No playlist found at {playlist_dir}")
            sys.exit(1)

        print(f"Playlist Progress: {progress['completed']}/{progress['total']} completed")
        if progress['in_progress']:
            print("\nIn Progress:")
            for name, step in progress['in_progress']:
                print(f"  {name} (step {step})")
        if progress['not_started']:
            print(f"\nNot Started: {len(progress['not_started'])} videos")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
