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

| Study | Real Empirical Dataset | Key Finding and Evidence Status |
|---|---|---|
| [`PolymarketFactors/`](PolymarketFactors/) | 1,810 5-day obs across 70 CLOB markets & 82 dates (`2024-01` to `2026-10`) | Walk-forward `expanding_ic_ir_weights` achieves OOS Rank IC **+0.0671 ($t = +3.24$)** and **+0.475 pp** gross 5d Q3-Q1 spread vs **-0.0240 ($t = -0.77$)** for fixed signs; `PM-SPREAD` survives 5% BH-FDR ($t = -3.11, q = 0.0131$); passive maker preserves **+0.338 pp** net spread at `$100` while taker is **-0.327 pp**. |
| [`CryptoFactors/`](CryptoFactors/) | 785 daily Binance perpetual factor returns (`2024-06-03` to `2026-07-27`) | **Superseded headline.** The published 20d `inverse_volatility_weights` + 5d funding-squeeze-gate overlay (Sharpe 2.19; 2.12 with 15% vol targeting, MaxDD -8.55%, Calmar 4.33) charged nothing for re-weighting and sits on factor returns whose long–short cost was under-charged by half (about 2.5 instead of 5 bp per side). Factors and gate were chosen in sample (728 of the 785 days precede publication; the gate was added after the Jun–Aug 2026 squeeze). Charging the overlay's re-weighting at 5 bp per side gives Sharpe **2.05** / **1.96** (MaxDD -9.25%, Calmar 3.64), still upper bounds. The repo's own 2026-10 stress test of the vol-targeted version (835 days to 2026-10-20) gives Sharpe **1.48** at 5 bp, **1.18** at 15 bp and **0.72** at 30 bp. A rerun with corrected costs is pending access to the raw panels. |
| [`EMFactorTiming/`](EMFactorTiming/) | 312 monthly JKP EM factor timing portfolios (`2000-01` to `2025-12`) | Fixed $\kappa = 240$ shrinkage has the highest net Sharpe in this table at 20 bp (**2.0522** vs **1.9054** at the $\kappa = 120$ baseline); an adaptive-$\kappa$ rule gives **1.9186** ($t = 8.81$), and a 75/25 blend of $\kappa=240$ and forecast-shrunk GBRT (`gbrt_rs:own`) has the highest gross Sharpe (**2.1719**) but a lower net Sharpe (**2.0122**). $\kappa$ and the blend were chosen on these same 312 months, and no committed script generates this table (`reports/jkp_em/eb_and_long_only_summary.csv`). |
| [`Microstructure/`](Microstructure/) | 144 Binance BTCUSDT/ETHUSDT L2 execution scenarios (`2026-08-13/14`) | 110/144 scenarios have positive gross edge (max **2.3852 bp**, median **0.1445 bp**); none is net-positive at the frozen **4.00 bp** taker fee. Re-pricing the same market-order scenarios at lower hurdles leaves 9/144 above a 1.50 bp VIP-9 taker fee and 19/144 above an assumed 0.45 bp front-of-queue maker hurdle. The best of these (+1.9352 bp) is the maximum over 144 overlapping scenarios, taken from a 10-fill ETHUSDT scenario, with no multiplicity adjustment, no simulated passive fills and the table's fill-probability assumption unused: exploratory, not an achievable maker edge. |
| [`TariffIncidence/`](TariffIncidence/) | 923,440-row official U.S. Census HS10 × country × month panel (`2017-01` to `2020-02`); stacked event study on 395,468 obs | Duty-inclusive landed unit values rise **+0.1544** log points (`CLEAN`, passes the date placebo) while pre-duty customs unit values move only **+0.0253** (`PRECISE_NULL_EFFECT_BOUNDED`, within ±0.076). Sourcing is a **qualified** finding: counterfactual-adjusted third-country replacement of lost Chinese import value is **11.16%** across 1,376 treated HS6 headings, but the quantity outcome fails its date placebo. |

The CryptoFactors Sharpe ratios in the Research Portfolio table above (+1.42, +1.39, +1.63) come from the same under-charged long–short cost formula and should be read as upper bounds until the rerun; see [`CryptoFactors/README.md`](CryptoFactors/README.md).

## Quick Verification & Ecosystem Sync

```bash
# Run oeq-core tests, 8-project contract & AST import hygiene checks, and sample reproductions
make verify-all

# Synchronize subprojects to standalone checkouts, YangXiaoShawn.github.io manifest/evidence, and Space catalogs
make sync-local
```
