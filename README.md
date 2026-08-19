# RateCraft — Health-Plan Actuarial Pricing & IBNR Reserving Engine

A Python actuarial pricing and reserving engine for a health plan:
chain-ladder + Bornhuetter-Ferguson IBNR reserving (validated against a
published textbook triangle **and** an independent naive oracle), small-group
premium rate development with limited-fluctuation credibility blending,
reserve backtests against **known ground truth**, and generated Excel
rate/reserve exhibits (openpyxl) with cell-exact round-trip tests.

> **HONESTY TAG — SYNTHETIC DATA:** every claim record in this repo is
> synthetic and seeded (`datagen/`). Real claims data would be PHI and is
> never used. The only real-world data is the published Taylor & Ashe (1983)
> textbook triangle committed as a validation fixture.

## Pipeline

```
claims (synthetic, seeded)          datagen/generator.py
  └─> triangles (origin x lag)      ratecraft/reserving.py::build_triangle
        └─> completion / IBNR       chain_ladder, bornhuetter_ferguson
              └─> trend             ratecraft/pricing.py::measure_trend
                    └─> rates       ratecraft/pricing.py::develop_rate
                          └─> Excel exhibits   ratecraft/exhibits.py
```

## Reserving formula chain

Cumulative triangle `C[o, d]` (origin month x development lag, NaN = future).

1. Volume-weighted age-to-age factors: `f[d] = Σ_o C[o, d+1] / Σ_o C[o, d]`
   over origins with both cells observed (zero denominator → factor 1.0).
2. Cumulative development factors: `CDF[d] = tail * Π_{j>=d} f[j]`.
3. Completion factor (% reported) = `1 / CDF[d]`.
4. Chain-ladder ultimate: `U_CL[o] = latest[o] * CDF[age(o)]`.
5. Bornhuetter-Ferguson: `U_BF[o] = latest[o] + prior[o] * (1 − 1/CDF[age(o)])`
   with an expected-loss prior (here: log-linear trend fit to origins already
   fully developed at the valuation date).
6. IBNR = ultimate − latest paid.

**Validation A (textbook):** the committed fixture
`tests/fixtures/taylor_ashe.json` is the Taylor & Ashe (1983) 10×10 paid
triangle. The engine reproduces the volume-weighted age-to-age factors
hand-computed in **Mack (1993), ASTIN Bulletin 23(2)** (3.4906, 1.7473,
1.4574, 1.1739, 1.1038, 1.0863, 1.0539, 1.0766, 1.0177) exactly to 4
decimals, and the chain-ladder ultimates / total reserve **18,680,856** as
published in **England & Verrall (2002), British Actuarial Journal 8**
exactly to the unit. Sources are cited inside the fixture file.

**Validation B (independent oracle):** `eval/naive_oracle.py` is a
deliberately-naive pure-Python loop implementation sharing no code with the
engine; max relative deviation across the textbook + 50 synthetic triangles
is reported in `results/validation.json`.

## Rate development formula chain (small group)

Every intermediate is stored and reconciled to the cent
(`ratecraft/pricing.py::reconcile`, invariant: all step diffs == 0 cents):

1. `experience_pmpm = round(completed_claims / member_months, 2)`
2. `trend_factor    = (1 + annual_trend) ^ (trend_months / 12)`
3. `projected_pmpm  = round(experience_pmpm * trend_factor, 2)`
4. `Z = min(1, sqrt(n / full_credibility_n))`  (limited fluctuation)
5. `blended_pmpm    = round(Z * projected_pmpm + (1 − Z) * manual_pmpm, 2)`
6. `required_pmpm   = round(blended_pmpm / target_loss_ratio, 2)`
   where target loss ratio = 1 − admin load − margin.

## Backtest with known ground truth

Because the generator splits each origin month's true ultimate across lags
with a Dirichlet draw, incremental payments sum **exactly** to the true
ultimate — so true IBNR is known by construction. `eval/backtest.py`
truncates each of 200 seeded datasets (3 lines × 36 origins) at the
valuation diagonal, estimates IBNR with both methods, and scores vs truth
(MAPE, median APE, bias, % of datasets with true ultimate within ±10% of the
estimate). See `results/backtest.json` and RESULTS.md.

## Excel exhibits

One workbook per run: per-line triangle sheets with LDFs and CDFs, IBNR
summary (CL + BF), trend exhibit, line-by-line rate-development buildup, and
a credibility table. Numeric cells use a canonical precision (dollars to the
cent, factors to 8 decimals) because openpyxl serializes floats with
`%.16g`; at that precision tests reopen the workbook and assert cell values
equal engine output with `==` (no tolerance). Sample committed at
`examples/sample_exhibits.xlsx` (seed 42, deterministic).

## Layout

```
datagen/     seeded synthetic claims generator (ground truth known)
ratecraft/   engine: reserving.py, pricing.py, exhibits.py
eval/        naive oracle, textbook validation, backtest, reconciliation sweep
bench/       benchmarks -> results/benchmarks.json
tests/       77 pytest tests incl. textbook + oracle + Excel round-trip
results/     committed measured outputs (JSON)
examples/    committed sample exhibit workbook
```

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -U pip numpy pandas openpyxl pytest pytest-cov
.venv/bin/python -m pytest --cov=ratecraft --cov-report=term --color=no -q
.venv/bin/python eval/validate.py        # textbook + oracle -> results/validation.json
.venv/bin/python eval/backtest.py 200    # 200 triangle sets -> results/backtest.json
.venv/bin/python eval/reconciliation.py 200
.venv/bin/python eval/make_exhibits.py   # -> examples/sample_exhibits.xlsx
.venv/bin/python bench/benchmark.py      # -> results/benchmarks.json
```

## Honest limits

- **Synthetic data only.** Lag curves are stationary and Dirichlet-clean, so
  chain-ladder is close to well-specified here; real claims (case reserve
  changes, benefit changes, seasonality shocks, large claims) are messier.
  Backtest error rates should be read as a lower bound.
- **BF underperforms CL in this backtest** (MAPE 7.8–13.0% vs 3.8–7.4%) and
  runs biased low (−4.7 to −12.8%): its prior is a log-linear trend fit to
  only the 13 fully-developed origins, which under-projects recent months.
  Reported honestly; a better prior (e.g. pricing-based ELR) would help.
- **Trend recovery is noisy:** measuring annualized trend from only 13
  fully-runoff months with 3–5% ultimate noise and seasonality gives mean
  absolute errors of 3.6–7.8pp vs the true configured trend. That is a
  statistical limit of the short window, reported as measured.
- No Mack/stochastic variance, no GLM rating, no risk adjustment, no state
  filing formats (out of scope by design).
- Excel round-trip exactness is defined at the workbook's canonical
  precision (cents / 8dp), a documented consequence of openpyxl's `%.16g`
  float serialization.
