"""6.9 cross-check: the bootstrap loop against statsmodels' cum_errband_mc.

cum_errband_mc simulates with normally distributed errors; the loop resamples
the residuals. So the two should give similar bands for the cumulative
responses (before rescaling) when the residuals are close to normal, and that
is the test of the loop: a VAR whose errors are normal by construction.

On the real data the residuals of the interest-rate equations are far from
normal (very fat tails), and resampled residuals legitimately give wider bands
at short horizons than normal errors do; there the test checks what holds
whatever the error distribution: the bands are centred in the same place.
"""
import numpy as np
import pytest
from statsmodels.tsa.api import VAR

from analysis.var import (COLUMNS, DRAWS, SEED, crosscheck, crosscheck_gaps,
                          residual_bootstrap, var_data, var_levels)
from ecbdata.build import CLEAN_PATH, load_clean

# Tolerances. With normal errors the two band widths still differ through
# Monte Carlo noise in both sets of 1,000 draws and because 282 residuals have
# their own sample kurtosis (standard error about 0.3), which alone moves the
# h = 0 width ratio by roughly +-15%. Checked against broken versions of the
# loop: B0 not recomputed in each draw, residuals drawn column by column (not
# whole rows), no refit, the wrong shock column and draws without replacement
# all fail the normal-errors test; the location check on the data catches the
# column-by-column draws and the wrong shock column.
WIDTH_RATIO = (0.7, 1.4)  # loop band width / MC band width, normal errors
MAX_MID_SHIFT_NORMAL = 0.25  # band midpoints apart by at most 1/4 of the MC band width
MAX_MID_SHIFT_DATA = 0.5  # real data: at most half the MC band width


def normal_var(T=284, p=2, seed=1):
    """A persistent 4-variable VAR(2) with correlated normal errors, ordered like
    6.3 (an inflation-like level first, then three changes), fitted by OLS."""
    A1 = np.array([[0.90, 0.20, 0.00, 0.00],
                   [0.02, 0.45, 0.00, 0.00],
                   [0.00, 0.35, 0.30, 0.00],
                   [0.00, 0.15, 0.05, 0.45]])
    A2 = np.array([[0.05, 0.00, 0.00, 0.00],
                   [0.00, 0.10, 0.00, 0.00],
                   [0.00, 0.10, 0.10, 0.00],
                   [0.00, 0.05, 0.00, 0.20]])
    sd = np.array([0.30, 0.10, 0.10, 0.05])
    corr = np.array([[1.0, 0.1, 0.1, 0.0],
                     [0.1, 1.0, 0.6, 0.3],
                     [0.1, 0.6, 1.0, 0.3],
                     [0.0, 0.3, 0.3, 1.0]])
    chol = np.linalg.cholesky(corr * np.outer(sd, sd))
    rng = np.random.default_rng(seed)
    y = np.zeros((T + 200, 4))
    for t in range(p, T + 200):
        y[t] = 0.1 + A1 @ y[t - 1] + A2 @ y[t - 2] + chol @ rng.standard_normal(4)
    return VAR(y[200:]).fit(p)


def test_loop_matches_cum_errband_mc_with_normal_errors():
    res = normal_var()
    boot = residual_bootstrap(res, np.asarray(res.model.endog))
    gaps = crosscheck_gaps(crosscheck(res, boot))
    print("\n", gaps.round(3).to_string())
    assert gaps["width_ratio_min"].min() >= WIDTH_RATIO[0], gaps
    assert gaps["width_ratio_max"].max() <= WIDTH_RATIO[1], gaps
    assert gaps["mid_shift_max"].max() <= MAX_MID_SHIFT_NORMAL, gaps


@pytest.mark.skipif(not CLEAN_PATH.exists(), reason="no data: run `make refresh`")
@pytest.mark.parametrize("ic", ["bic", "aic"])
def test_crosscheck_on_the_data(ic, capsys):
    y = var_data(var_levels(load_clean()))
    sel = VAR(y).select_order(maxlags=12)
    p = max(1, int(getattr(sel, ic)))
    res = VAR(y).fit(p)
    boot = residual_bootstrap(res, y.to_numpy(), draws=DRAWS, seed=SEED)
    table = crosscheck(res, boot)
    gaps = crosscheck_gaps(table)
    with capsys.disabled():
        print(f"\n6.9 cross-check on the data, VAR({p}) ({ic.upper()}): loop band width / "
              "cum_errband_mc band width, and largest midpoint shift in MC widths")
        print(gaps.round(2).to_string())
    assert list(gaps.index) == COLUMNS
    assert gaps["mid_shift_max"].max() <= MAX_MID_SHIFT_DATA, gaps
