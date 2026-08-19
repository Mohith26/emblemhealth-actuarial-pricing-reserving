"""Reserve backtest on held-out runoff diagonals with KNOWN ground truth.

For each of N seeded SYNTHETIC datasets (3 lines x 36 origin months, runoff
complete by lag 23):
  1. Build the full cumulative square per line; TRUE ultimates are known
     exactly from the generator (Dirichlet split sums exactly to ultimate).
  2. Truncate at the standard valuation diagonal (origin + dev <= 35),
     hiding the held-out future runoff.
  3. Estimate IBNR via chain-ladder and Bornhuetter-Ferguson.
     BF prior: log-linear trend fit to the ultimates of origins already fully
     developed at the valuation date (origins 0..12), projected to all
     origins -- an expected-loss prior derived only from observable data.
  4. Compare estimated total IBNR / ultimate vs KNOWN truth.

Metrics per line per method: MAPE and median APE of total IBNR, bias (mean
signed percentage error of IBNR), and % of datasets where the TRUE total
ultimate falls within +/-10% of the estimated total ultimate.

Also measures trend recovery: annualized trend measured from completed
origins vs the generator's true configured trend.

HONESTY TAG: SYNTHETIC seeded data only (real claims would be PHI).
"""

import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datagen.generator import N_DEVS, generate_claims  # noqa: E402
from ratecraft.pricing import measure_trend  # noqa: E402
from ratecraft.reserving import (bornhuetter_ferguson, build_triangle,  # noqa: E402
                                 chain_ladder, truncate_triangle)

LINES = ("IP", "OP", "Rx")
WITHIN_BAND = 0.10


def bf_prior_from_completed(trunc: np.ndarray) -> np.ndarray:
    """Expected-loss prior: log-linear fit to fully-developed origins'
    ultimates (observable at valuation), projected to every origin."""
    n_o, n_d = trunc.shape
    complete = [i for i in range(n_o) if not np.isnan(trunc[i, n_d - 1])]
    y = np.array([trunc[i, n_d - 1] for i in complete], dtype=float)
    t = np.array(complete, dtype=float)
    slope, intercept = np.polyfit(t, np.log(y), 1)
    return np.exp(intercept + slope * np.arange(n_o))


def run_one(seed: int, n_months: int = 36):
    payments, truth = generate_claims(seed, n_months=n_months)
    out = {}
    for line in LINES:
        full = build_triangle(payments, line=line,
                              n_origins=n_months, n_devs=N_DEVS)
        trunc = truncate_triangle(full)
        true_ult = truth["true_ultimate"][line]
        latest = np.array([trunc[i, min(n_months - 1 - i, N_DEVS - 1)]
                           for i in range(n_months)])
        true_total_ult = float(true_ult.sum())
        true_total_ibnr = float(true_ult.sum() - latest.sum())

        prior = bf_prior_from_completed(trunc)
        cl = chain_ladder(trunc)
        bf = bornhuetter_ferguson(trunc, prior)

        n_d = trunc.shape[1]
        complete = [i for i in range(n_months)
                    if not np.isnan(trunc[i, n_d - 1])]
        measured = measure_trend([trunc[i, n_d - 1] for i in complete])

        out[line] = {
            "true_total_ultimate": true_total_ult,
            "true_total_ibnr": true_total_ibnr,
            "true_trend": truth["true_trend"][line],
            "measured_trend": measured,
            "methods": {
                "chain_ladder": {"est_ibnr": cl.total_ibnr,
                                 "est_ultimate": cl.total_ultimate},
                "bornhuetter_ferguson": {"est_ibnr": bf.total_ibnr,
                                         "est_ultimate": bf.total_ultimate},
            },
        }
    return out


def aggregate(per_run):
    agg = {}
    for line in LINES:
        agg[line] = {"methods": {}}
        for method in ("chain_ladder", "bornhuetter_ferguson"):
            apes, pes, within = [], [], []
            for r in per_run:
                d = r[line]
                est_ibnr = d["methods"][method]["est_ibnr"]
                est_ult = d["methods"][method]["est_ultimate"]
                true_ibnr = d["true_total_ibnr"]
                true_ult = d["true_total_ultimate"]
                pe = (est_ibnr - true_ibnr) / true_ibnr
                pes.append(pe)
                apes.append(abs(pe))
                within.append(abs(true_ult - est_ult) / est_ult <= WITHIN_BAND)
            agg[line]["methods"][method] = {
                "ibnr_mape_pct": 100.0 * float(np.mean(apes)),
                "ibnr_median_ape_pct": 100.0 * float(np.median(apes)),
                "ibnr_bias_pct": 100.0 * float(np.mean(pes)),
                "ultimate_within_10pct_rate": float(np.mean(within)),
            }
        terr = [abs(r[line]["measured_trend"] - r[line]["true_trend"])
                for r in per_run]
        agg[line]["trend_recovery"] = {
            "true_trend": per_run[0][line]["true_trend"],
            "mean_abs_error_pp": 100.0 * float(np.mean(terr)),
            "max_abs_error_pp": 100.0 * float(np.max(terr)),
        }
    return agg


def run_backtest(n_triangle_sets: int = 200, base_seed: int = 1000,
                 out_path: str = None):
    t0 = time.time()
    per_run = [run_one(base_seed + k) for k in range(n_triangle_sets)]
    elapsed = time.time() - t0
    result = {
        "honesty": "SYNTHETIC seeded data; ground truth known by construction",
        "n_triangle_sets": n_triangle_sets,
        "n_triangles_total": n_triangle_sets * len(LINES),
        "base_seed": base_seed,
        "within_band": WITHIN_BAND,
        "elapsed_seconds": elapsed,
        "aggregate": aggregate(per_run),
    }
    if out_path:
        with open(out_path, "w") as fh:
            json.dump(result, fh, indent=2)
    return result


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, "results", "backtest.json")
    res = run_backtest(n, out_path=out)
    print(json.dumps(res["aggregate"], indent=2))
    print(f"elapsed: {res['elapsed_seconds']:.1f}s -> {out}")
