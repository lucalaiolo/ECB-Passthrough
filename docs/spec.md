# Interest-rate pass-through in the euro area, 2003 to 2026: specification

This is the full specification behind the [README](../README.md). Code comments such as `# 6.9 step 2` refer to its section numbers.

## 1. The idea

An interest rate is the price of borrowing. The ECB sets the rate banks earn on money they deposit with it, the deposit facility rate. Three-month Euribor, the rate at which banks lend to each other, stays close to it and also reflects where markets expect the ECB rate to go. Banks then price loans at roughly Euribor plus a markup.

Pass-through is the share of a Euribor move that reaches loan rates. If Euribor rises by 4 points and a loan rate by 3, pass-through is 0.75. Euribor is the same everywhere in the euro area, but banks differ: some pay more for their own funding, competition varies, and in some countries mortgages follow Euribor while in others they are fixed for years.

The test case is the tightening of July 2022 to September 2023, when the ECB raised the deposit rate ten times, from −0.50% to 4.00%.

## 2. Notation

Rates are in % per year, monthly. $i$ is a country, $t$ a month and $h$ the number of months after a shock. $\Delta x_t = x_t - x_{t-1}$ is a monthly change.

| Symbol | Meaning |
|---|---|
| $r_t$ | 3-month Euribor, monthly average |
| $L^{\text{NFC}}_{i,t}$ | rate on new loans to companies in country $i$ |
| $L^{\text{HH}}_{i,t}$ | rate on new mortgages in country $i$ |
| $L_t$ without $i$ | the same rates for the euro area |
| $\pi_t$ | euro-area inflation, % change over 12 months |

The lending rates are the ECB's composite cost-of-borrowing indicators, which average new loans of all maturities so that countries can be compared.

## 3. Data

Everything comes from the ECB Data Portal API (`https://data-api.ecb.europa.eu/service/data/{FLOW}/{KEY}?format=csvdata`).

| Series | Flow | Key |
|---|---|---|
| Lending rate to companies, euro area | `MIR` | `M.U2.B.A2I.AM.R.A.2240.EUR.N` |
| Mortgage rate, euro area | `MIR` | `M.U2.B.A2C.AM.R.A.2250.EUR.N` |
| Lending rate to companies, every country | `MIR` | `M..B.A2I.AM.R.A.2240.EUR.N` |
| Mortgage rate, every country | `MIR` | `M..B.A2C.AM.R.A.2250.EUR.N` |
| 3-month Euribor | `FM` | `M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA` |
| ECB deposit facility rate | `FM` | `B.U2.EUR.4F.KR.DFR.LEV` |
| Inflation (HICP) | `HICP` | `M.U2.N.000000.4D0.ANR` |

The deposit rate has one row per change, so it is forward-filled to a daily calendar and averaged by month. Inflation uses the new `HICP` dataset, which replaced the old `ICP` one in February 2026. The country keys also return the euro-area aggregate `U2`, which is set aside, and each country is kept only from the month it adopted the euro.

`ecbdata/fetch.py` downloads the series into `data/raw/` and stops if a series is empty, a euro-area series starts after January 2003, or a country code is not a euro-area member. `make refresh` then downloads only what changed since the last run. `ecbdata/build.py` writes one clean table (country, month, variable, value) to `data/clean/`. The tests check for duplicate rows, report gaps per country and check that values are plausible (rates between −1% and 15%, inflation between −2% and 12%).

## 4. Three charts

1. Euribor, the deposit rate and the two euro-area lending rates since 2003, with the euro-area recessions dated by the CEPR–EABCN committee shaded (2008Q1 to 2009Q2, 2011Q3 to 2013Q1, 2019Q4 to 2020Q2).
2. How far apart countries are: each month, the standard deviation of lending rates across countries, for company loans and mortgages. It is also computed for the 12 members of 2003, so that new members joining does not move the line.
3. One small panel per country from January 2021, with its two lending rates and Euribor in grey.

## 5. The 2022 to 2023 hikes, by arithmetic

$t_0$ is the month of lowest Euribor between January 2021 and June 2022, and $t_1$ the month of highest Euribor in 2023 and 2024. For each country,

$$\text{PT}_i = \frac{L_{i,t_1} - L_{i,t_0}}{r_{t_1} - r_{t_0}}$$

The same ratio is computed six months after the peak, because loan rates lag. Speed is the number of months after $t_0$ until a country's rate covered half of its total rise. Everything is done for company loans and mortgages, countries are ranked, and the whole exercise is repeated with $t_0$ = June 2022 as a check.

## 6. The VAR

### 6.1 The goal

Section 5 looks at one episode. The VAR uses every month since 2003 to ask: if Euribor rises by 1 point unexpectedly, how do lending rates move that month and in each of the next 24?

### 6.2 Autoregression

An autoregression predicts a series from its own past, for example $r_t = c + a\,r_{t-1} + e_t$, with $c$ and $a$ estimated by least squares and $e_t$ the surprise.

### 6.3 The VAR

A VAR predicts each variable from the past of all of them. The four variables, in this order, are

$$y_t = (\pi_t,\ \Delta r_t,\ \Delta L^{\text{NFC}}_t,\ \Delta L^{\text{HH}}_t)$$

and the model is $y_t = c + A_1 y_{t-1} + \dots + A_p y_{t-p} + u_t$, where each $A_j$ is a $4\times4$ matrix and $u_t$ are the surprises, with covariance $\Sigma_u$. In practice it is four ordinary regressions on the same lagged variables.

### 6.4 Levels or changes

Interest rates behave almost like random walks, and regressions on two unrelated random walks often look significant. An ADF test (`adfuller(w, regression="c", autolag="AIC")`) checks each rate in levels. If it can't reject a random walk at 5%, the rate enters as a monthly change, and the change must then pass the test. Inflation enters as it is; its p-value is reported anyway.

### 6.5 Number of lags

The lag length $p$ is chosen by BIC over $p = 1$ to $12$ on the same months (`select_order(maxlags=12).bic`). BIC penalises each extra lag, which adds 16 coefficients.

### 6.6 Checks

The VAR must be stable (`results.is_stable()`): a shock has to die out rather than explode. Its residuals should have no pattern left (`results.test_whiteness(nlags=24)`). If that test rejects, the VAR is also fitted with the lag chosen by AIC and both results are reported.

### 6.7 Identifying a Euribor shock

Surprises in Euribor and lending rates happen together, so the data alone can't say which caused which. The shocks are separated with a Cholesky decomposition $\Sigma_u = B_0 B_0'$, where $B_0$ is lower triangular. In words: within a month, inflation reacts to nothing else, Euribor reacts to inflation, and lending rates react to both. This ordering is an assumption. Swapping the two lending rates changes nothing for the Euribor shock.

### 6.8 Impulse responses and pass-through

A Euribor shock moves the variables by column 2 of $B_0$ in month 0. After that the VAR rolls forward with no new shocks: $y_{t+h} = A_1 y_{t+h-1} + \dots + A_p y_{t+h-p}$. Dividing by $b_{22}$ makes the initial Euribor move exactly 1 point. Adding up the monthly changes gives the cumulative response $\text{CIRF}_k(h)$, and pass-through is

$$\text{PT}(h) = \frac{\text{CIRF}_{\text{loan}}(h)}{\text{CIRF}_{\text{Euribor}}(h)}$$

Euribor often keeps moving after the shock, so dividing by its own cumulative move gives the share of the actual Euribor move that reached loans. In `statsmodels` this is `irf.orth_cum_effects[h, k, 1] / irf.orth_cum_effects[h, 1, 1]` with $k = 2$ for companies and $k = 3$ for mortgages.

A two-variable example tests the code: with $A_1 = \begin{pmatrix}0.5 & 0\\0.3 & 0.4\end{pmatrix}$ and $B_0 = \begin{pmatrix}0.2 & 0\\0.1 & 0.15\end{pmatrix}$, PT is 0.50, 0.67, 0.77 and 0.83 in months 0 to 3, and 0.92 in the long run.

### 6.9 Uncertainty: residual bootstrap

1. Keep the estimated $c$, $A_1, \dots, A_p$ and the residuals, one row of four numbers per month.
2. Build a fake history of the same length: copy the first $p$ real months, then add one residual row drawn at random (whole rows, with replacement) to each month the VAR predicts.
3. Refit the VAR with the same $p$, recompute its own $B_0$ and the two PT curves.
4. Repeat 1,000 times with a fixed seed and store every draw.
5. The 5th and 95th percentiles at each $h$ give a 90% band.

PT is computed inside each draw because its numerator and denominator move together. A draw in which Euribor's cumulative response reaches zero makes the ratio meaningless, so the number of such draws is reported. As a cross-check, `irf.cum_errband_mc(orth=True, repl=1000, signif=0.10, rng=...)` gives bands for the cumulative responses under normal errors; they should be close to the bootstrap's when the residuals are close to normal.

### 6.10 What the VAR can't tell you

A Euribor surprise mixes ECB news with bank risk and changing expectations, so this is not the effect of monetary policy. The results depend on the ordering in 6.7. The VAR assumes one reaction for the whole period, which is why Section 5 looks at one episode separately, and it uses euro-area averages, so country differences come from Sections 4 and 5. It also leaves out the long-run link between Euribor and loan rates (a VECM would add it), mixes a very persistent inflation series with differenced rates, and has approximate bands on a sample this short.

## 7. How to run

```bash
pip install -r requirements.txt
make refresh   # download / update data
make test      # data checks and tests
make figures   # Sections 4 and 5
make var       # Section 6, with the bootstrap
```

## 8. Repo layout

```
ecbdata/    keys.yaml, fetch.py, build.py
analysis/   charts.py, hiking_cycle.py, var.py
tests/      data checks, impulse-response and bootstrap tests
data/       raw/ and clean/ (not committed)
figures/    charts
tables/     results as CSV
note/       note.md, written by hand
```

## 9. Results

See the [README](../README.md).
