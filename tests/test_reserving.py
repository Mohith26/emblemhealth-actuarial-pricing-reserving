"""Unit tests for triangle construction, chain-ladder and BF (hand-computed)."""

import numpy as np
import pandas as pd
import pytest

from ratecraft.reserving import (ata_factors, bornhuetter_ferguson,
                                 build_triangle, cdfs, chain_ladder,
                                 latest_diagonal, truncate_triangle)


def small_payments():
    rows = [
        ("A", 0, 0, 100.0), ("A", 0, 1, 50.0), ("A", 0, 2, 25.0),
        ("A", 1, 0, 200.0), ("A", 1, 1, 80.0), ("A", 1, 2, 40.0),
        ("A", 2, 0, 300.0), ("A", 2, 1, 90.0), ("A", 2, 2, 60.0),
        ("B", 0, 0, 999.0),
    ]
    return pd.DataFrame(rows, columns=["line", "origin", "dev", "amount"])


def test_build_triangle_cumulative():
    tri = build_triangle(small_payments(), line="A")
    expected = np.array([[100, 150, 175], [200, 280, 320], [300, 390, 450.0]])
    np.testing.assert_array_equal(tri, expected)


def test_build_triangle_incremental():
    tri = build_triangle(small_payments(), line="A", cumulative=False)
    assert tri[0, 1] == 50.0 and tri[2, 2] == 60.0


def test_build_triangle_line_filter():
    tri = build_triangle(small_payments(), line="B", n_origins=1, n_devs=1)
    assert tri.shape == (1, 1) and tri[0, 0] == 999.0


def test_build_triangle_aggregates_duplicates():
    df = pd.DataFrame([("A", 0, 0, 10.0), ("A", 0, 0, 15.0)],
                      columns=["line", "origin", "dev", "amount"])
    tri = build_triangle(df, line="A")
    assert tri[0, 0] == 25.0


def test_truncate_masks_future_cells():
    full = build_triangle(small_payments(), line="A")
    trunc = truncate_triangle(full)
    assert np.isnan(trunc[1, 2]) and np.isnan(trunc[2, 1]) and np.isnan(trunc[2, 2])
    assert trunc[0, 2] == 175.0 and trunc[2, 0] == 300.0


def test_truncate_custom_valuation():
    full = build_triangle(small_payments(), line="A")
    trunc = truncate_triangle(full, valuation=1)
    assert np.isnan(trunc[0, 2]) and trunc[0, 1] == 150.0 and trunc[1, 0] == 200.0


def test_ata_factors_hand_computed():
    full = build_triangle(small_payments(), line="A")
    tri = truncate_triangle(full)
    f = ata_factors(tri)
    # dev0->1: (150+280)/(100+200) = 430/300; dev1->2: 175/150
    np.testing.assert_allclose(f, [430.0 / 300.0, 175.0 / 150.0])


def test_ata_factor_zero_denominator_defaults_to_one():
    tri = np.array([[0.0, 0.0], [0.0, np.nan]])
    np.testing.assert_array_equal(ata_factors(tri), [1.0])


def test_cdfs_product_and_tail():
    f = np.array([2.0, 1.5])
    np.testing.assert_allclose(cdfs(f), [3.0, 1.5, 1.0])
    np.testing.assert_allclose(cdfs(f, tail=1.1), [3.3, 1.65, 1.1])


def test_latest_diagonal():
    tri = truncate_triangle(build_triangle(small_payments(), line="A"))
    latest, age = latest_diagonal(tri)
    np.testing.assert_array_equal(latest, [175.0, 280.0, 300.0])
    np.testing.assert_array_equal(age, [2, 1, 0])


def test_latest_diagonal_empty_row():
    tri = np.array([[1.0, np.nan], [np.nan, np.nan]])
    latest, age = latest_diagonal(tri)
    assert latest[1] == 0.0 and age[1] == 0


def test_chain_ladder_hand_computed():
    tri = truncate_triangle(build_triangle(small_payments(), line="A"))
    res = chain_ladder(tri)
    f1, f2 = 430.0 / 300.0, 175.0 / 150.0
    exp_ult = [175.0, 280.0 * f2, 300.0 * f1 * f2]
    np.testing.assert_allclose(res.ultimate, exp_ult)
    np.testing.assert_allclose(res.ibnr, np.array(exp_ult) - res.latest)
    assert res.total_ibnr == pytest.approx(sum(exp_ult) - 755.0)


def test_chain_ladder_complete_triangle_no_ibnr():
    tri = build_triangle(small_payments(), line="A")  # no NaNs
    res = chain_ladder(tri)
    np.testing.assert_allclose(res.ibnr, 0.0, atol=1e-9)


def test_chain_ladder_tail_factor():
    tri = truncate_triangle(build_triangle(small_payments(), line="A"))
    res = chain_ladder(tri, tail=1.05)
    assert res.ultimate[0] == pytest.approx(175.0 * 1.05)


def test_chain_ladder_single_column():
    tri = np.array([[100.0], [200.0]])
    res = chain_ladder(tri)
    np.testing.assert_array_equal(res.ultimate, [100.0, 200.0])
    assert res.total_ibnr == 0.0


def test_chain_ladder_zero_cells_finite():
    tri = np.array([[100.0, 150.0, 160.0],
                    [0.0, 0.0, np.nan],
                    [50.0, np.nan, np.nan]])
    res = chain_ladder(tri)
    assert np.all(np.isfinite(res.ultimate))


def test_completion_factors_inverse_of_cdf():
    tri = truncate_triangle(build_triangle(small_payments(), line="A"))
    res = chain_ladder(tri)
    np.testing.assert_allclose(res.completion, 1.0 / res.cdf)


def test_bf_hand_computed():
    tri = truncate_triangle(build_triangle(small_payments(), line="A"))
    prior = np.array([180.0, 320.0, 500.0])
    res = bornhuetter_ferguson(tri, prior)
    f1, f2 = 430.0 / 300.0, 175.0 / 150.0
    cdf0 = f1 * f2
    exp = [175.0 + 180.0 * 0.0,
           280.0 + 320.0 * (1 - 1 / f2),
           300.0 + 500.0 * (1 - 1 / cdf0)]
    np.testing.assert_allclose(res.ultimate, exp)


def test_bf_with_cl_prior_equals_cl():
    tri = truncate_triangle(build_triangle(small_payments(), line="A"))
    cl = chain_ladder(tri)
    bf = bornhuetter_ferguson(tri, cl.ultimate)
    np.testing.assert_allclose(bf.ultimate, cl.ultimate, rtol=1e-12)


def test_ibnr_equals_ultimate_minus_latest():
    tri = truncate_triangle(build_triangle(small_payments(), line="A"))
    for res in (chain_ladder(tri),
                bornhuetter_ferguson(tri, np.array([1.0, 2.0, 3.0]))):
        np.testing.assert_allclose(res.ibnr, res.ultimate - res.latest)
