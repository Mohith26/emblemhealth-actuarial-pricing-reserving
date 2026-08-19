"""Build a full deterministic exhibit workbook from one seeded run.

``python eval/make_exhibits.py [path]`` writes examples/sample_exhibits.xlsx
by default (seed 42 -- SYNTHETIC data, deterministic).
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datagen.generator import N_DEVS, generate_claims  # noqa: E402
from eval.backtest import bf_prior_from_completed  # noqa: E402
from ratecraft.exhibits import write_exhibits  # noqa: E402
from ratecraft.pricing import develop_rate, limited_fluctuation_z, measure_trend  # noqa: E402
from ratecraft.reserving import (bornhuetter_ferguson, build_triangle,  # noqa: E402
                                 chain_ladder, truncate_triangle)

LINES = ("IP", "OP", "Rx")


def build_run(seed: int = 42, n_months: int = 36, members: int = 10000):
    payments, truth = generate_claims(seed, n_months=n_months, members=members)
    triangles, cl, bf, trend, rate_dev = {}, {}, {}, {}, {}
    for line in LINES:
        full = build_triangle(payments, line=line,
                              n_origins=n_months, n_devs=N_DEVS)
        trunc = truncate_triangle(full)
        triangles[line] = trunc
        cl[line] = chain_ladder(trunc)
        bf[line] = bornhuetter_ferguson(trunc, bf_prior_from_completed(trunc))
        n_d = trunc.shape[1]
        complete = [i for i in range(n_months)
                    if not np.isnan(trunc[i, n_d - 1])]
        totals = [float(trunc[i, n_d - 1]) for i in complete]
        measured = measure_trend(totals)
        trend[line] = {"monthly_totals": totals,
                       "measured_annual_trend": measured}
        exp_months = 12
        claims_12m = float(sum(totals[-exp_months:]))
        mm = float(members * exp_months)
        rate_dev[line] = develop_rate(
            completed_claims=claims_12m, member_months=mm,
            annual_trend=measured, trend_months=24.0,
            manual_pmpm=round(claims_12m / mm * 1.05, 2),
            credibility_n=mm, full_credibility_n=200000.0,
            target_loss_ratio=0.85)
    cred_rows = [(lbl, n, fn, limited_fluctuation_z(n, fn))
                 for lbl, n, fn in [("small_group", 2500, 200000),
                                    ("mid_group", 50000, 200000),
                                    ("large_group", 200000, 200000),
                                    ("jumbo_group", 400000, 200000)]]
    return triangles, cl, bf, trend, rate_dev, cred_rows


def make(path: str, seed: int = 42):
    write_exhibits(path, *build_run(seed))
    return path


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default = os.path.join(here, "examples", "sample_exhibits.xlsx")
    target = sys.argv[1] if len(sys.argv) > 1 else default
    os.makedirs(os.path.dirname(target), exist_ok=True)
    print("wrote", make(target))
