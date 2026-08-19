# Resume bullets (format: 2 lines, each ≤135 chars; every number measured)

Honesty tags: all claims data SYNTHETIC/seeded (real claims would be PHI);
textbook match is against the published Taylor & Ashe (1983) triangle with
factors/ultimates from Mack (1993) / England & Verrall (2002); all metrics
below are from committed runs in `results/*.json` and RESULTS.md.

Built health-plan IBNR reserving engine (chain-ladder + Bornhuetter-Ferguson) reproducing the published Taylor-Ashe/Mack triangle
exactly (all 9 factors to 4dp, 18,680,856 reserve); backtest on 600 seeded synthetic triangles hit 3.8-7.4% IBNR MAPE vs known truth

Developed small-group rates via 6-step PMPM buildup with limited-fluctuation credibility blending; inputs-to-outputs reconciliation
balanced to the cent in 100% of 200 seeded runs (0 violations); chain-ladder honestly beat BF (biased -4.7% to -12.8%) on all 3 lines

Generated Excel rate/reserve exhibits (openpyxl) verified cell-exact on reopen across 7 sheets; 77 pytest tests at 100% coverage on
the engine; 9,748 triangles/sec chain-ladder throughput; independent naive-oracle cross-check max deviation 7.0e-10 (synthetic data)
