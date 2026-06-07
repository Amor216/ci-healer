import sys
from pathlib import Path

import pytest

from ci_healer.verifier import _wrap_sandbox, verify

PY = f'"{sys.executable}"'


def test_passes_on_success(tmp_path: Path):
    r = verify(tmp_path, f"{PY} -c \"print('ok')\"")
    assert r.ok
    assert r.exit_code == 0
    assert "ok" in r.stdout


def test_fails_on_nonzero(tmp_path: Path):
    r = verify(tmp_path, f"{PY} -c \"raise SystemExit(2)\"")
    assert not r.ok
    assert r.exit_code == 2


def test_captures_stderr(tmp_path: Path):
    r = verify(tmp_path, f"{PY} -c \"import sys; sys.stderr.write('boom'); sys.exit(1)\"")
    assert not r.ok
    assert "boom" in r.stderr


def test_timeout(tmp_path: Path):
    r = verify(tmp_path, f"{PY} -c \"import time; time.sleep(5)\"", timeout=1)
    assert not r.ok
    assert "timeout" in r.stderr.lower()


def test_sandbox_none_passthrough(tmp_path: Path):
    assert _wrap_sandbox("pytest", tmp_path, None) == "pytest"


def test_sandbox_docker_wraps(tmp_path: Path):
    out = _wrap_sandbox("pytest -q", tmp_path, "docker:python:3.12-slim")
    assert "docker run --rm" in out
    assert "-v" in out
    assert "/repo" in out
    assert "python:3.12-slim" in out
    assert "pytest -q" in out


def test_sandbox_docker_requires_image(tmp_path: Path):
    with pytest.raises(ValueError, match="requires an image"):
        _wrap_sandbox("pytest", tmp_path, "docker:")


def test_sandbox_unknown_scheme(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown sandbox"):
        _wrap_sandbox("pytest", tmp_path, "podman:image")
