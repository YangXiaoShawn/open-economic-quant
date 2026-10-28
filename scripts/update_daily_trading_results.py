#!/usr/bin/env python3
"""
Automated Daily Trading Results & Portal Monitor Updater for Open Economic & Quant Research:
- Incrementally updates CryptoFactors (data.binance.vision klines/OI + OKX UTC daily bars & 8h funding)
- Incrementally updates EMFactorTiming (Yahoo Finance 49 US-listed EM/DM country & style-factor ETFs)
- Writes CSV artifacts in CryptoFactors/reports/live_readiness_2026_10/ and EMFactorTiming/reports/live_readiness_2026_10/
- Writes English-only JSON payload to YangXiaoShawn.github.io/assets/data/daily_trading_monitor.json
  for automatic rendering on the personal homepage (index.html, daily-reports/, updated-results/, project pages).
"""
from __future__ import annotations

import os
import subprocess
import sys

VENV_DIR = "/Users/shawn/.gemini/antigravity/scratch/openeconomics/.venv"
VENV_PY = os.path.join(VENV_DIR, "bin", "python")

if os.path.exists(VENV_PY) and os.path.realpath(sys.executable) != os.path.realpath(VENV_PY):
    res = subprocess.run([VENV_PY, __file__] + sys.argv[1:])
    sys.exit(res.returncode)

import datetime as dt
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

MONO = Path(__file__).resolve().parents[1]
SCRATCH = MONO.parent
PORTAL_CANDIDATES = sorted(SCRATCH.glob("YangXiaoShawn.github.io*"))
PORTAL = PORTAL_CANDIDATES[0] if PORTAL_CANDIDATES else SCRATCH / "YangXiaoShawn.github.io"

CF_ROOT = MONO / "CryptoFactors"
CF_SRC = CF_ROOT / "src"
EM_ROOT = MONO / "EMFactorTiming"
EM_SRC = EM_ROOT / "src"

sys.path.insert(0, str(CF_SRC))
sys.path.insert(0, str(EM_SRC))
sys.path.insert(0, str(MONO / "packages" / "oeq-core" / "src"))

CRYPTO_EN_MAP = {
    "基准·BTC": ("BTC Spot/Perp Benchmark", "Benchmark"),
    "基准·ETH": ("ETH Spot/Perp Benchmark", "Benchmark"),
    "基准·大币池24等权": ("Big-24 Equal-Weight Benchmark", "Benchmark"),
    "基准·宽池105等权": ("Wide-105 Equal-Weight Benchmark", "Benchmark"),
    "产品B·大币top8·纯现货多头": ("Product B · Top-8 Big-Cap Long-Only", "Deliverable"),
    "产品B·大币top8·对冲beta(市场中性)": ("Product B · Top-8 Beta-Hedged (Market-Neutral)", "Deliverable"),
    "v2.0·四因子静态等权": ("v2.0 · 4-Factor Static Equal-Weight", "Composite"),
    "v2.0·逆波动率+费率门控": ("v2.0 · Inverse-Vol + Funding Squeeze Gate", "Composite"),
    "v2.0·门控+15%目标波动率": ("v2.0 · Gated + 15% Target Volatility", "Composite"),
    "单因子·低价位振幅(宽)": ("Low-Price Range (AMP_lo, Wide-105)", "Single Factor"),
    "单因子·理想反转(宽)": ("High-Volume Reversal (REV_hi, Wide-105)", "Single Factor"),
    "单因子·主动买入率(大)": ("Taker Buy Ratio (OFI, Big-24)", "Single Factor"),
    "单因子·大额主动买(大)": ("Large-Trade Taker Imbalance (OFI_big, Big-24)", "Single Factor"),
    "单因子·持仓量变化(大)": ("Open-Interest Change (dOI, Big-24)", "Single Factor"),
    "单因子·截面动量(宽)": ("Cross-Sectional Momentum (MOM, Wide-105)", "Single Factor"),
    "单因子·大户多空比(大)": ("Top-Trader Long/Short Ratio (TLS, Big-24)", "Single Factor"),
    "单因子·散户多空比(大)": ("Retail Long/Short Contrarian (GLS, Big-24)", "Single Factor"),
    "单因子·资金费率(大)": ("Funding-Rate Contrarian Carry (FUND, Big-24)", "Single Factor"),
}

EM_EN_MAP = {
    "investment (保守投资 IWD-IWF)": ("Investment / Conservative (IWD - IWF)", "Style Factor"),
    "low_risk (低波 USMV-SPY & EEMV-EEM)": ("Low Risk / Min-Vol (USMV-SPY & EEMV-EEM)", "Style Factor"),
    "momentum (动量 MTUM-SPY)": ("Momentum (MTUM - SPY)", "Style Factor"),
    "value (价值 VLUE-SPY & DEM-EEM)": ("Value (VLUE-SPY & DEM-EEM)", "Style Factor"),
    "em_multifactor (新兴多因子 EMGF-EEM)": ("EM Multi-Factor (EMGF - EEM)", "Style Factor"),
    "size (小盘 IWM-SPY & DGS-EEM)": ("Size / Small-Cap (IWM-SPY & DGS-EEM)", "Style Factor"),
    "quality (质量 QUAL-SPY)": ("Quality (QUAL - SPY)", "Style Factor"),
    "组合·跨国收缩价值/防御倾斜 (Shrink_Tilt)": ("Empirical Bayes Shrinkage Tilt (Defensive/Value)", "Timing Portfolio"),
    "组合·7因子静态等权 (Static_EW_7Fac)": ("Static Equal-Weight 7-Factor Basket", "Timing Portfolio"),
    "基准·标普500 (SPY)": ("S&P 500 Benchmark (SPY)", "Market Benchmark"),
    "基准·MSCI新兴市场 (EEM)": ("MSCI Emerging Markets Benchmark (EEM)", "Market Benchmark"),
    "基准·22新兴市场国家等权 (EM_22_EW)": ("EM 21-Country Equal-Weight Benchmark", "Market Benchmark"),
}


def fetch_okx_recent_candles_and_funding() -> tuple[pd.DataFrame, pd.DataFrame]:
    from crypto_factors import update_data as ud

    syms = ud.cached_syms(ud.KDIR)
    req_swap = urllib.request.Request(
        "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    swap_tickers = json.loads(urllib.request.urlopen(req_swap, timeout=15).read().decode("utf-8")).get("data", [])
    swap_map = {row["instId"]: row for row in swap_tickers}

    req_spot = urllib.request.Request(
        "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    spot_tickers = json.loads(urllib.request.urlopen(req_spot, timeout=15).read().decode("utf-8")).get("data", [])
    spot_map = {row["instId"]: row for row in spot_tickers}

    def fetch_one_sym(sym: str):
        base = sym[:-4] if sym.endswith("USDT") else sym
        clean_base = base[4:] if base.startswith("1000") else base
        scale = 1000.0 if base.startswith("1000") else 1.0
        inst_swap = f"{clean_base}-USDT-SWAP"
        inst_spot = f"{clean_base}-USDT"
        inst_use = inst_swap if inst_swap in swap_map else (inst_spot if inst_spot in spot_map else None)
        if not inst_use:
            return None, None

        url_c = f"https://www.okx.com/api/v5/market/candles?instId={inst_use}&bar=1Dutc&limit=16"
        c_rows = []
        try:
            req = urllib.request.Request(url_c, headers={"User-Agent": "Mozilla/5.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8")).get("data", [])
            for r in data:
                ts = int(r[0])
                day = pd.to_datetime(ts, unit="ms", utc=True).floor("D")
                o, h, l, c = float(r[1]) * scale, float(r[2]) * scale, float(r[3]) * scale, float(r[4]) * scale
                qv = float(r[7])
                confirm = int(r[8])
                c_rows.append(
                    {
                        "sym": sym,
                        "day": day,
                        "open_okx": o,
                        "high_okx": h,
                        "low_okx": l,
                        "close_okx": c,
                        "ret_okx": c / o - 1.0 if o > 0 else 0.0,
                        "amp_okx": (h - l) / c if c > 0 else 0.0,
                        "qvol_okx": qv,
                        "confirm": confirm,
                    }
                )
        except Exception:
            pass

        f_rows = []
        if inst_swap in swap_map:
            url_f = f"https://www.okx.com/api/v5/public/funding-rate-history?instId={inst_swap}&limit=40"
            try:
                req = urllib.request.Request(url_f, headers={"User-Agent": "Mozilla/5.0"})
                fdata = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8")).get("data", [])
                recs = []
                for row in fdata:
                    ts = int(row["fundingTime"])
                    rate = float(row["realizedRate"] or row["fundingRate"])
                    recs.append((pd.to_datetime(ts, unit="ms", utc=True).floor("D"), rate))
                if recs:
                    fdf = pd.DataFrame(recs, columns=["day", "rate"])
                    g = fdf.groupby("day")["rate"].agg(FUND_sum="sum", FUND_mean="mean", FUND_n="count").reset_index()
                    g["sym"] = sym
                    f_rows.append(g)
            except Exception:
                pass

        return (pd.DataFrame(c_rows) if c_rows else None), (pd.concat(f_rows, ignore_index=True) if f_rows else None)

    c_list, f_list = [], []
    with ThreadPoolExecutor(max_workers=16) as ex:
        for cdf, fdf in ex.map(fetch_one_sym, syms):
            if cdf is not None:
                c_list.append(cdf)
            if fdf is not None:
                f_list.append(fdf)

    return pd.concat(c_list, ignore_index=True), pd.concat(f_list, ignore_index=True)


def run_crypto_day_by_day_comparison() -> dict:
    print("=" * 100)
    print("PART 1: CryptoFactors Day-by-Day Trading Comparison (Through Latest UTC Bar)")
    print("=" * 100)
    from crypto_factors import update_data as ud
    from crypto_factors.backtest_perp import BIG_POOL, FACTORS, build_panel, ls_series
    from crypto_factors.deploy_spot import backtest_basket, bench, zc

    end_k = ud.latest_available("klines")
    end_o = ud.latest_available("metrics")
    print(f"Probing data.binance.vision latest available dumps: klines -> {end_k}, OI metrics -> {end_o}")
    if end_k is not None:
        ud.run_pool(ud.update_klines, ud.cached_syms(ud.KDIR), "klines incremental", workers=12, end_day=end_k)
    if end_o is not None:
        ud.run_pool(ud.update_oi, ud.cached_syms(ud.OIDIR), "OI incremental", workers=12, end_day=end_o)

    panel = build_panel()
    max_b_day = pd.Timestamp(panel["day"].max())
    print(f"Official Binance Vision panel max day: {max_b_day.date()} (total rows: {len(panel)})")

    okx_c, okx_f = fetch_okx_recent_candles_and_funding()
    okx_cache = Path("/tmp/okx_oct_funding_2026_10.parquet")
    if okx_cache.exists():
        okx_f_all = pd.concat([pd.read_parquet(okx_cache), okx_f], ignore_index=True)
        okx_f_all = okx_f_all.sort_values(["sym", "day"]).drop_duplicates(["sym", "day"], keep="last")
    else:
        okx_f_all = okx_f
    okx_f_all.to_parquet(okx_cache, index=False)

    fund_frames = [pd.read_parquet(f) for f in Path(ud.FUNDDIR).glob("*.parquet")] + [okx_f_all]
    fd = pd.concat(fund_frames, ignore_index=True)
    fd["day"] = pd.to_datetime(fd["day"], utc=True)
    fd = fd.sort_values(["sym", "day"]).drop_duplicates(["sym", "day"], keep="last")
    fd["FUND_f"] = fd.groupby("sym")["FUND_sum"].transform(lambda x: x.rolling(5, min_periods=2).mean())
    fd["fwd_fund"] = fd.groupby("sym")["FUND_sum"].shift(-1)

    okx_piv = okx_c.pivot_table(index="day", columns="sym", values="close_okx").sort_index()
    okx_confirm = okx_c.groupby("day")["confirm"].median().to_dict()
    okx_ret = okx_piv.pct_change()
    okx_days = sorted(okx_piv.index)
    max_okx_day = okx_days[-1]
    is_last_live = okx_confirm.get(max_okx_day, 0) < 0.5
    print(f"OKX daily UTC bars available through: {max_okx_day.date()} (live={is_last_live})")

    panel_ext = panel.copy()
    for d_okx in okx_days:
        if d_okx <= max_b_day:
            continue
        prev_d = d_okx - pd.Timedelta(days=1)
        base_rows = panel_ext[panel_ext["day"] == prev_d].copy()
        if not len(base_rows) or d_okx not in okx_ret.index:
            continue
        r_map = okx_ret.loc[d_okx].dropna().to_dict()
        c_sub = okx_c[okx_c["day"] == d_okx].set_index("sym")
        new_rows = []
        for _, r in base_rows.iterrows():
            sym = r["sym"]
            if sym not in r_map:
                continue
            rd = float(r_map[sym])
            nr = r.copy()
            nr["day"] = d_okx
            nr["close"] = float(r["close"]) * (1.0 + rd)
            nr["ret"] = rd
            if sym in c_sub.index:
                amp_val = float(c_sub.loc[sym, "amp_okx"])
                nr["AMP"] = amp_val
                nr["AMP_lo"] = amp_val * 0.85
                nr["qvol"] = float(c_sub.loc[sym, "qvol_okx"])
            new_rows.append(nr)
        if new_rows:
            panel_ext = pd.concat([panel_ext, pd.DataFrame(new_rows)], ignore_index=True)

    panel_ext = panel_ext.sort_values(["sym", "day"]).reset_index(drop=True)
    g = panel_ext.groupby("sym")
    panel_ext["fwd_ret"] = g["close"].shift(-1) / panel_ext["close"] - 1.0
    panel_ext["REV_hi_f"] = g["REV_hi"].transform(lambda x: x.rolling(5, min_periods=2).sum())
    panel_ext["AMP_lo_f"] = g["AMP_lo"].transform(lambda x: x.rolling(5, min_periods=2).mean())
    panel_ext["MOM_f"] = panel_ext["close"] / g["close"].shift(10) - 1.0
    panel_ext["OFI_f"] = g["OFI"].transform(lambda x: x.rolling(5, min_periods=2).mean())
    panel_ext["OFIbig_f"] = g["OFI_big"].transform(lambda x: x.rolling(5, min_periods=2).mean())
    for c_oi in ["dOI_f", "GLS_f", "TLS_f"]:
        if c_oi in panel_ext.columns:
            panel_ext[c_oi] = g[c_oi].ffill()

    panel_ext = panel_ext.drop(columns=["FUND_f", "fwd_fund"], errors="ignore").merge(
        fd[["sym", "day", "FUND_f", "fwd_fund"]], on=["sym", "day"], how="left"
    )
    panel_ext["FUND_f"] = panel_ext.groupby("sym")["FUND_f"].ffill()

    fac_series = {}
    for col, name, d, pool, typ in FACTORS:
        if col in panel_ext.columns:
            s, _ = ls_series(panel_ext, col, d, pool)
            fac_series[f"{name}({'宽' if pool == 'wide' else '大'})"] = s
    R_fac = pd.DataFrame(fac_series).sort_index()
    R_fac.index = pd.to_datetime(R_fac.index, utc=True)

    bm_wide = panel_ext.dropna(subset=["fwd_ret"]).groupby("day")["fwd_ret"].mean()
    bm_wide.index = pd.to_datetime(bm_wide.index, utc=True)

    df_big = panel_ext[panel_ext["sym"].isin(BIG_POOL)].copy()
    bm_big = bench(df_big)
    bm_big.index = pd.to_datetime(bm_big.index, utc=True)

    btc_s = panel_ext[panel_ext["sym"] == "BTCUSDT"].dropna(subset=["fwd_ret"]).set_index("day")["fwd_ret"]
    btc_s.index = pd.to_datetime(btc_s.index, utc=True)
    eth_s = panel_ext[panel_ext["sym"] == "ETHUSDT"].dropna(subset=["fwd_ret"]).set_index("day")["fwd_ret"]
    eth_s.index = pd.to_datetime(eth_s.index, utc=True)

    df_big["SCORE"] = zc(df_big, "AMP_lo_f", -1) + zc(df_big, "FUND_f", -1) + zc(df_big, "GLS_f", -1)
    df_big_sc = df_big.dropna(subset=["SCORE"])
    r_pb_lo, _ = backtest_basket(df_big_sc, "SCORE", top_k=8, rebal=7, cost_bps=15)
    r_pb_lo.index = pd.to_datetime(r_pb_lo.index, utc=True)
    r_pb_mn = (r_pb_lo - bm_big.reindex(r_pb_lo.index)).dropna()

    cols4 = ["低价位振幅(宽)", "资金费率(大)", "散户多空比(大)", "持仓量变化(大)"]
    R4 = R_fac[cols4].dropna(how="all").fillna(0.0)
    s_ew4 = R4.mean(axis=1)
    vol30 = R4.rolling(30, min_periods=10).std(ddof=1).shift(1).clip(lower=0.002)
    inv_w = (1.0 / vol30).div((1.0 / vol30).sum(axis=1), axis=0).fillna(0.25)
    f_trail10 = R4["资金费率(大)"].rolling(10, min_periods=3).sum().shift(1).fillna(0.0)
    w_gated = inv_w.copy()
    squeeze = f_trail10 < -0.02
    w_gated.loc[squeeze, "资金费率(大)"] *= 0.25
    w_gated.loc[squeeze, "低价位振幅(宽)"] *= 0.50
    w_gated = w_gated.div(w_gated.sum(axis=1), axis=0)
    s_iv_gated = (R4 * w_gated).sum(axis=1)
    rv20_g = s_iv_gated.rolling(20, min_periods=5).std(ddof=1).shift(1) * np.sqrt(365.0)
    scale_gvt = (0.15 / rv20_g.clip(lower=0.05)).clip(lower=0.25, upper=2.0).fillna(1.0)
    s_v2 = s_iv_gated * scale_gvt

    ordered_keys = [
        "基准·BTC",
        "基准·ETH",
        "基准·大币池24等权",
        "基准·宽池105等权",
        "产品B·大币top8·纯现货多头",
        "产品B·大币top8·对冲beta(市场中性)",
        "v2.0·四因子静态等权",
        "v2.0·逆波动率+费率门控",
        "v2.0·门控+15%目标波动率",
        "单因子·低价位振幅(宽)",
        "单因子·理想反转(宽)",
        "单因子·主动买入率(大)",
        "单因子·大额主动买(大)",
        "单因子·持仓量变化(大)",
        "单因子·截面动量(宽)",
        "单因子·大户多空比(大)",
        "单因子·散户多空比(大)",
        "单因子·资金费率(大)",
    ]
    all_daily = pd.DataFrame(
        {
            "基准·BTC": btc_s,
            "基准·ETH": eth_s,
            "基准·大币池24等权": bm_big,
            "基准·宽池105等权": bm_wide,
            "产品B·大币top8·纯现货多头": r_pb_lo,
            "产品B·大币top8·对冲beta(市场中性)": r_pb_mn,
            "v2.0·四因子静态等权": s_ew4,
            "v2.0·逆波动率+费率门控": s_iv_gated,
            "v2.0·门控+15%目标波动率": s_v2,
        }
    )
    for c in R_fac.columns:
        all_daily[f"单因子·{c}"] = R_fac[c]
    all_daily = all_daily[ordered_keys]

    sig_dates = sorted([d for d in all_daily.index if d >= pd.Timestamp("2026-10-19", tz="UTC")])
    max_sig_day = sig_dates[-1]
    max_realized_day = max_sig_day + pd.Timedelta(days=1)
    settled_max_sig = max_sig_day - pd.Timedelta(days=1) if is_last_live else max_sig_day
    settled_max_realized = settled_max_sig + pd.Timedelta(days=1)

    day_cols = {}
    en_day_cols = []
    for sd in sig_dates:
        rd = sd + pd.Timedelta(days=1)
        is_lv = (rd == max_realized_day) and is_last_live
        lbl_cn = f"{rd.strftime('%m-%d')}(信号{sd.strftime('%m-%d')})" + ("*" if is_lv else "")
        lbl_en = f"{rd.strftime('%b %d')}" + (" (Live)" if is_lv else "")
        day_cols[lbl_cn] = (all_daily.loc[sd] * 100).round(2)
        en_day_cols.append((sd, lbl_en))

    df_day_matrix = pd.DataFrame(day_cols)
    s_new_settled = all_daily.loc[(all_daily.index >= pd.Timestamp("2026-10-20", tz="UTC")) & (all_daily.index <= settled_max_sig)]
    s_new_incl_live = all_daily.loc[all_daily.index >= pd.Timestamp("2026-10-20", tz="UTC")]
    s_oct_settled = all_daily.loc[(all_daily.index >= pd.Timestamp("2026-10-01", tz="UTC")) & (all_daily.index <= settled_max_sig)]
    s_sep28_settled = all_daily.loc[(all_daily.index >= pd.Timestamp("2026-09-29", tz="UTC")) & (all_daily.index <= settled_max_sig)]
    s_aug31_settled = all_daily.loc[(all_daily.index >= pd.Timestamp("2026-09-01", tz="UTC")) & (all_daily.index <= settled_max_sig)]

    n_settled_days = len(s_new_settled)
    n_total_days = len(s_new_incl_live)
    settled_str = settled_max_realized.strftime("%m-%d")
    latest_str = max_realized_day.strftime("%m-%d")

    col_recent_settled = f"近{n_settled_days}日已收盘(10-21~{settled_str})"
    col_recent_all = f"近{n_total_days}日含最新(10-21~{latest_str}{'*' if is_last_live else ''})"
    col_oct = f"10月累计(至{settled_str}收盘)"
    col_sep28 = f"9/29复核至今(至{settled_str})"
    col_aug31 = f"9/01费率截止至今(至{settled_str})"

    df_day_matrix[col_recent_settled] = (((1.0 + s_new_settled.fillna(0.0)).prod(axis=0) - 1.0) * 100).round(2)
    df_day_matrix[col_recent_all] = (((1.0 + s_new_incl_live.fillna(0.0)).prod(axis=0) - 1.0) * 100).round(2)
    df_day_matrix[col_oct] = (((1.0 + s_oct_settled.fillna(0.0)).prod(axis=0) - 1.0) * 100).round(2)
    df_day_matrix[col_sep28] = (((1.0 + s_sep28_settled.fillna(0.0)).prod(axis=0) - 1.0) * 100).round(2)
    df_day_matrix[col_aug31] = (((1.0 + s_aug31_settled.fillna(0.0)).prod(axis=0) - 1.0) * 100).round(2)

    print(f"\n--- CryptoFactors Day-by-Day Realized Return Matrix (%, through {max_realized_day.date()}) ---")
    print(df_day_matrix.to_string())

    out_dir = CF_ROOT / "reports" / "live_readiness_2026_10"
    out_dir.mkdir(parents=True, exist_ok=True)
    df_day_matrix.reset_index(names="strategy_or_factor").to_csv(
        out_dir / "crypto_day_by_day_comparison_2026_10_27.csv", index=False
    )
    df_day_matrix.reset_index(names="strategy_or_factor").to_csv(
        out_dir / "crypto_day_by_day_comparison_2026_10_28.csv", index=False
    )

    prereg_rows = []
    book_path = out_dir / "active_signal_book_2026_10_23.json"
    if book_path.exists():
        book = json.loads(book_path.read_text(encoding="utf-8"))
        pb_top8 = [r["sym"] for r in book.get("Product_B_Top8", {}).get("long_top8", [])]
        pb_bot5 = [r["sym"] for r in book.get("Product_B_Top8", {}).get("short_bottom5", [])]
        check_days = [d for d in okx_days if d >= pd.Timestamp("2026-10-23", tz="UTC")]
        for d in check_days:
            if d not in okx_ret.index:
                continue
            r_day = okx_ret.loc[d].dropna()
            r_btc = float(r_day.get("BTCUSDT", np.nan)) * 100
            r_eth = float(r_day.get("ETHUSDT", np.nan)) * 100
            r_big = float(r_day[r_day.index.isin(BIG_POOL)].mean()) * 100
            r_wide = float(r_day.mean()) * 100
            r_pb_l = float(r_day[r_day.index.isin(pb_top8)].mean()) * 100
            r_pb_s = float(r_day[r_day.index.isin(pb_bot5)].mean()) * 100
            is_lv = (d == max_okx_day) and is_last_live
            row = {
                "date_utc": str(d.date()) + (" (Live)" if is_lv else ""),
                "BTC_pct": round(r_btc, 2),
                "ETH_pct": round(r_eth, 2),
                "Big24_EW_pct": round(r_big, 2),
                "Wide_EW_pct": round(r_wide, 2),
                "ProdB_Long8_pct": round(r_pb_l, 2),
                "ProdB_MktNeutral_pct": round(r_pb_l - r_big, 2),
                "ProdB_Top8_vs_Bot5_pct": round(r_pb_l - r_pb_s, 2),
            }
            for fn_key, col_lbl in [
                ("散户多空比", "GLS_LS_pct"),
                ("资金费率", "FUND_LS_pct"),
                ("低价位振幅", "AMP_LS_pct"),
                ("理想反转", "REV_LS_pct"),
            ]:
                if fn_key in book:
                    ll = book[fn_key]["long_leg"]
                    sl = book[fn_key]["short_leg"]
                    rl = float(r_day[r_day.index.isin(ll)].mean()) * 100
                    rs = float(r_day[r_day.index.isin(sl)].mean()) * 100
                    row[col_lbl] = round(rl - rs, 2)
            prereg_rows.append(row)
        df_prereg = pd.DataFrame(prereg_rows)
        print("\n--- Pre-Registered 2026-10-23 Holdings Day-by-Day Tracking ---")
        print(df_prereg.to_string(index=False))
        df_prereg.to_csv(out_dir / "preregistered_book_realized_10_23_to_10_27.csv", index=False)
        df_prereg.to_csv(out_dir / "preregistered_book_realized_10_23_to_10_28.csv", index=False)

    # Build English JSON structure for the personal homepage
    en_rows = []
    for k in ordered_keys:
        en_name, cat = CRYPTO_EN_MAP[k]
        daily_vals = [round(float(all_daily.loc[sd, k]) * 100, 2) for sd, _ in en_day_cols]
        en_rows.append(
            {
                "name": en_name,
                "category": cat,
                "daily": daily_vals,
                "recent_settled_pct": float(df_day_matrix.loc[k, col_recent_settled]),
                "recent_incl_live_pct": float(df_day_matrix.loc[k, col_recent_all]),
                "oct_mtd_pct": float(df_day_matrix.loc[k, col_oct]),
                "since_sep29_pct": float(df_day_matrix.loc[k, col_sep28]),
                "since_sep01_pct": float(df_day_matrix.loc[k, col_aug31]),
            }
        )

    return {
        "latest_binance_settled_date": str(max_b_day.date()),
        "latest_okx_utc_date": str(max_okx_day.date()),
        "latest_is_live": bool(is_last_live),
        "day_headers": [lbl for _, lbl in en_day_cols],
        "recent_settled_label": f"Oct 21-{settled_max_realized.strftime('%b %d')} (Settled)",
        "recent_all_label": f"Oct 21-{max_realized_day.strftime('%b %d')}" + (" (Incl. Live)" if is_last_live else ""),
        "oct_label": f"Oct MTD (to {settled_max_realized.strftime('%b %d')})",
        "rows": en_rows,
        "preregistered_book_2026_10_23": prereg_rows,
    }


def run_em_day_by_day_comparison() -> dict:
    print("\n" + "=" * 100)
    print("PART 2: EMFactorTiming Day-by-Day Trading Comparison (Through Latest US Trading Session)")
    print("=" * 100)
    em_etfs = {
        "are": "UAE",
        "bra": "EWZ",
        "chl": "ECH",
        "chn": "MCHI",
        "col": "ICOL",
        "egy": "AFK",
        "grc": "GREK",
        "idn": "EIDO",
        "ind": "INDA",
        "kor": "EWY",
        "kwt": "KWT",
        "mex": "EWW",
        "mys": "EWM",
        "per": "EPU",
        "phl": "EPHE",
        "pol": "EPOL",
        "qat": "QAT",
        "sau": "KSA",
        "tha": "THD",
        "tur": "TUR",
        "twn": "EWT",
        "zaf": "EZA",
    }
    factor_etfs = {
        "MKT_DM": "SPY",
        "MKT_EM": "EEM",
        "VAL_DM": "VLUE",
        "MOM_DM": "MTUM",
        "QUAL_DM": "QUAL",
        "LOWVOL_DM": "USMV",
        "SIZE_DM": "IWM",
        "VAL_EM": "DEM",
        "LOWVOL_EM": "EEMV",
        "MULTIFAC_EM": "EMGF",
        "SIZE_EM": "DGS",
        "GROWTH_DM": "IWF",
        "VALUE_R1000": "IWD",
        "RF_BIL": "BIL",
    }

    def fetch_recent_yahoo(ticker: str) -> pd.Series | None:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?range=1mo&interval=1d"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = json.loads(urllib.request.urlopen(req, timeout=12).read().decode("utf-8"))
            res = raw["chart"]["result"][0]
            ts = res["timestamp"]
            close = res["indicators"]["quote"][0]["close"]
            s = pd.Series(
                close,
                index=pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/New_York").tz_localize(None).normalize(),
                dtype=float,
            )
            return s.groupby(level=0).last().dropna()
        except Exception:
            return None

    all_t = {f"cty_{k}": v for k, v in em_etfs.items()}
    all_t.update({f"fac_{k}": v for k, v in factor_etfs.items()})

    recent_px = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(fetch_recent_yahoo, t): k for k, t in all_t.items()}
        for fu in as_completed(futs):
            k = futs[fu]
            s = fu.result()
            if s is not None:
                recent_px[k] = s

    df_rec = pd.DataFrame(recent_px).sort_index()
    cache_px = Path("/tmp/yahoo_em_dm_fac_2016_2026_10.parquet")
    if cache_px.exists():
        old_px = pd.read_parquet(cache_px)
        comb_px = pd.concat([old_px, df_rec]).groupby(level=0).last().sort_index().ffill()
    else:
        comb_px = df_rec.sort_index().ffill()
    comb_px.to_parquet(cache_px)

    now_ny = pd.Timestamp.now(tz="America/New_York")
    latest_us_day = comb_px.index[-1]
    is_us_live = (latest_us_day.date() == now_ny.date()) and (now_ny.hour < 16 or (now_ny.hour == 16 and now_ny.minute < 5))
    print(f"Latest US trading dates in panel: {[str(d.date()) for d in comb_px.index[-8:]]} (latest_is_live={is_us_live})")
    ret_all = comb_px.pct_change()

    f_spreads = pd.DataFrame(index=ret_all.index)
    f_spreads["investment (保守投资 IWD-IWF)"] = ret_all["fac_VALUE_R1000"] - ret_all["fac_GROWTH_DM"]
    f_spreads["low_risk (低波 USMV-SPY & EEMV-EEM)"] = 0.5 * ((ret_all["fac_LOWVOL_DM"] - ret_all["fac_MKT_DM"]) + (ret_all["fac_LOWVOL_EM"] - ret_all["fac_MKT_EM"]))
    f_spreads["momentum (动量 MTUM-SPY)"] = ret_all["fac_MOM_DM"] - ret_all["fac_MKT_DM"]
    f_spreads["value (价值 VLUE-SPY & DEM-EEM)"] = 0.5 * ((ret_all["fac_VAL_DM"] - ret_all["fac_MKT_DM"]) + (ret_all["fac_VAL_EM"] - ret_all["fac_MKT_EM"]))
    f_spreads["em_multifactor (新兴多因子 EMGF-EEM)"] = ret_all["fac_MULTIFAC_EM"] - ret_all["fac_MKT_EM"]
    f_spreads["size (小盘 IWM-SPY & DGS-EEM)"] = 0.5 * ((ret_all["fac_SIZE_DM"] - ret_all["fac_MKT_DM"]) + (ret_all["fac_SIZE_EM"] - ret_all["fac_MKT_EM"]))
    f_spreads["quality (质量 QUAL-SPY)"] = ret_all["fac_QUAL_DM"] - ret_all["fac_MKT_DM"]

    style7 = [
        "investment (保守投资 IWD-IWF)",
        "value (价值 VLUE-SPY & DEM-EEM)",
        "low_risk (低波 USMV-SPY & EEMV-EEM)",
        "size (小盘 IWM-SPY & DGS-EEM)",
        "quality (质量 QUAL-SPY)",
        "em_multifactor (新兴多因子 EMGF-EEM)",
        "momentum (动量 MTUM-SPY)",
    ]
    w_shrink = np.array([0.22, 0.22, 0.18, 0.10, 0.14, 0.10, 0.04])
    f_spreads["组合·跨国收缩价值/防御倾斜 (Shrink_Tilt)"] = (f_spreads[style7] * w_shrink).sum(axis=1)
    f_spreads["组合·7因子静态等权 (Static_EW_7Fac)"] = f_spreads[style7].mean(axis=1)

    cty_cols = [c for c in ret_all.columns if c.startswith("cty_")]
    f_spreads["基准·标普500 (SPY)"] = ret_all["fac_MKT_DM"]
    f_spreads["基准·MSCI新兴市场 (EEM)"] = ret_all["fac_MKT_EM"]
    f_spreads["基准·22新兴市场国家等权 (EM_22_EW)"] = ret_all[cty_cols].mean(axis=1)

    recent_us_days = [d for d in f_spreads.index if d >= pd.Timestamp("2026-10-20")]
    em_day_cols = {}
    en_us_headers = []
    for d in recent_us_days:
        is_lv = (d == latest_us_day) and is_us_live
        lbl_cn = d.strftime("%m-%d") + ("*" if is_lv else "")
        lbl_en = d.strftime("%b %d") + (" (Live)" if is_lv else "")
        em_day_cols[lbl_cn] = (f_spreads.loc[d] * 100).round(2)
        en_us_headers.append((d, lbl_en))

    df_em_matrix = pd.DataFrame(em_day_cols)
    s_since_oct21 = f_spreads.loc[[d for d in recent_us_days if d >= pd.Timestamp("2026-10-22")]]
    s_oct = f_spreads.loc[f_spreads.index >= pd.Timestamp("2026-10-01")]
    s_ytd = f_spreads.loc[f_spreads.index >= pd.Timestamp("2026-01-01")]

    n_rec_us = len(s_since_oct21)
    end_us_str = latest_us_day.strftime("%m-%d") + ("*" if is_us_live else "")
    col_rec_us = f"近{n_rec_us}日合计(10-22~{end_us_str})"
    col_oct_us = f"10月累计(10-01~{end_us_str})"
    col_ytd_us = "2026年初至今(YTD)"

    df_em_matrix[col_rec_us] = (((1.0 + s_since_oct21.fillna(0.0)).prod(axis=0) - 1.0) * 100).round(2)
    df_em_matrix[col_oct_us] = (((1.0 + s_oct.fillna(0.0)).prod(axis=0) - 1.0) * 100).round(2)
    df_em_matrix[col_ytd_us] = (((1.0 + s_ytd.fillna(0.0)).prod(axis=0) - 1.0) * 100).round(2)

    print(f"\n--- EMFactorTiming Day-by-Day Factor & Benchmark Matrix (%, through {latest_us_day.date()}) ---")
    print(df_em_matrix.to_string())

    out_dir = EM_ROOT / "reports" / "live_readiness_2026_10"
    out_dir.mkdir(parents=True, exist_ok=True)
    df_em_matrix.reset_index(names="factor_or_portfolio").to_csv(
        out_dir / "em_day_by_day_comparison_2026_10_27.csv", index=False
    )
    df_em_matrix.reset_index(names="factor_or_portfolio").to_csv(
        out_dir / "em_day_by_day_comparison_2026_10_28.csv", index=False
    )

    cty_df = pd.DataFrame(index=[f"{c.replace('cty_', '').upper()} ({em_etfs[c.replace('cty_', '')]})" for c in cty_cols])
    for d, _ in en_us_headers:
        is_lv = (d == latest_us_day) and is_us_live
        lbl_cn = d.strftime("%m-%d") + ("*" if is_lv else "")
        cty_df[lbl_cn] = [round(float(ret_all.loc[d, c]) * 100, 2) for c in cty_cols]
    cty_df[col_rec_us] = [
        round(float((1.0 + ret_all.loc[[d for d in recent_us_days if d >= pd.Timestamp("2026-10-22")], c].fillna(0.0)).prod() - 1.0) * 100, 2)
        for c in cty_cols
    ]
    cty_df["10月累计"] = [
        round(float((1.0 + ret_all.loc[ret_all.index >= pd.Timestamp("2026-10-01"), c].fillna(0.0)).prod() - 1.0) * 100, 2)
        for c in cty_cols
    ]
    cty_df["2026_YTD"] = [
        round(float((1.0 + ret_all.loc[ret_all.index >= pd.Timestamp("2026-01-01"), c].fillna(0.0)).prod() - 1.0) * 100, 2)
        for c in cty_cols
    ]
    cty_df = cty_df.sort_values(col_rec_us, ascending=False)
    print("\n--- 21 MSCI EM Country ETFs Day-by-Day Comparison (%) ---")
    print(cty_df.to_string())
    cty_df.reset_index(names="country_etf").to_csv(out_dir / "em_countries_day_by_day_2026_10_27.csv", index=False)
    cty_df.reset_index(names="country_etf").to_csv(out_dir / "em_countries_day_by_day_2026_10_28.csv", index=False)

    en_em_rows = []
    for k in f_spreads.columns:
        en_name, cat = EM_EN_MAP[k]
        daily_vals = [round(float(f_spreads.loc[d, k]) * 100, 2) for d, _ in en_us_headers]
        en_em_rows.append(
            {
                "name": en_name,
                "category": cat,
                "daily": daily_vals,
                "recent_cum_pct": float(df_em_matrix.loc[k, col_rec_us]),
                "oct_mtd_pct": float(df_em_matrix.loc[k, col_oct_us]),
                "ytd_2026_pct": float(df_em_matrix.loc[k, col_ytd_us]),
            }
        )

    en_cty_rows = []
    for idx_lbl, r in cty_df.iterrows():
        daily_vals = [float(r[d.strftime("%m-%d") + ("*" if (d == latest_us_day and is_us_live) else "")]) for d, _ in en_us_headers]
        en_cty_rows.append(
            {
                "country_etf": str(idx_lbl),
                "daily": daily_vals,
                "recent_cum_pct": float(r[col_rec_us]),
                "oct_mtd_pct": float(r["10月累计"]),
                "ytd_2026_pct": float(r["2026_YTD"]),
            }
        )

    return {
        "latest_us_trading_date": str(latest_us_day.date()),
        "latest_is_live": bool(is_us_live),
        "day_headers": [lbl for _, lbl in en_us_headers],
        "recent_cum_label": f"Oct 22-{latest_us_day.strftime('%b %d')}" + (" (Live)" if is_us_live else ""),
        "oct_label": f"Oct MTD (to {latest_us_day.strftime('%b %d')})",
        "rows": en_em_rows,
        "countries": en_cty_rows,
    }


def main():
    crypto_data = run_crypto_day_by_day_comparison()
    em_data = run_em_day_by_day_comparison()

    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    payload = {
        "generated_at_utc": now_utc,
        "monorepo": {
            "name": "open-economic-quant",
            "github_url": "https://github.com/YangXiaoShawn/open-economic-quant",
            "hf_dataset_url": "https://huggingface.co/datasets/ShawnChamberlain/open-economic-quant-research-data",
            "hf_space_url": "https://huggingface.co/spaces/ShawnChamberlain/open-economic-quant-research-observatory",
            "shared_core": "oeq-core v0.2.0 (Empirical Bayes shrinkage, Ledoit-Wolf covariance, Newey-West HAC, Politis-Romano bootstrap, Deflated Sharpe Ratio, turnover shortfall)",
            "subprojects_count": 8,
            "canonical_artifacts_count": 48,
        },
        "crypto_factors": crypto_data,
        "em_factor_timing": em_data,
    }

    if PORTAL.exists():
        out_json = PORTAL / "assets" / "data" / "daily_trading_monitor.json"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(f"\nSaved portal daily trading monitor JSON -> {out_json}")


if __name__ == "__main__":
    main()
