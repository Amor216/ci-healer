from types import SimpleNamespace
from unittest.mock import MagicMock

from ci_healer.costs import CostTracker
from ci_healer.planner import _parse, plan
from ci_healer.verifier import VerifyResult


def _msg(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )


def test_parse_well_formed():
    raw = """Some preamble. {"hypotheses": [{"summary": "missing import", "confidence": 0.9,
              "relevant_files": ["a.py"], "reasoning": "stack trace points to a.py"}]}"""
    out = _parse(raw)
    assert len(out) == 1
    assert out[0].summary == "missing import"
    assert out[0].confidence == 0.9


def test_parse_garbage_returns_empty():
    assert _parse("not json") == []
    assert _parse("") == []


def test_parse_sorts_by_confidence_desc():
    raw = ('{"hypotheses": ['
           '{"summary": "low", "confidence": 0.1, "relevant_files": [], "reasoning": ""},'
           '{"summary": "high", "confidence": 0.9, "relevant_files": [], "reasoning": ""}'
           ']}')
    out = _parse(raw)
    assert [h.summary for h in out] == ["high", "low"]


def test_parse_caps_at_three():
    items = ",".join(
        f'{{"summary": "h{i}", "confidence": {0.5 + i * 0.01}, "relevant_files": [], "reasoning": ""}}'
        for i in range(5)
    )
    out = _parse('{"hypotheses": [' + items + ']}')
    assert len(out) == 3


def test_plan_calls_client(tmp_path):
    client = MagicMock()
    client.messages.create.return_value = _msg(
        '{"hypotheses": [{"summary": "x", "confidence": 0.5, "relevant_files": [], "reasoning": ""}]}'
    )
    cost = CostTracker()
    res = plan(tmp_path, VerifyResult(False, 1, "", "boom"), "pytest", cost, client=client)
    assert len(res) == 1
    assert client.messages.create.call_count == 1
    assert cost.by_model
