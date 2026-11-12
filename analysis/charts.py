"""4 The facts: three charts.

1. The chain over time           -> figures/chart1_chain.png, tables/chart1_chain.csv
2. How different countries are   -> figures/chart2_dispersion.png, tables/dispersion.csv
3. The 2022-23 hikes by country  -> figures/chart3_countries.png

Usage: python -m analysis.charts
"""
from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from ecbdata.build import EURO_AREA, euro_area, load_clean, wide  # noqa: E402
from ecbdata.fetch import ROOT, load_keys  # noqa: E402

FIGURES = ROOT / "figures"
TABLES = ROOT / "tables"
SAMPLE_START = "2003-01-01"  # 4 chart 1: "January 2003 to the latest month"
COUNTRY_PANELS_START = "2021-01-01"  # 4 chart 3: "January 2021 to the latest month"

# 4 chart 1: euro-area recessions dated by the CEPR-EABCN Euro Area Business
# Cycle Dating Committee, as (peak, trough). COVID trough: the committee's
# statement of 9 November 2021, "a trough in economic activity occurred in
# 2020Q2, marking the end of the recession that had started after 2019Q4".
# Shading follows the committee's own charts ("recessions (peak excluded)"):
# from the end of the peak quarter to the end of the trough quarter.
RECESSIONS = [("2008Q1", "2009Q2"), ("2011Q3", "2013Q1"), ("2019Q4", "2020Q2")]

# 4 chart 2: the fixed group, the 12 members of 2003.
MEMBERS_2003 = ["AT", "BE", "FI", "FR", "DE", "GR", "IE", "IT", "LU", "NL", "PT", "ES"]

# Shared style: one colour per variable in every chart (identity, fixed order),
# Euribor in neutral grey; text in ink colours; hairline solid grid.
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, RECESSION = "#e1e0d9", "#c3c2b7", "#eceae4"
COLORS = {"L_NFC": "#2a78d6", "L_HH": "#eb6834", "dfr": "#1baf7a", "euribor3m": INK_2}
LABELS = {"L_NFC": "Loans to companies", "L_HH": "Mortgages",
          "dfr": "ECB deposit facility rate", "euribor3m": "3-month Euribor"}
LINE_WIDTH = 1.5


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
        "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
        "text.color": INK, "font.size": 9.5, "axes.titlesize": 10.5, "axes.titlelocation": "left",
        "lines.linewidth": LINE_WIDTH, "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round", "lines.dash_capstyle": "round",
        "legend.frameon": False, "legend.fontsize": 9, "savefig.dpi": 200,
    })


def title_block(fig, title: str, subtitle: str, source: str) -> None:
    """Title, subtitle and source at fixed distances (in inches) from the edges."""
    h = fig.get_figheight()
    fig.text(0.01, 1 - 0.10 / h, title, fontsize=12.5, fontweight="bold", color=INK, va="top")
    fig.text(0.01, 1 - 0.38 / h, subtitle, fontsize=9.5, color=INK_2, va="top")
    fig.text(0.01, 0.08 / h, source, fontsize=8, color=MUTED, va="bottom")


def legend_anchor(fig) -> tuple[float, float]:
    """Upper-left corner of a figure legend placed under the subtitle."""
    return (0.005, 1 - 0.62 / fig.get_figheight())


def year_axis(ax, step: int = 2) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator(step))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def chart_chain(ea: pd.DataFrame) -> pd.DataFrame:
    """4 chart 1: Euribor, the ECB deposit rate and the two euro-area lending
    rates, January 2003 to the latest month, euro-area recessions shaded."""
    order = ["dfr", "euribor3m", "L_NFC", "L_HH"]
    data = ea.loc[SAMPLE_START:, order].dropna(how="all")
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.06, right=0.98, top=1 - 1.05 / 5.6, bottom=0.14)
    # 4 chart 1: recession shading (quarter after the peak through the trough quarter)
    for peak, trough in RECESSIONS:
        ax.axvspan(pd.Period(peak, "Q").end_time, pd.Period(trough, "Q").end_time,
                   color=RECESSION, lw=0, zorder=0)
    for var in order:
        s = data[var].dropna()
        ax.plot(s.index, s.to_numpy(), color=COLORS[var], label=LABELS[var], zorder=3)
    ax.axhline(0, color=AXIS, lw=0.8, zorder=1)
    ax.set_ylabel("% per year")
    ax.set_xlim(data.index[0], data.index[-1])
    year_axis(ax)
    handles = [Line2D([], [], color=COLORS[v], lw=LINE_WIDTH) for v in order]
    handles.append(Patch(color=RECESSION, lw=0))
    fig.legend(handles, [LABELS[v] for v in order] + ["Recession (CEPR-EABCN)"],
               loc="upper left", bbox_to_anchor=legend_anchor(fig), ncol=5, handlelength=1.6)
    last = data.index[-1].strftime("%b %Y")
    title_block(fig, "Chart 1. From the ECB rate to loan rates",
                f"Euro area, monthly averages, January 2003 to {last}",
                "Source: ECB Data Portal (FM, MIR). Lending rates: composite cost-of-borrowing "
                "indicators for new loans.\nShading: euro-area recessions dated by the CEPR-EABCN "
                "committee (2008Q1-2009Q2, 2011Q3-2013Q1, 2019Q4-2020Q2), peak quarter excluded.")
    fig.savefig(FIGURES / "chart1_chain.png")
    plt.close(fig)
    return data


def dispersion(table: pd.DataFrame, countries: list[str] | None = None) -> pd.DataFrame:
    """4 chart 2: L-bar_t, the plain average across the countries with data in
    month t (U2 left out), and Disp_t, their sample standard deviation
    (divides by N_t - 1)."""
    t = table.drop(columns=EURO_AREA, errors="ignore")
    if countries is not None:
        t = t[countries]
    return pd.DataFrame({"N": t.count(axis=1), "mean": t.mean(axis=1),
                         "disp": t.std(axis=1, ddof=1)})


def chart_dispersion(clean: pd.DataFrame) -> pd.DataFrame:
    """4 chart 2: for each month, how spread out the countries' lending rates
    are, for all members and for the fixed group of the 12 members of 2003."""
    out = {}
    for var in ["L_NFC", "L_HH"]:
        table = wide(clean, var).loc[SAMPLE_START:]
        all_members = dispersion(table)
        fixed = dispersion(table, MEMBERS_2003)
        out[var] = pd.DataFrame({
            f"N_{var}": all_members["N"], f"mean_{var}": all_members["mean"],
            f"disp_{var}": all_members["disp"],
            f"N_{var}_members2003": fixed["N"], f"disp_{var}_members2003": fixed["disp"],
        })
    table = pd.concat(out.values(), axis=1)
    table.index.name = "month"

    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.06, right=0.98, top=1 - 1.30 / 5.6, bottom=0.11)
    handles, labels = [], []
    for var in ["L_NFC", "L_HH"]:
        for suffix, style, label in [("", "-", "all members"),
                                     ("_members2003", (0, (4, 2.5)), "12 members of 2003")]:
            s = table[f"disp_{var}{suffix}"].dropna()
            (line,) = ax.plot(s.index, s.to_numpy(), color=COLORS[var], linestyle=style)
            handles.append(line)
            labels.append(f"{LABELS[var]}, {label}")
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Standard deviation across countries, pp")
    ax.set_xlim(table.index[0], table.index[-1])
    year_axis(ax)
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=legend_anchor(fig), ncol=2,
               handlelength=2.4, columnspacing=2.5)
    n = table["N_L_NFC"]
    title_block(fig, "Chart 2. How spread out lending rates are across countries",
                f"Euro-area members with data each month (N from {int(n.min())} to {int(n.max())})"
                " and the fixed group of the 12 members of 2003",
                "Source: ECB Data Portal (MIR). Each member counts from the month it adopted the "
                "euro; plain average, every country weighted equally.")
    fig.savefig(FIGURES / "chart2_dispersion.png")
    plt.close(fig)
    return table


def chart_countries(clean: pd.DataFrame) -> None:
    """4 chart 3: one small panel per country, January 2021 to the latest
    month: its company and mortgage rates, with Euribor in grey behind."""
    names = {c: m["name"] for c, m in load_keys()["euro_area_members"].items()}
    nfc = wide(clean, "L_NFC").loc[COUNTRY_PANELS_START:]
    hh = wide(clean, "L_HH").loc[COUNTRY_PANELS_START:]
    r = euro_area(clean)["euribor3m"].loc[COUNTRY_PANELS_START:].dropna()
    with_data = (set(nfc.columns[nfc.notna().any()]) | set(hh.columns[hh.notna().any()]))
    countries = sorted(with_data - {EURO_AREA}, key=lambda c: names[c])
    ncols = 4
    nrows = math.ceil(len(countries) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(11, 2.0 * nrows + 1.4),
                             sharex=True, sharey=True)
    fig.subplots_adjust(left=0.05, right=0.99, top=1 - 1.15 / (2.0 * nrows + 1.4),
                        bottom=0.6 / (2.0 * nrows + 1.4), hspace=0.38, wspace=0.08)
    for ax, c in zip(axes.flat, countries):
        ax.plot(r.index, r.to_numpy(), color=MUTED, lw=1.1, zorder=1)
        for var, table in [("L_NFC", nfc), ("L_HH", hh)]:
            s = table[c].dropna()
            ax.plot(s.index, s.to_numpy(), color=COLORS[var], zorder=3)
        ax.set_title(names[c], fontsize=9.5, fontweight="bold", pad=3)
        ax.axhline(0, color=AXIS, lw=0.8, zorder=1)
        year_axis(ax, step=1)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("'%y"))
        ax.tick_params(labelsize=8)
    for ax in axes.flat[len(countries):]:
        ax.set_visible(False)
    for i in range(len(countries) - ncols, len(countries)):
        axes.flat[i].xaxis.set_tick_params(labelbottom=True)
    handles = [Line2D([], [], color=COLORS["L_NFC"], lw=LINE_WIDTH),
               Line2D([], [], color=COLORS["L_HH"], lw=LINE_WIDTH),
               Line2D([], [], color=MUTED, lw=1.1)]
    last = max(nfc.dropna(how="all").index[-1], r.index[-1]).strftime("%b %Y")
    height = 2.0 * nrows + 1.4
    fig.text(0.01, 1 - 0.12 / height, "Chart 3. The 2022-23 hikes, country by country",
             fontsize=12.5, fontweight="bold", va="top")
    fig.text(0.01, 1 - 0.42 / height, f"Lending rates on new loans, % per year, "
             f"January 2021 to {last}; each country from the month it adopted the euro",
             fontsize=9.5, color=INK_2, va="top")
    fig.legend(handles, [LABELS["L_NFC"], LABELS["L_HH"], "3-month Euribor (euro area)"],
               loc="upper left", bbox_to_anchor=(0.005, 1 - 0.62 / height), ncol=3,
               handlelength=1.6)
    fig.text(0.01, 0.12 / height, "Source: ECB Data Portal (FM, MIR).", fontsize=8,
             color=MUTED, va="bottom")
    fig.savefig(FIGURES / "chart3_countries.png")
    plt.close(fig)


def main() -> None:
    apply_style()
    FIGURES.mkdir(exist_ok=True)
    TABLES.mkdir(exist_ok=True)
    clean = load_clean()
    ea = euro_area(clean)

    chain = chart_chain(ea)
    chain.to_csv(TABLES / "chart1_chain.csv", float_format="%.4f", date_format="%Y-%m")
    disp = chart_dispersion(clean)
    disp.to_csv(TABLES / "dispersion.csv", float_format="%.4f", date_format="%Y-%m")
    chart_countries(clean)

    # Plain summary of the numbers behind the charts.
    print("4 chart 1: latest values (%):")
    for var in ["dfr", "euribor3m", "L_NFC", "L_HH"]:
        s = chain[var].dropna()
        print(f"  {LABELS[var]:28s} {s.index[-1]:%Y-%m}  {s.iloc[-1]:6.2f}")
    print("4 chart 2: dispersion across countries, pp (all members / 12 members of 2003):")
    for var in ["L_NFC", "L_HH"]:
        d, f = disp[f"disp_{var}"], disp[f"disp_{var}_members2003"]
        print(f"  {LABELS[var]:20s} max {d.max():.2f} ({d.idxmax():%Y-%m})"
              f" / {f.max():.2f} ({f.idxmax():%Y-%m});"
              f" latest {d.dropna().iloc[-1]:.2f} / {f.dropna().iloc[-1]:.2f}"
              f" ({d.dropna().index[-1]:%Y-%m}, N={int(disp[f'N_{var}'].dropna().iloc[-1])})")
    print("Wrote figures/chart1_chain.png, figures/chart2_dispersion.png, "
          "figures/chart3_countries.png, tables/chart1_chain.csv, tables/dispersion.csv")


if __name__ == "__main__":
    main()
