from ci_healer.costs import CostTracker, cost_usd


def test_pricing_known_models():
    assert cost_usd("claude-sonnet-4-5", 1_000_000, 1_000_000) == 18.0
    assert cost_usd("claude-opus-4-5", 1_000_000, 1_000_000) == 90.0


def test_pricing_unknown():
    assert cost_usd("nothing", 1000, 1000) == 0.0


def test_tracker_accumulates():
    c = CostTracker()
    c.add("claude-sonnet-4-5", 100, 50)
    c.add("claude-sonnet-4-5", 200, 100)
    c.add("claude-opus-4-5", 50, 20)
    assert c.by_model["claude-sonnet-4-5"] == (300, 150)
    assert c.by_model["claude-opus-4-5"] == (50, 20)
    assert c.total_usd() > 0


def test_tracker_lines_have_total():
    c = CostTracker()
    c.add("claude-sonnet-4-5", 1000, 500)
    lines = c.lines()
    assert any("sonnet" in line for line in lines)
    assert any("total cost" in line for line in lines)
