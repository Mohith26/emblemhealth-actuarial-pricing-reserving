"""Reconciliation invariant sweep: run the rate-development chain over many
seeded random cases and count to-the-cent violations (must be 0).

HONESTY TAG: SYNTHETIC seeded inputs.
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ratecraft.pricing import develop_rate, reconcile  # noqa: E402


def run_sweep(n_cases: int = 200, seed: int = 777):
    rng = np.random.default_rng(seed)
    violations = 0
    worst = 0
    for _ in range(n_cases):
        mm = float(rng.integers(500, 50000))
        rd = develop_rate(
            completed_claims=float(rng.uniform(50, 600)) * mm,
            member_months=mm,
            annual_trend=float(rng.uniform(0.02, 0.12)),
            trend_months=float(rng.integers(6, 36)),
            manual_pmpm=float(rng.uniform(200, 800)),
            credibility_n=mm,
            full_credibility_n=float(rng.integers(5000, 30000)),
            target_loss_ratio=float(rng.uniform(0.75, 0.92)),
        )
        diffs = reconcile(rd)
        if any(v != 0 for v in diffs.values()):
            violations += 1
            worst = max(worst, max(abs(v) for v in diffs.values()))
    return {"n_cases": n_cases, "seed": seed,
            "violations": violations, "worst_abs_diff_cents": worst}


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    res = run_sweep(n)
    path = os.path.join(here, "results", "reconciliation.json")
    with open(path, "w") as fh:
        json.dump(res, fh, indent=2)
    print(json.dumps(res, indent=2))
