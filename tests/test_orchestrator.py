from pathlib import Path
from unittest.mock import patch

from ci_healer.orchestrator import heal
from ci_healer.planner import Hypothesis
from ci_healer.verifier import VerifyResult


def _v(ok: bool) -> VerifyResult:
    return VerifyResult(ok=ok, exit_code=0 if ok else 1, stdout="", stderr="" if ok else "boom")


def test_first_verify_pass_short_circuits(tmp_path: Path):
    with patch("ci_healer.orchestrator.verify", return_value=_v(True)) as v:
        result = heal(tmp_path, "true", max_iters=3)
    assert result.ok
    assert result.iterations == 0
    assert v.call_count == 1


def test_plan_then_fix(tmp_path: Path):
    results = [_v(False), _v(True)]
    with patch("ci_healer.orchestrator.verify", side_effect=results) as v, \
         patch("ci_healer.orchestrator.planner.plan",
               return_value=[Hypothesis("fix it", 0.9, ["a.py"], "because")]) as p, \
         patch("ci_healer.orchestrator.coder.apply_hypothesis", return_value=("edited a.py", 2)) as c:
        result = heal(tmp_path, "pytest", max_iters=3)
    assert result.ok
    assert result.iterations == 1
    assert v.call_count == 2
    assert p.call_count == 1
    assert c.call_count == 1


def test_no_hypotheses_gives_up(tmp_path: Path):
    with patch("ci_healer.orchestrator.verify", return_value=_v(False)), \
         patch("ci_healer.orchestrator.planner.plan", return_value=[]):
        result = heal(tmp_path, "pytest", max_iters=3)
    assert not result.ok
    assert "no hypotheses" in result.reason


def test_dedupes_repeated_hypothesis(tmp_path: Path):
    hyp = Hypothesis("same", 0.9, [], "")
    with patch("ci_healer.orchestrator.verify", return_value=_v(False)), \
         patch("ci_healer.orchestrator.planner.plan", return_value=[hyp]), \
         patch("ci_healer.orchestrator.coder.apply_hypothesis", return_value=("noop", 0)):
        result = heal(tmp_path, "pytest", max_iters=4)
    assert not result.ok
    assert "no new hypotheses" in result.reason
