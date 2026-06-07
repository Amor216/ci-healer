import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.syntax import Syntax

from . import patch
from .orchestrator import heal
from .telemetry import Telemetry

console = Console()


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parse(argv)

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        console.print(f"[red]not a directory: {repo}[/red]")
        return 2

    patch.init_baseline(repo)

    telemetry = Telemetry(path=Path(args.telemetry).expanduser().resolve()) if args.telemetry else None
    result = heal(repo, args.cmd, max_iters=args.max_iters, log=_log,
                  max_usd=args.max_budget, telemetry=telemetry, sandbox=args.sandbox)

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

        if args.review and sys.stdin.isatty():
            console.print()
            console.print(Syntax(diff, "diff", theme="ansi_dark", word_wrap=True))
            console.print()
            answer = input("apply this patch? [Y/n] ").strip().lower()
            if answer in ("n", "no"):
                if patch.revert_working_tree(repo):
                    console.print("[yellow]reverted working tree; patch kept in healer.patch[/yellow]")
                else:
                    console.print("[red]revert failed — repo is left modified[/red]")

    return 0 if result.ok else 1


def _parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="ci-healer", description="Autonomous CI failure repair agent")
    sub = p.add_subparsers(dest="action", required=True)

    fx = sub.add_parser("fix", help="run the heal loop against a repo")
    fx.add_argument("repo", help="path to the project directory")
    fx.add_argument("--cmd", required=True, help="the failing command, e.g. 'pytest' or 'npm test'")
    fx.add_argument("--max-iters", type=int, default=5, dest="max_iters")
    fx.add_argument("--out", default="./healer.patch", help="where to write the patch")
    fx.add_argument("--review", action="store_true",
                    help="show the diff and prompt before keeping the changes")
    fx.add_argument("--max-budget", type=float, default=None, dest="max_budget",
                    help="abort if cumulative cost in USD exceeds this cap")
    fx.add_argument("--telemetry", default=None,
                    help="append per-attempt JSONL telemetry to this path")
    fx.add_argument("--sandbox", default=None,
                    help="run the verifier inside a sandbox, e.g. 'docker:python:3.12-slim'")

    return p.parse_args(argv)


def _log(line: str) -> None:
    console.print(line, markup=False, highlight=False)


if __name__ == "__main__":
    sys.exit(main())
