# Results that did not work, or did not hold up

Recorded so they are not quietly dropped. Source files are named for each item; all use
the JKP data downloaded 2026-09-29 (through 2025-12), emerging-market test set,
out of sample 2000–2025, unless stated.

1. **No learned model beats the shrinkage mean on capped value-weighted factors.**
   All 12 model × scope combinations have negative R²_OS (−0.05% to −0.48%).
   `reports/jkp_em/r2_oos.csv`.
2. **Forecasts are overconfident.** Realised-on-forecast deviation slopes 0.19–0.40
   (`reports/jkp_em/forecast_slopes.csv`). The neural net is the worst (EM-trained 0.19).
3. **Timing does not pay net of 20 bp on capped VW factors.** Every learned-model portfolio
   (net Sharpe 0.71–1.26) trails the static equal-weight factor portfolio (1.48).
   `reports/jkp_em/portfolios.csv`.
4. **Factor momentum as a forecast fails.** R²_OS −6.2% against the own mean; its sign
   portfolio's net Sharpe is 0.77. `reports/jkp_em/`.
5. **Linear-model timing evidence is fragile.** Clark–West t for OLS / elastic net falls
   to 0.8–1.5 with κ = 240 and to 1.3–1.5 on uncapped value-weighted factors, and is below
   1.645 for EM-trained linear models in the baseline (1.56, 1.61).
   `reports/jkp_em_kappa240/`, `reports/jkp_em_vw/`.
6. **Tree significance is not universal.** EM-trained gradient-boosted trees have
   Clark–West t = 1.21 on uncapped value-weighted factors (`reports/jkp_em_vw/r2_oos.csv`);
   an earlier draft sentence saying tree statistics were significant "in every
   specification" was withdrawn once this run was done.
7. **Country-level transfer is noise.** Elastic net: positive R²_OS in 12 / 22 markets when
   EM-trained, 8 / 22 when DM-trained; CW t > 1.645 in 2 and 5. Not adjusted for multiple
   testing. `reports/jkp_em/transfer_by_country_enet.csv`.
8. **Two markets drop out.** The Czech Republic and Hungary have no out-of-sample
   observations after the five-stock filter (`reports/jkp_em/coverage.csv`).
9. **U.S. state variables hurt.** Adding log VIX, the 10y–3m Treasury spread and the
   12-month dollar change makes every model worse on the matched 1990+ sample; trees fall
   to R²_OS −0.38% (EM-trained) / −1.05% (DM-trained) with CW t 1.37 / 0.58.
   `reports/jkp_em_macro/` vs `reports/jkp_em_from1990/`.
10. **Real-time forecast shrinkage does not make capped-VW forecasts beat the benchmark.**
    R²_OS improves for every model but stays negative (best −0.02%); EM-trained linear
    models' CW t falls to 0.8–0.9. Its EM-trained portfolios beat static (1.51–1.71 vs
    1.48), the DM-trained ones do not (1.02–1.48), and none beats the shrinkage-mean tilt. This extension was chosen after seeing the full-sample slope diagnostic.
    `reports/jkp_em_rs/`.
11. **Break-even costs are low on value-weighted factors** (≤ 16 bp per unit of turnover;
    the DM-trained elastic net never beats static). `reports/robustness/breakeven.csv`.
