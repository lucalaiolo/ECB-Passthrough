"""3 Pipeline: download every series in keys.yaml and keep the raw files in data/raw/.

The first run downloads each series in full. Later runs (``make refresh``) ask
the API only for observations updated after the last download (API parameter
``updatedAfter``) and merge them in: new and revised observations overwrite old
ones, matched on series key and period.

After downloading, prints per series its title, first and last period with a
value, and number of rows, and stops (non-zero exit) if
- a series comes back empty,
- a euro-area series starts after 2003-01,
- a country wildcard returns a code that is neither U2 nor a euro-area member.

Usage: python -m ecbdata.fetch [--full]
"""
from __future__ import annotations

import argparse
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
KEYS_PATH = Path(__file__).with_name("keys.yaml")
RAW_DIR = ROOT / "data" / "raw"
STATE_PATH = RAW_DIR / "state.json"  # time of the last download, per series
TABLES_DIR = ROOT / "tables"
EURO_AREA_START = "2003-01"  # 3: "The euro-area series should start by January 2003"


class StopPipeline(SystemExit):
    """Raised when a check in §3 fails: the message is printed and make stops."""


def load_keys() -> dict:
    with open(KEYS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def raw_path(name: str) -> Path:
    return RAW_DIR / f"{name}.csv"


def read_raw(name: str) -> pd.DataFrame:
    return pd.read_csv(raw_path(name), dtype=str)


def request_csv(api: str, flow: str, key: str, updated_after: str | None = None,
                retries: int = 4) -> pd.DataFrame | None:
    """One API request. Returns the rows, or None when the API returns no series
    (HTTP 404 "No Series was returned": with updatedAfter, nothing changed)."""
    params = {"format": "csvdata"}
    if updated_after is not None:
        params["updatedAfter"] = updated_after
    for attempt in range(retries + 1):
        try:
            resp = requests.get(f"{api}/{flow}/{key}", params=params, timeout=180)
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)
            continue
        if resp.status_code >= 500 and attempt < retries:
            time.sleep(2 ** attempt)
            continue
        if resp.status_code == 404:
            return None
        resp.raise_for_status()  # any other HTTP error stops here
        if not resp.text.strip():
            return None
        return pd.read_csv(io.StringIO(resp.text), dtype=str)
    raise RuntimeError("unreachable")


def fetch(full: bool = False) -> None:
    cfg = load_keys()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}

    for name, s in cfg["series"].items():
        path = raw_path(name)
        incremental = not full and path.exists() and name in state
        # 3 make refresh: updatedAfter is the time of the last download, taken
        # before the request so that nothing published during it is missed.
        started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        rows = request_csv(cfg["api"], s["flow"], s["key"],
                           updated_after=state[name] if incremental else None)
        if not incremental:
            # 3 "Stops if a series comes back empty."
            if rows is None or rows.empty:
                raise StopPipeline(f"STOP: {s['flow']}.{s['key']} ({name}) came back empty.")
            rows.to_csv(path, index=False)
            status = f"downloaded {len(rows)} rows"
        elif rows is None or rows.empty:
            status = "unchanged since last download"
        else:
            # 3 make refresh: new and revised observations overwrite old ones,
            # matched on series (KEY) and period (TIME_PERIOD).
            old = read_raw(name)
            merged = (pd.concat([old, rows], ignore_index=True)
                      .drop_duplicates(subset=["KEY", "TIME_PERIOD"], keep="last")
                      .sort_values(["KEY", "TIME_PERIOD"]))
            merged.to_csv(path, index=False)
            status = f"{len(rows)} new or revised rows merged"
        state[name] = started
        STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
        print(f"{name:16s} {s['flow']}.{s['key']}: {status}")

    summary = summarise(cfg)
    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print("\n" + summary.to_string(index=False))
    TABLES_DIR.mkdir(exist_ok=True)
    summary.to_csv(TABLES_DIR / "data_series.csv", index=False)
    check(summary, cfg)


def summarise(cfg: dict) -> pd.DataFrame:
    """3 "print its title, first month, last month and number of rows", per
    series key (one key per country for the wildcards). first/last are the
    first and last periods with a value; missing counts rows without one."""
    out = []
    for name, s in cfg["series"].items():
        raw = read_raw(name)
        value = pd.to_numeric(raw["OBS_VALUE"], errors="coerce")
        for key, g in raw.assign(value=value).groupby("KEY", sort=True):
            ok = g[g["value"].notna()]
            out.append({
                "name": name,
                "key": key,
                "country": key.split(".")[2],
                "title": g["TITLE"].iloc[0],
                "first": ok["TIME_PERIOD"].min() if len(ok) else None,
                "last": ok["TIME_PERIOD"].max() if len(ok) else None,
                "rows": len(g),
                "missing": int(g["value"].isna().sum()),
            })
    return pd.DataFrame(out)


def check(summary: pd.DataFrame, cfg: dict) -> None:
    problems = []
    for name, s in cfg["series"].items():
        rows = summary[summary["name"] == name]
        # 3 stop: a series with no values at all is empty.
        if rows["first"].isna().all():
            problems.append(f"{name}: no values (empty series)")
            continue
        # 3 stop: a euro-area series must start by January 2003.
        if s["scope"] == "euro_area":
            first = rows["first"].min()[:7]
            if first > EURO_AREA_START:
                problems.append(f"{name}: first month {first} is after {EURO_AREA_START}")
        # 3 stop: every country code must be U2 or a euro-area member.
        else:
            unknown = sorted(set(rows["country"]) - set(cfg["euro_area_members"]) - {"U2"})
            if unknown:
                problems.append(f"{name}: country codes not mapped to a euro-area member: {unknown}")
    if problems:
        raise StopPipeline("STOP:\n  " + "\n  ".join(problems))
    print("\n3 checks passed: no empty series, euro-area series start by "
          f"{EURO_AREA_START}, every country code is U2 or a euro-area member.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--full", action="store_true",
                        help="re-download every series in full instead of only updates")
    fetch(full=parser.parse_args().full)


if __name__ == "__main__":
    main()
