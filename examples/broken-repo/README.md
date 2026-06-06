# broken-repo

A tiny Python project used as a fixture for `ci-healer`. The bug is intentional: `tests/test_calc.py` is missing the import for `add` and `divide`. Running `pytest` fails with `NameError`.

From the repo root:

```
uv run ci-healer fix ./examples/broken-repo --cmd "pytest"
```
