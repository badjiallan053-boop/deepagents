## Signal library: 23 cross-asset signals, backtested, kill rule applied

Method: event = first trigger after a cooldown of h days; entry at the first close after publication; the excess move is drift-adjusted and signed; precision = share of events with positive excess; costs are deducted per event. **KEPT** = OOS mean > 0 and OOS precision ≥ 52%, and in-sample agrees. **FRAGILE** = OOS passes but in-sample disagrees. **UNTESTED** = fewer than 8 OOS events. **KILLED** = fails OOS. Rules were set before the OOS numbers were read; nothing was re-tuned after (S3 lost KEPT when a data error was fixed: the 20 Apr 2020 negative WTI print had produced a +154% 'event').

| ID | Class | Signal (trigger → trade) | h | IS n / prec / mean / t | OOS n / prec / mean / t | Verdict | Live now |
|---|---|---|---|---|---|---|---|
| S1 | commodities | MM net/OI percentile vs 3y ≥95%; trade short 20d | 20d | 127 / 49% / +0.47% / t=None | 72 / 51% / -0.23% / t=None (OOS from 2019-01-01) | **KILLED** | FIRED: ZS=F pctile 97% (2026-10-13) |
| S2 | commodities | MM net/OI percentile vs 3y ≤5%; trade long 20d | 20d | 164 / 45% / -0.97% / t=None | 73 / 53% / +0.96% / t=None (OOS from 2019-01-01) | **FRAGILE (IS disagrees)** | —: no commodity at an extreme in the last 2 weeks |
| S3 | commodities | Weekly US crude stocks ex-SPR change vs same-week 5y average, |z|>1.5; trade with the surp | 10d | 130 / 60% / +1.23% / t=2.06 | 50 / 50% / -1.46% / t=-0.73 (OOS from 2019-01-01) | **KILLED** | —: latest week 2026-10-16 z=-0.94 |
| S4 | commodities | Lower-48 working gas vs 5y same-week avg beyond ±10%; trade toward normalisation 20d | 20d | 35 / 57% / -2.70% / t=-1.24 | 36 / 44% / -2.24% / t=-0.86 (OOS from 2019-01-01) | **KILLED** | —: 2026-10-16 storage vs 5y -0.0% |
| S5 | bonds | 10y/30y auction bid-to-cover z < −1.5 vs prior 12 long-end auctions; short TLT 5d from nex | 5d | 30 / 37% / -0.49% / t=-1.61 | 22 / 55% / +0.31% / t=0.82 (OOS from 2019-01-01) | **FRAGILE (IS disagrees)** | —: last long-end auction 2026-10-08 z=+0.08 |
| S6 | bonds | HYG under-performs IEF by >4% in 22 trading days; buy HYG 60d | 60d | 22 / 59% / +1.49% / t=1.01 | 7 / 71% / +1.04% / t=0.69 (OOS from 2019-01-01) | **UNTESTED (n_oos=7<8)** | —: HYG vs IEF 22d -2.0% |
| S7 | stocks | VIX closes above 30 for the first time in 60 days; long SPY 20d | 20d | 20 / 50% / -0.46% / t=-0.3 | 10 / 80% / +3.02% / t=1.15 (OOS from 2019-01-01) | **FRAGILE (IS disagrees)** | —: VIX 16.7 (2026-10-21) |
| S8 | stocks | DXY +5% over 63 trading days; short EEM 20d | 20d | 41 / 44% / +0.11% / t=0.09 | 11 / 64% / +0.38% / t=0.18 (OOS from 2019-01-01) | **FRAGILE (IS disagrees)** | —: DXY 3m +0.1% |
| S9 | bonds | Copper/gold ratio +10% in 63 days; short TLT 20d | 20d | 66 / 47% / +0.19% / t=0.54 | 23 / 57% / -0.24% / t=-0.3 (OOS from 2019-01-01) | **KILLED** | —: Cu/Au 3m +1.8% |
| S10 | crypto | Total stablecoin market cap +5% in 30 days; long BTC 30d | 30d | 41 / 44% / -0.89% / t=-0.24 | 9 / 11% / -7.94% / t=-2.48 (OOS from 2023-01-01) | **KILLED** | —: 30d supply change -0.5% |
| S11 | crypto | 7d avg Bybit BTCUSDT funding >0.03%; short BTC 7d | 7d | 34 / 47% / -0.84% / t=-0.43 | 5 / 20% / -1.88% / t=-0.79 (OOS from 2023-01-01) | **UNTESTED (n_oos=5<8)** | —: 7d funding 0.0055%/8h (2026-10-22) |
| S12 | crypto | 7d avg Bybit BTCUSDT funding <0; long BTC 7d | 7d | 35 / 51% / +0.75% / t=0.5 | 16 / 50% / +0.12% / t=0.08 (OOS from 2023-01-01) | **KILLED** | —: 7d funding 0.0055%/8h (2026-10-22) |
| S13 | crypto | Bybit BTCUSDT OI +20% in 7 days; short BTC 7d | 7d | 35 / 60% / +1.33% / t=0.73 | 3 / 67% / +3.28% / t=1.38 (OOS from 2023-01-01) | **UNTESTED (n_oos=3<8)** | —: OI 7d +4.6% |
| S14 | stocks | KRE −20% from its 20-day high; long KRE 60d | 60d | 6 / 67% / +8.55% / t=1.04 | 3 / 33% / -0.96% / t=-0.17 (OOS from 2019-01-01) | **UNTESTED (n_oos=3<8)** | —: KRE vs 20d high +1.0% |
| S15 | bonds | Monthly IT–DE 10y spread +40bp m/m; short EWI 20d (lag 45d for publication) | 20d | 9 / 67% / +2.01% / t=0.86 | 1 / 100% / +0.74% / t=None (OOS from 2019-01-01) | **UNTESTED (n_oos=1<8)** | —: IT–DE spread 0.80pp (2026-08-01) |
| S16 | critical minerals | MOFCOM/GACC export-control announcement on a critical mineral; long REMX 5d | 5d | 1 / 100% / +1.69% / t=None | 3 / 67% / +2.01% / t=0.84 (OOS from 2024-01-01) | **UNTESTED (n_oos=3<8)** | —: no new MOFCOM control in the last 30 days found (not monitored automat |
| S17 | critical minerals | District new BLM claims in a month ≥50 and ≥3× trailing-12m average; long nearby listed ow | 60d | — | 19 / 42% / -11.09% / t=None (OOS from 2021-01-01) | **KILLED** | —: no surge in last 4 months |
| S18 | bonds | Japan 10y (OECD monthly) +20bp over 3 months; short EWJ 20d after 45d publication lag | 20d | 22 / 50% / +0.74% / t=0.53 | 23 / 35% / -1.49% / t=-1.4 (OOS from 2019-01-01) | **KILLED** | FIRED: JGB 10y 3.05% (2026-09-01), 3m +0.38pp |
| S19 | commodities | US 10y TIPS yield −50bp in 63 days; long GLD 20d | 20d | 21 / 57% / +0.39% / t=0.28 | 12 / 50% / +0.99% / t=0.74 (OOS from 2019-01-01) | **KILLED** | —: 10y real 2.77%, 63d +0.40pp |
| S20 | critical minerals | US new MLRS claims in a month >1.5× trailing-12m average; long GDXJ 60d | 60d | 1 / 100% / +8.21% / t=None | 5 / 60% / -2.05% / t=-0.28 (OOS from 2023-01-01) | **KILLED** | FIRED: last month 2026-10: 3531 new claims vs 12m avg 5712 |
| S21 | bonds | (WALCL − RRP) +$200bn over 13 weeks; long SPY 20d | 20d | 2 / 100% / +1.54% / t=None | 23 / 74% / +2.04% / t=2.06 (OOS from 2019-01-01) | **KEPT** | —: net liquidity 13w change +13bn |
| S22 | stocks | USDJPY −5% in 10 trading days; long EWJ 20d | 20d | 11 / 55% / -0.63% / t=-0.3 | 3 / 67% / +0.75% / t=0.43 (OOS from 2019-01-01) | **UNTESTED (n_oos=3<8)** | —: USDJPY 10d +0.2% |
| S23 | stocks | STLFSI4 crosses above 1.0; long SPY 60d | 60d | 12 / 50% / +1.52% / t=0.68 | 2 / 100% / +19.80% / t=None (OOS from 2019-01-01) | **UNTESTED (n_oos=2<8)** | —: STLFSI4 -0.63 (2026-10-16) |

**Score:** 1 kept (S21), 4 fragile (S2, S5, S7, S8), 8 untested (S6, S11, S13, S14, S15, S16, S22, S23), 10 killed (S1, S3, S4, S9, S10, S12, S17, S18, S19, S20).

**Honest read:** only S21 (Fed net liquidity, WALCL − RRP) survives, and its OOS is dominated by the 2020–21 QE window. Its events from 2022 onward lose money, so treat it as regime-conditional. Killed: COT crowded-long fade, EIA crude surprise, NG storage, copper/gold → yields, stablecoin impulse, negative funding, JGB jump, real-rate → gold, and both staking signals (S17 district surges −11% vs GDXJ at 60d across 19 events; S20 national surges). Most mechanisms in the library are well known and already priced. The edge has to come from data others do not have (gap audit below), not from re-testing public series.

### Staking-surge backtest (S17): dated claims from the BLM MLRS hub 'Created' field

BLM's public MLRS layers carry no location date, but the national hub FeatureServers do carry a record `Created` date. For MLRS-native serials (no legacy LR2000 number) this is the date the claim was filed into MLRS, so it is usable from 2021 onward. Legacy records were migrated in bulk and are excluded. LR2000 case recordation dates sit behind the interactive reports.blm.gov forms and were not scraped.

| District | Ticker | Month after surge | New claims | Excess vs GDXJ +20d | +60d |
|---|---|---|---|---|---|
| Mountain Pass | MP | 2023-04-01 | 198 | -29.1% | -6.3% |
| Mountain Pass | MP | 2024-07-01 | 56 | -12.3% | 0.4% |
| Mountain Pass | MP | 2025-10-01 | 110 | -4.8% | -44.7% |
| Mountain Pass | MP | 2025-12-01 | 129 | -26.5% | -44.1% |
| Mountain Pass | MP | 2026-01-01 | 205 | -3.1% | -19.2% |
| Mountain Pass | MP | 2026-02-01 | 146 | -10.9% | 11.2% |
| Mountain Pass | MP | 2026-03-01 | 226 | -0.8% | 28.7% |
| Thacker Pass | LAC | 2021-08-01 | 272 | -27.8% | -33.3% |
| Thacker Pass | LAC | 2021-09-01 | 159 | -24.7% | -35.2% |
| Thacker Pass | LAC | 2025-04-01 | 184 | 0.9% | -23.0% |
| Stibnite | PPTA | 2022-11-01 | 201 | -26.3% | 27.8% |
| Stibnite | PPTA | 2025-10-01 | 73 | 23.7% | -0.3% |
| Stibnite | PPTA | 2025-12-01 | 54 | -11.7% | 1.5% |
| Stibnite | PPTA | 2026-01-01 | 218 | 1.0% | 7.5% |
| Rhyolite Ridge | INR.AX | 2022-01-01 | 93 | -10.8% | -46.8% |
| Rhyolite Ridge | INR.AX | 2022-03-01 | 216 | -2.0% | 13.8% |
| Rhyolite Ridge | INR.AX | 2022-07-01 | 204 | 25.2% | 43.8% |
| Rhyolite Ridge | INR.AX | 2023-09-01 | 431 | 4.5% | -49.4% |
| Rhyolite Ridge | INR.AX | 2024-05-01 | 183 | -8.8% | -43.1% |

Result: KILLED. The surges come *after* the nearby developer has already re-rated (staking follows price), so buying the developer after the surge loses. The inverse (fade) is not tested here, because testing it after seeing this result would be data-snooping.

### Top 10 live signals (ranked: verdict tier, then distance to trigger)

No KEPT or candidate signal is firing today (23 Oct 2026). Ranking by how close each credible signal is to firing:

| Rank | Signal | Verdict | Now | Trigger | Distance |
|---|---|---|---|---|---|
| 1 | S21 Fed net liquidity → SPY | KEPT (regime-conditional) | +$13bn / 13w | +$200bn | far |
| 2 | S6 HYG vs IEF credit flush → buy HYG | UNTESTED (IS 59%/+1.5%, OOS 7 events 71%/+1.0%) | −2.0% / 22d | −4% | halfway |
| 3 | S8 Dollar squeeze → short EEM | FRAGILE | DXY +0.1% / 3m | +5% | far |
| 4 | S7 VIX>30 → long SPY | FRAGILE | VIX 16.7 | 30 | far |
| 5 | S5 Weak long-end UST auction → short TLT | FRAGILE | last z +0.08 (8 Oct) | z < −1.5 | next 10y/30y auction |
| 6 | S2 COT crowded short → long | FRAGILE | none ≤5th pctile | ≤5% | — |
| 7 | S13 BTC OI +20%/7d → short | UNTESTED | +4.6% | +20% | far |
| 8 | S15 BTP–Bund +40bp m/m → short EWI | UNTESTED | 0.80pp (Aug) | +0.40 m/m | far |
| 9 | S23 STLFSI4 > 1 → long SPY 60d | UNTESTED | −0.63 | +1.0 | far |
| 10 | S16 MOFCOM control → long REMX 5d | UNTESTED (3 OOS) | no new notice found | announcement | event-driven |

Fired but KILLED (shown, not traded): S1 soybeans MM 97th pctile; S18 JGB +38bp/3m; S20 national claims (October lower than average).

## Alpha Committee v2: signals only, costs included

Tier A = KEPT signals only (S21). Tier B adds candidates whose IS and OOS means are both positive (S6, S8, S13, S15, S16, S23). **Tier B was chosen after seeing OOS, so its OOS number is biased upward. Treat it as an upper bound.** Daily book: equal weight across open trades, cash otherwise. Costs: 10 bp round trip (20 bp crypto), 5 bp/month short borrow. Agents abstain when they disagree on the same asset (paper's consensus rule). The risk-averse profile halves gross exposure.

| Book (OOS 2019-01 → 2026-10) | CAGR | Vol | Sharpe | Max DD | Trades | 2022+ Sharpe |
|---|---|---|---|---|---|---|
| v2_tierA_kept_only · risk_neutral | 6.2% | 10.3% | 0.63 | -18.6% | 23 | -0.15 |
| v2_tierA_kept_only · risk_averse | 3.2% | 5.2% | 0.63 | -9.7% | 23 | -0.15 |
| v2_tierA+B_candidates · risk_neutral | 7.6% | 16.8% | 0.52 | -25.2% | 64 | 0.72 |
| v2_tierA+B_candidates · risk_averse | 4.1% | 8.4% | 0.52 | -12.7% | 64 | 0.72 |
| Equal-weight 22-asset benchmark | 13.6% | 15.4% | 0.91 | -27.5% | — | 0.75 |
| Committee v1 (rule agents, monthly) net of costs | 12.9% | 15.1% | 0.88 | -28.7% | — | — |

**Honest result:** after costs, no committee beats the equal-weight benchmark on Sharpe over 2019–2026. The tier-A book (S21 only) loses money from 2022. The biased tier-B book roughly matches the benchmark from 2022 with half the drawdown. The product claim therefore cannot be 'we have alpha' yet. It can be: (1) a verified, timestamped forward record; (2) forced-flow and credit-situation intelligence buyers can't easily assemble; (3) honest kill-lists that save a desk research time.

## Public ledger proofs (OpenTimestamps)

Ledger: 39 paper calls (32 v1 + 7 v2 FLAT records), SHA-256 chain verified. Anchored 23 Oct 2026 with the OpenTimestamps reference client: only the digest of `ledger_proofs/2026-10-23.anchor.txt` (which contains the last hash) went to 4 public calendars. Status at build time: **pending Bitcoin confirmation** (normal; upgrade after a few hours). Outsider steps: `ledger_proofs/README.md` and `verify_ledger.py`. Daily anchoring is a manual or scheduled command (`anchor_ledger.py`). No scheduler has been set up yet.

## Data added this pass

| Dataset | Rows | Source | Fetched |
|---|---|---|---|
| blm_hub:Bear Lodge | 574 | https://nlsdbpubgis.blm.gov/arcgishub/rest/services/HUB/BLM_Natl_MLRS_ | 2026-10-23T02:00 |
| blm_hub:Mountain Pass | 2,123 | https://nlsdbpubgis.blm.gov/arcgishub/rest/services/HUB/BLM_Natl_MLRS_ | 2026-10-23T02:00 |
| blm_hub:Rhyolite Ridge | 2,599 | https://nlsdbpubgis.blm.gov/arcgishub/rest/services/HUB/BLM_Natl_MLRS_ | 2026-10-23T02:00 |
| blm_hub:Stibnite | 2,837 | https://nlsdbpubgis.blm.gov/arcgishub/rest/services/HUB/BLM_Natl_MLRS_ | 2026-10-23T02:00 |
| blm_hub:Thacker Pass | 2,605 | https://nlsdbpubgis.blm.gov/arcgishub/rest/services/HUB/BLM_Natl_MLRS_ | 2026-10-23T02:00 |
| blm_hub:national_monthly | 70 | https://nlsdbpubgis.blm.gov/arcgishub/rest/services/HUB/BLM_Natl_MLRS_ | 2026-10-23T02:02 |
| eia:NG storage L48 weekly | 877 | https://www.eia.gov/dnav/ng/hist_xls/NW2_EPG0_SWO_R48_BCFw.xls | 2026-10-23T02:00 |
| eia:WCESTUS1 weekly crude ex-SPR | 2,299 | https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls | 2026-10-23T02:00 |
| firms:VIIRS NOAA-20 7d global (no key) | 478,400 | https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2 | 2026-10-23T02:00 |
| fiscaldata:auctions notes+bonds 2006+ | 1,863 | https://api.fiscaldata.treasury.gov/.../auctions_query | 2026-10-23T02:00 |
| yahoo:EWI | 6,291 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:EWJ | 6,291 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:FXI | 5,545 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:GDX | 5,138 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:GDXJ | 4,262 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:IBIT | 698 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:INR.AX | 4,767 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:KRE | 5,116 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:LAC | 768 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:UNG | 4,911 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:USO | 5,167 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:UUP | 4,944 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| yahoo:XLE | 6,291 | query1.finance.yahoo.com/v8/finance/chart | 2026-10-23T01:57 |
| FRED IT/DE/FR/GB 10y, WALCL, RRP, STLFSI4, DEXJPUS | 13,985 max | fred.stlouisfed.org/graph/fredgraph.csv | 2026-10-23 |

NASA FIRMS: the MAP_KEY is issued only through an email form on firms.modaps.eosdis.nasa.gov/api/map_key/ (submitting it is an outbound action that needs your email; not done). The **no-key public 7-day VIIRS NOAA-20 global CSV** was ingested instead (478,400 detections): Kolwezi (DRC) 12, Bayan Obo 2, Mountain Pass 1, Norilsk 1 detection within ±0.15° this week. VIIRS night lights (Black Marble) need an Earthdata login (yours).

## Gap audit: what a sceptical buyer (Citadel, Elliott, a sovereign fund, a trading house) would say is missing

| Gap | Why it matters | Free source? | Status |
|---|---|---|---|
| Point-in-time database (as-first-published values, vintages) | Revised macro/positioning data inflate backtests | ALFRED vintages (FRED) free | MISSING — biggest methodological gap |
| Survivorship-bias control | Index/ETF lists today exclude dead names | Wikipedia S&P changes, delisted prices (paid) | MISSING — S&P inclusion signal not built for this reason |
| Transaction costs and capacity | A signal that can't be traded at size is worthless | Spreads from exchange data (paid); bp assumptions | PARTIAL — flat bp costs + short borrow; no capacity model |
| Multiple-testing control | 23 signals tested → some pass by luck | Deflated Sharpe / Bonferroni | PARTIAL — t-stats shown; no deflation |
| AIS ship tracking / port congestion | Physical flows lead prices for oil, LNG, grains, metals | AISHub (exchange), NOAA MarineCadastre (US, lagged), UN Global Platform | MISSING |
| Sentinel-1 SAR (oil tank floating roofs, stockpiles) | Storage without clouds | Copernicus/Earth Search sentinel-1-grd | MISSING |
| Customs data (China GACC, Comtrade monthly) | Export-control effects show up in tonnages | UN Comtrade (free tier, key), GACC site | MISSING |
| LME/SHFE/CME warehouse stocks & cancelled warrants | Squeeze precursors in metals | LME (paid/delayed), SHFE weekly PDFs (free), CME depository reports (free xls) | MISSING — CME xls is the top free next step |
| JODI oil, USDA WASDE | Global balances | JODI csv (free), USDA WASDE xml (free) | MISSING |
| TIC foreign holdings, ECB SDW, BoJ | Who must sell Treasuries/JGBs | treasury.gov TIC (free), ECB data portal API (free), BoJ time-series (free) | PARTIAL — OECD 10y yields via FRED only |
| Sovereign CDS | Default-risk pricing | Paid (Markit) | MISSING (paid) |
| ESMA/FCA net short positions, Japan TDnet, HKEX DI, EDINET large holdings | Forced covering / stake-building | FCA daily xlsx (free), HKEX DI (free), EDINET API (free key) | MISSING — FCA short-position xlsx is the top free next step |
| Crypto: ETF flows, token unlocks, estate (Mt Gox/FTX) & government wallets | Mechanical supply | Issuer sites (free), on-chain explorers | MISSING (funding/OI/stablecoins only) |
| Power & grid (ENTSO-E, EIA-930) | Industrial activity, data-centre load | ENTSO-E (free key), EIA-930 (free) | MISSING |
| Patents, job postings, app data | Alt-data growth signals | USPTO/EPO bulk (free), job boards (ToS), app data (paid) | MISSING |
| ECB bank stress / EBA transparency | Bank forced sellers | EBA transparency exercise CSVs (free) | MISSING |
| Night lights (VIIRS Black Marble) | Operating activity | NASA LAADS (Earthdata login) | MISSING — needs Earthdata account (user) |
| Geology (MRDS/USMIN), GA, provincial registries | Deposit join for staking signal | USGS (403 to box), GA (403) | BLOCKED from box — try from user's machine |

Top 5 free ingests done now: EIA weekly crude, EIA weekly gas storage, Treasury auction results (1,863), BLM MLRS dated claims (hub `Created`), NASA FIRMS VIIRS 7-day. Also: FRED sovereign/liquidity/stress series and 14 extra price series.
Next free ingests by value: ALFRED point-in-time vintages, CME depository stocks, FCA short positions, EIA-930 grid, UN Comtrade (free key).

## Recommended new agents (charters only; not created)

- **Quant Validation.** Owns backtest hygiene for every signal and committee: point-in-time data (ALFRED vintages), publication lags, survivorship, multiple-testing (deflated Sharpe), cost and capacity models, and the kill rule. Nothing reaches the PDF or the ledger without its sign-off; it may only veto, never add signals. This is the agent a Citadel or Elliott diligence team would ask to meet first.
- **Commodities & Shipping desk.** Ingests physical-flow data — EIA/JODI/WASDE balances, CME/SHFE warehouse stocks and cancelled warrants, AIS/port congestion, Sentinel-1 storage — and maintains the commodity signals (S1–S4, S16). Output: weekly balance tables and squeeze watchlist for trading houses.
- **Crypto Flows desk.** Tracks mechanical crypto supply/demand: stablecoin mint/burn, perp funding and OI, ETF creations/redemptions, token unlock calendars, estate and government wallet movements. Maintains S10–S13 and owns the on-chain source list and its address labels.
- **Macro Regime agent.** Maintains the Dalio-style regime dashboard (real rates, credit, curve, debasement, COFER, central-bank gold, liquidity) with point-in-time vintages, and supplies the regime vote in the committee. Publishes a one-page regime note weekly.
- **Mining Geologist.** Joins deposits (MRDS/USMIN, GA, provincial databases, historical reports) to tenure (BLM MLRS, state/provincial registries) and owners (SEDAR+/ASX). Maintains the staking signals (S17, S20) and the satellite site list; flags controlled-mineral deposits on lapsed ground.
- **Ledger & Compliance clerk.** Runs the daily OpenTimestamps anchor, checks the chain, keeps every published call impersonal (no personalised advice), and keeps the licensing memo current. Escalates anything that looks like advice to a person.