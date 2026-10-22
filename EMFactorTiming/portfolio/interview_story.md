# Interview Story: Emerging-Market Factor Timing

- **Question**: Can machine-learning models time equity factors in emerging markets, or transfer developed-market history to emerging markets out of sample?
- **Key Diagnostic**: Against the naive own-series mean, every ML model shows positive $R^2_{\text{OS}}$ (+0.73% to +1.16%, CW $t$ 8.3-9.0)—but a non-timing shrinkage mean alone reaches +1.20% ($t = 9.05$). Pooling explains the apparent predictability.
- **Finding**: Against the proper shrinkage-mean benchmark on capped value-weighted factors (801,536 country-factor-months), all 12 model x scope combinations have negative $R^2_{\text{OS}}$ (-0.05% to -0.48%) because forecasts are 2.5-5x over-dispersed, and at 20 bp turnover cost the shrinkage-mean tilt (net Sharpe 1.91) beats every learned timing portfolio (0.71-1.26).
