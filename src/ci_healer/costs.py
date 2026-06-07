from dataclasses import dataclass, field

# USD per 1M tokens.
PRICING = {
    "claude-opus-4-5":   (15.00, 75.00),
    "claude-sonnet-4-5": (3.00,  15.00),
    "claude-haiku-4-5":  (1.00,  5.00),
}


def cost_usd(model: str, in_tok: int, out_tok: int) -> float:
    for prefix, (in_p, out_p) in PRICING.items():
        if model.startswith(prefix):
            return (in_tok / 1_000_000) * in_p + (out_tok / 1_000_000) * out_p
    return 0.0


class BudgetExceeded(Exception):
    def __init__(self, spent: float, cap: float) -> None:
        super().__init__(f"budget exceeded: spent ${spent:.4f} > cap ${cap:.4f}")
        self.spent = spent
        self.cap = cap


@dataclass
class CostTracker:
    by_model: dict[str, tuple[int, int]] = field(default_factory=dict)
    max_usd: float | None = None

    def add(self, model: str, in_tok: int, out_tok: int) -> None:
        cur_in, cur_out = self.by_model.get(model, (0, 0))
        self.by_model[model] = (cur_in + in_tok, cur_out + out_tok)
        if self.max_usd is not None and self.total_usd() > self.max_usd:
            raise BudgetExceeded(self.total_usd(), self.max_usd)

    def total_usd(self) -> float:
        return sum(cost_usd(m, i, o) for m, (i, o) in self.by_model.items())

    def lines(self) -> list[str]:
        out = []
        for m, (i, o) in self.by_model.items():
            label = m.split("-")[1] if "-" in m else m
            out.append(f"{label}: {_h(i)} in, {_h(o)} out, ${cost_usd(m, i, o):.4f}")
        out.append(f"total cost: ${self.total_usd():.4f}")
        return out


def _h(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)
