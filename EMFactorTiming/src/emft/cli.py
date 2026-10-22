"""Command line: python -m emft run --data <path> --out <dir>   (or --synthetic)."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from . import backtest, data, evaluate, features, report
from .models import LEARNED, RULES, SCALED


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="emft")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="build features, backtest, evaluate, report")
    src = r.add_mutually_exclusive_group(required=True)
    src.add_argument("--data", help="JKP CSV file, directory, glob or .zip")
    src.add_argument("--synthetic", action="store_true", help="known-truth synthetic panel")
    r.add_argument("--out", default="reports/latest")
    r.add_argument("--oos-start", type=int, default=2000)
    r.add_argument("--test-region", default="EM", choices=["EM", "DM"])
    r.add_argument("--models", default="ols,enet,gbrt,hist_mean,shrink_mean,fmom",
                   help="comma list; add nn for the neural-net ensemble (slow on the full panel)")
    r.add_argument("--cost-bps", type=float, default=20.0)
    r.add_argument("--min-stocks", type=int, default=5)
    r.add_argument("--weighting", default="vw_cap", choices=["vw_cap", "vw", "ew"])
    r.add_argument("--kappa", type=float, default=120.0, help="prior weight (months) in the shrinkage mean")
    r.add_argument("--market-history", action="store_true",
                   help="time-varying MSCI classification from config/market_history.yaml")
    r.add_argument("--macro", help="directory of FRED CSVs; adds U.S. state variables as predictors")
    r.add_argument("--sample-start", help="drop feature months before YYYY-MM (to match --macro samples)")
    r.add_argument("--seed", type=int, default=0)

    c = sub.add_parser("coverage", help="print country coverage of a JKP file")
    c.add_argument("--data", required=True)

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "coverage":
        panel = data.load_jkp(args.data)
        print(data.coverage(panel).to_string(index=False))
        return

    if args.synthetic:
        panel, _ = data.synthetic_panel(seed=args.seed)
        provenance = "SYNTHETIC"
        oos_start = 2005 if args.oos_start < 2005 else args.oos_start
    else:
        panel = data.load_jkp(args.data, weighting=args.weighting, min_stocks=args.min_stocks)
        if args.market_history:
            panel = data.apply_market_history(panel)
        provenance = "JKP"
        oos_start = args.oos_start

    built = features.build_features(panel, kappa=args.kappa)
    predictors = tuple(features.FEATURES)
    if args.macro:
        built = built.merge(data.load_macro(args.macro), left_on="month", right_index=True, how="left")
        predictors += tuple(data.MACRO_FEATURES)
    if args.sample_start:
        built = built[built["month"] >= pd.Period(args.sample_start, freq="M")]
    feats = features.model_ready(built, extra=predictors[len(features.FEATURES):])
    models = tuple(m.strip() for m in args.models.split(",") if m.strip())
    preds = backtest.run_backtest(feats, test_region=args.test_region, models=models,
                                  oos_start=oos_start, seed=args.seed, features=predictors)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(out / "predictions.parquet", index=False)

    r2 = evaluate.r2_table(preds)
    learned = r2[r2["model"].isin(LEARNED + SCALED)]
    top = learned.iloc[0] if not learned.empty else r2.iloc[0]
    r2c = evaluate.r2_by_country(preds, top["model"], top["scope"])
    monthly = evaluate.portfolio_returns(preds, cost_bps=args.cost_bps)
    port = evaluate.portfolio_table(monthly)
    report.write_report(
        out, provenance, data.coverage(panel), r2, r2c, port, monthly,
        {"test_region": args.test_region, "oos_start": oos_start, "cost_bps": args.cost_bps,
         "models": models, "weighting": args.weighting, "min_stocks": args.min_stocks, "kappa": args.kappa,
         "market_history": args.market_history,
         "macro": args.macro, "sample_start": args.sample_start,
         "data": args.data or "synthetic", "seed": args.seed},
    )
    print(r2.to_string(index=False))
    print()
    print(port.to_string(index=False))


if __name__ == "__main__":
    main()
