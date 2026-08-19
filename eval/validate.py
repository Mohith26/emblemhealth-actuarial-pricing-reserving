"""Validation A (textbook oracle) + Validation B (independent naive oracle).

A: reproduce the published Taylor & Ashe (1983) 10x10 chain-ladder example
   (factors as hand-computed in Mack 1993; ultimates/total reserve as
   published in England & Verrall 2002) from the committed fixture.
B: compare the vectorized engine vs the deliberately-naive loop
   implementation on the textbook triangle plus seeded synthetic triangles;
   report max deviations.
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datagen.generator import N_DEVS, generate_claims  # noqa: E402
from eval.naive_oracle import naive_chain_ladder, triangle_to_lists  # noqa: E402
from ratecraft.reserving import build_triangle, chain_ladder, truncate_triangle  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "tests", "fixtures", "taylor_ashe.json")


def load_taylor_ashe():
    with open(FIXTURE) as fh:
        fx = json.load(fh)
    n = len(fx["incremental_paid"])
    tri = np.full((n, n), np.nan)
    for i, row in enumerate(fx["incremental_paid"]):
        tri[i, :len(row)] = np.cumsum(row)
    return tri, fx


def validate_textbook():
    tri, fx = load_taylor_ashe()
    res = chain_ladder(tri)
    factor_dev = np.abs(np.round(res.factors, 4)
                        - np.array(fx["published_ata_factors_4dp"]))
    ult_dev = np.abs(np.round(res.ultimate)
                     - np.array(fx["published_ultimates"], dtype=float))
    return {
        "factors_match_published_4dp": bool(np.all(factor_dev == 0)),
        "max_factor_abs_dev_after_4dp_rounding": float(factor_dev.max()),
        "ultimates_match_published_rounded_to_unit": bool(np.all(ult_dev == 0)),
        "max_ultimate_abs_dev_after_unit_rounding": float(ult_dev.max()),
        "total_reserve_engine": float(round(res.total_ibnr)),
        "total_reserve_published": fx["published_total_reserve"],
        "total_reserve_match": int(round(res.total_ibnr)) == fx["published_total_reserve"],
    }


def validate_oracle(n_random: int = 50, base_seed: int = 5000):
    tri, _ = load_taylor_ashe()
    triangles = [tri]
    for k in range(n_random):
        payments, _ = generate_claims(base_seed + k, n_months=36)
        for line in ("IP", "OP", "Rx"):
            full = build_triangle(payments, line=line,
                                  n_origins=36, n_devs=N_DEVS)
            triangles.append(truncate_triangle(full))
        if len(triangles) > n_random:
            break
    max_rel = 0.0
    for t in triangles[:n_random + 1]:
        res = chain_ladder(t)
        f, cdf, ult, ibnr = naive_chain_ladder(triangle_to_lists(t))
        for a, b in [(res.factors, f), (res.cdf, cdf),
                     (res.ultimate, ult), (res.ibnr, ibnr)]:
            a = np.asarray(a, dtype=float)
            b = np.asarray(b, dtype=float)
            denom = np.maximum(np.abs(a), 1.0)
            max_rel = max(max_rel, float(np.max(np.abs(a - b) / denom)))
    return {"n_triangles_compared": min(len(triangles), n_random + 1),
            "max_relative_deviation": max_rel}


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = {
        "honesty": "textbook fixture is published data; other triangles SYNTHETIC seeded",
        "textbook": validate_textbook(),
        "naive_oracle": validate_oracle(),
    }
    path = os.path.join(here, "results", "validation.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))
