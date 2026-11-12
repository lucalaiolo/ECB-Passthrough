# Interest-rate pass-through in the euro area, 2003–2026

*When market interest rates move, how much of the move reaches the rates banks charge companies and families, how fast, and is it the same in every euro-area country?*

A small project on public ECB data. The full specification, with every formula, is in [`docs/spec.md`](docs/spec.md).

## The problem

The ECB sets the rate banks earn on money parked with it (the *deposit facility rate*). Market rates follow it: 3-month **Euribor**, the rate at which banks lend to each other, is the wholesale price of money. The rates banks charge on new loans are the retail price. Monetary policy works only if moves in the wholesale price reach the retail one.

**Pass-through** measures how much does: if Euribor rises by 4 pp and loan rates by 3 pp, pass-through is 3 ÷ 4 = 0.75. Euribor is the same everywhere in the euro area, but banks are not. Funding costs, competition and, above all, whether mortgages are fixed- or variable-rate differ across countries.

The test case is the sharpest tightening in the euro's history. Between July 2022 and September 2023 the ECB raised its deposit rate ten times, from −0.50% to 4.00%.

## Data

All data come from the ECB Data Portal (free API):

- **Lending rates:** composite cost-of-borrowing indicators for new loans to companies and new mortgages, for the euro area and for each of its 21 members.
- **Market and policy rates:** 3-month Euribor and the deposit facility rate.
- **Inflation:** euro-area HICP, annual rate.

The sample is January 2003 to September 2026. Each country counts from the month it adopted the euro.

## Method

1. **Facts.** Three charts: the chain from the ECB rate to loan rates; how spread out lending rates are across countries (cross-country standard deviation); and each country's rates through the 2022–23 hikes.
2. **The 2022–23 episode, by arithmetic.** Take $t_0$ = the month of lowest Euribor before the hikes (December 2021) and $t_1$ = its peak (November 2023). For each country, pass-through is
   $\text{PT}_i = (L_{i,t_1} - L_{i,t_0}) / (r_{t_1} - r_{t_0})$. The same is computed six months after the peak, and with $t_0$ = June 2022 as a robustness check.
3. **Pass-through over time, with a VAR.** A vector autoregression on euro-area data uses all months since 2003:
   - **Variables:** inflation and the monthly changes of Euribor, the company-loan rate and the mortgage rate. The rates are in changes because ADF tests can't reject a random walk in their levels.
   - **Lags:** chosen by BIC, plus the AIC choice because the BIC model leaves patterns in its residuals.
   - **The shock:** a Euribor surprise, identified by assuming lending rates react to Euribor within the month but Euribor does not react to them.
   - **Pass-through after $h$ months:** $\text{PT}(h)$ is the cumulative response of the lending rate divided by the cumulative response of Euribor.
   - **Uncertainty:** 90% bands from a residual bootstrap with 1,000 draws.

## Results

### 1. Company loans follow Euribor; mortgages only partly

| Months after a Euribor surprise | 0 | 3 | 6 | 12 | 24 |
|---|--:|--:|--:|--:|--:|
| Company loans, 1 lag | 0.58 | 0.68 | 0.70 | 0.71 | 0.72 [0.67, 0.76] |
| Company loans, 6 lags | 0.58 | 0.67 | 0.74 | 0.75 | 0.75 [0.68, 0.80] |
| Mortgages, 1 lag | 0.12 | 0.31 | 0.37 | 0.40 | 0.42 [0.35, 0.48] |
| Mortgages, 6 lags | 0.12 | 0.30 | 0.35 | 0.33 | 0.32 [0.16, 0.43] |

![Pass-through curves](figures/var_pt_bic.png)

More than half of a Euribor move reaches company-loan rates in the same month, and about 0.7 within six months. Company loans in the euro area are largely short-term or variable-rate, so they reprice quickly.

Mortgages start at about a tenth and settle around a third to two fifths. That fits the large share of fixed-rate mortgages in the big countries: a new 20-year fixed-rate loan is priced off long-term rates more than off 3-month Euribor.

The two lag choices agree for company loans. For mortgages after the first half year they differ, and the six-lag band is wide, so the long-run mortgage number is the least certain result here.

### 2. The 2022–23 hikes passed through more than the average

Between December 2021 and November 2023 Euribor rose by 4.55 pp. The euro-area company-loan rate rose from 1.36% to 5.25% (pass-through 0.85) and the mortgage rate from 1.31% to 4.03% (0.60). Both are well above the VAR's two-year averages of about 0.72–0.75 and 0.32–0.42.

The comparison is not like for like, and both differences point the same way:
- **Surprise vs path.** The VAR measures the response to a surprise; the hikes were large and largely announced, and long-term rates rose with them, which also lifts fixed-rate mortgage pricing.
- **Average vs episode.** The VAR averages over 2003–2026, much of it spent near zero rates, when pass-through may have been weaker.

Six months after the Euribor peak, rates in 17 of 19 countries were already lower than at the peak, for both kinds of loan.

![The chain over time](figures/chart1_chain.png)

### 3. Countries differ little for company loans and a lot for mortgages

Pass-through between December 2021 and November 2023, by country (the 19 members at the start of the hikes):

| Country | Company loans | Mortgages |
|---|--:|--:|
| Estonia | 0.98 | 0.89 |
| Lithuania | 0.86 | 0.83 |
| Portugal | 0.81 | 0.83 |
| Finland | 1.00 | 0.79 |
| Latvia | 0.86 | 0.79 |
| Italy | 0.95 | 0.70 |
| Slovakia | 0.92 | 0.69 |
| Luxembourg | 0.69 | 0.67 |
| Austria | 0.88 | 0.66 |
| Cyprus | 0.68 | 0.65 |
| Germany | 0.87 | 0.64 |
| Spain | 0.84 | 0.56 |
| Netherlands | 0.79 | 0.53 |
| France | 0.79 | 0.53 |
| Slovenia | 0.82 | 0.52 |
| Belgium | 0.81 | 0.52 |
| Greece | 0.70 | 0.42 |
| Ireland | 0.80 | 0.33 |
| Malta | 0.38 | 0.04 |

For company loans the middle half of countries lies between 0.79 and 0.87. For mortgages it lies between 0.53 and 0.75, and the extremes are 0.89 (Estonia) and 0.04 (Malta).

The countries at the top for mortgages (the Baltic states, Finland, Portugal) are where most mortgages are variable-rate and tied to Euribor. Germany, France, the Netherlands and Belgium, where fixed rates dominate, sit in the lower half. Malta's mortgage rate barely moved (1.92% → 2.09%), and its company-loan pass-through is also by far the lowest.

Starting the episode in June 2022 keeps the extremes: Estonia stays in the top two and Malta last for both kinds of loan. Some countries in the middle move a lot; Germany drops from 6th to 15th for company loans.

![Country panels](figures/chart3_countries.png)

The hikes also pulled mortgage rates apart. Their cross-country standard deviation doubled, from 0.45 pp in June 2022 to 0.93 pp in October 2023, while among the 12 members of 2003 it fell from 0.55 to 0.35 pp. The widening came from the countries that joined after 2003, the Baltic states above all. For company loans dispersion stayed at 0.6–0.8 pp, far below its euro-crisis peak of 1.68 pp in 2012.

![Dispersion across countries](figures/chart2_dispersion.png)

## What to keep in mind

- **Not the effect of monetary policy.** A Euribor surprise mixes ECB news with bank risk and shifting expectations. The VAR measures how market-rate moves reach loans.
- **The VAR is imperfect.** Its results rest on an ordering assumption, and residual autocorrelation remains with both lag choices. Inflation looks like a random walk over the sample (ADF p = 0.13). The long-run link between Euribor and loan rates (cointegration) is left out.
- **The bands are approximate.** The residuals have very fat tails, from the 2008 crisis above all, so the bootstrap bands are wider at short horizons than bands that assume normal errors.
- **Euro-area averages.** Country differences come from the 2022–23 arithmetic, not from the VAR.

All numbers, with full country tables (rates, rises, speed, robustness) and the diagnostics (ADF, lag criteria, stability, whiteness, cross-check), are in [`tables/`](tables/).

## How to run

```bash
pip install -r requirements.txt
make refresh   # download / update the ECB data
make test      # data checks and tests of the VAR code
make figures   # charts and the 2022–23 tables
make var       # the VAR and its bootstrap
```

`ecbdata/` downloads and cleans the data, `analysis/` holds `charts.py`, `hiking_cycle.py` and `var.py`, and outputs go to `figures/` and `tables/`. Data (`data/`) is not committed. Results here use data downloaded on 12 November 2026.
