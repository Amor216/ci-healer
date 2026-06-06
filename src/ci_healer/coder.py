import os
from pathlib import Path

import anthropic

from .costs import CostTracker
from .planner import Hypothesis
from .tools import Tool, build_tools
from .verifier import VerifyResult

CODER_MODEL = os.environ.get("HEALER_CODER_MODEL", "claude-sonnet-4-5")
MAX_STEPS = 10

SYSTEM = """You are a code-fixing agent. You receive one hypothesis for what's broken and a set of file tools to investigate and patch the repo.

Rules:
- Read before you write. Confirm the actual file contents match the hypothesis.
- Prefer `replace_in_file` over `write_file` for small edits.
- Make the minimum change needed to fix the hypothesis. Do not refactor.
- Stop when you've made an edit you believe addresses the hypothesis. The verifier will tell you if it worked.
- Output one brief sentence about what you changed, then stop. No code dumps.
"""


def apply_hypothesis(
    root: Path,
    hypothesis: Hypothesis,
    failure: VerifyResult,
    cmd: str,
    cost: CostTracker,
    client: anthropic.Anthropic | None = None,
) -> tuple[str, int]:
    """Returns (summary_text, tool_call_count)."""
    client = client or anthropic.Anthropic()
    tools = build_tools(root)
    by_name = {t.name: t for t in tools}

    user_msg = (
        f"Command that failed: {cmd}\n"
        f"Exit code: {failure.exit_code}\n\n"
        f"=== ERROR (tail) ===\n{(failure.stderr or failure.stdout)[-2000:]}\n\n"
        f"=== HYPOTHESIS ===\n{hypothesis.summary}\n"
        f"confidence: {hypothesis.confidence:.2f}\n"
        f"reasoning: {hypothesis.reasoning}\n"
        f"likely files: {', '.join(hypothesis.relevant_files) or '(none specified)'}\n"
    )
    messages: list[dict] = [{"role": "user", "content": user_msg}]
    tool_schemas = [t.schema() for t in tools]
    tool_calls = 0

    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=CODER_MODEL,
            max_tokens=2048,
            system=SYSTEM,
            tools=tool_schemas,
            messages=messages,
        )
        cost.add(CODER_MODEL, resp.usage.input_tokens, resp.usage.output_tokens)
        messages.append({"role": "assistant", "content": [_serialize(b) for b in resp.content]})

        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return text.strip() or "no edits made", tool_calls

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            tool_calls += 1
            results.append(_run(block, by_name))
        messages.append({"role": "user", "content": results})

    return "max steps reached without finishing", tool_calls


def _run(block, by_name: dict[str, Tool]) -> dict:
    try:
        out = by_name[block.name].handler(block.input)
        return {"type": "tool_result", "tool_use_id": block.id, "content": out}
    except KeyError:
        return {"type": "tool_result", "tool_use_id": block.id,
                "content": f"unknown tool: {block.name}", "is_error": True}
    except Exception as e:
        return {"type": "tool_result", "tool_use_id": block.id,
                "content": f"{type(e).__name__}: {e}", "is_error": True}


def _serialize(block) -> dict:
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return block.model_dump()
