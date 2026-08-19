"""Benchmarks: chain-ladder triangles/sec, workbook generation time, and the
200-triangle-set backtest end-to-end time (read from results/backtest.json,
which records its own measured elapsed time).

HONESTY TAG: SYNTHETIC seeded data; all numbers are wall-clock measurements
on the build machine.
"""

import json
import os
import platform
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datagen.generator import N_DEVS, generate_claims  # noqa: E402
from eval.make_exhibits import build_run, make  # noqa: E402
from ratecraft.reserving import build_triangle, chain_ladder, truncate_triangle  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bench_chain_ladder(n_iters: int = 3000, n_months: int = 36):
    payments, _ = generate_claims(123, n_months=n_months)
    tris = [truncate_triangle(build_triangle(payments, line=ln,
                                             n_origins=n_months,
                                             n_devs=N_DEVS))
            for ln in ("IP", "OP", "Rx")]
    # warmup
    for t in tris:
        chain_ladder(t)
    t0 = time.perf_counter()
    for k in range(n_iters):
        chain_ladder(tris[k % 3])
    dt = time.perf_counter() - t0
    return {"n_triangles": n_iters, "triangle_shape": [n_months, N_DEVS],
            "elapsed_seconds": dt, "triangles_per_sec": n_iters / dt}


def bench_workbook(n_iters: int = 5):
    run = build_run(seed=42)
    times = []
    from ratecraft.exhibits import write_exhibits
    for _ in range(n_iters):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "wb.xlsx")
            t0 = time.perf_counter()
            write_exhibits(p, *run)
            times.append(time.perf_counter() - t0)
    return {"n_iters": n_iters, "mean_seconds": sum(times) / len(times),
            "min_seconds": min(times)}


def main():
    out = {
        "honesty": "SYNTHETIC seeded data; wall-clock on build machine",
        "machine": {"platform": platform.platform(),
                    "python": platform.python_version()},
        "chain_ladder": bench_chain_ladder(),
        "workbook_generation": bench_workbook(),
    }
    bt_path = os.path.join(HERE, "results", "backtest.json")
    if os.path.exists(bt_path):
        with open(bt_path) as fh:
            bt = json.load(fh)
        out["backtest_end_to_end"] = {
            "n_triangle_sets": bt["n_triangle_sets"],
            "n_triangles_total": bt["n_triangles_total"],
            "elapsed_seconds": bt["elapsed_seconds"],
        }
    path = os.path.join(HERE, "results", "benchmarks.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
