# `oeq-core` — Shared Research Primitives

Shared library for the `open-economic-quant` monorepo providing:

- **`oeq_core.provenance`**: Deterministic SHA-256 hashing and run-manifest verification.
- **`oeq_core.claim_guard`**: Evidence-grade taxonomy (`SYNTHETIC_SMOKE`, `ASSOCIATIONAL_ONLY`, `BACKTEST_ASSOCIATION`, `OOS_PREDICTIVE_COMPARISON`, `CAUSAL_IDENTIFIED`, `INSUFFICIENT_DATA`) and automated claim-boundary checks.
- **`oeq_core.factors`**: Cross-sectional rank IC, quadratic price-level residualization ($[1, p, p^2]$), Newey-West $t$-statistics, and turnover-penalized net returns.
