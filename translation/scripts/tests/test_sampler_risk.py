"""--order risk: the riskiest pages first, deterministically."""


def _info(rel, verdict=None, reviewed=None, unverified=(), lines=10):
    return {"rel": rel, "verdict": verdict, "reviewed": reviewed,
            "unverified": list(unverified), "lines": lines}


def test_risk_order_puts_fail_then_unread_then_unverified_then_oldest(sampler):
    cat = {
        "old.mdx": _info("old.mdx", "PASS", "2026-06-01"),
        "new.mdx": _info("new.mdx", "MINOR_ISSUES", "2026-09-29"),
        "fail.mdx": _info("fail.mdx", "FAIL", "2026-09-29"),
        "never.mdx": _info("never.mdx"),
        "delta.mdx": _info("delta.mdx", "PASS", "2026-09-29", unverified=[{"index": 1}]),
    }
    rows = [(rel, "guides", 10, "?", "full", []) for rel in cat]
    picked = [r[0] for r in sampler.pick_by_risk(rows, 5, cat)]
    assert picked == ["fail.mdx", "never.mdx", "delta.mdx", "old.mdx", "new.mdx"]
    assert [r[0] for r in sampler.pick_by_risk(rows, 2, cat)] == ["fail.mdx", "never.mdx"]


def test_risk_order_prefers_longer_pages_within_a_tier(sampler):
    cat = {"short.mdx": _info("short.mdx", "FAIL", "2026-09-01", lines=5),
           "long.mdx": _info("long.mdx", "FAIL", "2026-09-01", lines=500)}
    rows = [(rel, "guides", 0, "?", "full", []) for rel in cat]
    assert [r[0] for r in sampler.pick_by_risk(rows, 2, cat)] == ["long.mdx", "short.mdx"]
