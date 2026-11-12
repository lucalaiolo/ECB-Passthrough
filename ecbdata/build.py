"""3 Pipeline: build one clean table (country, month, variable, value) from
data/raw/ and save it as Parquet in data/clean/.

- Monthly frequency. The deposit rate has one row per change: it is
  forward-filled to a daily calendar, then averaged by month.
- Country filter: only euro-area members, each from the month it adopted the
  euro. The euro-area aggregate U2 in the country wildcards is dropped; the
  dedicated euro-area series are stored with country "U2".

Variables: L_NFC, L_HH (lending rates), euribor3m, dfr, inflation; all in %.

Usage: python -m ecbdata.build
"""
from __future__ import annotations

import json

import pandas as pd

from ecbdata.fetch import ROOT, STATE_PATH, StopPipeline, load_keys, read_raw

CLEAN_PATH = ROOT / "data" / "clean" / "rates.parquet"
EURO_AREA = "U2"


def to_month(period: pd.Series) -> pd.Series:
    return pd.to_datetime(period, format="%Y-%m")


def values(raw: pd.DataFrame) -> pd.DataFrame:
    """Rows with a value, as (country, period, value)."""
    out = pd.DataFrame({
        "country": raw["KEY"].str.split(".").str[2],
        "period": raw["TIME_PERIOD"],
        "value": pd.to_numeric(raw["OBS_VALUE"], errors="coerce"),
    })
    return out.dropna(subset=["value"])


def deposit_rate_monthly(changes: pd.DataFrame, downloaded: str) -> pd.DataFrame:
    """3 "Forward-fill it to a daily calendar, then take the monthly average."

    The calendar runs from the first change to the end of the last full month
    before the download: a change in that month would already be in the data.
    """
    rate = changes.set_index(pd.to_datetime(changes["period"]))["value"].sort_index()
    last_full_month = pd.Timestamp(downloaded).tz_convert(None).to_period("M") - 1
    end = last_full_month.to_timestamp(how="end").normalize()
    daily = rate.reindex(pd.date_range(rate.index.min(), end, freq="D")).ffill()
    monthly = daily.resample("MS").mean()
    return pd.DataFrame({"country": EURO_AREA, "month": monthly.index, "value": monthly.to_numpy()})


def build() -> pd.DataFrame:
    cfg = load_keys()
    state = json.loads(STATE_PATH.read_text())
    members = cfg["euro_area_members"]
    parts = []
    for name, s in cfg["series"].items():
        obs = values(read_raw(name))
        if s.get("changes_only"):
            # 3 deposit rate: daily forward-fill, then monthly average
            df = deposit_rate_monthly(obs, state[name])
        elif s["scope"] == "euro_area":
            df = pd.DataFrame({"country": EURO_AREA, "month": to_month(obs["period"]),
                               "value": obs["value"]})
        else:
            # 3 country filter: drop U2, stop on unknown codes, keep each
            # member from the month it adopted the euro
            obs = obs[obs["country"] != EURO_AREA]
            unknown = sorted(set(obs["country"]) - set(members))
            if unknown:
                raise StopPipeline(f"STOP: {name}: country codes not mapped to a "
                                   f"euro-area member: {unknown}")
            month = to_month(obs["period"])
            adopted = to_month(obs["country"].map({c: m["adopted"] for c, m in members.items()}))
            keep = month >= adopted
            df = pd.DataFrame({"country": obs["country"][keep], "month": month[keep],
                               "value": obs["value"][keep]})
        parts.append(df.assign(variable=s["variable"]))

    clean = (pd.concat(parts, ignore_index=True)[["country", "month", "variable", "value"]]
             .sort_values(["variable", "country", "month"], ignore_index=True))
    clean["country"] = clean["country"].astype(str)
    clean["variable"] = clean["variable"].astype(str)
    clean["month"] = clean["month"].astype("datetime64[ns]")
    clean["value"] = clean["value"].astype(float)
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(CLEAN_PATH, index=False)
    return clean


def load_clean() -> pd.DataFrame:
    return pd.read_parquet(CLEAN_PATH)


def wide(clean: pd.DataFrame, variable: str) -> pd.DataFrame:
    """One variable as a table: one row per month (no month skipped), one
    column per country."""
    table = clean[clean["variable"] == variable].pivot(index="month", columns="country",
                                                      values="value")
    return table.asfreq("MS")


def euro_area(clean: pd.DataFrame) -> pd.DataFrame:
    """The euro-area (U2) series as columns, one row per month."""
    ea = clean[clean["country"] == EURO_AREA].pivot(index="month", columns="variable",
                                                   values="value")
    return ea.asfreq("MS")


def main() -> None:
    clean = build()
    summary = (clean.groupby(["variable", "country"])["month"]
               .agg(first="min", last="max", months="size").reset_index())
    summary["first"] = summary["first"].dt.strftime("%Y-%m")
    summary["last"] = summary["last"].dt.strftime("%Y-%m")
    print(f"Wrote {CLEAN_PATH.relative_to(ROOT)}: {len(clean)} rows")
    for variable, g in summary.groupby("variable"):
        ea = g[g["country"] == EURO_AREA]
        cty = g[g["country"] != EURO_AREA]
        line = f"  {variable:10s}"
        if len(ea):
            line += f" euro area {ea['first'].iloc[0]} to {ea['last'].iloc[0]}"
        if len(cty):
            line += (f" {len(cty)} countries, first {cty['first'].min()},"
                     f" last {cty['last'].max()}")
        print(line)


if __name__ == "__main__":
    main()
