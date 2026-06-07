import shutil
import subprocess
from pathlib import Path


def git_available() -> bool:
    return shutil.which("git") is not None


def init_baseline(workdir: Path) -> bool:
    """If the repo is not a git repo, create a one-off baseline so we can capture a diff later."""
    if not git_available():
        return False
    if (workdir / ".git").exists():
        return True
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=False)
    subprocess.run(["git", "add", "-A"], cwd=workdir, check=False)
    subprocess.run(
        ["git", "-c", "user.email=healer@local", "-c", "user.name=healer",
         "commit", "-q", "--allow-empty", "-m", "baseline"],
        cwd=workdir, check=False,
    )
    return True


def capture_diff(workdir: Path) -> str:
    if not git_available() or not (workdir / ".git").exists():
        return ""
    r = subprocess.run(
        ["git", "diff", "--no-color"],
        cwd=workdir, capture_output=True, text=True, check=False,
    )
    return r.stdout


def revert_working_tree(workdir: Path) -> bool:
    if not git_available() or not (workdir / ".git").exists():
        return False
    r = subprocess.run(
        ["git", "checkout", "--", "."],
        cwd=workdir, capture_output=True, check=False,
    )
    return r.returncode == 0
