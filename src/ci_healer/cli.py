import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from . import patch
from .orchestrator import heal

console = Console()


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parse(argv)

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        console.print(f"[red]not a directory: {repo}[/red]")
        return 2

    patch.init_baseline(repo)

    result = heal(repo, args.cmd, max_iters=args.max_iters, log=_log)

    console.print()
    if result.ok:
        console.print(f"[green]fixed in {result.iterations} iteration(s)[/green]")
    else:
        console.print(f"[yellow]could not fix: {result.reason}[/yellow]")

    for line in result.cost.lines():
        console.print(f"[dim]{line}[/dim]")

    diff = patch.capture_diff(repo)
    if diff:
        out = Path(args.out).expanduser().resolve()
        out.write_text(diff, encoding="utf-8")
        console.print(f"\n[dim]patch written: {out}[/dim]")

    return 0 if result.ok else 1


def _parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="ci-healer", description="Autonomous CI failure repair agent")
    sub = p.add_subparsers(dest="action", required=True)

    fx = sub.add_parser("fix", help="run the heal loop against a repo")
    fx.add_argument("repo", help="path to the project directory")
    fx.add_argument("--cmd", required=True, help="the failing command, e.g. 'pytest' or 'npm test'")
    fx.add_argument("--max-iters", type=int, default=5, dest="max_iters")
    fx.add_argument("--out", default="./healer.patch", help="where to write the patch")

    return p.parse_args(argv)


def _log(line: str) -> None:
    console.print(line)


if __name__ == "__main__":
    sys.exit(main())
