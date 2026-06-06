# ci-healer

A CLI agent that points at a project with a failing build and tries to fix it. Multi-agent: a planner (Opus) forms ranked hypotheses from the failure log, a coder (Sonnet) applies fixes through a small set of file tools, a deterministic verifier re-runs the command. The loop runs until the build is green or `max-iters` is reached. The result is a `git diff` patch and a per-model cost report.

No LangChain or other agent framework. Direct Anthropic SDK calls, ~600 lines of Python.

## Run

```
uv sync
cp .env.example .env  # add ANTHROPIC_API_KEY
uv run ci-healer fix ./examples/broken-repo --cmd "pytest"
```

Example output:

```
[verifier] running pytest
[verifier] FAIL (exit 1)
  E   NameError: name 'add' is not defined
[planner] reading repo and forming hypotheses
[planner] 2 candidate(s):
  1 (0.88) missing import in tests/test_calc.py
  2 (0.20) calc module not on sys.path
[coder] attempt 1 of 5: missing import in tests/test_calc.py
[coder] added 'from calc import add, divide' to tests/test_calc.py (2 tool call(s))
[verifier] running pytest
[verifier] PASS

fixed in 1 iteration(s)
opus: 1.4k in, 220 out, $0.0375
sonnet: 3.2k in, 78 out, $0.0108
total cost: $0.0483

patch written: ./healer.patch
```

## Why a CLI, not a webhook server

A webhook listener is more complex to set up, run, and demo. The interesting work is the agent loop: nothing about it requires HTTP. You can wire this into a CI runner (e.g. an Actions step that runs `ci-healer fix .` when a job fails) without changing the core.

## Architecture

```
ci-healer fix <repo> --cmd <command>
       |
       v
  Orchestrator (heal loop, max 5 iterations)
       |
       +-- Verifier   subprocess, parses exit code + stderr (no LLM, deterministic)
       |
       +-- Planner    Opus, JSON output: ranked hypotheses with files + reasoning
       |
       +-- Coder      Sonnet, tool-use loop: read, write, replace, list, grep
       |
       v
   git diff -> healer.patch, multi-model cost report
```

The roles use different models on purpose. Opus does the diagnostic reasoning where breadth matters. Sonnet handles the structured edits in the tool loop. The verifier doesn't need an LLM at all, it just runs the command.

## Tools the coder has

All tools are scoped to the target repo path. Any attempt to read or write outside that path raises `SandboxError` before any IO happens.

| Tool | Purpose |
|---|---|
| `read_file` | Read a text file, up to 200KB |
| `write_file` | Write a full file, creating parents |
| `replace_in_file` | Replace one unique substring, fails if 0 or >1 matches |
| `list_dir` | Non-recursive listing, optional glob |
| `grep` | Regex over the repo, up to 200 hits |

`replace_in_file` is preferred over `write_file` for small fixes. It refuses to act on ambiguous matches, which keeps the coder from accidentally rewriting unrelated code that happens to share a substring.

## Safety

- Path sandboxing: every tool resolves paths under the repo root and rejects `..` escapes.
- Iteration cap: the heal loop stops after `--max-iters` (default 5).
- Hypothesis dedup: the orchestrator refuses to retry a hypothesis it already attempted.
- No write outside the repo and no shell escapes through the tools. Subprocesses live only in the verifier.

## Layout

```
src/ci_healer/
  cli.py            argparse entrypoint
  orchestrator.py   heal loop
  planner.py        Opus call, JSON parse
  coder.py          Sonnet tool-use loop
  verifier.py       subprocess runner
  tools.py          read, write, replace_in_file, list_dir, grep
  patch.py          git baseline + diff capture
  costs.py          per-model token cost
examples/
  broken-repo/      a tiny Python project with a deliberate bug
```

## Limits

- Single-language fixes work best (Python in the bundled fixture). Multi-language repos need the verifier command to be the right entry point.
- The planner sees a flat file listing, not the contents of every file. The coder pulls files in as needed via tools.
- If the failure needs a multi-file refactor, the coder won't be aggressive enough on its own. The loop will eventually give up rather than thrash.

## License

MIT.
