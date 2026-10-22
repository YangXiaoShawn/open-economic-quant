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

## Shared Infrastructure (`packages/oeq-core` v0.2.0)

[`packages/oeq-core/`](packages/oeq-core/) provides shared primitives used across the workspace:
- `oeq_core.manifest`: Deterministic SHA-256 hashing and run-manifest verification (`build_run_manifest`, `verify_manifest_checksums`).
- `oeq_core.claim_guard`: Evidence-grade taxonomy, automated diagnostic demotion (`auto_demote_claim`), and claim-boundary enforcement (`validate_claim_boundary`).
- `oeq_core.factors`: Cross-sectional Rank IC, quadratic price-level residualization ($[1, p, p^2]$), Newey-West $t$-statistics, Benjamini-Hochberg FDR $q$-values (`benjamini_hochberg_fdr`), quantile long-short spreads (`quantile_long_short_spread`), volatility-targeted weights (`volatility_target_weights`), walk-forward expanding IC-IR weights (`expanding_ic_ir_weights`), and Empirical Bayes shrinkage weights (`empirical_bayes_shrinkage_weight`).

## Quick Verification & Ecosystem Sync

```bash
# Run oeq-core tests, 8-project contract & AST import hygiene checks, and sample reproductions
make verify-all

# Synchronize subprojects to standalone checkouts, YangXiaoShawn.github.io manifest/evidence, and Space catalogs
make sync-local
```
