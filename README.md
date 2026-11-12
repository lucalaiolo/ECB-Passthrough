# Interest-rate pass-through in the euro area, 2003 to 2026

When market interest rates move, how much of the move reaches the rates banks charge companies and households, how fast, and is it the same in every euro-area country? This project answers those questions with public ECB data. The full specification is in [`docs/spec.md`](docs/spec.md).

## The question

The ECB sets the rate banks earn on money they deposit with it. Three-month Euribor, the rate banks charge each other, follows that rate, and loan rates follow Euribor plus a markup. Monetary policy reaches households and firms only if a change in Euribor shows up in the rates they pay. Pass-through is the share that does: if Euribor rises by 4 points and loan rates by 3, pass-through is 0.75.

Euribor is the same across the euro area, but banks and loan contracts differ from country to country. The 2022 to 2023 tightening is the natural test: the ECB raised its deposit rate from −0.50% to 4.00% in ten steps.

## Data and method

The data are monthly, from January 2003 to September 2026, all from the ECB Data Portal. They cover rates on new loans to companies and on new mortgages for the euro area and each member country, along with Euribor, the ECB deposit rate and inflation.

The analysis has three parts. Charts show how the rates moved and how far apart countries were. For the 2022 to 2023 hikes, each country's pass-through is the rise in its loan rate divided by the rise in Euribor, measured from the month Euribor bottomed (December 2021) to its peak (November 2023). A vector autoregression (VAR) on euro-area data since 2003 then estimates how loan rates respond, month by month, to an unexpected rise in Euribor, with 90% bootstrap bands.

## Results

Company loans follow Euribor closely and mortgages much less. In the VAR, 0.58 of a Euribor surprise reaches company-loan rates in the same month and 0.72 to 0.75 after two years. Mortgage rates take up 0.12 at first and 0.32 to 0.42 after two years; the ranges cover the two lag lengths tried. Company loans are largely short term or variable rate, so they reprice quickly. Many mortgages, especially in the larger countries, are fixed for years and priced off long-term rates.

| Pass-through after | 0 months | 6 months | 24 months |
|---|--:|--:|--:|
| Company loans | 0.58 | 0.70 to 0.74 | 0.72 to 0.75 |
| Mortgages | 0.12 | 0.35 to 0.37 | 0.32 to 0.42 |

![Pass-through curves](figures/var_pt_bic.png)

The 2022 to 2023 hikes passed through more than this long-run average. Euribor rose by 4.55 points, the euro-area company-loan rate rose from 1.36% to 5.25% (pass-through 0.85) and the mortgage rate from 1.31% to 4.03% (0.60). The two estimates measure different things. The VAR averages the response to surprises over 23 years, many of them spent near zero rates, while the hikes were large, announced in advance and came with rising long-term rates.

![Rates over time](figures/chart1_chain.png)

Countries were alike for company loans and far apart for mortgages. For the middle half of countries, company-loan pass-through was between 0.79 and 0.87. Mortgage pass-through ranged from 0.89 in Estonia to 0.33 in Ireland and 0.04 in Malta, where the mortgage rate barely moved. Countries where variable-rate mortgages are common (the Baltic states, Finland, Portugal) are at the top; Germany, France, the Netherlands and Belgium, where fixed rates are common, are lower. Mortgage rates also drifted apart during the hikes. Their cross-country standard deviation doubled, from 0.45 to 0.93 points, and the increase came from countries that joined the euro after 2003.

![Country panels](figures/chart3_countries.png)

The country tables, the dispersion chart and the VAR diagnostics are in `figures/` and `tables/`.

## Limits

A Euribor surprise is not a pure monetary policy shock, since it also reflects bank risk and changing expectations. The VAR assumes Euribor does not respond to loan rates within the same month, leaves out the long-run link between Euribor and loan rates, and its residuals still show autocorrelation. The country comparison rests on a single episode.

## How to run

```bash
pip install -r requirements.txt
make refresh   # download / update the ECB data
make test      # data checks and tests of the VAR code
make figures   # charts and the 2022–23 tables
make var       # the VAR and its bootstrap
```

Results use data downloaded on 12 November 2026.
