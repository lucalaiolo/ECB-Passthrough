"""6.8 tests of the impulse-response code, written as a function of (A matrices, B0)."""
import numpy as np
import pytest
from statsmodels.tsa.api import VAR

from analysis.var import cumulative, impulse_responses, pass_through

# 6.8 worked example (made-up numbers): y_t = (d r_t, d L_t), one lag.
# Here Euribor is variable 1 (index 0) and the lending rate variable 2 (index 1).
A1 = np.array([[0.5, 0.0], [0.3, 0.4]])
B0 = np.array([[0.2, 0.0], [0.1, 0.15]])


def worked_example(horizon):
    irf = impulse_responses([A1], B0, horizon)
    cum = cumulative(irf) / B0[0, 0]  # rescaled by b11 = 0.2: Euribor +1 pp in month 0
    (pt,) = pass_through(cum, rate=0, loans=(1,))
    return irf, cum, pt


def test_worked_example_months_0_to_3():
    irf, cum, pt = worked_example(3)
    # responses to the Euribor shock, rescaled: (1, 0.5), then A1 times each month
    np.testing.assert_allclose(irf[:, :, 0] / 0.2,
                               [[1, 0.5], [0.5, 0.5], [0.25, 0.35], [0.125, 0.215]])
    np.testing.assert_allclose(cum[:, 0, 0], [1, 1.5, 1.75, 1.875])  # Euribor total
    np.testing.assert_allclose(cum[:, 1, 0], [0.5, 1.0, 1.35, 1.565])  # lending-rate total
    np.testing.assert_array_equal(np.round(pt, 2), [0.50, 0.67, 0.77, 0.83])


def test_worked_example_long_run():
    _, cum, pt = worked_example(400)
    assert cum[-1, 0, 0] == pytest.approx(2.0)
    assert cum[-1, 1, 0] == pytest.approx(1.8333333333)
    assert round(pt[-1], 2) == 0.92


def test_pt_needs_no_rescaling():
    # 6.8: b22 divides numerator and denominator, so PT is the same without rescaling
    (pt_raw,) = pass_through(cumulative(impulse_responses([A1], B0, 24)), rate=0, loans=(1,))
    _, _, pt = worked_example(24)
    np.testing.assert_allclose(pt_raw, pt)


def simulated_var(p=3, T=300, seed=0):
    rng = np.random.default_rng(seed)
    K = 4
    A = [np.diag([0.5, 0.4, 0.3, 0.2]) + 0.05 * rng.standard_normal((K, K))] + \
        [0.1 * rng.standard_normal((K, K)) for _ in range(p - 1)]
    L = np.tril(rng.uniform(0.2, 1.0, (K, K)))
    y = np.zeros((T + 100, K))
    for t in range(p, T + 100):
        y[t] = sum(A[j] @ y[t - 1 - j] for j in range(p)) + L @ rng.standard_normal(K)
    return VAR(y[100:]).fit(p)


def test_matches_statsmodels_orth_responses():
    # The function of (A, B0) reproduces statsmodels' Cholesky responses and
    # their cumulative sums, so PT(h) from either is the same.
    res = simulated_var()
    irf = res.irf(24)
    own = impulse_responses(res.coefs, np.linalg.cholesky(res.sigma_u), 24)
    np.testing.assert_allclose(own, irf.orth_irfs, rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(cumulative(own), irf.orth_cum_effects, rtol=1e-10, atol=1e-12)
    pt_nfc, pt_hh = pass_through(cumulative(own))
    c = irf.orth_cum_effects
    np.testing.assert_allclose(pt_nfc, c[:, 2, 1] / c[:, 1, 1])
    np.testing.assert_allclose(pt_hh, c[:, 3, 1] / c[:, 1, 1])


def test_swapping_the_lending_rates_changes_nothing():
    # 6.7: for the Euribor shock only which variables come before Euribor matters
    res = simulated_var()
    y = np.asarray(res.model.endog)
    swapped = VAR(y[:, [0, 1, 3, 2]]).fit(res.k_ar)
    a = pass_through(cumulative(impulse_responses(res.coefs, np.linalg.cholesky(res.sigma_u), 24)))
    b = pass_through(cumulative(impulse_responses(swapped.coefs,
                                                  np.linalg.cholesky(swapped.sigma_u), 24)))
    np.testing.assert_allclose(a[0], b[1])
    np.testing.assert_allclose(a[1], b[0])
