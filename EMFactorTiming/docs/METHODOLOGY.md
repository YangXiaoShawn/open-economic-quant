# Methodology & Benchmark Discipline

1. **The Multi-Country Benchmark Problem**: In a multi-country factor panel (153 JKP factors across 22 emerging and 23 developed markets), each country-factor mean is estimated from a noisy history. Testing a learned model against each series own expanding mean (`hist_mean`) conflates genuine time-series predictability with cross-sectional pooling of unconditional means (size = 87.5% under a no-predictability null).
2. **Shrinkage-Mean Benchmark (`shrink_mean`)**: Shrinking each series expanding mean toward the regional mean of the same factor restores nominal 5.0% size while retaining 92.5%-100% power.
3. **Deviation Forecasting & Turnover-Penalized Portfolios**: All learned models (`ols`, `enet`, `gbrt`, `nn`) forecast deviations from `shrink_mean` across three scopes (`own`, `dm_only`, `pooled`) and are evaluated via out-of-sample $R^2_{\text{OS}}$, Clark-West $t$-statistics, and timing portfolios net of 20 bp per unit of turnover.
