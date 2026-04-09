#!/usr/bin/env python3
"""Tests for srt_utils.py — covers bug fixes, core functions, and CLI."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from srt_utils import (
    ASS_PRESETS,
    check_whisper,
    fix_srt,
    merge_bilingual,
    ms_to_time,
    parse_srt,
    slugify,
    time_to_ms,
    to_ass,
    validate_srt,
    write_srt,
)

SCRIPT = str(Path(__file__).parent / "srt_utils.py")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_entries():
    return [
        {"index": 1, "start": "00:00:01,000", "end": "00:00:03,000", "text": "Hello"},
        {"index": 2, "start": "00:00:04,000", "end": "00:00:06,000", "text": "World"},
    ]


@pytest.fixture
def sample_srt_file(tmp_path):
    content = (
        "1\n00:00:01,000 --> 00:00:03,000\nHello\n\n"
        "2\n00:00:04,000 --> 00:00:06,000\nWorld\n"
    )
    p = tmp_path / "test.srt"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def bilingual_entries():
    return [
        {"index": 1, "start": "00:00:01,000", "end": "00:00:03,000", "text": "Hello\n你好"},
        {"index": 2, "start": "00:00:04,000", "end": "00:00:06,000", "text": "World\n世界"},
    ]


# ---------------------------------------------------------------------------
# time_to_ms / ms_to_time
# ---------------------------------------------------------------------------

class TestTimeConversion:
    def test_basic(self):
        assert time_to_ms("00:00:01,500") == 1500
        assert time_to_ms("01:30:00,000") == 5400000

    def test_roundtrip(self):
        for ms in [0, 500, 1234, 3661999]:
            assert time_to_ms(ms_to_time(ms)) == ms

    def test_negative_clamped(self):
        assert ms_to_time(-100) == "00:00:00,000"


# ---------------------------------------------------------------------------
# parse_srt
# ---------------------------------------------------------------------------

class TestParseSrt:
    def test_basic(self, sample_srt_file):
        entries = parse_srt(str(sample_srt_file))
        assert len(entries) == 2
        assert entries[0]["text"] == "Hello"
        assert entries[1]["start"] == "00:00:04,000"

    def test_malformed_blocks_skipped(self, tmp_path, capsys):
        content = (
            "1\n00:00:01,000 --> 00:00:03,000\nGood\n\n"
            "BAD BLOCK\n\n"
            "not a timestamp\nstill bad\nthird line\n\n"
            "3\n00:00:04,000 --> 00:00:06,000\nAlso good\n"
        )
        p = tmp_path / "malformed.srt"
        p.write_text(content, encoding="utf-8")
        entries = parse_srt(str(p))
        assert len(entries) == 2
        captured = capsys.readouterr()
        assert "skipped 2 malformed block(s)" in captured.err

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.srt"
        p.write_text("", encoding="utf-8")
        assert parse_srt(str(p)) == []


# ---------------------------------------------------------------------------
# write_srt
# ---------------------------------------------------------------------------

class TestWriteSrt:
    def test_roundtrip(self, sample_entries, tmp_path):
        p = tmp_path / "out.srt"
        write_srt(sample_entries, str(p))
        parsed = parse_srt(str(p))
        assert len(parsed) == 2
        assert parsed[0]["text"] == "Hello"
        assert parsed[1]["text"] == "World"


# ---------------------------------------------------------------------------
# merge_bilingual
# ---------------------------------------------------------------------------

class TestMergeBilingual:
    def test_equal_counts(self):
        en = [{"index": 1, "start": "00:00:01,000", "end": "00:00:03,000", "text": "Hi"}]
        zh = [{"index": 1, "start": "00:00:01,000", "end": "00:00:03,000", "text": "你好"}]
        merged = merge_bilingual(en, zh)
        assert len(merged) == 1
        assert merged[0]["text"] == "Hi\n你好"

    def test_count_mismatch_fails_by_default(self):
        en = [
            {"index": 1, "start": "00:00:01,000", "end": "00:00:03,000", "text": "Hi"},
            {"index": 2, "start": "00:00:04,000", "end": "00:00:06,000", "text": "Bye"},
        ]
        zh = [{"index": 1, "start": "00:00:01,000", "end": "00:00:03,000", "text": "你好"}]
        with pytest.raises(ValueError, match="count mismatch"):
            merge_bilingual(en, zh)

    def test_count_mismatch_pad(self):
        en = [
            {"index": 1, "start": "00:00:01,000", "end": "00:00:03,000", "text": "Hi"},
            {"index": 2, "start": "00:00:04,000", "end": "00:00:06,000", "text": "Bye"},
        ]
        zh = [{"index": 1, "start": "00:00:01,000", "end": "00:00:03,000", "text": "你好"}]
        merged = merge_bilingual(en, zh, pad_missing=True)
        assert len(merged) == 2
        assert "[翻译缺失]" in merged[1]["text"]


# ---------------------------------------------------------------------------
# fix_srt — Codex finding #1: cascade negative duration bug
# ---------------------------------------------------------------------------

class TestFixSrt:
    def test_short_duration_extended(self):
        entries = [
            {"index": 1, "start": "00:00:01,000", "end": "00:00:01,100", "text": "Short"},
        ]
        fixed = fix_srt(entries)
        end_ms = time_to_ms(fixed[0]["end"])
        start_ms = time_to_ms(fixed[0]["start"])
        assert end_ms - start_ms >= 500

    def test_cascade_no_negative_duration(self):
        """Three tightly overlapping entries — the bug that Codex found."""
        entries = [
            {"index": 1, "start": "00:00:00,000", "end": "00:00:01,000", "text": "A"},
            {"index": 2, "start": "00:00:00,500", "end": "00:00:00,620", "text": "B"},
            {"index": 3, "start": "00:00:00,600", "end": "00:00:00,700", "text": "C"},
        ]
        fixed = fix_srt(entries)
        issues = validate_srt(fixed)
        assert len(issues) == 0, f"Expected no issues, got: {issues}"
        for e in fixed:
            start = time_to_ms(e["start"])
            end = time_to_ms(e["end"])
            assert end > start, f"Negative duration in #{e['index']}: {e['start']} -> {e['end']}"

    def test_overlap_resolved(self):
        entries = [
            {"index": 1, "start": "00:00:00,000", "end": "00:00:02,000", "text": "A"},
            {"index": 2, "start": "00:00:01,000", "end": "00:00:03,000", "text": "B"},
        ]
        fixed = fix_srt(entries)
        prev_end = time_to_ms(fixed[0]["end"])
        curr_start = time_to_ms(fixed[1]["start"])
        assert curr_start > prev_end

    def test_already_valid_unchanged(self, sample_entries):
        fixed = fix_srt(sample_entries)
        assert len(validate_srt(fixed)) == 0


# ---------------------------------------------------------------------------
# validate_srt
# ---------------------------------------------------------------------------

class TestValidateSrt:
    def test_valid(self, sample_entries):
        assert validate_srt(sample_entries) == []

    def test_short_duration(self):
        entries = [{"index": 1, "start": "00:00:01,000", "end": "00:00:01,100", "text": "X"}]
        issues = validate_srt(entries)
        assert any("duration" in i for i in issues)

    def test_overlap(self):
        entries = [
            {"index": 1, "start": "00:00:00,000", "end": "00:00:03,000", "text": "A"},
            {"index": 2, "start": "00:00:02,000", "end": "00:00:05,000", "text": "B"},
        ]
        issues = validate_srt(entries)
        assert any("overlaps" in i for i in issues)


# ---------------------------------------------------------------------------
# slugify — Codex finding #4: empty string for CJK
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_ascii(self):
        assert slugify("Hello World") == "hello-world"
        assert slugify("My Video 123") == "my-video-123"

    def test_cjk_fallback(self):
        s = slugify("视频标题")
        assert s != ""
        assert s.startswith("video-")

    def test_japanese_fallback(self):
        s = slugify("日本語タイトル")
        assert s != ""
        assert s.startswith("video-")

    def test_mixed_keeps_ascii(self):
        s = slugify("Test 视频")
        assert "test" in s

    def test_deterministic(self):
        assert slugify("视频标题") == slugify("视频标题")


# ---------------------------------------------------------------------------
# to_ass
# ---------------------------------------------------------------------------

class TestToAss:
    def test_presets_produce_valid_ass(self, bilingual_entries):
        for preset in ["clean", "cinema", "glow"]:
            ass = to_ass(bilingual_entries, preset=preset)
            assert "[Script Info]" in ass
            assert "[V4+ Styles]" in ass
            assert "[Events]" in ass
            assert "Style: EN," in ass
            assert "Style: ZH," in ass

    def test_dialogue_count(self, bilingual_entries):
        ass = to_ass(bilingual_entries)
        lines = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
        # 2 entries x 2 lines (EN + ZH) = 4
        assert len(lines) == 4

    def test_zh_on_top_default(self, bilingual_entries):
        ass = to_ass(bilingual_entries, top_lang="zh")
        for line in ass.splitlines():
            if line.startswith("Style: ZH,"):
                # ZH should have higher MarginV (70)
                assert ",70," in line
            if line.startswith("Style: EN,"):
                # EN should have lower MarginV (35)
                assert ",35," in line

    def test_en_on_top(self, bilingual_entries):
        ass = to_ass(bilingual_entries, top_lang="en")
        for line in ass.splitlines():
            if line.startswith("Style: EN,"):
                assert ",70," in line
            if line.startswith("Style: ZH,"):
                assert ",35," in line

    def test_glow_has_blur_tags(self, bilingual_entries):
        ass = to_ass(bilingual_entries, preset="glow")
        lines = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
        for l in lines:
            assert r"{\blur5}" in l

    def test_custom_style_file(self, bilingual_entries, tmp_path):
        style_file = tmp_path / "custom.ass"
        style_file.write_text(
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: EN,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,70,1\n"
            "Style: ZH,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,35,1\n"
            "; en_tag=\n"
            "; zh_tag={\\blur3}\n",
            encoding="utf-8",
        )
        ass = to_ass(bilingual_entries, style_file=str(style_file))
        assert "Arial" in ass
        assert "custom" in ass
        zh_dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:") and ",ZH," in l]
        assert all(r"{\blur3}" in l for l in zh_dialogues)

    def test_resolution(self, bilingual_entries):
        ass = to_ass(bilingual_entries, resolution=(1280, 720))
        assert "PlayResX: 1280" in ass
        assert "PlayResY: 720" in ass

    def test_font_substitution(self, bilingual_entries):
        ass = to_ass(bilingual_entries, font="Noto Sans CJK SC")
        assert "Noto Sans CJK SC" in ass
        assert "PingFang" not in ass


# ---------------------------------------------------------------------------
# check_whisper
# ---------------------------------------------------------------------------

class TestCheckWhisper:
    def test_returns_structured_dict(self):
        result = check_whisper()
        assert result["ok"] is True
        assert result["command"] == "check-whisper"
        assert "platform" in result
        assert "gpu" in result
        assert "backends" in result
        assert "models" in result
        assert "recommendation" in result

    def test_recommendation_has_required_fields(self):
        result = check_whisper()
        rec = result["recommendation"]
        assert "backend" in rec
        assert "model" in rec
        assert "model_cached" in rec
        assert "model_download_gb" in rec
        assert "command" in rec


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

def _run_cli(args, expect_exit=0):
    r = subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True, text=True,
    )
    assert r.returncode == expect_exit, (
        f"Expected exit {expect_exit}, got {r.returncode}\n"
        f"stdout: {r.stdout}\nstderr: {r.stderr}"
    )
    return r


class TestCLI:
    def test_merge_text(self, tmp_path):
        en = tmp_path / "en.srt"
        zh = tmp_path / "zh.srt"
        out = tmp_path / "bi.srt"
        en.write_text("1\n00:00:01,000 --> 00:00:03,000\nHi\n", encoding="utf-8")
        zh.write_text("1\n00:00:01,000 --> 00:00:03,000\n你好\n", encoding="utf-8")
        r = _run_cli(["merge", str(en), str(zh), str(out)])
        assert "Merged 1 entries" in r.stdout
        assert out.exists()

    def test_merge_json(self, tmp_path):
        en = tmp_path / "en.srt"
        zh = tmp_path / "zh.srt"
        out = tmp_path / "bi.srt"
        en.write_text("1\n00:00:01,000 --> 00:00:03,000\nHi\n", encoding="utf-8")
        zh.write_text("1\n00:00:01,000 --> 00:00:03,000\n你好\n", encoding="utf-8")
        r = _run_cli(["merge", str(en), str(zh), str(out), "--format", "json"])
        d = json.loads(r.stdout)
        assert d["ok"] is True
        assert d["entries"] == 1

    def test_merge_count_mismatch_json(self, tmp_path):
        en = tmp_path / "en.srt"
        zh = tmp_path / "zh.srt"
        out = tmp_path / "bi.srt"
        en.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nHi\n\n"
            "2\n00:00:04,000 --> 00:00:06,000\nBye\n",
            encoding="utf-8",
        )
        zh.write_text("1\n00:00:01,000 --> 00:00:03,000\n你好\n", encoding="utf-8")
        r = _run_cli(["merge", str(en), str(zh), str(out), "--format", "json"], expect_exit=2)
        d = json.loads(r.stdout)
        assert d["ok"] is False
        assert d["error"]["code"] == "count_mismatch"

    def test_merge_io_error_json(self, tmp_path):
        out = tmp_path / "bi.srt"
        r = _run_cli(
            ["merge", "/nonexistent.srt", "/also_nonexistent.srt", str(out), "--format", "json"],
            expect_exit=1,
        )
        d = json.loads(r.stdout)
        assert d["ok"] is False
        assert d["error"]["code"] == "io_error"

    def test_validate_ok_json(self, sample_srt_file):
        r = _run_cli(["validate", str(sample_srt_file), "--format", "json"])
        d = json.loads(r.stdout)
        assert d["ok"] is True
        assert d["issue_count"] == 0

    def test_validate_issues_json(self, tmp_path):
        p = tmp_path / "bad.srt"
        p.write_text("1\n00:00:01,000 --> 00:00:01,100\nToo short\n", encoding="utf-8")
        r = _run_cli(["validate", str(p), "--format", "json"], expect_exit=2)
        d = json.loads(r.stdout)
        assert d["ok"] is False
        assert d["issue_count"] > 0

    def test_fix_json(self, tmp_path):
        p = tmp_path / "bad.srt"
        out = tmp_path / "fixed.srt"
        p.write_text("1\n00:00:01,000 --> 00:00:01,100\nShort\n", encoding="utf-8")
        r = _run_cli(["fix", str(p), str(out), "--format", "json"])
        d = json.loads(r.stdout)
        assert d["ok"] is True
        assert d["issues_before"] > 0
        assert d["issues_after"] == 0

    def test_slugify_json(self):
        r = _run_cli(["slugify", "Hello World", "--format", "json"])
        d = json.loads(r.stdout)
        assert d["ok"] is True
        assert d["slug"] == "hello-world"

    def test_slugify_cjk_json(self):
        r = _run_cli(["slugify", "视频标题", "--format", "json"])
        d = json.loads(r.stdout)
        assert d["slug"].startswith("video-")

    def test_to_ass_json(self, tmp_path):
        srt = tmp_path / "bi.srt"
        out = tmp_path / "bi.ass"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nHello\n你好\n",
            encoding="utf-8",
        )
        r = _run_cli(["to_ass", str(srt), str(out), "--format", "json"])
        d = json.loads(r.stdout)
        assert d["ok"] is True
        assert d["entries"] == 1
        assert out.exists()

    def test_to_ass_presets(self, tmp_path):
        srt = tmp_path / "bi.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nHello\n你好\n",
            encoding="utf-8",
        )
        for preset in ["clean", "cinema", "glow"]:
            out = tmp_path / f"{preset}.ass"
            r = _run_cli(["to_ass", str(srt), str(out), "--preset", preset, "--format", "json"])
            d = json.loads(r.stdout)
            assert d["ok"] is True

    def test_check_whisper_json(self):
        r = _run_cli(["check-whisper", "--format", "json"])
        d = json.loads(r.stdout)
        assert d["ok"] is True
        assert "recommendation" in d
        assert "models" in d

    def test_check_whisper_text(self):
        r = _run_cli(["check-whisper"])
        assert "Whisper Environment Check" in r.stdout
        assert "Recommended:" in r.stdout

    def test_missing_subcommand(self):
        _run_cli([], expect_exit=2)

    def test_missing_args(self):
        _run_cli(["merge"], expect_exit=2)
