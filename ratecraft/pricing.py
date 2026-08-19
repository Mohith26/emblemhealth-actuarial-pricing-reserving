"""Small-group premium rate development with credibility blending.

Formula chain (every intermediate stored and reconciled to the cent):

  1. experience_pmpm  = round(completed_claims / member_months, 2)
  2. trend_factor     = (1 + annual_trend) ** (trend_months / 12)
  3. projected_pmpm   = round(experience_pmpm * trend_factor, 2)
  4. z                = min(1, sqrt(credibility_n / full_credibility_n))
     (limited-fluctuation / classical credibility)
  5. blended_pmpm     = round(z * projected_pmpm + (1 - z) * manual_pmpm, 2)
  6. required_pmpm    = round(blended_pmpm / target_loss_ratio, 2)
     (target loss ratio = 1 - admin load - margin; premium needed so that
      expected claims / premium = target loss ratio)

``reconcile`` recomputes every step from the stored inputs and reports the
difference in cents per step; the invariant is that every difference is 0.

HONESTY TAG: all experience data used with this module in this repo is
SYNTHETIC seeded data (real claims would be PHI).
"""

import math
from dataclasses import dataclass, asdict
from typing import Dict

import numpy as np


def measure_trend(monthly_totals) -> float:
    """Annualized trend from a log-linear fit of monthly completed totals.

    Returns the annualized rate r such that totals grow ~ (1+r)^(t/12).
    """
    y = np.asarray(monthly_totals, dtype=float)
    if len(y) < 2:
        raise ValueError("need at least 2 months to measure trend")
    if np.any(y <= 0):
        raise ValueError("monthly totals must be positive for log-linear trend")
    t = np.arange(len(y), dtype=float)
    slope, _ = np.polyfit(t, np.log(y), 1)
    return float(math.exp(12.0 * slope) - 1.0)


def trend_factor(annual_trend: float, months: float) -> float:
    """Projection factor over ``months`` months at an annualized trend."""
    return float((1.0 + annual_trend) ** (months / 12.0))


def limited_fluctuation_z(n: float, full_credibility_n: float) -> float:
    """Classical limited-fluctuation credibility: Z = min(1, sqrt(n/N_full))."""
    if full_credibility_n <= 0:
        raise ValueError("full_credibility_n must be positive")
    if n < 0:
        raise ValueError("n must be non-negative")
    return float(min(1.0, math.sqrt(n / full_credibility_n)))


def credibility_blend(experience: float, manual: float, z: float) -> float:
    """Z-weighted blend of group experience and the manual rate."""
    if not 0.0 <= z <= 1.0:
        raise ValueError("z must be in [0, 1]")
    return float(z * experience + (1.0 - z) * manual)


@dataclass
class RateDevelopment:
    # --- inputs ---
    completed_claims: float      # completed (ultimate) incurred claims, $
    member_months: float
    annual_trend: float
    trend_months: float          # experience midpoint -> rating midpoint
    manual_pmpm: float
    credibility_n: float         # e.g. group member months or claim count
    full_credibility_n: float
    target_loss_ratio: float     # = 1 - admin load - margin
    # --- outputs (rounded to cents where dollar-valued) ---
    experience_pmpm: float = 0.0
    trend_factor: float = 0.0
    projected_pmpm: float = 0.0
    z: float = 0.0
    blended_pmpm: float = 0.0
    required_pmpm: float = 0.0

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


def develop_rate(completed_claims: float,
                 member_months: float,
                 annual_trend: float,
                 trend_months: float,
                 manual_pmpm: float,
                 credibility_n: float,
                 full_credibility_n: float,
                 target_loss_ratio: float) -> RateDevelopment:
    """Run the documented six-step formula chain and store every intermediate."""
    if member_months <= 0:
        raise ValueError("member_months must be positive")
    if not 0.0 < target_loss_ratio <= 1.0:
        raise ValueError("target_loss_ratio must be in (0, 1]")
    rd = RateDevelopment(completed_claims, member_months, annual_trend,
                         trend_months, manual_pmpm, credibility_n,
                         full_credibility_n, target_loss_ratio)
    rd.experience_pmpm = round(completed_claims / member_months, 2)
    rd.trend_factor = trend_factor(annual_trend, trend_months)
    rd.projected_pmpm = round(rd.experience_pmpm * rd.trend_factor, 2)
    rd.z = limited_fluctuation_z(credibility_n, full_credibility_n)
    rd.blended_pmpm = round(credibility_blend(rd.projected_pmpm,
                                              manual_pmpm, rd.z), 2)
    rd.required_pmpm = round(rd.blended_pmpm / target_loss_ratio, 2)
    return rd


def reconcile(rd: RateDevelopment) -> Dict[str, int]:
    """Recompute every output from the stored inputs; return per-step
    differences in integer cents.  Invariant: every value is exactly 0."""
    diffs: Dict[str, int] = {}

    def cents(x: float) -> int:
        return int(round(x * 100))

    exp_pmpm = round(rd.completed_claims / rd.member_months, 2)
    diffs["experience_pmpm"] = cents(rd.experience_pmpm) - cents(exp_pmpm)
    tf = trend_factor(rd.annual_trend, rd.trend_months)
    proj = round(exp_pmpm * tf, 2)
    diffs["projected_pmpm"] = cents(rd.projected_pmpm) - cents(proj)
    z = limited_fluctuation_z(rd.credibility_n, rd.full_credibility_n)
    blended = round(credibility_blend(proj, rd.manual_pmpm, z), 2)
    diffs["blended_pmpm"] = cents(rd.blended_pmpm) - cents(blended)
    required = round(blended / rd.target_loss_ratio, 2)
    diffs["required_pmpm"] = cents(rd.required_pmpm) - cents(required)
    return diffs


def reconciliation_ok(rd: RateDevelopment) -> bool:
    """True iff the inputs->outputs chain balances to the cent at every step."""
    return all(v == 0 for v in reconcile(rd).values())
