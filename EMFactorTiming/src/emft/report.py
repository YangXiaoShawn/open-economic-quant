"""Write tables, a figure and a short markdown summary for one run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def _md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, r in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in r]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cumulative_plot(monthly: pd.DataFrame, strategies: list[str], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for s in strategies:
        g = monthly[monthly["strategy"] == s].sort_values("target_month")
        if g.empty:
            continue
        x = g["target_month"].dt.to_timestamp()
        ax.plot(x, np.cumsum(g["net"].to_numpy()), label=s, linewidth=1.4)
    ax.axhline(0, color="0.6", linewidth=0.8)
    ax.set_ylabel("Cumulative net return (sum of monthly)")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_report(
    out: Path,
    provenance: str,
    coverage: pd.DataFrame,
    r2: pd.DataFrame,
    r2_country: pd.DataFrame,
    port: pd.DataFrame,
    monthly: pd.DataFrame,
    settings: dict,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(out / "coverage.csv", index=False)
    r2.to_csv(out / "r2_oos.csv", index=False)
    r2_country.to_csv(out / "r2_oos_by_country.csv", index=False)
    port.to_csv(out / "portfolios.csv", index=False)
    monthly.to_csv(out / "portfolio_monthly.csv", index=False)

    best = port[port["strategy"] != "static_ew"].head(3)["strategy"].tolist()
    prefix = "SYNTHETIC DATA (validation only): " if provenance == "SYNTHETIC" else ""
    cumulative_plot(monthly, ["static_ew"] + best, out / "cumulative_net.png",
                    f"{prefix}{settings['test_region']} factor timing, net of {settings['cost_bps']:.0f} bp per unit turnover")

    stamp = {
        "provenance": provenance,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **settings,
    }
    (out / "run_manifest.json").write_text(json.dumps(stamp, indent=2, default=str))

    banner = (
        "> **SYNTHETIC DATA — software validation, not a finding.**\n"
        if provenance == "SYNTHETIC"
        else "> **Real data (JKP global factor returns).** Results are out-of-sample forecasts; see caveats.\n"
    )
    md = [
        "# Emerging-market factor timing — run summary",
        "",
        banner,
        f"Test region: {settings['test_region']} · out-of-sample from {settings['oos_start']} · "
        f"cost {settings['cost_bps']} bp per unit of timing turnover",
        "",
        "## Out-of-sample R² against each factor's historical mean",
        "",
        "Positive = beats the historical mean. `cw_t` is the Clark–West statistic (monthly, Newey–West).",
        "",
        _md_table(r2),
        "",
        "## Timing portfolios (equal-weighted across countries)",
        "",
        _md_table(port),
        "",
        "![cumulative](cumulative_net.png)",
        "",
        "## Coverage",
        "",
        f"{coverage['country'].nunique()} countries, {int(coverage['factors'].max())} factors at most per country.",
        "",
    ]
    (out / "summary.md").write_text("\n".join(md))
