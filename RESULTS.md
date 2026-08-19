# Validation and benchmark notes

Numbers below are from runs on my machine (macOS-26.4.1-arm64, Python
3.9.6; numpy 2.0.2, pandas 2.3.3, openpyxl 3.1.5, pytest 8.4.2). Raw
outputs live in `results/*.json`. All claims data is synthetic and seeded;
the only real-world data is the published Taylor & Ashe (1983) fixture.

## Textbook triangle (Taylor & Ashe 1983 / Mack 1993)

From `results/validation.json`; reproduce with `.venv/bin/python eval/validate.py`.

The engine's volume-weighted age-to-age factors match Mack (1993) exactly
at 4 decimals for all 9 factors (max abs deviation after 4dp rounding =
0.0). Ultimates match England & Verrall (2002) exactly for all 10 origins
after rounding to the unit (max abs deviation = 0.0). Total reserve comes
out to 18,680,856, equal to the published figure, and the latest diagonal
sums to 34,358,090 as a sanity check.

## Independent naive oracle

Also in `results/validation.json`. Comparing the vectorized engine against
the pure-Python loop implementation on 51 triangles (the textbook one plus
50 seeded synthetic runoff triangles), the maximum relative deviation
across factors, CDFs, ultimates, and IBNR is 6.98e-10, which is float noise
between loop and vectorized arithmetic.

## Reserve backtest against known ground truth

From `results/backtest.json`; reproduce with `.venv/bin/python eval/backtest.py 200`.

200 seeded triangle sets, 3 lines each, so 600 triangles (36 origin months,
24 dev lags, truncated at the valuation diagonal; true IBNR known by
construction). Metrics are on total IBNR per dataset; "within 10%" is the
share of datasets where the true total ultimate is within 10 percent of the
estimate.

| Line | Method | IBNR MAPE | Median APE | Bias | Ult within 10% |
|---|---|---|---|---|---|
| IP | chain-ladder | 3.75% | 3.08% | -0.33% | 100% |
| IP | Bornhuetter-Ferguson | 10.40% | 9.74% | -8.64% | 100% |
| OP | chain-ladder | 4.43% | 3.77% | +0.55% | 100% |
| OP | Bornhuetter-Ferguson | 13.04% | 12.92% | -12.76% | 100% |
| Rx | chain-ladder | 7.40% | 6.49% | +1.20% | 100% |
| Rx | Bornhuetter-Ferguson | 7.79% | 6.47% | -4.72% | 100% |

Chain-ladder beats BF on every line here, and BF is systematically biased
low (-4.7% to -12.8%). That traces back to the BF prior, a log-linear trend
fit to only the 13 fully-developed origins, which under-projects recent
months. Worth remembering that the synthetic generating process is friendly
to chain-ladder's assumptions, so I read these error rates as a lower
bound on what real claims would show.

## Trend recovery

From `results/backtest.json` (200 runs; trend measured by log-linear fit on
the 13 fully-runoff origins observable at valuation).

| Line | True trend | Mean abs error | Max abs error |
|---|---|---|---|
| IP | 8.0% | 5.65 pp | 19.78 pp |
| OP | 6.0% | 7.75 pp | 16.37 pp |
| Rx | 10.0% | 3.59 pp | 9.71 pp |

A 13-month window with 3 to 5 percent ultimate noise plus seasonality is a
weak trend signal, so errors of this size are the statistical limit of the
window rather than a code defect. Exact recovery on a noise-free series is
covered by `test_measure_trend_exact_on_noise_free_series`.

## Rate development reconciliation

From `results/reconciliation.json`; reproduce with `.venv/bin/python eval/reconciliation.py 200`.

200 seeded random rate developments (plus 50 more inside the test suite):
0 to-the-cent violations, worst absolute step difference 0 cents, balanced
in 100% of 200 runs.

## Credibility hand checks

Verified in `tests/test_pricing.py`, all passing: Z(1082, 1082)=1;
Z(5000, 1082) capped at 1; Z(0, N)=0; Z(270.5, 1082)=0.5; Z(400, 1600)=0.5;
Z(900, 1600)=0.75; blend(100, 80, 0.6)=92. The full six-step hand-computed
rate case: 5.4M claims / 12,000 member months gives 450.00, times 1.08^2
gives 524.88, Z=0.5 blend with a 500.00 manual gives 512.44, divided by
0.85 gives a required PMPM of 602.87, matched exactly by the engine.

## Excel round-trip

`tests/test_exhibits.py` (8 tests, all passing) reopens the workbook with
openpyxl and checks triangle cells, ATA factors, CDFs, the IBNR summary for
both methods, trend, the rate buildup, and the credibility table against
engine output with `==` and no tolerance, at the workbook's canonical
precision (dollars to the cent, factors to 8 decimals; openpyxl serializes
floats via `%.16g`, which cannot round-trip 17-significant-digit doubles).
The worksheet XML is byte-identical across runs. Sample workbook:
`examples/sample_exhibits.xlsx` (seed 42).

## Benchmarks

From `results/benchmarks.json`; reproduce with `.venv/bin/python bench/benchmark.py`.
Single-machine wall clock, no CPU pinning, small repeat counts, so treat as
rough throughput rather than controlled measurement.

| Benchmark | Measured |
|---|---|
| Chain-ladder throughput (36x24 triangles, 3,000 runs) | 9,748 triangles/sec |
| 200-set backtest end-to-end (600 triangles, gen + CL + BF + scoring) | 0.62 s |
| Exhibit workbook generation (7 sheets, mean of 5) | 0.021 s |

## Tests and coverage

Reproduce with `.venv/bin/python -m pytest --cov=ratecraft --cov-report=term --color=no -q`.

77 passed, 0 failed. Coverage on `ratecraft/` is 100% (243/243 statements:
reserving.py 86, pricing.py 73, exhibits.py 84, `__init__.py` 0).

Things I have not measured: any validation on real claims (would require
PHI), and BF with a pricing-based expected-loss-ratio prior instead of the
trend-fit prior.
