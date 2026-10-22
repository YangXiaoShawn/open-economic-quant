import zipfile

import pandas as pd
import pytest

from emft.data import load_jkp, normalise

SITE = pd.DataFrame(
    {
        "location": ["bra", "bra", "usa", "usa"],
        "name": ["be_me", "be_me", "be_me", "be_me"],
        "freq": "monthly",
        "weighting": "vw_cap",
        "direction": 1,
        "n_stocks": [100, 100, 3000, 3000],
        "n_stocks_min": [30, 3, 900, 900],
        "date": ["2020-01-31", "2020-02-29", "2020-01-31", "2020-02-29"],
        "ret": [0.01, -0.02, 0.005, 0.0],
    }
)


def test_site_layout_is_normalised_and_thin_cells_dropped():
    df = normalise(SITE.copy(), min_stocks=5)
    assert list(df.columns) == ["country", "factor", "month", "ret", "region"]
    assert len(df) == 3  # the bra Feb row has n_stocks_min = 3
    assert set(df["region"]) == {"EM", "DM"}
    assert str(df["month"].iloc[0]) == "2020-01"


def test_internal_layout_uses_requested_weighting():
    raw = pd.DataFrame(
        {"excntry": ["CHN"], "characteristic": ["ret_12_1"], "date": ["2021-06-30"],
         "ret_ew": [0.03], "ret_vw": [0.02], "ret_vw_cap": [0.01]}
    )
    assert normalise(raw, weighting="vw").loc[0, "ret"] == pytest.approx(0.02)
    assert normalise(raw).loc[0, "country"] == "chn"


def test_percent_returns_are_rejected():
    bad = SITE.copy()
    bad["ret"] = [1.5, -2.0, 0.8, 0.9]
    with pytest.raises(ValueError, match="percent"):
        normalise(bad, min_stocks=0)


def test_duplicates_are_rejected():
    dup = pd.concat([SITE, SITE.iloc[[0]]])
    with pytest.raises(ValueError, match="duplicate"):
        normalise(dup, min_stocks=0)


def test_macro_state_variables(tmp_path):
    import numpy as np

    from emft.data import load_macro

    days = pd.date_range("2004-01-01", "2007-12-31", freq="D")
    pd.DataFrame({"observation_date": days, "VIXCLS": np.arange(len(days)) % 40 + 10.0}).to_csv(
        tmp_path / "VIXCLS.csv", index=False)
    pd.DataFrame({"observation_date": days, "T10Y3M": "."}).assign(T10Y3M=lambda d: d["T10Y3M"].where(
        d["observation_date"].dt.day != 15, "1.5")).to_csv(tmp_path / "T10Y3M.csv", index=False)
    months = pd.date_range("2004-01-01", "2007-12-01", freq="MS")  # overlaps the new index, as on FRED
    pd.DataFrame({"observation_date": months, "TWEXBMTH": 100 * 1.01 ** np.arange(len(months))}).to_csv(
        tmp_path / "TWEXBMTH.csv", index=False)
    new_days = pd.date_range("2006-01-01", "2007-12-31", freq="D")
    # the new index has a different base but keeps growing 1% a month
    level = 50 * 1.01 ** ((new_days.year - 2006) * 12 + new_days.month - 1)
    pd.DataFrame({"observation_date": new_days, "DTWEXBGS": level}).to_csv(tmp_path / "DTWEXBGS.csv", index=False)
    m = load_macro(tmp_path)
    assert m.loc[pd.Period("2004-02", freq="M"), "mac_vix"] == pytest.approx(np.log(10 + (59 % 40)))  # Feb 29
    assert m.loc[pd.Period("2006-06", freq="M"), "mac_term"] == pytest.approx(1.5)  # "." is missing, not zero
    # 12-month log change is 12 * log(1.01) on both sides of the 2006-01 splice
    assert m.loc["2005-01":"2007-12", "mac_usd12"].to_numpy() == pytest.approx(12 * np.log(1.01))


def test_directory_with_site_zip_is_read(tmp_path):
    # jkpfactors.com serves one zip per selection; dropping it in data/raw/ must work
    with zipfile.ZipFile(tmp_path / "[all_countries]_[all_factors]_[monthly]_[vw_cap].zip", "w") as z:
        z.writestr("factors.csv", SITE.to_csv(index=False))
    df = load_jkp(tmp_path, min_stocks=5)
    assert len(df) == 3
