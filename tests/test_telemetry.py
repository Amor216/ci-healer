import json
from pathlib import Path

from ci_healer.telemetry import Telemetry


def test_buffered_when_path_none():
    t = Telemetry()
    t.record(iteration=1, hypothesis="x", fixed=True)
    assert len(t.buffered) == 1
    assert t.buffered[0]["hypothesis"] == "x"
    assert "ts" in t.buffered[0]


def test_writes_jsonl(tmp_path: Path):
    p = tmp_path / "telemetry.jsonl"
    t = Telemetry(path=p)
    t.record(iteration=1, hypothesis="a", fixed=False)
    t.record(iteration=2, hypothesis="b", fixed=True)

    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    a = json.loads(lines[0])
    b = json.loads(lines[1])
    assert a["hypothesis"] == "a"
    assert b["fixed"] is True


def test_creates_parent_dir(tmp_path: Path):
    p = tmp_path / "nested" / "dir" / "log.jsonl"
    Telemetry(path=p).record(iteration=1, hypothesis="x", fixed=True)
    assert p.exists()
