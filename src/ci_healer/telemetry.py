import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Telemetry:
    path: Path | None = None
    buffered: list[dict[str, Any]] = field(default_factory=list)

    def record(self, **fields: Any) -> None:
        event = {"ts": time.time(), **fields}
        self.buffered.append(event)
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
