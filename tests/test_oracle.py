"""Validation B: vectorized engine vs independent naive loop oracle."""

import json
import os

import numpy as np

from datagen.generator import N_DEVS, generate_claims
from eval.naive_oracle import naive_chain_ladder, triangle_to_lists
from ratecraft.reserving import build_triangle, chain_ladder, truncate_triangle

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "taylor_ashe.json")
TOL = 1e-9


def _compare(tri):
    res = chain_ladder(tri)
    f, cdf, ult, ibnr = naive_chain_ladder(triangle_to_lists(tri))
    np.testing.assert_allclose(res.factors, f, rtol=TOL)
    np.testing.assert_allclose(res.cdf, cdf, rtol=TOL)
    np.testing.assert_allclose(res.ultimate, ult, rtol=TOL)
    np.testing.assert_allclose(res.ibnr, ibnr, rtol=TOL, atol=1e-6)


def test_oracle_matches_on_taylor_ashe():
    with open(FIXTURE) as fh:
        fx = json.load(fh)
    n = len(fx["incremental_paid"])
    tri = np.full((n, n), np.nan)
    for i, row in enumerate(fx["incremental_paid"]):
        tri[i, :len(row)] = np.cumsum(row)
    _compare(tri)


def test_oracle_matches_on_synthetic_triangles():
    payments, _ = generate_claims(seed=99, n_months=30)
    for line in ("IP", "OP", "Rx"):
        full = build_triangle(payments, line=line, n_origins=30,
                              n_devs=N_DEVS)
        _compare(truncate_triangle(full))


def test_oracle_matches_on_small_hand_triangle():
    tri = np.array([[100.0, 150.0, 175.0],
                    [200.0, 280.0, np.nan],
                    [300.0, np.nan, np.nan]])
    _compare(tri)


def test_oracle_zero_denominator_agrees():
    tri = np.array([[0.0, 0.0], [0.0, np.nan]])
    _compare(tri)


def test_oracle_ragged_input_rows():
    f, cdf, ult, ibnr = naive_chain_ladder([[100.0, 150.0], [200.0]])
    assert f == [1.5]
    assert ult == [150.0, 300.0]
    assert ibnr == [0.0, 100.0]
