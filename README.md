# RateCraft

A Python engine for the two core quantitative problems of a health plan's
actuarial team: figuring out how much has been incurred but not yet paid
(IBNR reserving), and turning completed claims experience into a premium
rate (small-group pricing). It also writes the Excel exhibits an actuary
would actually hand around: triangles with development factors, IBNR
summaries, trend, a rate buildup, and a credibility table.

I built the whole thing on synthetic, seeded claims data. Real claims data
is PHI, so the generator in `datagen/` simulates it instead, and that turns
out to be a feature: because the simulation runs every claim to completion,
the true ultimates and true IBNR are known exactly, which makes honest
backtesting possible. The one piece of real-world data in the repo is the
published Taylor & Ashe (1983) triangle used as a validation fixture.

## The reserving problem

Health claims incurred in a given month get paid out over the following
months (fast for pharmacy, slowly for inpatient). At any valuation date you
can only see a triangle of the data: older incurral months are nearly
complete, recent ones are mostly unpaid. Chain-ladder estimates the missing
lower right of that triangle from the development pattern of the completed
part.

Given a cumulative triangle `C[o, d]` (origin month by development lag,
NaN for the unobserved future):

1. Volume-weighted age-to-age factors: `f[d] = Σ_o C[o, d+1] / Σ_o C[o, d]`
   over origins with both cells observed (a zero denominator falls back to
   a factor of 1.0).
2. Cumulative development factors: `CDF[d] = tail * Π_{j>=d} f[j]`.
3. Completion factor (percent reported) = `1 / CDF[d]`.
4. Chain-ladder ultimate: `U_CL[o] = latest[o] * CDF[age(o)]`.
5. Bornhuetter-Ferguson, as a second opinion that leans on an expected-loss
   prior instead of trusting the latest diagonal:
   `U_BF[o] = latest[o] + prior[o] * (1 - 1/CDF[age(o)])`. The prior here is
   a log-linear trend fit to the origins already fully developed at the
   valuation date.
6. IBNR = ultimate minus latest paid.

Everything lives in `ratecraft/reserving.py`; triangles are built from
transaction-level payment records.

## How I convinced myself the math is right

Three layers, because reserving bugs are quiet:

**A published textbook triangle.** `tests/fixtures/taylor_ashe.json` is the
Taylor & Ashe (1983) 10x10 paid triangle. The engine reproduces the
volume-weighted age-to-age factors hand-computed in Mack (1993), ASTIN
Bulletin 23(2) (3.4906, 1.7473, 1.4574, 1.1739, 1.1038, 1.0863, 1.0539,
1.0766, 1.0177) exactly to 4 decimals, and the chain-ladder ultimates and
total reserve of 18,680,856 published in England & Verrall (2002), British
Actuarial Journal 8, exactly to the unit. Sources are cited inside the
fixture file.

**An independent naive implementation.** `eval/naive_oracle.py` is a
deliberately plain pure-Python loop version of chain-ladder that shares no
code with the engine. The two are compared on the textbook triangle plus 50
synthetic ones; the maximum relative deviation is reported in
`results/validation.json`.

**A backtest against known truth.** The generator splits each origin
month's true ultimate across payment lags with a Dirichlet draw, so
incremental payments sum exactly to the true ultimate. `eval/backtest.py`
generates 200 seeded datasets (3 lines of business, 36 origin months),
truncates each at the valuation diagonal, estimates IBNR with both methods,
and scores against truth: MAPE, median APE, bias, and the share of datasets
where the true ultimate lands within 10 percent of the estimate. Numbers in
`results/backtest.json` and RESULTS.md, including the ones that are
unflattering.

## Pricing

`ratecraft/pricing.py` measures annualized trend from completed months by
log-linear fit, then develops a small-group rate through a six-step chain
where every intermediate is stored and reconciled back to the cent
(`reconcile` recomputes each step from the inputs; the invariant is that
every difference is 0 cents):

1. `experience_pmpm = round(completed_claims / member_months, 2)`
2. `trend_factor    = (1 + annual_trend) ^ (trend_months / 12)`
3. `projected_pmpm  = round(experience_pmpm * trend_factor, 2)`
4. `Z = min(1, sqrt(n / full_credibility_n))`, classical limited-fluctuation
   credibility
5. `blended_pmpm    = round(Z * projected_pmpm + (1 - Z) * manual_pmpm, 2)`
6. `required_pmpm   = round(blended_pmpm / target_loss_ratio, 2)`,
   where the target loss ratio is 1 minus admin load and margin.

## Excel exhibits

`ratecraft/exhibits.py` writes one workbook per run: a triangle sheet per
line with LDFs and CDFs, an IBNR summary for both methods, a trend exhibit,
the line-by-line rate buildup, and a credibility table. Numeric cells use a
canonical precision (dollars to the cent, factors to 8 decimals) because
openpyxl serializes floats with `%.16g`, which cannot round-trip a full
17-significant-digit double. At that precision the tests reopen the
workbook and assert every cell equals engine output with `==`, no
tolerance. A deterministic sample (seed 42) is committed at
`examples/sample_exhibits.xlsx`.

## Layout

```
datagen/     seeded synthetic claims generator (ground truth known)
ratecraft/   engine: reserving.py, pricing.py, exhibits.py
eval/        naive oracle, textbook validation, backtest, reconciliation sweep
bench/       benchmarks -> results/benchmarks.json
tests/       77 pytest tests incl. textbook, oracle, and Excel round-trip
results/     committed measured outputs (JSON)
examples/    committed sample exhibit workbook
```

## Running it

```bash
python3 -m venv .venv && .venv/bin/pip install -U pip numpy pandas openpyxl pytest pytest-cov
.venv/bin/python -m pytest --cov=ratecraft --cov-report=term --color=no -q
.venv/bin/python eval/validate.py        # textbook + oracle -> results/validation.json
.venv/bin/python eval/backtest.py 200    # 200 triangle sets -> results/backtest.json
.venv/bin/python eval/reconciliation.py 200
.venv/bin/python eval/make_exhibits.py   # -> examples/sample_exhibits.xlsx
.venv/bin/python bench/benchmark.py      # -> results/benchmarks.json
```

## Limitations

- Everything is synthetic. The lag curves are stationary and the Dirichlet
  split is clean, so chain-ladder is close to well-specified on this data.
  Real claims bring case reserve changes, benefit changes, seasonality
  shocks, and large claims, so the backtest error rates here should be read
  as a lower bound, not what you would see in production.
- Bornhuetter-Ferguson loses to chain-ladder in this backtest (MAPE 7.8 to
  13.0 percent vs 3.8 to 7.4 percent) and runs biased low, between -4.7 and
  -12.8 percent. That is mostly my prior's fault: a log-linear trend fit to
  only the 13 fully-developed origins under-projects recent months. A
  pricing-based expected-loss-ratio prior would be the natural fix, and I
  have not built or measured one.
- Trend measurement is noisy by construction: 13 fully-runoff months with 3
  to 5 percent ultimate noise plus seasonality give mean absolute errors of
  3.6 to 7.8 percentage points against the true trend. That is a
  statistical limit of the short window, not a code defect; exact recovery
  on a noise-free series is unit-tested.
- Excel round-trip exactness is defined at the workbook's canonical
  precision (cents and 8 decimals), a documented consequence of openpyxl's
  `%.16g` float serialization.
- No Mack or stochastic variance estimates, no GLM rating, no risk
  adjustment, no state filing formats. Point estimates only.
