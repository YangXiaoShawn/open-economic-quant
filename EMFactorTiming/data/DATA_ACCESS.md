# Data access

Raw data are not in the repository (`data/raw*/` is git-ignored). Everything needed to
rebuild them is public.

## JKP global factor returns

Jensen, Kelly and Pedersen (2023), https://jkpfactors.com → Data → Factor Returns.
Selection: **All Countries**, **All 153 Factors**, **Monthly**, and a weighting. The site
serves each selection as one zip from `https://jkpfactors-data.s3.amazonaws.com/public/`:

| Directory | File | Weighting | Used for |
|---|---|---|---|
| `data/raw/` | `[all_countries]_[all_factors]_[monthly]_[vw_cap].zip` | capped value-weighted | baseline |
| `data/raw_ew/` | `[all_countries]_[all_factors]_[monthly]_[ew].zip` | equal-weighted | robustness |
| `data/raw_vw/` | `[all_countries]_[all_factors]_[monthly]_[vw].zip` | value-weighted | robustness |

Files used for the current results were downloaded on 2026-09-29 (S3 last-modified
2026-08-04; about 45 MB each; data through 2025-12). Columns: `location, name, freq,
weighting, direction, n_stocks, n_stocks_min, date, ret`; returns are decimals.

**Licence.** The site distributes the data under CC BY-NC 4.0. Cite Jensen, Kelly and
Pedersen (2023, *Journal of Finance*); do not redistribute the raw files. The
repository only holds aggregated results derived from them.

## U.S. state variables (extension)

`data/raw_macro/`: FRED series saved as downloaded from
`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>` on 2026-09-30 —
`VIXCLS` (from 1990), `T10Y3M` (from 1982), `TWEXBMTH` (broad dollar index, monthly,
1973–2019, discontinued) and `DTWEXBGS` (broad dollar index, daily, from 2006).
`emft.data.load_macro` documents the transformations and the 2006-01 splice.

## Market classification

`config/markets.yaml` (current MSCI classification) and `config/market_history.yaml`
(dated MSCI reclassifications, each with its source). MSCI's own list, "Previous Market Reclassifications.xlsx"
(downloaded 2026-09-30 into `data/raw_msci/`), was used to cross-check the events.
