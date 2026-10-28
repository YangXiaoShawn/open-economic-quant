# Do Factor Premia Travel? Machine-Learning Factor Timing in Emerging-Market Equities

**Question.** Is the predictability of equity factor returns documented in developed
markets present in emerging markets, and does a model trained on developed-market
history forecast emerging-market factor returns out of sample, net of the costs of
acting on the forecast?

**Data.** Jensen, Kelly and Pedersen (2023) global factor returns: 153 signed,
characteristic-managed long-short portfolios in 93 countries, monthly, capped
value-weighted, excess returns in USD ([jkpfactors.com](https://jkpfactors.com/)).
Markets are split into developed and emerging by the MSCI classification in
`config/markets.yaml`.

**Design.** For every country-factor-month, seven point-in-time predictors (own
1/3/12/36-month means, own 12-month volatility, the country's average 12-month factor
return, and the same factor's developed-market 12-month return) forecast next month's
return. Models are refitted every January on labels already realised, and evaluated
on the following year:

| Model | Type |
|---|---|
| `hist_mean` | own expanding mean (Campbell–Thompson benchmark) |
| `shrink_mean` | own mean shrunk toward the regional mean of the same factor |
| `fmom` | trailing 12-month mean (factor momentum) |
| `ols`, `enet` | pooled linear, elastic net |
| `gbrt` | gradient-boosted trees |
| `nn` | 3-seed neural-net ensemble (CLI opt-in `--models ...,nn`; included in `make run`) |

Training scopes for the emerging-market test set: `own` (EM → EM), `dm_only`
(DM → EM, the transfer test) and `pooled`.

**Evaluation.** Out-of-sample R² and Clark–West tests against both benchmarks, and
timing portfolios (weights proportional to forecasts within each country, gross
exposure one) against a static equal-weight factor portfolio, net of a cost per unit
of timing turnover.

## Why two benchmarks

In a multi-country factor panel, each country-factor mean is estimated from a short,
noisy history. A model can beat that own historical mean simply by pooling means
across countries, with no timing ability at all. On known-truth synthetic panels
(`scripts/size_power.py`, 40 draws per row), the standard test against the own mean
rejects **87.5%** of the time when there is no predictability; against the shrinkage
benchmark it rejects **5.0%**, the nominal size, with 92.5–100% power when
predictability exists. Learned models therefore forecast deviations from the
shrinkage mean, and timing claims are made only against it.

## Results (real data, emerging-market test set)

Evidence grade: **out-of-sample predictive comparisons** (association). Nothing here
identifies why a predictor works. JKP files downloaded 2026-09-29, data through 2025-12;
801,536 country-factor-months in 22 emerging markets, out of sample 2000–2025. Main run
`reports/jkp_em/` (capped value-weighted factors, 20 bp); robustness `reports/robustness/`;
paper `paper/draft.pdf`.

- **The benchmark problem is real.** Against each series' own historical mean every
  learned model has R²_OS 0.73–1.16% (Clark–West t 8.3–9.0), but the shrinkage mean alone
  reaches **1.20%** (t = 9.05). The apparent predictability is pooling, not timing.
- **Against the shrinkage mean** all 12 model × training-scope combinations have a
  negative R²_OS (−0.05% to −0.48%). Clark–West t is positive in all 12 and above 1.645
  in 10: linear 1.56–2.10, trees 3.66–4.25, neural net 1.82–3.88. Realised-on-forecast
  deviation slopes are 0.19–0.40: forecasts point the right way but are 2.5–5× too large.
- **DM → EM transfer.** DM-only training gives Clark–West statistics at least as large as
  EM training for every model (OLS 2.10 vs 1.61, elastic net 2.08 vs 1.56, trees 3.79 vs
  3.66, neural net 3.88 vs 1.82), with more dispersed forecasts and lower R²_OS.
- **Economic value.** At 20 bp per unit of turnover, learned-model timing portfolios have
  net Sharpe 0.71–1.26 vs **1.48** for the static equal-weight factor portfolio (turnover
  0.41–0.63 vs 0.02 a month). The best net Sharpe (**1.91**) is the shrinkage-mean tilt,
  which barely trades. At 10 bp the EM-trained tree portfolio (1.60) beats static (1.49).
- **Robustness** (κ 60/240, OOS from 2005, EW and uncapped VW factors, time-varying MSCI
  classification, 10/40 bp). The shrinkage mean beats the own mean and the shrinkage-mean
  tilt has the best net Sharpe in every row. **Equal-weighted factors differ:** 7 of 9
  learned models beat the shrinkage mean (R²_OS up to 0.17%, CW 3.8–5.0) and every
  learned timing portfolio beats static net of 20 bp (2.28–3.08 vs 2.01), though not the
  tilt (3.90). Linear-model timing evidence is fragile (CW 0.8–1.5 with κ = 240, 1.3–1.5
  on uncapped VW factors); EM-trained trees fail on uncapped VW factors (t = 1.21).
- **Break-even costs** (`reports/robustness/breakeven.csv`): on value-weighted factors a
  timing portfolio beats static only below 3–16 bp per unit of turnover (the DM-trained
  elastic net never does); on equal-weighted factors below 30–48 bp.
- **Exploratory extensions** (chosen after seeing the results; `reports/robustness/extensions.csv`).
  *Real-time forecast shrinkage* (`<model>_rs`: slope estimated in the last 36 months of each
  training window, clipped to [0, 1]) cuts turnover by a third to a half; EM-trained timing
  portfolios reach net Sharpe 1.51–1.71 vs static 1.48, but R²_OS on capped VW factors stays
  negative and every portfolio stays below the tilt (1.91; EW 3.65 vs 3.90). *U.S. state
  variables* (log VIX, 10y–3m spread, 12-month dollar change; FRED) make every model worse on
  the matched 1990+ sample (trees: R²_OS −0.38% / −1.05%, CW 1.37 / 0.58).
- Sharpe levels are inflated because factor returns are gross of their own rebalancing
  costs and signed by the original studies; read them comparatively. Negative and fragile
  results are listed in `reports/failed_hypotheses.md`.

### v2.0 Real-Data Empirical Validation (312 Monthly JKP Portfolios, 2000-01 to 2025-12)

Evaluated directly on the 312 monthly out-of-sample portfolio return series across `reports/jkp_em*/portfolio_monthly.csv` (`reports/jkp_em/eb_and_long_only_summary.csv`):

| Specification | OOS $R^2$ vs Own (%) | Gross Sharpe | Net Sharpe (20 bp) | Turnover / mo | Max DD (%) | NW $t$ (net) |
|---|---:|---:|---:|---:|---:|---:|
| `shrink_mean:rule` ($\kappa = 60$) | +0.9759 | 1.8337 | 1.7315 | 0.0648 | -3.26 | 8.19 |
| `shrink_mean:rule` ($\kappa = 120$ baseline) | +1.2025 | 1.9979 | 1.9054 | 0.0606 | -3.43 | 8.77 |
| `shrink_mean:rule` ($\kappa = 240$) | +1.3564 | 2.1325 | 2.0522 | 0.0558 | -3.60 | 9.15 |
| `eb_shrink_mean:rule` (36m adaptive $\kappa_t$) | +1.2116 | 2.0113 | 1.9186 | 0.0605 | -3.43 | 8.81 |
| `gbrt_rs:own` (forecast-shrunk GBRT) | +1.1835 | 2.0937 | 1.7050 | 0.2436 | -3.80 | 7.63 |
| `turnover_damped_blend` (75% $\kappa=240$ + 25% `gbrt_rs`) | +1.3131 | 2.1719 | 2.0122 | 0.1028 | -3.64 | 8.95 |

Three caveats. The turnover-damped blend has the highest gross Sharpe but not the highest
net Sharpe: at 20 bp it reaches 2.0122, below $\kappa = 240$ alone (2.0522), because it
turns over 0.1028 a month against 0.0558. The blend's $\kappa = 240$ and its 75/25 weight
were chosen after seeing these same 312 out-of-sample months, so differences between rows
are in-sample model selection, not an out-of-sample test. And no committed script writes
`reports/jkp_em/eb_and_long_only_summary.csv`, or the `reports/post_2025_oos_2026_10/` and
`reports/live_readiness_2026_10/` tables used below and in the 2026-10 audit: the blend is
not implemented in `src/`, and the committed `eb_shrink_mean` rule sets $\kappa_t$ from an
expanding within/between-variance ratio clipped to [12, 600] (`src/emft/features.py`), not
the "36m rolling inverse-vol adaptive kappa in {60,120,240}" described in that CSV.

### Post-2025 Out-of-Sample Extension Through Latest Trading Day (`2026-01` to `2026-10-21`, 10 Months / 202 Trading Days)

Extended from the JKP `2025-12` cutoff through `2026-10-21` using 49 daily MSCI EM/DM country and style-factor ETFs (`reports/UPDATE_2026-10.md`, `reports/post_2025_oos_2026_10/`):

| Strategy | 2026 YTD Cum Net (%) | 2026 Net Sharpe (20 bp) | 2026 Max DD (%) | Win Months (of 10) | Full 322m (`2000-01 ~ 2026-10`) Net Sharpe |
|---|---:|---:|---:|---:|---:|
| **`shrink_mean_k240:rule` ($\kappa=240$)** | **+6.95** | **3.61** | -0.07 | 9 / 10 | **2.0981** |
| **`shrink_mean:rule` ($\kappa=120$ baseline)** | **+6.73** | **3.71** | -0.10 | 9 / 10 | **1.9594** |
| **`turnover_damped_blend:own` (75% $\kappa=240$ + 25% `gbrt_rs`)** | **+6.61** | **3.58** | -0.02 | 9 / 10 | **2.0592** |
| **`eb_shrink_mean:rule` (adaptive $\hat{\kappa}_t$)** | **+6.33** | **3.96** | **-0.01** | 9 / 10 | **1.9765** |
| `enet_rs:own` (forecast-shrunk elastic net) | +5.78 | 2.67 | -0.19 | 9 / 10 | 1.5640 |
| `ols_rs:own` (forecast-shrunk OLS) | +5.75 | 2.57 | -0.22 | 9 / 10 | 1.6085 |
| `gbrt_rs:own` (forecast-shrunk GBRT) | +4.86 | 2.75 | 0.00 | 10 / 10 | 1.7336 |
| `static_ew` (1/N equal-weight factor portfolio) | +4.07 | 3.55 | -0.06 | 9 / 10 | 1.5155 |
| `gbrt:own` (unshrunk GBRT) | +3.56 | 2.13 | -0.11 | 9 / 10 | 1.2882 |
| `gbrt:dm_only` (DM → EM transfer, unshrunk) | +0.22 | 0.14 | -1.49 | 6 / 10 | 0.7061 |

## Evidence status

| Layer | State |
|---|---|
| Pipeline, tests, synthetic validation | complete — 19 tests pass (2026-10-26); size/power in `reports/validation/` |
| Real-data run on JKP factors | complete — `reports/jkp_em/` (OLS, elastic net, trees, neural net) |
| Robustness | complete for κ, OOS start, factor weighting, time-varying classification, costs, break-even costs; size-dependent costs pending |
| Extensions | real-time forecast shrinkage and U.S. state variables (exploratory) |
| Paper draft | `paper/draft.pdf` (19 pp.), every table generated from the runs |

## Run it

```bash
pip install -e ".[dev]"          # or: pip install numpy pandas scikit-learn scipy matplotlib pyyaml pyarrow pytest
make test                         # 19 tests: loader, macro, leakage, market history, recovery, null, transfer, real-time shrinkage, published-table checks
make validate                     # size/power simulation (~3 min)
make demo                         # full pipeline on synthetic data (~8 min)
make run                          # main real-data run incl. neural net (~17 min); files in data/raw/
make robustness                   # kappa, EW/VW, time-varying classification reruns + tables (~25 min)
make extensions                   # real-time shrinkage and U.S. state-variable runs + table (~20 min)
make tables                       # paper/tables/*.tex and the figure from reports/jkp_em
make paper                        # pdflatex; or: .tools/tectonic -X compile paper/draft.tex
```

### Getting the data

From [jkpfactors.com](https://jkpfactors.com/) → Data Download → Factor Returns,
choose **All Countries**, **All 153 Factors**, **Monthly**, **Capped Value Weighted**
(one ~45 MB zip, `[all_countries]_[all_factors]_[monthly]_[vw_cap].zip`, served from
`jkpfactors-data.s3.amazonaws.com/public/`). Put the zip, or the CSVs, in `data/raw/`; the
equal- and value-weighted files for robustness go in `data/raw_ew/` and `data/raw_vw/`
(see `data/DATA_ACCESS.md`). The loader accepts the site layout (`location, name, …, date,
ret`) and the authors' code-output layout (`excntry, characteristic, …, ret_vw_cap`),
drops country-factor-months with fewer than 5 stocks in a leg, and rejects files that
look like percentages or contain duplicates.

`python -m emft coverage --data data/raw/` prints what was loaded before you run anything.

## Limitations recorded up front

- The baseline market classification is static (current MSCI); `--market-history` uses
  dated MSCI reclassifications (`config/market_history.yaml`) but not first index inclusion.
- After the five-stock filter the Czech Republic and Hungary contribute no out-of-sample
  observations, so the EM test set has 22 markets.
- Factor signs come from the original studies, several published after 2000.
- Factor returns are gross of their own rebalancing costs; the cost parameter applies
  only to timing trades. Emerging-market factor legs can be thin and costly to trade.
- Hyperparameters are fixed in advance, not tuned; the neural net's early stopping uses
  a random validation split within the training window only.
- Portfolio Sharpe ratios on synthetic data are meaningless by construction.

## References

Campbell and Thompson (2008, RFS); Clark and West (2007, J. Econometrics);
Gu, Kelly and Xiu (2020, RFS); Jensen, Kelly and Pedersen (2023, JF);
Haddad, Kozak and Santosh (2020, RFS); Ehsani and Linnainmaa (2022, JF).
