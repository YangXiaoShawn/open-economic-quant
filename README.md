# Open Economic & Quant (`open-economic-quant`)

Unified monorepo for **eight end-to-end applied economics, econometrics, and quantitative finance research systems**, paired with the public research portal ([yangxiaoshawn.github.io](https://yangxiaoshawn.github.io/)), the versioned Hugging Face Dataset ([`ShawnChamberlain/open-economic-quant-research-data`](https://huggingface.co/datasets/ShawnChamberlain/open-economic-quant-research-data)), and the interactive Hugging Face Space ([`ShawnChamberlain/open-economic-quant-research-observatory`](https://huggingface.co/spaces/ShawnChamberlain/open-economic-quant-research-observatory)).

## Research Portfolio (8 Studies)

| # | Directory | Slug | Central Question | Headline Finding & Evidence Boundary |
|---|---|---|---|---|
| 01 | [`CasualLab/`](CasualLab/) | `casuallab` | Who should get the offer? | HTE learner RMSE is **0.0417** vs **0.0247** constant oracle; uniform allocation beats model targeting (68.50 vs 64.50 incremental trips). *Semi-synthetic known-truth validation.* |
| 02 | [`Macroeconomics/`](Macroeconomics/) | `macroeconomics` | Would the forecast work in real time? | Strict as-of mode uses **0** future cells across 7,985 audited cells; revised data at fixed availability imports 5,464 later revisions and changes all 6 GDP model ranks. *Official agency archive.* |
| 03 | [`RealEstate/`](RealEstate/) | `realestate` | Does a cheap mortgage keep a loan in place? | Each +1 pp mortgage rate gap is associated with a **0.817** exit-hazard ratio across 3.81M loan-months (2021–2023). *Observational hazard association.* |
| 04 | [`TariffIncidence/`](TariffIncidence/) | `tariff-incidence` | Who absorbed the tariff? | Pre-duty unit values stay near **+0.025** log points (within $\pm 0.076$ bound) while duty-inclusive values rise ~**+0.154**, pointing to U.S. importer incidence. *Stacked multi-wave event study.* |
| 05 | [`Microstructure/`](Microstructure/) | `microstructure` | How much short-horizon edge does order flow carry? | **110 of 144** execution scenarios show positive gross edge (up to **2.39 bp**) against a frozen **4.00 bp** taker fee. *Exploratory simulation · research reference only.* |
| 06 | [`EMFactorTiming/`](EMFactorTiming/) | `em-factor-timing` | Can machine learning time equity factors in emerging markets? | Against each series own mean, ML models show $R^2_{\text{OS}}$ +0.73% to +1.16%, but a non-timing regional **shrinkage mean reaches +1.20%** ($t = 9.05$) and **1.91 net Sharpe** at 20 bp. *Out-of-sample predictive comparison (801,536 country-factor-months).* |
| 07 | [`PolymarketFactors/`](PolymarketFactors/) | `polymarket-factors` | Which prediction-market signals survive a realistic backtest? | Five backtest artifacts inflate 30-day momentum IC eightfold (**-0.440 → -0.054**). After correction, illiquidity (**-0.072** price-neutral IC), volatility (**-0.069**), and reversal (**-0.032**) survive out of sample. *Backtest association (~$100–200 capacity).* |
| 08 | [`CryptoFactors/`](CryptoFactors/) | `crypto-factors` | Do equity microstructure factors travel to crypto? | Most A-share factors fail over 730 days; perpetual **funding (+1.42 Sharpe)**, **retail positioning (+1.39)**, and **low-price range (+1.63)** survive pre-publication, while frozen post-publication tracking (Jun–Aug 2026) returned **-6.5%** without re-fitting. *Backtest & post-publication OOS audit.* |

## Shared Infrastructure (`packages/oeq-core` v0.2.1)

[`packages/oeq-core/`](packages/oeq-core/) provides shared primitives used across the workspace:
- `oeq_core.manifest`: Deterministic SHA-256 hashing and run-manifest verification (`build_run_manifest`, `verify_manifest_checksums`).
- `oeq_core.claim_guard`: Evidence-grade taxonomy, automated diagnostic demotion (`auto_demote_claim`), and claim-boundary enforcement (`validate_claim_boundary`).
- `oeq_core.factors`: Cross-sectional Rank IC, quadratic price-level residualization ($[1, p, p^2]$), Newey-West $t$-statistics, Benjamini-Hochberg FDR $q$-values (`benjamini_hochberg_fdr`), quantile long-short spreads (`quantile_long_short_spread`), volatility-targeted weights (`volatility_target_weights`), walk-forward expanding IC-IR weights (`expanding_ic_ir_weights`), inverse-volatility risk-parity weights (`inverse_volatility_weights`), and Empirical Bayes shrinkage weights (`empirical_bayes_shrinkage_weight`).

## v2.0 Real-Data Empirical Validation Highlights

| Study | Real Empirical Dataset | Key Validated Finding |
|---|---|---|
| [`PolymarketFactors/`](PolymarketFactors/) | 1,810 5-day obs across 70 CLOB markets & 82 dates (`2024-01` to `2026-10`) | Walk-forward `expanding_ic_ir_weights` achieves OOS Rank IC **+0.0671 ($t = +3.24$)** and **+0.475 pp** gross 5d Q3-Q1 spread vs **-0.0240 ($t = -0.77$)** for fixed signs; `PM-SPREAD` survives 5% BH-FDR ($t = -3.11, q = 0.0131$); passive maker preserves **+0.338 pp** net spread at `$100` while taker is **-0.327 pp**. |
| [`CryptoFactors/`](CryptoFactors/) | 785 daily Binance perpetual factor returns (`2024-06-03` to `2026-07-27`) | 20d `inverse_volatility_weights` + 5d funding-squeeze gate raises 785-day Sharpe from **1.87 to 2.19** (`+163.88%` cum return, NW $t = 3.23$); combining with 15% vol targeting cuts MaxDD nearly in half (**-16.26% → -8.55%**) and lifts Calmar from **3.28 to 4.33**. |
| [`EMFactorTiming/`](EMFactorTiming/) | 312 monthly JKP EM factor timing portfolios (`2000-01` to `2025-12`) | 36m adaptive shrinkage ($\kappa \in \{60, 120, 240\}$) lifts Net Sharpe from **1.9054 to 1.9186** ($t = 8.81$); a 75/25 turnover-damped blend of $\kappa=240$ and forecast-shrunk GBRT (`gbrt_rs:own`) achieves the highest Gross Sharpe (**2.1719**) and **2.0122 Net Sharpe** ($t = 8.95$). |
| [`Microstructure/`](Microstructure/) | 144 Binance BTCUSDT/ETHUSDT L2 execution scenarios (`2026-08-13/14`) | 110/144 scenarios have positive gross edge (max **2.3852 bp**, median **0.1445 bp**); net-positive count rises from **0/144** at 4.00 bp retail taker to **9/144** at VIP-9 taker (1.50 bp) and **19/144** at front-of-queue Maker (0 bp fee, 0.45 bp adverse selection, best net **+1.9352 bp**). |
| [`TariffIncidence/`](TariffIncidence/) | 395,468 official U.S. Census HS10-country-month obs (`2017-01` to `2020-02`) | Duty-inclusive landed unit values rise **+0.1544** log points (`CLEAN`) while pre-duty customs unit values move only **+0.0253** (`PRECISE_NULL_EFFECT_BOUNDED`), with **11.16%** counterfactual-adjusted third-country replacement across 4,306 products. |

## Quick Verification & Ecosystem Sync

```bash
# Run oeq-core tests, 8-project contract & AST import hygiene checks, and sample reproductions
make verify-all

# Synchronize subprojects to standalone checkouts, YangXiaoShawn.github.io manifest/evidence, and Space catalogs
make sync-local
```
