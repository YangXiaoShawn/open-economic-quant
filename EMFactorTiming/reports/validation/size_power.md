# Size and power on synthetic panels (software validation, not a finding)

6 DM + 6 EM countries, 12 factors, 300 months, OOS from 2005, pooled OLS.
Rejection = Clark-West t > 1.645 (one-sided 5%). Row signal_sd = 0 is the null.

|   signal_sd |   reps |   mean_r2_vs_hist |   reject_vs_hist |   mean_r2_vs_shrink |   reject_vs_shrink |
|------------:|-------:|------------------:|-----------------:|--------------------:|-------------------:|
|       0     |     40 |             0.058 |            0.875 |              -0.055 |              0.05  |
|       0.004 |     40 |             0.264 |            0.975 |               0.133 |              0.925 |
|       0.008 |     40 |             1.773 |            1     |               1.599 |              1     |
