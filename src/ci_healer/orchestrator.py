from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import coder, planner
from .costs import BudgetExceeded, CostTracker
from .telemetry import Telemetry
from .verifier import VerifyResult, verify


@dataclass
class HealResult:
    ok: bool
    iterations: int
    reason: str
    cost: CostTracker
    last: VerifyResult | None


Logger = Callable[[str], None]


def _noop(_: str) -> None:
    pass


def heal(
    workdir: Path,
    cmd: str,
    max_iters: int = 5,
    log: Logger = _noop,
    max_usd: float | None = None,
    telemetry: Telemetry | None = None,
    sandbox: str | None = None,
) -> HealResult:
    cost = CostTracker(max_usd=max_usd)
    tel = telemetry or Telemetry()
    last: VerifyResult | None = None
    tried: set[str] = set()

    for i in range(max_iters):
        log(f"[verifier] running {cmd}" + (f" in {sandbox}" if sandbox else ""))
        last = verify(workdir, cmd, sandbox=sandbox)
        if last.ok:
            log("[verifier] PASS")
            return HealResult(True, i, "tests pass", cost, last)
        log(f"[verifier] FAIL (exit {last.exit_code})")
        _log_error_tail(log, last)

        log("[planner] reading repo and forming hypotheses")
        try:
            hypotheses = planner.plan(workdir, last, cmd, cost)
        except BudgetExceeded as exc:
            return HealResult(False, i + 1, str(exc), cost, last)
        if not hypotheses:
            return HealResult(False, i + 1, "planner produced no hypotheses", cost, last)

        log(f"[planner] {len(hypotheses)} candidate(s):")
        for j, h in enumerate(hypotheses, 1):
            log(f"  {j} ({h.confidence:.2f}) {h.summary}")

        fresh = [h for h in hypotheses if h.summary not in tried]
        if not fresh:
            return HealResult(False, i + 1, "no new hypotheses to try", cost, last)

        chosen = fresh[0]
        rank = hypotheses.index(chosen)
        tried.add(chosen.summary)
        log(f"[coder] attempt {i + 1} of {max_iters}: {chosen.summary}")
        try:
            summary, calls = coder.apply_hypothesis(workdir, chosen, last, cmd, cost)
        except BudgetExceeded as exc:
            return HealResult(False, i + 1, str(exc), cost, last)
        log(f"[coder] {summary} ({calls} tool call(s))")

        after = verify(workdir, cmd, sandbox=sandbox)
        tel.record(
            iteration=i + 1,
            hypothesis=chosen.summary,
            rank=rank,
            confidence=chosen.confidence,
            tool_calls=calls,
            fixed=after.ok,
            exit_code=after.exit_code,
        )
        if after.ok:
            log("[verifier] PASS")
            return HealResult(True, i + 1, "tests pass", cost, after)
        last = after

    return HealResult(False, max_iters, "max iterations reached", cost, last)


def _log_error_tail(log: Logger, result: VerifyResult) -> None:
    tail = (result.stderr or result.stdout).strip().splitlines()[-6:]
    for line in tail:
        log(f"  {line}")
