"""3 tests/: no duplicate (series, month) rows; gaps reported per country;
values in a plausible range. Run after `make refresh`."""
import pandas as pd
import pytest

from ecbdata.build import CLEAN_PATH, EURO_AREA, load_clean
from ecbdata.fetch import RAW_DIR, load_keys, read_raw

pytestmark = pytest.mark.skipif(not CLEAN_PATH.exists(), reason="no data: run `make refresh`")

# 3 "interest rates between -1% and 15%, inflation between -2% and 12%"
RANGES = {"L_NFC": (-1, 15), "L_HH": (-1, 15), "euribor3m": (-1, 15), "dfr": (-1, 15),
          "inflation": (-2, 12)}


@pytest.fixture(scope="module")
def clean():
    return load_clean()


def test_no_duplicate_series_month_clean(clean):
    # 3 test: a series is (country, variable) in the clean table
    dup = clean[clean.duplicated(["country", "variable", "month"], keep=False)]
    assert dup.empty, f"duplicate (series, month) rows:\n{dup}"


def test_no_duplicate_series_period_raw():
    # 3 test: the same check on the raw downloads, series = KEY
    for name in load_keys()["series"]:
        if not (RAW_DIR / f"{name}.csv").exists():
            pytest.skip("raw files missing")
        raw = read_raw(name)
        dup = raw[raw.duplicated(["KEY", "TIME_PERIOD"], keep=False)]
        assert dup.empty, f"{name}: duplicate (KEY, TIME_PERIOD) rows:\n{dup}"


def gap_report(clean: pd.DataFrame) -> pd.DataFrame:
    """3 test: for each country and variable, the months missing between its
    first and last month."""
    rows = []
    for (country, variable), g in clean.groupby(["country", "variable"]):
        months = pd.DatetimeIndex(g["month"])
        expected = pd.date_range(months.min(), months.max(), freq="MS")
        missing = expected.difference(months)
        rows.append({"country": country, "variable": variable,
                     "first": months.min().strftime("%Y-%m"),
                     "last": months.max().strftime("%Y-%m"),
                     "months": len(months), "gaps": len(missing),
                     "missing": " ".join(missing.strftime("%Y-%m"))})
    return pd.DataFrame(rows)


def test_gaps_reported_per_country(clean, capsys):
    report = gap_report(clean)
    with capsys.disabled():
        print("\n3 gap report (months missing between each series' first and last month):")
        print(report.drop(columns="missing").to_string(index=False))
        with_gaps = report[report["gaps"] > 0]
        print("series with gaps:", "none" if with_gaps.empty else "")
        if not with_gaps.empty:
            print(with_gaps.to_string(index=False))
    # The euro-area series feed the VAR, which needs consecutive months.
    ea = report[(report["country"] == EURO_AREA)]
    assert (ea["gaps"] == 0).all(), f"gaps in euro-area series:\n{ea[ea['gaps'] > 0]}"


@pytest.mark.parametrize("variable", sorted(RANGES))
def test_plausible_range(clean, variable):
    lo, hi = RANGES[variable]
    v = clean[clean["variable"] == variable]
    assert len(v) > 0, f"no rows for {variable}"
    out = v[(v["value"] < lo) | (v["value"] > hi)]
    assert out.empty, f"{variable} outside [{lo}, {hi}]:\n{out}"
