"""Claim-triangle construction and IBNR reserving.

Methods
-------
* Volume-weighted chain-ladder (age-to-age factors, tail, CDFs, completion
  factors, ultimate + IBNR per origin month).
* Bornhuetter-Ferguson with an expected-loss prior.

Validated against (a) the published Taylor & Ashe (1983) 10x10 triangle with
chain-ladder factors/ultimates as published in Mack (1993) / England &
Verrall (2002), and (b) an independent deliberately-naive loop implementation
in ``eval/naive_oracle.py``.

HONESTY TAG: all runtime data fed to this engine in this repo is SYNTHETIC
seeded data (real claims would be PHI).
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


def build_triangle(payments: pd.DataFrame,
                   line: Optional[str] = None,
                   n_origins: Optional[int] = None,
                   n_devs: Optional[int] = None,
                   cumulative: bool = True) -> np.ndarray:
    """Build an (origin x development-lag) triangle from transaction-level
    payment records with columns [line, origin, dev, amount]."""
    df = payments if line is None else payments[payments["line"] == line]
    if n_origins is None:
        n_origins = int(df["origin"].max()) + 1
    if n_devs is None:
        n_devs = int(df["dev"].max()) + 1
    tri = np.zeros((n_origins, n_devs), dtype=float)
    g = df.groupby(["origin", "dev"])["amount"].sum()
    for (o, d), v in g.items():
        o, d = int(o), int(d)
        if o < n_origins and d < n_devs:
            tri[o, d] += v
    if cumulative:
        tri = np.cumsum(tri, axis=1)
    return tri


def truncate_triangle(full: np.ndarray, valuation: Optional[int] = None) -> np.ndarray:
    """Mask (NaN) cells not yet observable at the valuation month.

    Cell (o, d) is observed iff o + d <= valuation.  Default valuation is the
    latest origin month (n_origins - 1), i.e. a standard runoff triangle.
    """
    n_o, n_d = full.shape
    if valuation is None:
        valuation = n_o - 1
    out = full.astype(float).copy()
    mask = np.add.outer(np.arange(n_o), np.arange(n_d)) > valuation
    out[mask] = np.nan
    return out


def ata_factors(tri: np.ndarray) -> np.ndarray:
    """Volume-weighted age-to-age (link) factors from a cumulative triangle."""
    n_o, n_d = tri.shape
    f = np.ones(max(n_d - 1, 0), dtype=float)
    for j in range(n_d - 1):
        valid = ~np.isnan(tri[:, j]) & ~np.isnan(tri[:, j + 1])
        den = tri[valid, j].sum()
        num = tri[valid, j + 1].sum()
        f[j] = num / den if den > 0 else 1.0
    return f


def cdfs(factors: np.ndarray, tail: float = 1.0) -> np.ndarray:
    """Cumulative development factors: cdf[j] develops age j to ultimate."""
    n_d = len(factors) + 1
    out = np.empty(n_d, dtype=float)
    out[-1] = tail
    for j in range(n_d - 2, -1, -1):
        out[j] = out[j + 1] * factors[j]
    return out


def latest_diagonal(tri: np.ndarray):
    """(latest cumulative value, age index) per origin row."""
    n_o, n_d = tri.shape
    latest = np.zeros(n_o, dtype=float)
    age = np.zeros(n_o, dtype=int)
    for i in range(n_o):
        obs = np.where(~np.isnan(tri[i]))[0]
        if len(obs) == 0:
            latest[i], age[i] = 0.0, 0
        else:
            age[i] = obs.max()
            latest[i] = tri[i, age[i]]
    return latest, age


@dataclass
class ReservingResult:
    method: str
    factors: np.ndarray      # age-to-age factors
    cdf: np.ndarray          # cumulative development factors (to ultimate)
    latest: np.ndarray       # latest observed cumulative per origin
    age: np.ndarray          # age (dev index) of latest observation
    ultimate: np.ndarray     # estimated ultimate per origin
    ibnr: np.ndarray         # ultimate - latest per origin

    @property
    def total_ultimate(self) -> float:
        return float(self.ultimate.sum())

    @property
    def total_ibnr(self) -> float:
        return float(self.ibnr.sum())

    @property
    def completion(self) -> np.ndarray:
        """Completion factors (percent reported) = 1 / cdf."""
        return 1.0 / self.cdf


def chain_ladder(tri: np.ndarray, tail: float = 1.0) -> ReservingResult:
    """Volume-weighted chain-ladder on a cumulative runoff triangle."""
    f = ata_factors(tri)
    cdf = cdfs(f, tail=tail)
    latest, age = latest_diagonal(tri)
    ultimate = latest * cdf[age]
    return ReservingResult("chain_ladder", f, cdf, latest, age,
                           ultimate, ultimate - latest)


def bornhuetter_ferguson(tri: np.ndarray,
                         prior_ultimate: np.ndarray,
                         tail: float = 1.0) -> ReservingResult:
    """Bornhuetter-Ferguson: ultimate = latest + prior * (1 - 1/cdf).

    ``prior_ultimate`` is the expected-loss prior per origin (e.g. earned
    premium x expected loss ratio, or a trend-fitted expected ultimate).
    """
    prior_ultimate = np.asarray(prior_ultimate, dtype=float)
    f = ata_factors(tri)
    cdf = cdfs(f, tail=tail)
    latest, age = latest_diagonal(tri)
    pct_unreported = 1.0 - 1.0 / cdf[age]
    ultimate = latest + prior_ultimate * pct_unreported
    return ReservingResult("bornhuetter_ferguson", f, cdf, latest, age,
                           ultimate, ultimate - latest)
