"""Load Jensen-Kelly-Pedersen (JKP) global factor returns, or generate a synthetic panel.

Two input layouts are accepted and normalised to one long table:

* jkpfactors.com download:   location, name, freq, weighting, direction,
                             n_stocks, n_stocks_min, date, ret
* JKP code output (internal): excntry, characteristic, direction, date,
                             ret_ew, ret_vw, ret_vw_cap, n_stocks_min

Output columns: country, factor, month (pandas Period[M]), ret, region
Returns are decimal excess returns (0.01 = 1%). JKP factors are already signed so
that the long leg is the side the original paper predicts to earn more.
"""

from __future__ import annotations

import glob
import io
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MARKETS_FILE = ROOT / "config" / "markets.yaml"

_COUNTRY_COLS = ("location", "excntry", "country")
_FACTOR_COLS = ("name", "characteristic", "factor")
_DATE_COLS = ("date", "eom", "month")


@dataclass(frozen=True)
class Markets:
    developed: frozenset[str]
    emerging: frozenset[str]

    def region(self, country: str) -> str:
        if country in self.developed:
            return "DM"
        if country in self.emerging:
            return "EM"
        return "OTHER"


def load_markets(path: Path = MARKETS_FILE) -> Markets:
    cfg = yaml.safe_load(path.read_text())
    return Markets(frozenset(cfg["developed"]), frozenset(cfg["emerging"]))


MACRO_FEATURES = ["mac_vix", "mac_term", "mac_usd12"]


def load_macro(directory: str | Path) -> pd.DataFrame:
    """Monthly U.S. state variables from FRED CSVs (fredgraph.csv layout), indexed by Period[M].

    mac_vix    log of the last VIX close in the month (VIXCLS, from 1990)
    mac_term   last 10-year minus 3-month Treasury spread in the month (T10Y3M, percent)
    mac_usd12  12-month log change of the broad trade-weighted dollar: the discontinued
               monthly TWEXBMTH through 2005-12, then the monthly average of DTWEXBGS,
               level-spliced at 2006-01 (the two indexes differ in coverage)
    Every value dated t is observable at the end of month t.
    """
    d = Path(directory)

    def series(name: str) -> pd.Series:
        f = pd.read_csv(d / f"{name}.csv")
        s = pd.to_numeric(f.iloc[:, 1], errors="coerce")
        s.index = pd.to_datetime(f.iloc[:, 0]).dt.to_period("M")
        return s.dropna()

    vix = series("VIXCLS").groupby(level=0).last()
    term = series("T10Y3M").groupby(level=0).last()
    old = np.log(series("TWEXBMTH").groupby(level=0).mean())
    new = np.log(series("DTWEXBGS").groupby(level=0).mean())
    splice = pd.Period("2006-01", freq="M")
    if splice not in old.index or splice not in new.index:
        raise ValueError("TWEXBMTH and DTWEXBGS must both cover 2006-01 to splice the dollar index")
    usd = pd.concat([old[old.index < splice], new[new.index >= splice] + old[splice] - new[splice]])
    usd = usd.reindex(pd.period_range(usd.index.min(), usd.index.max(), freq="M"))
    out = pd.DataFrame({"mac_vix": np.log(vix), "mac_term": term, "mac_usd12": usd - usd.shift(12)})
    out.index.name = "month"
    return out


MARKET_HISTORY_FILE = ROOT / "config" / "market_history.yaml"


def apply_market_history(
    panel: pd.DataFrame, markets: Markets | None = None, path: Path = MARKET_HISTORY_FILE
) -> pd.DataFrame:
    """Replace the static region with the region in force in each month (see market_history.yaml)."""
    markets = markets or load_markets()
    events = pd.DataFrame(yaml.safe_load(Path(path).read_text())["events"])
    events["from_month"] = pd.PeriodIndex(events["from_month"].astype(str), freq="M")
    events = events.sort_values(["country", "from_month"])
    out = panel.copy()
    for country, ev in events.groupby("country"):
        if ev.iloc[-1]["region"] != markets.region(country):
            raise ValueError(f"{country}: last event region {ev.iloc[-1]['region']} "
                             f"differs from markets.yaml ({markets.region(country)})")
        rows = out["country"] == country
        if not rows.any():
            continue
        month = out.loc[rows, "month"]
        region = pd.Series(ev.iloc[0]["was"], index=month.index)
        for _, e in ev.iterrows():
            region[month >= e["from_month"]] = e["region"]
        out.loc[rows, "region"] = region
    return out


def _read_any(path: str | Path) -> pd.DataFrame:
    """Read one CSV, every CSV or .zip in a directory/glob, or every CSV inside a .zip."""
    p = Path(path)
    frames: list[pd.DataFrame] = []
    if p.is_dir():
        files = sorted(f for f in p.iterdir() if f.suffix.lower() in (".csv", ".zip"))
    elif any(ch in str(path) for ch in "*?["):
        files = [Path(f) for f in sorted(glob.glob(str(path)))]
    else:
        files = [p]
    if not files:
        raise FileNotFoundError(f"No CSV files found at {path}")
    for f in files:
        if f.suffix.lower() == ".zip":
            with zipfile.ZipFile(f) as z:
                for name in sorted(n for n in z.namelist() if n.lower().endswith(".csv")):
                    frames.append(pd.read_csv(io.BytesIO(z.read(name))))
        else:
            frames.append(pd.read_csv(f))
    return pd.concat(frames, ignore_index=True)


def _pick(cols: pd.Index, candidates: tuple[str, ...], what: str) -> str:
    for c in candidates:
        if c in cols:
            return c
    raise ValueError(f"Cannot find a {what} column; expected one of {candidates}, got {list(cols)}")


def normalise(
    raw: pd.DataFrame,
    weighting: str = "vw_cap",
    min_stocks: int = 5,
    markets: Markets | None = None,
) -> pd.DataFrame:
    """Map either JKP layout to the canonical long table and validate it."""
    markets = markets or load_markets()
    cols = raw.columns
    c_country = _pick(cols, _COUNTRY_COLS, "country")
    c_factor = _pick(cols, _FACTOR_COLS, "factor")
    c_date = _pick(cols, _DATE_COLS, "date")

    if "ret" in cols:
        c_ret = "ret"
        if "weighting" in cols:
            kept = raw["weighting"].astype(str).str.lower().unique()
            if len(kept) > 1:
                raw = raw[raw["weighting"].astype(str).str.lower() == weighting]
                log.info("Kept weighting=%s out of %s", weighting, list(kept))
    else:
        c_ret = f"ret_{weighting}"
        if c_ret not in cols:
            raise ValueError(f"No 'ret' or '{c_ret}' column in input")

    df = pd.DataFrame(
        {
            "country": raw[c_country].astype(str).str.lower().str.strip(),
            "factor": raw[c_factor].astype(str).str.strip(),
            "month": pd.to_datetime(raw[c_date]).dt.to_period("M"),
            "ret": pd.to_numeric(raw[c_ret], errors="coerce"),
        }
    )
    if "n_stocks_min" in cols and min_stocks > 0:
        n = pd.to_numeric(raw["n_stocks_min"], errors="coerce")
        before = len(df)
        df = df[(n >= min_stocks).to_numpy()]
        log.info("Dropped %d rows with n_stocks_min < %d", before - len(df), min_stocks)

    df = df.dropna(subset=["ret"])

    # Unit check: JKP returns are decimals. A median absolute return above 0.2
    # (20% a month for a long-short factor) means the file is in percent.
    if df["ret"].abs().median() > 0.2:
        raise ValueError(
            "Returns look like percentages (median |ret| > 0.2). "
            "Pass decimal returns or divide by 100 before loading."
        )

    dup = df.duplicated(["country", "factor", "month"])
    if dup.any():
        raise ValueError(f"{int(dup.sum())} duplicate country-factor-month rows")

    df["region"] = df["country"].map(markets.region)
    return df.sort_values(["country", "factor", "month"]).reset_index(drop=True)


def load_jkp(path: str | Path, **kwargs) -> pd.DataFrame:
    return normalise(_read_any(path), **kwargs)


def coverage(df: pd.DataFrame) -> pd.DataFrame:
    """One row per country: region, factors, first and last month, months."""
    g = df.groupby(["region", "country"])
    out = g.agg(
        factors=("factor", "nunique"),
        first=("month", "min"),
        last=("month", "max"),
        months=("month", "nunique"),
        obs=("ret", "size"),
    )
    return out.reset_index().sort_values(["region", "country"])


# ---------------------------------------------------------------------------
# Synthetic panel with a known data-generating process (software validation)
# ---------------------------------------------------------------------------


def synthetic_panel(
    n_dm: int = 8,
    n_em: int = 8,
    n_factors: int = 20,
    n_months: int = 360,
    signal_sd: float = 0.004,
    noise_sd: float = 0.03,
    phi: float = 0.95,
    global_share: float = 0.6,
    premium: float = 0.002,
    premium_sd: float = 0.003,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (panel, truth).

    r[c,f,t+1] = mu[c,f] + x[c,f,t] + e[c,f,t+1],   mu[c,f] ~ N(premium, premium_sd)
    x[c,f,t]   = sqrt(global_share) * z[f,t] + sqrt(1 - global_share) * u[c,f,t]
    z, u       = independent AR(1) processes with persistence phi, sd signal_sd

    x is the predictable part. It is persistent, so trailing mean returns carry
    information about it, and its global component z is shared across
    countries, so developed-market history is informative about emerging markets.
    Setting signal_sd = 0 gives a panel with no predictability at all.
    """
    rng = np.random.default_rng(seed)
    dm = [f"d{i:02d}" for i in range(n_dm)]
    em = [f"e{i:02d}" for i in range(n_em)]
    countries = dm + em
    factors = [f"f{j:03d}" for j in range(n_factors)]
    months = pd.period_range("1990-01", periods=n_months, freq="M")

    def ar1(shape):
        x = np.zeros(shape)
        innov_sd = signal_sd * np.sqrt(1 - phi**2)
        x[0] = rng.normal(0, signal_sd, shape[1:])
        for t in range(1, shape[0]):
            x[t] = phi * x[t - 1] + rng.normal(0, innov_sd, shape[1:])
        return x

    z = ar1((n_months, n_factors))
    u = ar1((n_months, len(countries), n_factors))
    x = np.sqrt(global_share) * z[:, None, :] + np.sqrt(1 - global_share) * u
    e = rng.normal(0, noise_sd, (n_months, len(countries), n_factors))
    # Unconditional premia differ by country and factor, as in real data, so the
    # series' own historical mean is the right null benchmark.
    mu = rng.normal(premium, premium_sd, (len(countries), n_factors))

    r = np.full_like(x, np.nan)
    r[1:] = mu + x[:-1] + e[1:]  # return at t+1 depends on state at t

    idx = pd.MultiIndex.from_product([months, countries, factors], names=["month", "country", "factor"])
    panel = pd.DataFrame({"ret": r.reshape(-1)}, index=idx).reset_index().dropna()
    panel["region"] = np.where(panel["country"].str.startswith("d"), "DM", "EM")
    truth = pd.DataFrame(
        {"true_expected_next": (mu[None, :, :] + x).reshape(-1)}, index=idx
    ).reset_index()
    return panel.sort_values(["country", "factor", "month"]).reset_index(drop=True), truth
