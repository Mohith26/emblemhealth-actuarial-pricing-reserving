"""Backtest math and determinism (SYNTHETIC seeded ground truth)."""

import numpy as np
import pytest

from datagen.generator import N_DEVS, LineConfig, generate_claims
from eval.backtest import (WITHIN_BAND, aggregate, bf_prior_from_completed,
                           run_backtest, run_one)
from ratecraft.reserving import build_triangle, truncate_triangle


def test_bf_prior_recovers_noise_free_ultimates():
    cfgs = {"X": LineConfig(base_pmpm=100.0, annual_trend=0.06,
                            seasonality_amp=0.0, cv=0.0,
                            lag_shape=1.5, lag_scale=1.0,
                            dirichlet_conc=1e9)}
    payments, truth = generate_claims(seed=3, n_months=36, members=1000,
                                      line_configs=cfgs)
    full = build_triangle(payments, line="X", n_origins=36, n_devs=N_DEVS)
    prior = bf_prior_from_completed(truncate_triangle(full))
    np.testing.assert_allclose(prior, truth["true_ultimate"]["X"], rtol=1e-3)


def test_run_one_structure_and_truth():
    out = run_one(seed=1234)
    for line in ("IP", "OP", "Rx"):
        d = out[line]
        assert d["true_total_ibnr"] > 0
        assert d["true_total_ultimate"] > d["true_total_ibnr"]
        for m in ("chain_ladder", "bornhuetter_ferguson"):
            assert d["methods"][m]["est_ibnr"] > 0
            assert (d["methods"][m]["est_ultimate"]
                    > d["methods"][m]["est_ibnr"])


def test_aggregate_math_on_synthetic_metrics():
    per_run = []
    for est in (110.0, 90.0):  # +10% and -10% IBNR error
        per_run.append({ln: {
            "true_total_ultimate": 1000.0,
            "true_total_ibnr": 100.0,
            "true_trend": 0.08,
            "measured_trend": 0.09,
            "methods": {m: {"est_ibnr": est, "est_ultimate": 1000.0 + est - 100.0}
                        for m in ("chain_ladder", "bornhuetter_ferguson")},
        } for ln in ("IP", "OP", "Rx")})
    agg = aggregate(per_run)
    m = agg["IP"]["methods"]["chain_ladder"]
    assert m["ibnr_mape_pct"] == pytest.approx(10.0)
    assert m["ibnr_bias_pct"] == pytest.approx(0.0)
    assert m["ultimate_within_10pct_rate"] == 1.0
    assert agg["IP"]["trend_recovery"]["mean_abs_error_pp"] == pytest.approx(1.0)


def test_within_band_logic():
    per_run = [{ln: {
        "true_total_ultimate": 1200.0,  # 20% above estimate -> outside band
        "true_total_ibnr": 100.0,
        "true_trend": 0.08,
        "measured_trend": 0.08,
        "methods": {m: {"est_ibnr": 100.0, "est_ultimate": 1000.0}
                    for m in ("chain_ladder", "bornhuetter_ferguson")},
    } for ln in ("IP", "OP", "Rx")}]
    agg = aggregate(per_run)
    assert WITHIN_BAND == 0.10
    assert (agg["OP"]["methods"]["bornhuetter_ferguson"]
            ["ultimate_within_10pct_rate"] == 0.0)


def test_backtest_deterministic():
    r1 = run_backtest(2, base_seed=555)
    r2 = run_backtest(2, base_seed=555)
    assert r1["aggregate"] == r2["aggregate"]
    assert r1["n_triangles_total"] == 6


def test_backtest_writes_json(tmp_path):
    p = tmp_path / "bt.json"
    run_backtest(1, base_seed=9, out_path=str(p))
    import json
    with open(p) as fh:
        data = json.load(fh)
    assert data["n_triangle_sets"] == 1
    assert "SYNTHETIC" in data["honesty"]
