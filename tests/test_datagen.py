"""Generator determinism and ground-truth guarantees (SYNTHETIC data)."""

import numpy as np
import pandas as pd
import pytest

from datagen.generator import (N_DEVS, LineConfig, default_line_configs,
                               generate_claims, _gamma_lag_curve)


@pytest.fixture(scope="module")
def run():
    return generate_claims(seed=7, n_months=24, members=5000)


def test_same_seed_identical(run):
    payments, truth = run
    payments2, truth2 = generate_claims(seed=7, n_months=24, members=5000)
    pd.testing.assert_frame_equal(payments, payments2)
    for line in truth["true_ultimate"]:
        np.testing.assert_array_equal(truth["true_ultimate"][line],
                                      truth2["true_ultimate"][line])


def test_different_seed_differs(run):
    payments, _ = run
    payments2, _ = generate_claims(seed=8, n_months=24, members=5000)
    assert not payments["amount"].equals(payments2["amount"])


def test_true_ultimate_equals_sum_of_increments(run):
    payments, truth = run
    for line, ult in truth["true_ultimate"].items():
        sums = (payments[payments["line"] == line]
                .groupby("origin")["amount"].sum().values)
        np.testing.assert_allclose(sums, ult, rtol=1e-12)


def test_expected_shape_and_lines(run):
    payments, truth = run
    assert set(payments["line"]) == {"IP", "OP", "Rx"}
    assert len(payments) == 3 * 24 * N_DEVS
    assert set(payments.columns) == {"line", "origin", "dev", "amount"}
    assert truth["n_months"] == 24


def test_amounts_non_negative(run):
    payments, _ = run
    assert (payments["amount"] >= 0).all()


def test_devs_within_range(run):
    payments, _ = run
    assert payments["dev"].min() == 0
    assert payments["dev"].max() == N_DEVS - 1


def test_lag_curve_normalized():
    for cfg in default_line_configs().values():
        assert cfg.lag_curve.shape == (N_DEVS,)
        assert cfg.lag_curve.sum() == pytest.approx(1.0)
        assert (cfg.lag_curve >= 0).all()


def test_gamma_lag_curve_fast_vs_slow():
    fast = _gamma_lag_curve(1.2, 0.7)
    slow = _gamma_lag_curve(2.2, 2.5)
    assert fast[:3].sum() > slow[:3].sum()  # Rx-like pays sooner than IP-like


def test_noise_free_trend_exact():
    cfgs = {"X": LineConfig(base_pmpm=100.0, annual_trend=0.06,
                            seasonality_amp=0.0, cv=0.0,
                            lag_shape=1.5, lag_scale=1.0)}
    _, truth = generate_claims(seed=1, n_months=13, members=1000,
                               line_configs=cfgs)
    ult = truth["true_ultimate"]["X"]
    np.testing.assert_allclose(ult[12] / ult[0], 1.06, rtol=1e-12)


def test_true_trend_recorded(run):
    _, truth = run
    assert truth["true_trend"]["IP"] == pytest.approx(0.08)
    assert truth["true_trend"]["Rx"] == pytest.approx(0.10)
