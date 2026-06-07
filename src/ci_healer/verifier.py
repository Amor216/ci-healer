import shlex
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


def verify(workdir: Path, cmd: str, timeout: int = 90,
           sandbox: str | None = None) -> VerifyResult:
    exec_cmd = _wrap_sandbox(cmd, workdir, sandbox)
    try:
        r = subprocess.run(
            exec_cmd, shell=True, cwd=str(workdir),
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


def _wrap_sandbox(cmd: str, workdir: Path, sandbox: str | None) -> str:
    if not sandbox:
        return cmd
    if sandbox.startswith("docker:"):
        image = sandbox[len("docker:"):]
        if not image:
            raise ValueError("sandbox 'docker:' requires an image, e.g. docker:python:3.12-slim")
        mount = f"{workdir.resolve().as_posix()}:/repo"
        return (
            f"docker run --rm "
            f"-v {shlex.quote(mount)} "
            f"-w /repo "
            f"{shlex.quote(image)} "
            f"sh -c {shlex.quote(cmd)}"
        )
    raise ValueError(f"unknown sandbox scheme: {sandbox!r}")
