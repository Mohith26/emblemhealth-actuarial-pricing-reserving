# RESULTS

All numbers below were measured by actual runs on the build machine
(macOS-26.4.1-arm64, Python 3.9.6; numpy 2.0.2, pandas 2.3.3,
openpyxl 3.1.5, pytest 8.4.2). **All claims data is SYNTHETIC and seeded**
(real claims would be PHI); the only real-world data is the published
Taylor & Ashe (1983) fixture. Raw outputs: `results/*.json`.

## 1. Validation A — textbook triangle (Taylor & Ashe 1983 / Mack 1993)

Source: `results/validation.json` · reproduce: `.venv/bin/python eval/validate.py`

| Check | Result |
|---|---|
| Volume-weighted ATA factors vs Mack (1993), 4 decimals | **exact match, all 9 factors** (max abs dev after 4dp rounding = 0.0) |
| Ultimates vs England & Verrall (2002), rounded to unit | **exact match, all 10 origins** (max abs dev after unit rounding = 0.0) |
| Total reserve | engine 18,680,856 = published **18,680,856** ✔ |
| Latest diagonal total (sanity) | 34,358,090 ✔ |

## 2. Validation B — independent naive oracle

Source: `results/validation.json`

- Triangles compared: **51** (textbook + 50 seeded synthetic runoff triangles)
- Max relative deviation (factors, CDFs, ultimates, IBNR): **6.98e-10**
  (pure float noise between loop and vectorized arithmetic)

## 3. Reserve backtest vs KNOWN ground truth

Source: `results/backtest.json` · reproduce: `.venv/bin/python eval/backtest.py 200`

200 seeded triangle sets × 3 lines = **600 triangles** (36 origin months,
24 dev lags, truncated at the valuation diagonal; true IBNR known by
construction). Metrics on total IBNR per dataset; "within ±10%" = share of
datasets where true total ultimate is within ±10% of the estimate.

| Line | Method | IBNR MAPE | Median APE | Bias | Ult within ±10% |
|---|---|---|---|---|---|
| IP | chain-ladder | **3.75%** | 3.08% | −0.33% | 100% |
| IP | Bornhuetter-Ferguson | 10.40% | 9.74% | −8.64% | 100% |
| OP | chain-ladder | **4.43%** | 3.77% | +0.55% | 100% |
| OP | Bornhuetter-Ferguson | 13.04% | 12.92% | −12.76% | 100% |
| Rx | chain-ladder | **7.40%** | 6.49% | +1.20% | 100% |
| Rx | Bornhuetter-Ferguson | 7.79% | 6.47% | −4.72% | 100% |

**Honest finding:** chain-ladder beats BF on every line in this backtest,
and BF is systematically biased low (−4.7% to −12.8%) because its prior is a
log-linear trend fit to only the 13 fully-developed origins. Reported as
measured.

## 4. Trend recovery (measured vs generator's true trend)

Source: `results/backtest.json` (200 runs; trend measured by log-linear fit
on the 13 fully-runoff origins observable at valuation).

| Line | True trend | Mean abs error | Max abs error |
|---|---|---|---|
| IP | 8.0% | 5.65 pp | 19.78 pp |
| OP | 6.0% | 7.75 pp | 16.37 pp |
| Rx | 10.0% | 3.59 pp | 9.71 pp |

**Honest finding:** a 13-month window with 3–5% ultimate noise plus
seasonality is a weak trend signal; errors of this size are the statistical
limit of the window, not a code defect (exact recovery on noise-free series
is unit-tested: `test_measure_trend_exact_on_noise_free_series`).

## 5. Reconciliation invariant (rate development)

Source: `results/reconciliation.json` · reproduce: `.venv/bin/python eval/reconciliation.py 200`

- Cases: **200** seeded random rate developments (+50 more inside the test suite)
- To-the-cent violations: **0** · worst absolute step difference: **0 cents**
- Balanced in **100% of 200 runs**

## 6. Credibility (limited fluctuation), hand-computed cases

Verified in `tests/test_pricing.py` (all pass): Z(1082, 1082)=1;
Z(5000, 1082) capped at 1; Z(0, N)=0; Z(270.5, 1082)=0.5; Z(400, 1600)=0.5;
Z(900, 1600)=0.75; blend(100, 80, 0.6)=92; full 6-step hand-computed rate
case: 5.4M claims / 12,000 MM → 450.00 → ×1.08² → 524.88 → Z=0.5 blend with
manual 500.00 → 512.44 → ÷0.85 → **602.87 required PMPM** (exact match).

## 7. Excel round-trip

`tests/test_exhibits.py` (8 tests, all pass): workbook reopened with
openpyxl; triangle cells, ATA factors, CDFs, IBNR summary (CL + BF), trend,
rate-development buildup, and credibility table all equal engine output with
`==` (no tolerance) at the canonical exhibit precision (dollars to the cent,
factors to 8 decimals — openpyxl serializes floats via `%.16g`, which cannot
round-trip 17-significant-digit doubles). Workbook is byte-deterministic in
its worksheet XML across runs. Sample: `examples/sample_exhibits.xlsx`
(seed 42).

## 8. Benchmarks

Source: `results/benchmarks.json` · reproduce: `.venv/bin/python bench/benchmark.py`

| Benchmark | Measured |
|---|---|
| Chain-ladder throughput (36×24 triangles, 3,000 runs) | **9,748 triangles/sec** |
| 200-set backtest end-to-end (600 triangles, gen + CL + BF + scoring) | **0.62 s** |
| Exhibit workbook generation (7 sheets, mean of 5) | **0.021 s** |

## 9. Tests + coverage

Reproduce: `.venv/bin/python -m pytest --cov=ratecraft --cov-report=term --color=no -q`

- **77 passed**, 0 failed
- Coverage on `ratecraft/`: **100%** (243/243 statements: reserving.py 86,
  pricing.py 73, exhibits.py 84, `__init__.py` 0)

## Not measured / caveats

- No real-claims validation of any kind (would require PHI) — all accuracy
  numbers are on synthetic data whose generating process favors
  chain-ladder's assumptions; treat backtest error as a lower bound.
- BF with a pricing-based ELR prior (rather than the trend-fit prior) was
  not implemented or measured — out of v1 scope.
- Benchmark numbers are single-machine wall-clock, not statistically
  controlled (no CPU pinning; min/mean of small repeat counts).
