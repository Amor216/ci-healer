import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_OUTPUT = 8000


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str

    @property
    def combined_tail(self) -> str:
        return (self.stdout + self.stderr).strip()


def verify(workdir: Path, cmd: str, timeout: int = 90) -> VerifyResult:
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=str(workdir),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return VerifyResult(
            ok=False, exit_code=-1,
            stdout=(e.stdout or b"").decode("utf-8", errors="replace")[-MAX_OUTPUT:],
            stderr=f"timeout after {timeout}s",
        )
    return VerifyResult(
        ok=r.returncode == 0,
        exit_code=r.returncode,
        stdout=r.stdout[-MAX_OUTPUT:],
        stderr=r.stderr[-MAX_OUTPUT:],
    )
