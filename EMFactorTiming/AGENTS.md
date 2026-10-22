# AGENTS.md — persistent instructions for anyone (human or agent) working in this repository

Read this before changing anything.

## What this project is

An out-of-sample study of whether the time variation in equity factor returns
documented in developed markets is present in emerging markets, whether models
trained on developed-market history forecast emerging-market factor returns, and
whether acting on those forecasts pays after trading costs. Data: Jensen, Kelly and
Pedersen (2023) global factor returns.

## Non-negotiable rules

1. **Never fabricate a number.** Every figure in the README, the paper or a CV line
   must come from a file under `reports/` written by the pipeline. Paper tables are
   generated (`make tables`, `make robustness`); do not edit `paper/tables/*.tex` by hand.
2. **Synthetic is not evidence.** Anything from `--synthetic` or `scripts/size_power.py`
   is stamped `SYNTHETIC` and is software validation only.
3. **Evidence grade is out-of-sample predictive comparison (association).** Do not
   write that a predictor or developed-market history *causes* emerging-market returns.
4. **Timing claims are made against the shrinkage mean**, never against the own
   historical mean alone (the own-mean test over-rejects; see `reports/validation/`).
5. **No look-ahead.** Features dated t use returns through t; models are refitted each
   January on realised labels only; market classifications use effective dates.
   `tests/test_no_leakage.py` and `tests/test_market_history.py` must pass.
6. **Report what does not work.** Negative and fragile results go in
   `reports/failed_hypotheses.md`, not in the bin.
7. **Classification facts need a source.** Every event in `config/market_history.yaml`
   cites an MSCI document; do not add one from memory.

## Layout

| Path | Contents |
|---|---|
| `src/emft/` | loader, features, models, backtest, evaluation, report, CLI |
| `config/` | static MSCI classification; time-varying reclassification events |
| `scripts/` | size/power simulation; paper tables; robustness table |
| `reports/` | run outputs (predictions are git-ignored); validation; robustness |
| `paper/` | draft, generated tables and figure |
| `data/` | access notes; raw JKP files are git-ignored |
