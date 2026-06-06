from pathlib import Path

import pytest

from ci_healer.tools import SandboxError, build_tools


def _by_name(root: Path):
    return {t.name: t for t in build_tools(root)}


def test_read_and_write(tmp_path: Path):
    tools = _by_name(tmp_path)
    tools["write_file"].handler({"path": "a.txt", "content": "hello"})
    out = tools["read_file"].handler({"path": "a.txt"})
    assert out == "hello"


def test_replace_unique(tmp_path: Path):
    (tmp_path / "f.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    tools = _by_name(tmp_path)
    msg = tools["replace_in_file"].handler({"path": "f.py", "old": "a = 1", "new": "a = 42"})
    assert "replaced 1" in msg
    assert (tmp_path / "f.py").read_text() == "a = 42\nb = 2\n"


def test_replace_ambiguous(tmp_path: Path):
    (tmp_path / "f.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    tools = _by_name(tmp_path)
    msg = tools["replace_in_file"].handler({"path": "f.py", "old": "x = 1", "new": "y = 1"})
    assert "matches 2 times" in msg


def test_replace_no_match(tmp_path: Path):
    (tmp_path / "f.py").write_text("a = 1\n", encoding="utf-8")
    tools = _by_name(tmp_path)
    msg = tools["replace_in_file"].handler({"path": "f.py", "old": "zzz", "new": "yyy"})
    assert "no match" in msg


def test_list_dir(tmp_path: Path):
    (tmp_path / "x.py").write_text("")
    (tmp_path / "sub").mkdir()
    out = _by_name(tmp_path)["list_dir"].handler({"path": "."})
    assert "x.py" in out
    assert "sub" in out


def test_grep(tmp_path: Path):
    (tmp_path / "a.py").write_text("import json\nfoo = 1\n")
    (tmp_path / "b.py").write_text("bar = 2\n")
    out = _by_name(tmp_path)["grep"].handler({"pattern": "import"})
    assert "a.py" in out
    assert "import json" in out


def test_path_escape_blocked(tmp_path: Path):
    tools = _by_name(tmp_path)
    with pytest.raises(SandboxError):
        tools["read_file"].handler({"path": "../etc/passwd"})


def test_unknown_path_not_found(tmp_path: Path):
    out = _by_name(tmp_path)["read_file"].handler({"path": "missing.py"})
    assert "not found" in out
