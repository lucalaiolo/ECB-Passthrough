"""5 Pass-through in 2022-23, with arithmetic.

Country by country, separately for company loans and mortgages:
PT_i = (L_{i,t1} - L_{i,t0}) / (r_{t1} - r_{t0}), the same 6 months after the
Euribor peak, and the speed of the rise. Baseline t0 by rule; robustness with
t0 = June 2022.

Tables (tables/):
  hiking_cycle_dates.csv                    t0, t1, t1+6 and Euribor at each
  hiking_cycle_nfc.csv, hiking_cycle_hh.csv baseline t0
  hiking_cycle_nfc_t0_2022-06.csv, hiking_cycle_hh_t0_2022-06.csv  robustness

Usage: python -m analysis.hiking_cycle
"""
from __future__ import annotations

import pandas as pd

from ecbdata.build import EURO_AREA, euro_area, load_clean, wide
from ecbdata.fetch import ROOT, load_keys

TABLES = ROOT / "tables"
ROBUST_T0 = pd.Timestamp("2022-06-01")  # 5 robustness: the last month before the first ECB hike
PRODUCTS = {"nfc": ("L_NFC", "Loans to companies"), "hh": ("L_HH", "Mortgages")}


def months_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return (end.to_period("M") - start.to_period("M")).n


def pick_dates(r: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp]:
    # 5 t0: the month with the lowest 3-month Euribor between January 2021 and June 2022
    t0 = r.loc["2021-01-01":"2022-06-01"].idxmin()
    # 5 t1: the month with the highest 3-month Euribor in 2023-2024
    t1 = r.loc["2023-01-01":"2024-12-01"].idxmax()
    return t0, t1


def pass_through(L: pd.DataFrame, r: pd.Series, t0: pd.Timestamp, t1: pd.Timestamp,
                 names: dict[str, str]) -> pd.DataFrame:
    """5 PT_i at t1 and at t1 + 6, and speed, for every country with a value at t0."""
    t6 = t1 + pd.DateOffset(months=6)
    # 5 how much Euribor rose: delta r = r_{t1} - r_{t0}
    dr = r[t1] - r[t0]
    rows = []
    for c in L.columns.drop(EURO_AREA, errors="ignore"):
        s = L[c]
        if pd.isna(s.get(t0)):
            continue  # not a member (or no data) at t0
        # 5 how much country i's lending rate rose: delta L_i = L_{i,t1} - L_{i,t0}
        dL = s[t1] - s[t0]
        # 5 the rise 6 months after the Euribor peak, divided by the same delta r
        dL6 = s.get(t6) - s[t0]
        # 5 speed: total rise = highest rate between t0 and t1+6 minus its value
        # at t0; months after t0 until the rate first covered half of it
        window = s.loc[t0:t6]
        total = window.max() - s[t0]
        if total > 0:
            t_half = window.index[(window - s[t0] >= total / 2).to_numpy()][0]
            speed = months_between(t0, t_half)
        else:
            t_half, speed = pd.NaT, float("nan")
        rows.append({
            "country": c, "name": names[c],
            "L_t0": s[t0], "L_t1": s[t1], "L_t1+6": s.get(t6),
            "dL": dL, "PT": dL / dr, "dL_t1+6": dL6, "PT_t1+6": dL6 / dr,
            "L_max": window.max(), "month_max": window.idxmax(),
            "total_rise": total, "month_half": t_half, "speed_months": speed,
        })
    table = pd.DataFrame(rows)
    # 5 rank the countries (1 = highest pass-through). delta r is the same for
    # every country, so the ranking by PT_i is the ranking by delta L_i; rank on
    # delta L rounded to 1e-6 so that equal rises (rates have 2 decimals) tie.
    for col, rank in [("dL", "rank_PT"), ("dL_t1+6", "rank_PT_t1+6")]:
        table[rank] = table[col].round(6).rank(ascending=False, method="min").astype("Int64")
    return table.sort_values("rank_PT", ignore_index=True)


def main() -> None:
    TABLES.mkdir(exist_ok=True)
    clean = load_clean()
    names = {c: m["name"] for c, m in load_keys()["euro_area_members"].items()}
    r = euro_area(clean)["euribor3m"]
    t0, t1 = pick_dates(r)
    t6 = t1 + pd.DateOffset(months=6)

    dates = []
    for rule, start in [("baseline", t0), ("robustness", ROBUST_T0)]:
        dates.append({"rule": rule, "t0": start, "t1": t1, "t1+6": t6,
                      "r_t0": r[start], "r_t1": r[t1], "dr": r[t1] - r[start]})
    dates = pd.DataFrame(dates)
    dates.to_csv(TABLES / "hiking_cycle_dates.csv", index=False, float_format="%.4f",
                 date_format="%Y-%m")

    print("5 dates: t0 = lowest 3-month Euribor Jan 2021-Jun 2022, t1 = highest in 2023-2024")
    for d in dates.to_dict("records"):
        print(f"  {d['rule']:10s} t0 {d['t0']:%Y-%m} (r={d['r_t0']:.3f})  "
              f"t1 {d['t1']:%Y-%m} (r={d['r_t1']:.3f})  t1+6 {d['t1+6']:%Y-%m}  "
              f"delta r = {d['dr']:.3f} pp")

    for rule, start in [("baseline", t0), ("robustness", ROBUST_T0)]:
        suffix = "" if rule == "baseline" else f"_t0_{ROBUST_T0:%Y-%m}"
        for product, (var, label) in PRODUCTS.items():
            L = wide(clean, var)
            table = pass_through(L, r, start, t1, names)
            table.to_csv(TABLES / f"hiking_cycle_{product}{suffix}.csv", index=False,
                         float_format="%.4f", date_format="%Y-%m")
            left_out = sorted(set(L.columns) - {EURO_AREA} - set(table["country"]))
            print(f"\n5 {label}, t0 = {start:%Y-%m} ({rule}); "
                  f"{len(table)} countries" + (f"; no value at t0: {', '.join(left_out)}"
                                               if left_out else ""))
            show = table[["rank_PT", "country", "L_t0", "L_t1", "dL", "PT", "PT_t1+6",
                          "rank_PT_t1+6", "total_rise", "speed_months"]]
            print(show.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
