"""6 The VAR: how lending rates react over time to a Euribor move.

y_t = (pi_t, d r_t, d L^NFC_t, d L^HH_t): euro-area inflation and the monthly
changes of 3-month Euribor and of the two euro-area lending rates, over the
months in which all four exist.

  6.4  ADF decision rules                 -> tables/var_adf.csv
  6.5  lag choice (BIC)                   -> tables/var_lag_order.csv
  6.6  stability and whiteness; if whiteness rejects, the AIC lag as well
                                          -> tables/var_checks.csv
  6.7-6.8  Cholesky impulse responses and PT(h)
  6.9  residual bootstrap: 90% bands      -> tables/var_pt_<spec>.csv, figures/var_pt_<spec>.png,
                                             tables/var_irf_<spec>.csv, figures/var_cirf_<spec>.png
       cross-check with cum_errband_mc    -> tables/var_crosscheck_<spec>.csv
(<spec> is "bic", and "aic" when that model is fitted too.)

Usage: python -m analysis.var
"""
from __future__ import annotations

from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from statsmodels.tsa.api import VAR  # noqa: E402
from statsmodels.tsa.stattools import adfuller  # noqa: E402

from analysis.charts import (AXIS, COLORS, INK_2, LABELS, LINE_WIDTH,  # noqa: E402
                             apply_style, legend_anchor, title_block)
from ecbdata.build import euro_area, load_clean  # noqa: E402
from ecbdata.fetch import ROOT, StopPipeline  # noqa: E402

FIGURES = ROOT / "figures"
TABLES = ROOT / "tables"

COLUMNS = ["pi", "d_r", "d_L_NFC", "d_L_HH"]  # 6.3 order = 6.7 Cholesky order
PI, R, NFC, HH = 0, 1, 2, 3  # 0-based positions: Euribor is "variable 2"
HORIZON = 24  # 6.1 "in that month, and in each of the following 24 months"
MAX_LAGS = 12  # 6.5
WHITENESS_LAGS = 24  # 6.6
SIGNIF = 0.05  # 6.4 and 6.6: the 5% level
DRAWS = 1000  # 6.9 step 4: B = 1,000
SEED = 2003  # 6.9 step 4: fixed random seed
BAND = (5, 95)  # 6.9 step 5: 90% band
BAND_WARN_SHARE = 0.05  # 6.9: band not meaningful where more than 5% of draws have CIRF*_2(h) <= 0


# ---------------------------------------------------------------- 6.3 the data
def var_levels(clean: pd.DataFrame) -> pd.DataFrame:
    """Levels of pi, r, L_NFC, L_HH (euro area) over the months in which all four exist."""
    ea = euro_area(clean)
    levels = pd.DataFrame({"pi": ea["inflation"], "r": ea["euribor3m"],
                           "L_NFC": ea["L_NFC"], "L_HH": ea["L_HH"]}).dropna()
    months = pd.date_range(levels.index[0], levels.index[-1], freq="MS")
    if len(months) != len(levels):
        raise StopPipeline("6.3: the months in which all four series exist are not consecutive.")
    return levels.asfreq("MS")


def var_data(levels: pd.DataFrame) -> pd.DataFrame:
    """6.3 y_t = (pi_t, d r_t, d L^NFC_t, d L^HH_t), in this order."""
    y = pd.DataFrame({"pi": levels["pi"], "d_r": levels["r"].diff(),
                      "d_L_NFC": levels["L_NFC"].diff(), "d_L_HH": levels["L_HH"].diff()})
    return y.dropna()[COLUMNS].asfreq("MS")


# ---------------------------------------------------------------- 6.4 ADF tests
def adf(w: pd.Series) -> dict:
    res = adfuller(w, regression="c", autolag="AIC", result_object=True)
    return {"adf_stat": res.statistic, "pvalue": res.pvalue, "lags": res.lags,
            "nobs": res.nobs, "crit_5pct": res.critical_values["5%"]}


def adf_rules(levels: pd.DataFrame, y: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """6.4 decision rules at the 5% level. Interest rates: test the level; if it
    can't reject rho = 0, use the monthly change, and check that the test rejects
    for the change. Inflation enters as it is; its p-value is reported, and a
    non-rejection is flagged for 6.10. Returns the table and that flag."""
    rows = []
    for name in ["r", "L_NFC", "L_HH"]:
        level, change = adf(levels[name]), adf(levels[name].diff().dropna())
        if level["pvalue"] < SIGNIF:
            raise StopPipeline(
                f"6.4: the ADF test rejects rho = 0 for the level of {name} "
                f"(p = {level['pvalue']:.3f}). The rule in 6.4 then doesn't call for the "
                "monthly change, but the VAR of 6.3 is specified in changes: decide before "
                "continuing.")
        if change["pvalue"] >= SIGNIF:
            raise StopPipeline(f"6.4: the ADF test can't reject rho = 0 for the monthly change "
                               f"of {name} (p = {change['pvalue']:.3f}).")
        rows.append({"series": name, "form": "level", **level, "decision": "use the change"})
        rows.append({"series": name, "form": "change", **change, "decision": "enters the VAR"})
    pi = adf(y["pi"])
    pi_unit_root = pi["pvalue"] >= SIGNIF
    rows.append({"series": "pi", "form": "as it is", **pi,
                 "decision": "enters as it is" + ("; can't reject: list in 6.10"
                                                  if pi_unit_root else "")})
    table = pd.DataFrame(rows)
    table.insert(table.columns.get_loc("crit_5pct") + 1, "rejects_5pct",
                 table["pvalue"] < SIGNIF)
    return table, pi_unit_root


# ---------------------------------------------------------------- 6.5 lag choice
def lag_choice(y: pd.DataFrame) -> tuple[int, int, pd.DataFrame]:
    """6.5 BIC(p) for p = 1..12 on the same months, smallest wins. statsmodels
    also lists p = 0; 6.5 compares p >= 1, so p = 0 is never picked."""
    sel = VAR(y).select_order(maxlags=MAX_LAGS)
    ics = pd.DataFrame({k: list(v) for k, v in sel.ics.items()})[["aic", "bic", "hqic", "fpe"]]
    ics.index.name = "p"
    p_bic = int(sel.bic) if sel.bic >= 1 else int(ics["bic"].loc[1:].idxmin())
    # 6.6: the AIC lag, used only if the whiteness test rejects
    p_aic = int(sel.aic) if sel.aic >= 1 else int(ics["aic"].loc[1:].idxmin())
    return p_bic, p_aic, ics


# ---------------------------------------------------------------- 6.6 checks
def companion(A: np.ndarray) -> np.ndarray:
    """6.6 the companion matrix built from A_1..A_p."""
    p, K, _ = A.shape
    return np.vstack([np.hstack(list(A)), np.eye(K * (p - 1), K * p)])


def checks(res) -> dict:
    """6.6 stability (all companion eigenvalues inside the unit circle) and
    whiteness (portmanteau test on 24 lags of the residuals)."""
    moduli = np.abs(np.linalg.eigvals(companion(res.coefs)))
    w = res.test_whiteness(nlags=WHITENESS_LAGS)
    return {"p": res.k_ar, "nobs": res.nobs,
            "sample": f"{res.dates[res.k_ar]:%Y-%m} to {res.dates[-1]:%Y-%m}",
            "is_stable": bool(res.is_stable()), "max_eigenvalue_modulus": moduli.max(),
            "whiteness_lags": WHITENESS_LAGS, "whiteness_stat": w.test_statistic,
            "whiteness_df": w.df, "whiteness_crit_5pct": w.crit_value,
            "whiteness_pvalue": w.pvalue, "whiteness_rejects_5pct": bool(w.pvalue < SIGNIF)}


# ---------------------------------------------------------------- 6.7-6.8 responses
def impulse_responses(A, B0, horizon: int) -> np.ndarray:
    """6.8 responses of every variable to every Cholesky shock, h = 0..horizon.

    A: the lag matrices A_1..A_p (a sequence of K x K arrays, or one array of
    shape (p, K, K)); B0: the K x K matrix with Sigma_u = B0 B0'.
    Returns an array of shape (horizon + 1, K, K) whose [h, k, l] entry is the
    response of variable k, h months after a unit shock l. Month 0 is B0 (the
    shock's column); then y_{t+h} = A_1 y_{t+h-1} + ... + A_p y_{t+h-p}, with
    the months before t counting as zero and the constant dropped.
    """
    A = np.asarray(A, dtype=float)
    if A.ndim == 2:
        A = A[np.newaxis]
    p = A.shape[0]
    B0 = np.asarray(B0, dtype=float)
    out = np.zeros((horizon + 1, *B0.shape))
    out[0] = B0
    for h in range(1, horizon + 1):
        for j in range(1, min(h, p) + 1):
            out[h] += A[j - 1] @ out[h - j]
    return out


def cumulative(irf: np.ndarray) -> np.ndarray:
    """6.8 CIRF(h) = sum of the responses from month 0 to h."""
    return irf.cumsum(axis=-3)


def pass_through(cum: np.ndarray, rate: int = R, loans: tuple[int, ...] = (NFC, HH),
                 shock: int | None = None) -> tuple[np.ndarray, ...]:
    """6.8 PT(h) = CIRF_loan(h) / CIRF_rate(h), responses to the rate's shock.
    Works on one set of responses (h, k, l) or on a stack of draws (b, h, k, l)."""
    shock = rate if shock is None else shock
    with np.errstate(divide="ignore", invalid="ignore"):
        return tuple(cum[..., k, shock] / cum[..., rate, shock] for k in loans)


# ---------------------------------------------------------------- 6.9 bootstrap
@dataclass
class Bootstrap:
    cum: np.ndarray  # (draws, H+1, K): cumulative responses to the Euribor shock, not rescaled
    b22: np.ndarray  # (draws,): each draw's own b*_22
    pt_nfc: np.ndarray  # (draws, H+1)
    pt_hh: np.ndarray  # (draws, H+1)


def residual_bootstrap(res, y: np.ndarray, draws: int = DRAWS, seed: int = SEED,
                       horizon: int = HORIZON) -> Bootstrap:
    """6.9 residual bootstrap of PT(h), computed inside every draw."""
    # 6.9 step 1: keep c-hat, A-hat_1..A-hat_p and the residuals u-hat_t
    # (one row of K numbers per month; they average zero).
    p, c, A = res.k_ar, np.asarray(res.intercept), np.asarray(res.coefs)
    U = np.asarray(res.resid)
    T, K = y.shape
    rng = np.random.default_rng(seed)

    # 6.9 step 2: fake histories of the same length as the real one. Copy the
    # first p real months, then y*_t = c + A_1 y*_{t-1} + ... + A_p y*_{t-p} + u*_t,
    # u*_t one residual row drawn at random with replacement: whole rows, so the
    # four surprises of a month stay together. All draws are built at once.
    rows = rng.integers(0, len(U), size=(draws, T - p))
    ystar = np.empty((draws, T, K))
    ystar[:, :p] = y[:p]
    for t in range(p, T):
        ystar[:, t] = c + U[rows[:, t - p]]
        for j in range(1, p + 1):
            ystar[:, t] += ystar[:, t - j] @ A[j - 1].T

    # 6.9 step 3: fit a VAR with the same p to each fake history; from its own
    # Sigma*_u, its own B*_0 (Cholesky), cumulative responses and PT*(h).
    # 6.9 step 4: store each draw's two PT curves and its cumulative responses.
    cum = np.empty((draws, horizon + 1, K))
    b22 = np.empty(draws)
    pt_nfc = np.empty((draws, horizon + 1))
    pt_hh = np.empty((draws, horizon + 1))
    for b in range(draws):
        fit = VAR(ystar[b]).fit(p)
        B0 = np.linalg.cholesky(fit.sigma_u)
        cum_b = cumulative(impulse_responses(fit.coefs, B0, horizon))
        cum[b] = cum_b[:, :, R]
        b22[b] = B0[R, R]
        pt_nfc[b], pt_hh[b] = pass_through(cum_b)
    return Bootstrap(cum=cum, b22=b22, pt_nfc=pt_nfc, pt_hh=pt_hh)


def band(draws: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """6.9 step 5: the 5th and 95th percentiles across draws, at each h."""
    lo, hi = np.percentile(draws, BAND, axis=0)
    return lo, hi


def crosscheck(res, boot: Bootstrap, horizon: int = HORIZON, seed: int = SEED,
               draws: int = DRAWS) -> pd.DataFrame:
    """6.9 cross-check: 90% bands of each cumulative response to the Euribor
    shock (not rescaled) from cum_errband_mc (normal errors) and from the loop."""
    mc = res.irf(horizon).cum_errband_mc(orth=True, repl=draws, signif=0.10,
                                         rng=np.random.default_rng(seed))
    lo, hi = band(boot.cum)
    rows = []
    for k, name in enumerate(COLUMNS):
        for h in range(horizon + 1):
            rows.append({"variable": name, "h": h,
                         "loop_p05": lo[h, k], "loop_p95": hi[h, k],
                         "mc_p05": mc.lower[h, k, R], "mc_p95": mc.upper[h, k, R]})
    return pd.DataFrame(rows)


def crosscheck_gaps(table: pd.DataFrame) -> pd.DataFrame:
    """Per variable: the loop's band width over the MC band width (range over h)
    and the largest shift of the band midpoint, in MC band widths. Responses
    fixed at zero (inflation at h = 0) are left out."""
    t = table.copy()
    t["mc_width"] = t["mc_p95"] - t["mc_p05"]
    t = t[t["mc_width"] > 1e-12]
    t["width_ratio"] = (t["loop_p95"] - t["loop_p05"]) / t["mc_width"]
    t["mid_shift"] = ((t["loop_p95"] + t["loop_p05"]) - (t["mc_p95"] + t["mc_p05"])).abs() \
        / (2 * t["mc_width"])
    return t.groupby("variable", sort=False).agg(
        width_ratio_min=("width_ratio", "min"), width_ratio_max=("width_ratio", "max"),
        mid_shift_max=("mid_shift", "max"))


# ---------------------------------------------------------------- one model, start to end
@dataclass
class SpecResult:
    spec: str
    res: object
    checks: dict
    pt: pd.DataFrame
    responses: pd.DataFrame
    boot: Bootstrap
    crosscheck: pd.DataFrame
    nonpositive_draws: int
    warn_horizons: list[int]


def run_spec(spec: str, y: pd.DataFrame, p: int) -> SpecResult:
    res = VAR(y).fit(p)
    chk = checks(res)  # 6.6

    # 6.8 point estimate from statsmodels: Cholesky responses in the order of 6.3
    irf = res.irf(HORIZON)
    cum = irf.orth_cum_effects
    b22 = irf.orth_irfs[0, R, R]
    pt_nfc = cum[:, NFC, R] / cum[:, R, R]
    pt_hh = cum[:, HH, R] / cum[:, R, R]
    # The impulse-response function of 6.8 must reproduce statsmodels exactly.
    own = impulse_responses(res.coefs, np.linalg.cholesky(res.sigma_u), HORIZON)
    if not np.allclose(own, irf.orth_irfs, rtol=1e-10, atol=1e-12):
        raise AssertionError("impulse_responses() disagrees with statsmodels orth_irfs")

    # 6.9 bootstrap
    boot = residual_bootstrap(res, y.to_numpy())
    nfc_lo, nfc_hi = band(boot.pt_nfc)
    hh_lo, hh_hi = band(boot.pt_hh)
    # 6.9 "Watch the denominator": draws with CIRF*_2(h) <= 0 at some h <= 24
    nonpos = boot.cum[:, :, R] <= 0
    share = nonpos.mean(axis=0)
    h = np.arange(HORIZON + 1)
    pt = pd.DataFrame({"h": h, "PT_NFC": pt_nfc, "PT_NFC_p05": nfc_lo, "PT_NFC_p95": nfc_hi,
                       "PT_HH": pt_hh, "PT_HH_p05": hh_lo, "PT_HH_p95": hh_hi,
                       "share_draws_cirf_r_le0": share,
                       "band_meaningful": share <= BAND_WARN_SHARE})

    # 6.8 responses to a 1 pp Euribor shock (divided by b22); 6.9 bands of the
    # cumulative responses, each draw divided by its own b*_22
    rescaled = boot.cum / boot.b22[:, None, None]
    lo, hi = band(rescaled)
    responses = pd.DataFrame({"h": h, "IRF_pi": irf.orth_irfs[:, PI, R] / b22})
    for k, name in [(R, "r"), (NFC, "L_NFC"), (HH, "L_HH")]:
        responses[f"IRF_{name}"] = irf.orth_irfs[:, k, R] / b22
        responses[f"CIRF_{name}"] = cum[:, k, R] / b22
        responses[f"CIRF_{name}_p05"] = lo[:, k]
        responses[f"CIRF_{name}_p95"] = hi[:, k]

    return SpecResult(spec=spec, res=res, checks=chk, pt=pt, responses=responses, boot=boot,
                      crosscheck=crosscheck(res, boot),
                      nonpositive_draws=int(nonpos.any(axis=1).sum()),
                      warn_horizons=[int(x) for x in h[share > BAND_WARN_SHARE]])


# ---------------------------------------------------------------- figures
def plot_pt(r: SpecResult, sample: str) -> None:
    """6.8 PT(h), h = 0..24, with the 90% band from 6.9."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.9), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.98, top=1 - 1.20 / 4.9, bottom=0.17, wspace=0.08)
    h = r.pt["h"].to_numpy()
    for ax, var, col in [(axes[0], "L_NFC", "PT_NFC"), (axes[1], "L_HH", "PT_HH")]:
        ax.fill_between(h, r.pt[f"{col}_p05"], r.pt[f"{col}_p95"], color=COLORS[var],
                        alpha=0.15, lw=0)
        ax.plot(h, r.pt[col], color=COLORS[var], marker="o", ms=3.2)
        for x in r.warn_horizons:
            ax.axvspan(x - 0.5, x + 0.5, color=AXIS, alpha=0.35, lw=0)
        ax.axhline(0, color=AXIS, lw=0.8)
        ax.set_title(LABELS[var], pad=4)
        ax.set_xlabel("Months after the shock, h")
        ax.set_xticks(range(0, HORIZON + 1, 3))
        ax.set_xlim(-0.5, HORIZON + 0.5)
    axes[0].set_ylabel("PT(h)")
    handles = [Line2D([], [], color=INK_2, lw=LINE_WIDTH, marker="o", ms=3.2),
               Patch(color=INK_2, alpha=0.15, lw=0)]
    labels = ["Point estimate", f"90% band, residual bootstrap ({DRAWS:,} draws)"]
    if r.warn_horizons:
        handles.append(Patch(color=AXIS, alpha=0.35, lw=0))
        labels.append("> 5% of draws with Euribor's cumulative response <= 0")
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=legend_anchor(fig),
               ncol=len(handles), handlelength=1.8)
    title_block(fig, f"Pass-through of a Euribor shock to lending rates, VAR({r.res.k_ar}), "
                f"lag by {r.spec.upper()}",
                f"PT(h) = cumulative response of the lending rate / cumulative response of "
                f"Euribor; euro area, {sample}",
                "Cholesky order: inflation, change in Euribor, change in company lending rate, "
                "change in mortgage rate. Source: ECB Data Portal (FM, MIR, HICP).")
    fig.savefig(FIGURES / f"var_pt_{r.spec}.png")
    plt.close(fig)


def plot_cirf(r: SpecResult, sample: str) -> None:
    """6.8-6.9 cumulative responses to a 1 pp Euribor shock, with 90% bands."""
    fig, axes = plt.subplots(1, 3, figsize=(10, 4.6), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.98, top=1 - 1.20 / 4.6, bottom=0.17, wspace=0.08)
    h = r.responses["h"].to_numpy()
    for ax, (name, var) in zip(axes, [("r", "euribor3m"), ("L_NFC", "L_NFC"),
                                      ("L_HH", "L_HH")]):
        ax.fill_between(h, r.responses[f"CIRF_{name}_p05"], r.responses[f"CIRF_{name}_p95"],
                        color=COLORS[var], alpha=0.15, lw=0)
        ax.plot(h, r.responses[f"CIRF_{name}"], color=COLORS[var], marker="o", ms=3.2)
        ax.axhline(0, color=AXIS, lw=0.8)
        ax.set_title(LABELS[var], pad=4)
        ax.set_xlabel("Months after the shock, h")
        ax.set_xticks(range(0, HORIZON + 1, 6))
        ax.set_xlim(-0.5, HORIZON + 0.5)
    axes[0].set_ylabel("Cumulative response, pp")
    handles = [Line2D([], [], color=INK_2, lw=LINE_WIDTH, marker="o", ms=3.2),
               Patch(color=INK_2, alpha=0.15, lw=0)]
    fig.legend(handles, ["Point estimate",
                         f"90% band, residual bootstrap ({DRAWS:,} draws, each rescaled by its "
                         "own b*22)"],
               loc="upper left", bbox_to_anchor=legend_anchor(fig), ncol=2, handlelength=1.8)
    title_block(fig, f"Cumulative responses to a 1 pp Euribor shock, VAR({r.res.k_ar}), "
                f"lag by {r.spec.upper()}",
                f"How much each level has moved h months after the shock; euro area, {sample}",
                "Responses divided by b22 so that Euribor rises by 1 pp in month 0. "
                "Source: ECB Data Portal (FM, MIR, HICP).")
    fig.savefig(FIGURES / f"var_cirf_{r.spec}.png")
    plt.close(fig)


# ---------------------------------------------------------------- main
def main() -> None:
    apply_style()
    FIGURES.mkdir(exist_ok=True)
    TABLES.mkdir(exist_ok=True)
    clean = load_clean()

    # 6.3 data
    levels = var_levels(clean)
    y = var_data(levels)
    sample = f"{y.index[0]:%b %Y} to {y.index[-1]:%b %Y}"

    # 6.4 ADF
    adf_table, pi_unit_root = adf_rules(levels, y)
    adf_table.to_csv(TABLES / "var_adf.csv", index=False, float_format="%.4f")

    # 6.5 lag choice
    p_bic, p_aic, ics = lag_choice(y)
    ics.to_csv(TABLES / "var_lag_order.csv", float_format="%.6f")

    # 6.6-6.9 the BIC model; 6.6 if whiteness rejects, the AIC model too
    results = [run_spec("bic", y, p_bic)]
    aic_note = "whiteness not rejected: AIC model not needed"
    if results[0].checks["whiteness_rejects_5pct"]:
        if p_aic != p_bic:
            results.append(run_spec("aic", y, p_aic))
            aic_note = f"whiteness rejected at p = {p_bic}: AIC model (p = {p_aic}) fitted too"
        else:
            aic_note = f"whiteness rejected, but AIC picks the same p = {p_bic}"

    pd.DataFrame([{"spec": r.spec, **r.checks} for r in results]).to_csv(
        TABLES / "var_checks.csv", index=False, float_format="%.6g")
    for r in results:
        r.pt.to_csv(TABLES / f"var_pt_{r.spec}.csv", index=False, float_format="%.4f")
        r.responses.to_csv(TABLES / f"var_irf_{r.spec}.csv", index=False, float_format="%.4f")
        r.crosscheck.to_csv(TABLES / f"var_crosscheck_{r.spec}.csv", index=False,
                            float_format="%.5f")
        plot_pt(r, sample)
        plot_cirf(r, sample)

    # Plain summary of the numbers.
    print(f"6.3 sample: {sample}, {len(y)} months; columns {', '.join(COLUMNS)}")
    print("6.4 ADF (constant, lags by AIC):")
    for row in adf_table.to_dict("records"):
        print(f"  {row['series']:6s} {row['form']:9s} stat {row['adf_stat']:7.3f}  "
              f"p {row['pvalue']:.4f}  lags {row['lags']:2d}  -> {row['decision']}")
    print(f"6.5 BIC picks p = {p_bic} (AIC: p = {p_aic}); values in tables/var_lag_order.csv")
    print(f"6.6 {aic_note}")
    for r in results:
        c = r.checks
        print(f"\n[{r.spec.upper()}] VAR({c['p']}), {c['nobs']} months used ({c['sample']})")
        print(f"  6.6 stable: {c['is_stable']} (largest eigenvalue modulus "
              f"{c['max_eigenvalue_modulus']:.4f}); whiteness, {WHITENESS_LAGS} lags: "
              f"stat {c['whiteness_stat']:.1f}, df {c['whiteness_df']}, "
              f"p {c['whiteness_pvalue']:.4g} -> "
              f"{'rejects' if c['whiteness_rejects_5pct'] else 'does not reject'} at 5%")
        b22 = r.res.irf(HORIZON).orth_irfs[0, R, R]
        print(f"  6.8 b22 (typical Euribor surprise) = {b22:.4f} pp")
        print("  6.8-6.9 PT(h) with 90% bands:")
        print("     h   PT_NFC [  p05,   p95]   PT_HH [  p05,   p95]")
        for hh in [0, 1, 2, 3, 6, 9, 12, 18, 24]:
            row = r.pt.iloc[hh]
            print(f"    {hh:2d}  {row.PT_NFC:6.3f} [{row.PT_NFC_p05:5.3f}, {row.PT_NFC_p95:5.3f}]"
                  f"  {row.PT_HH:6.3f} [{row.PT_HH_p05:5.3f}, {row.PT_HH_p95:5.3f}]")
        print(f"  6.9 draws with Euribor's cumulative response <= 0 at some h <= {HORIZON}: "
              f"{r.nonpositive_draws} of {DRAWS}; horizons where more than 5% of draws do: "
              f"{r.warn_horizons if r.warn_horizons else 'none'}")
        gaps = crosscheck_gaps(r.crosscheck)
        print("  6.9 cross-check vs cum_errband_mc (bands of cumulative responses, not "
              "rescaled): loop width / MC width, and largest midpoint shift in MC widths")
        for name, g in gaps.iterrows():
            print(f"    {name:8s} width ratio {g.width_ratio_min:.2f} to {g.width_ratio_max:.2f};"
                  f" midpoint shift up to {g.mid_shift_max:.2f}")
    if pi_unit_root:
        print("\n6.4/6.10 the ADF test can't reject rho = 0 for inflation "
              f"(p = {adf_table.loc[adf_table['series'] == 'pi', 'pvalue'].iloc[0]:.3f}): "
              "list it in 6.10.")
    written = ["var_adf.csv", "var_lag_order.csv", "var_checks.csv"] + [
        f"var_{kind}_{r.spec}.csv" for r in results for kind in ("pt", "irf", "crosscheck")]
    print("\nWrote tables/" + ", tables/".join(written))
    print("Wrote figures/" + ", figures/".join(
        f"var_{kind}_{r.spec}.png" for r in results for kind in ("pt", "cirf")))


if __name__ == "__main__":
    main()
