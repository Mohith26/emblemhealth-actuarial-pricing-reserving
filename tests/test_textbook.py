"""Validation A: reproduce the published Taylor & Ashe (1983) chain-ladder
example (factors hand-computed in Mack 1993; ultimates and total reserve
18,680,856 as published in England & Verrall 2002)."""

import json
import os

import numpy as np
import pytest

from ratecraft.reserving import chain_ladder

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "taylor_ashe.json")


@pytest.fixture(scope="module")
def fx():
    with open(FIXTURE) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def result(fx):
    n = len(fx["incremental_paid"])
    tri = np.full((n, n), np.nan)
    for i, row in enumerate(fx["incremental_paid"]):
        tri[i, :len(row)] = np.cumsum(row)
    return chain_ladder(tri)


def test_factors_match_published_to_4dp(fx, result):
    np.testing.assert_array_equal(np.round(result.factors, 4),
                                  fx["published_ata_factors_4dp"])


def test_ultimates_match_published_to_unit(fx, result):
    np.testing.assert_array_equal(np.round(result.ultimate),
                                  fx["published_ultimates"])


def test_total_reserve_matches_published(fx, result):
    assert int(round(result.total_ibnr)) == fx["published_total_reserve"]


def test_latest_diagonal_total(fx, result):
    assert int(round(result.latest.sum())) == fx["latest_diagonal_total"]


def test_first_origin_fully_developed(result):
    assert result.ibnr[0] == pytest.approx(0.0)


def test_reserves_are_positive_for_open_origins(result):
    assert (result.ibnr[1:] > 0).all()
