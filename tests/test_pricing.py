"""Pricing: trend measurement, credibility hand cases, rate development, and
the to-the-cent reconciliation invariant."""

import math

import numpy as np
import pytest

from ratecraft.pricing import (credibility_blend, develop_rate,
                               limited_fluctuation_z, measure_trend,
                               reconcile, reconciliation_ok, trend_factor)


# ---------- trend ----------

def test_measure_trend_exact_on_noise_free_series():
    y = [1000.0 * 1.07 ** (t / 12.0) for t in range(24)]
    assert measure_trend(y) == pytest.approx(0.07, abs=1e-12)


def test_measure_trend_flat_series_is_zero():
    assert measure_trend([500.0] * 12) == pytest.approx(0.0, abs=1e-12)


def test_measure_trend_rejects_short_series():
    with pytest.raises(ValueError):
        measure_trend([100.0])


def test_measure_trend_rejects_non_positive():
    with pytest.raises(ValueError):
        measure_trend([100.0, 0.0, 50.0])


def test_trend_factor_hand_computed():
    assert trend_factor(0.08, 24) == pytest.approx(1.08 ** 2)
    assert trend_factor(0.08, 6) == pytest.approx(1.08 ** 0.5)
    assert trend_factor(0.0, 18) == 1.0


# ---------- limited-fluctuation credibility (hand-computed cases) ----------

def test_z_full_credibility():
    assert limited_fluctuation_z(1082, 1082) == 1.0
    assert limited_fluctuation_z(5000, 1082) == 1.0  # capped at 1


def test_z_zero_experience():
    assert limited_fluctuation_z(0, 1082) == 0.0


def test_z_quarter_gives_half():
    assert limited_fluctuation_z(270.5, 1082) == pytest.approx(0.5)


def test_z_hand_case_sqrt():
    assert limited_fluctuation_z(400, 1600) == pytest.approx(0.5)
    assert limited_fluctuation_z(900, 1600) == pytest.approx(0.75)
    assert limited_fluctuation_z(50, 200000) == pytest.approx(math.sqrt(50 / 200000))


def test_z_invalid_inputs():
    with pytest.raises(ValueError):
        limited_fluctuation_z(10, 0)
    with pytest.raises(ValueError):
        limited_fluctuation_z(-1, 100)


def test_blend_hand_computed():
    assert credibility_blend(100.0, 80.0, 0.6) == pytest.approx(92.0)
    assert credibility_blend(100.0, 80.0, 1.0) == 100.0
    assert credibility_blend(100.0, 80.0, 0.0) == 80.0


def test_blend_rejects_bad_z():
    with pytest.raises(ValueError):
        credibility_blend(1.0, 1.0, 1.5)


# ---------- rate development ----------

def hand_case():
    return develop_rate(completed_claims=5_400_000.0, member_months=12_000.0,
                        annual_trend=0.08, trend_months=24.0,
                        manual_pmpm=500.0, credibility_n=12_000.0,
                        full_credibility_n=48_000.0, target_loss_ratio=0.85)


def test_develop_rate_hand_computed_chain():
    rd = hand_case()
    assert rd.experience_pmpm == 450.00                      # 5.4M / 12k
    assert rd.trend_factor == pytest.approx(1.08 ** 2)
    assert rd.projected_pmpm == round(450.00 * 1.08 ** 2, 2)  # 524.88
    assert rd.projected_pmpm == 524.88
    assert rd.z == pytest.approx(0.5)                        # sqrt(12k/48k)
    assert rd.blended_pmpm == round(0.5 * 524.88 + 0.5 * 500.0, 2)  # 512.44
    assert rd.required_pmpm == round(512.44 / 0.85, 2)       # 602.87
    assert rd.required_pmpm == 602.87


def test_develop_rate_full_credibility_ignores_manual():
    rd = develop_rate(1_000_000, 10_000, 0.05, 12, 999.0,
                      50_000, 50_000, 0.9)
    assert rd.z == 1.0
    assert rd.blended_pmpm == rd.projected_pmpm


def test_develop_rate_zero_credibility_uses_manual():
    rd = develop_rate(1_000_000, 10_000, 0.05, 12, 321.0, 0, 50_000, 0.9)
    assert rd.z == 0.0
    assert rd.blended_pmpm == 321.0


def test_develop_rate_outputs_rounded_to_cents():
    rd = hand_case()
    for f in ("experience_pmpm", "projected_pmpm", "blended_pmpm",
              "required_pmpm"):
        v = getattr(rd, f)
        assert round(v, 2) == v


def test_develop_rate_invalid_inputs():
    with pytest.raises(ValueError):
        develop_rate(1.0, 0.0, 0.05, 12, 1.0, 1, 10, 0.85)
    with pytest.raises(ValueError):
        develop_rate(1.0, 10.0, 0.05, 12, 1.0, 1, 10, 0.0)


def test_as_dict_contains_all_steps():
    d = hand_case().as_dict()
    for k in ("experience_pmpm", "trend_factor", "projected_pmpm", "z",
              "blended_pmpm", "required_pmpm"):
        assert k in d


# ---------- reconciliation invariant ----------

def test_reconcile_balances_to_zero_cents():
    diffs = reconcile(hand_case())
    assert set(diffs) == {"experience_pmpm", "projected_pmpm",
                          "blended_pmpm", "required_pmpm"}
    assert all(v == 0 for v in diffs.values())
    assert reconciliation_ok(hand_case())


def test_reconcile_detects_tampering():
    rd = hand_case()
    rd.required_pmpm += 0.01  # one cent off
    diffs = reconcile(rd)
    assert diffs["required_pmpm"] == 1
    assert not reconciliation_ok(rd)


def test_reconcile_detects_upstream_tampering():
    rd = hand_case()
    rd.experience_pmpm += 1.00
    assert reconcile(rd)["experience_pmpm"] == 100
    assert not reconciliation_ok(rd)


def test_reconcile_many_random_cases_zero_violations():
    rng = np.random.default_rng(31)
    for _ in range(50):
        mm = float(rng.integers(500, 40000))
        rd = develop_rate(float(rng.uniform(50, 600)) * mm, mm,
                          float(rng.uniform(0.0, 0.15)),
                          float(rng.integers(6, 36)),
                          float(rng.uniform(100, 900)), mm,
                          float(rng.integers(5000, 30000)),
                          float(rng.uniform(0.7, 0.95)))
        assert reconciliation_ok(rd)
