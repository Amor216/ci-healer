import json
import os
from dataclasses import dataclass
from pathlib import Path

import anthropic

from .costs import CostTracker
from .verifier import VerifyResult

PLANNER_MODEL = os.environ.get("HEALER_PLANNER_MODEL", "claude-opus-4-5")

SYSTEM = """You diagnose failing builds and tests. Given a failure log and a project layout, return a JSON object with 1-3 ranked hypotheses for what's broken and which files to look at.

Each hypothesis must be specific (a concrete change a coder could try), not vague advice. Confidence is your honest 0-1 estimate that fixing this single thing makes the build pass.

Output strictly this shape, nothing else:

{"hypotheses": [{"summary": "...", "confidence": 0.0, "relevant_files": ["..."], "reasoning": "..."}]}
"""


@dataclass
class Hypothesis:
    summary: str
    confidence: float
    relevant_files: list[str]
    reasoning: str


def _list_repo(root: Path, max_entries: int = 200) -> str:
    skip = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache"}
    out = []
    for p in sorted(root.rglob("*")):
        if any(part in skip for part in p.parts):
            continue
        rel = p.relative_to(root)
        out.append(("d " if p.is_dir() else "f ") + str(rel))
        if len(out) >= max_entries:
            out.append("...[truncated]")
            break
    return "\n".join(out)


def plan(workdir: Path, result: VerifyResult, cmd: str, cost: CostTracker,
         client: anthropic.Anthropic | None = None) -> list[Hypothesis]:
    client = client or anthropic.Anthropic()
    user = (
        f"Command: {cmd}\n"
        f"Exit code: {result.exit_code}\n\n"
        f"=== STDERR ===\n{result.stderr or '(empty)'}\n\n"
        f"=== STDOUT (tail) ===\n{result.stdout[-2000:] or '(empty)'}\n\n"
        f"=== REPO LAYOUT ===\n{_list_repo(workdir)}\n"
    )
    resp = client.messages.create(
        model=PLANNER_MODEL,
        max_tokens=2048,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    cost.add(PLANNER_MODEL, resp.usage.input_tokens, resp.usage.output_tokens)

    text = next((b.text for b in resp.content if b.type == "text"), "")
    return _parse(text)


def _parse(text: str) -> list[Hypothesis]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    out = []
    for h in data.get("hypotheses") or []:
        try:
            out.append(Hypothesis(
                summary=str(h["summary"])[:200],
                confidence=float(h.get("confidence", 0.5)),
                relevant_files=list(h.get("relevant_files") or [])[:5],
                reasoning=str(h.get("reasoning", ""))[:500],
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(out, key=lambda x: -x.confidence)[:3]
