import sys
from pathlib import Path

from ci_healer.verifier import verify

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
