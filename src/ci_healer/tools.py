import fnmatch
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MAX_READ_BYTES = 200_000
MAX_GREP_HITS = 200


class SandboxError(RuntimeError):
    pass


def _safe(root: Path, raw: str) -> Path:
    p = (root / raw).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        raise SandboxError(f"path escapes sandbox: {raw}") from None
    return p


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], str]

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


def build_tools(root: Path) -> list[Tool]:
    root = root.resolve()

    def read_file(args: dict) -> str:
        p = _safe(root, args["path"])
        if not p.exists():
            return f"not found: {args['path']}"
        if not p.is_file():
            return f"not a file: {args['path']}"
        data = p.read_bytes()[:MAX_READ_BYTES]
        return data.decode("utf-8", errors="replace")

    def write_file(args: dict) -> str:
        p = _safe(root, args["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args["content"], encoding="utf-8")
        return f"wrote {args['path']} ({len(args['content'])} bytes)"

    def replace_in_file(args: dict) -> str:
        p = _safe(root, args["path"])
        if not p.exists():
            return f"not found: {args['path']}"
        text = p.read_text(encoding="utf-8")
        old, new = args["old"], args["new"]
        n = text.count(old)
        if n == 0:
            return f"no match for old in {args['path']}"
        if n > 1:
            return f"old matches {n} times in {args['path']}, refine it"
        p.write_text(text.replace(old, new), encoding="utf-8")
        return f"replaced 1 occurrence in {args['path']}"

    def list_dir(args: dict) -> str:
        p = _safe(root, args.get("path") or ".")
        if not p.is_dir():
            return f"not a directory: {args.get('path')}"
        pat = args.get("pattern")
        out = []
        for e in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if pat and not fnmatch.fnmatch(e.name, pat):
                continue
            out.append(("d " if e.is_dir() else "f ") + e.name)
        return "\n".join(out) or "(empty)"

    def grep(args: dict) -> str:
        pattern = re.compile(args["pattern"])
        scope = _safe(root, args.get("path") or ".")
        hits: list[str] = []
        targets = [scope] if scope.is_file() else [p for p in scope.rglob("*") if p.is_file()]
        for f in targets:
            if any(part in {".git", ".venv", "__pycache__", "node_modules"} for part in f.parts):
                continue
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if pattern.search(line):
                        hits.append(f"{f.relative_to(root)}:{i}: {line}")
                        if len(hits) >= MAX_GREP_HITS:
                            return "\n".join(hits) + "\n...[truncated]"
            except OSError:
                continue
        return "\n".join(hits) or "(no matches)"

    return [
        Tool("read_file", "Read a text file. Returns up to 200KB.",
             {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
             read_file),
        Tool("write_file", "Write text to a file, creating parents as needed.",
             {"type": "object",
              "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
              "required": ["path", "content"]},
             write_file),
        Tool("replace_in_file",
             "Replace one exact occurrence of `old` with `new` in a file. Fails if old appears 0 or >1 times.",
             {"type": "object",
              "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}},
              "required": ["path", "old", "new"]},
             replace_in_file),
        Tool("list_dir", "List directory entries. Non-recursive. Optional glob pattern.",
             {"type": "object",
              "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}}},
             list_dir),
        Tool("grep", "Regex search across the repo or a single file. Returns up to 200 hits.",
             {"type": "object",
              "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
              "required": ["pattern"]},
             grep),
    ]
