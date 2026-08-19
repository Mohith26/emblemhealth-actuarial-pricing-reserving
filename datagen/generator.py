"""Seeded synthetic health-claims generator.

HONESTY TAG: All claims data produced here is SYNTHETIC and seeded.
No real claims data is used anywhere in this project (real claims would be PHI).

Design
------
For each line of business (medical IP, medical OP, Rx) and each incurred
(origin) month, a *true ultimate* incurred amount is drawn:

    ultimate[o] = members * base_pmpm * (1 + annual_trend)^(o/12)
                  * (1 + seasonality_amp * sin(2*pi*o/12))
                  * gamma_noise(mean=1, cv)

The ultimate is then split across development lags 0..n_devs-1 with a
Dirichlet draw centered on the line's payment-lag curve, so the incremental
payments sum *exactly* to the true ultimate.  Because runoff is simulated to
completion, TRUE ultimates and TRUE IBNR are known ground truth for
backtesting.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np
import pandas as pd

N_DEVS = 24  # development lags 0..23 (months); runoff completes by lag 23


def _gamma_lag_curve(shape: float, scale: float, n_devs: int = N_DEVS) -> np.ndarray:
    """Discrete payment-lag curve from a gamma density, normalized to sum 1."""
    d = np.arange(n_devs, dtype=float)
    w = d ** (shape - 1.0) * np.exp(-d / scale)
    w[0] = max(w[0], np.exp(-0.5 / scale))  # avoid a zero weight at lag 0
    return w / w.sum()


@dataclass
class LineConfig:
    base_pmpm: float
    annual_trend: float
    seasonality_amp: float
    cv: float                      # coefficient of variation of ultimate noise
    lag_shape: float
    lag_scale: float
    dirichlet_conc: float = 400.0  # higher = less noisy lag proportions
    lag_curve: np.ndarray = field(init=False)

    def __post_init__(self):
        self.lag_curve = _gamma_lag_curve(self.lag_shape, self.lag_scale)


def default_line_configs() -> Dict[str, LineConfig]:
    """IP pays slowest, OP medium, Rx fastest -- typical health-plan lags."""
    return {
        "IP": LineConfig(base_pmpm=180.0, annual_trend=0.08,
                         seasonality_amp=0.03, cv=0.05,
                         lag_shape=2.2, lag_scale=2.5),
        "OP": LineConfig(base_pmpm=120.0, annual_trend=0.06,
                         seasonality_amp=0.05, cv=0.04,
                         lag_shape=1.6, lag_scale=1.5),
        "Rx": LineConfig(base_pmpm=90.0, annual_trend=0.10,
                         seasonality_amp=0.02, cv=0.03,
                         lag_shape=1.2, lag_scale=0.7),
    }


def generate_claims(seed: int,
                    n_months: int = 36,
                    members: int = 10000,
                    line_configs: Optional[Dict[str, LineConfig]] = None):
    """Generate SYNTHETIC seeded claim payments with known ground truth.

    Returns
    -------
    payments : pd.DataFrame with columns [line, origin, dev, amount]
        Incremental paid amounts, complete runoff (dev 0..N_DEVS-1).
    truth : dict
        {"true_ultimate": {line: ndarray[n_months]},
         "true_trend": {line: float}, "members": int, "n_months": int}
    """
    if line_configs is None:
        line_configs = default_line_configs()
    rng = np.random.default_rng(seed)
    rows = []
    true_ult: Dict[str, np.ndarray] = {}
    for line, cfg in line_configs.items():
        origins = np.arange(n_months, dtype=float)
        level = members * cfg.base_pmpm * (1.0 + cfg.annual_trend) ** (origins / 12.0)
        season = 1.0 + cfg.seasonality_amp * np.sin(2.0 * math.pi * origins / 12.0)
        if cfg.cv > 0:
            k = 1.0 / (cfg.cv ** 2)
            noise = rng.gamma(shape=k, scale=1.0 / k, size=n_months)
        else:
            noise = np.ones(n_months)
        ult = level * season * noise
        true_ult[line] = ult
        alpha = cfg.dirichlet_conc * cfg.lag_curve
        props = rng.dirichlet(alpha, size=n_months)  # each row sums to 1
        inc = props * ult[:, None]                   # sums exactly to ult
        for o in range(n_months):
            for d in range(N_DEVS):
                rows.append((line, o, d, inc[o, d]))
    payments = pd.DataFrame(rows, columns=["line", "origin", "dev", "amount"])
    truth = {
        "true_ultimate": true_ult,
        "true_trend": {ln: cfg.annual_trend for ln, cfg in line_configs.items()},
        "members": members,
        "n_months": n_months,
    }
    return payments, truth
