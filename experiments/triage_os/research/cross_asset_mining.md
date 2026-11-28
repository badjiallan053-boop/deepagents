# TRIAGE Cross-Asset Radar

_As of 23 Oct 2026 (SGT). Public data only. Facts carry source + fetch date; **JUDGEMENT** marks our reads. Nothing sent._

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

## Mining + Land: what this layer does

Joins (1) export-control events from MOFCOM primary text, (2) US federal mining-claim status around documented deposits of controlled minerals (BLM MLRS), (3) Sentinel-2 scene coverage at three sites (Earth Search STAC), (4) supply concentration (USGS MCS 2026) and (5) a Dalio-style macro regime. The target signal — *staking surge or lapse near a historically documented controlled-mineral deposit* — is only partly testable today; we say exactly where.

## Backtest: junior/REE equities after Chinese export-control announcements

Excess return vs SPY (US) or ^AXJO (ASX), base = close before the announcement date. MOFCOM announcements land 17:00–18:00 Beijing, i.e. before the US open the same day.

| Event (MOFCOM, primary) | Ticker | +1d | +5d | +20d |
|---|---|---|---|---|
| 2023-07-03 Ga/Ge export controls (MOFCOM/GACC 2023 No.23, e | REMX | +1.6% | +3.5% | -5.1% |
| 2023-07-03 Ga/Ge export controls (MOFCOM/GACC 2023 No.23, e | MP | +1.1% | +11.2% | +1.0% |
| 2023-07-03 Ga/Ge export controls (MOFCOM/GACC 2023 No.23, e | LYC.AX | +0.3% | +5.7% | -7.0% |
| 2024-08-15 Antimony + superhard materials (2024 No.33, effe | PPTA | +22.0% | +29.5% | +28.7% |
| 2024-08-15 Antimony + superhard materials (2024 No.33, effe | REMX | +1.2% | +6.3% | +0.9% |
| 2025-04-04 Seven medium/heavy REEs incl. Sm, Gd, Tb, Dy, Lu | MP | -1.2% | -2.9% | -4.8% |
| 2025-04-04 Seven medium/heavy REEs incl. Sm, Gd, Tb, Dy, Lu | LYC.AX | +5.6% | +8.7% | +5.6% |
| 2025-04-04 Seven medium/heavy REEs incl. Sm, Gd, Tb, Dy, Lu | ARU.AX | -0.7% | +1.9% | +18.2% |
| 2025-04-04 Seven medium/heavy REEs incl. Sm, Gd, Tb, Dy, Lu | REMX | -1.9% | -3.2% | -3.9% |
| 2025-10-09 Ho, Er, Tm, Eu, Yb added (2025 No.57, effective  | MP | +2.7% | +28.5% | -22.8% |
| 2025-10-09 Ho, Er, Tm, Eu, Yb added (2025 No.57, effective  | LYC.AX | -4.0% | -1.4% | -34.6% |
| 2025-10-09 Ho, Er, Tm, Eu, Yb added (2025 No.57, effective  | ARU.AX | +8.5% | +45.1% | -10.7% |
| 2025-10-09 Ho, Er, Tm, Eu, Yb added (2025 No.57, effective  | REMX | +0.6% | +5.7% | -15.1% |

| Horizon | legs | mean excess | median | % positive |
|---|---|---|---|---|
| 1d | 13 | +2.8% | +1.1% | 69% |
| 5d | 13 | +10.7% | +5.7% | 77% |
| 20d | 13 | -3.8% | -4.8% | 38% |

**Honest read (JUDGEMENT):** four events, overlapping tickers — this is an event study, not a statistically powered backtest. Legs are not independent (same day, same theme). The April 2025 event coincides with the US tariff sell-off, which the market adjustment only partly removes. Use as a playbook with a known small-n, not a proven edge.

Event sources (fetched 23 Oct 2026, quote = effective-date clause):

- 2023-07-03: https://www.mofcom.gov.cn/zcfb/blgg/art/2023/art_ca2e9d349361441f847bdabac5d8331b.html — “本公告自2023年8月1日起正式实施” (found)
- 2024-08-15: https://www.mofcom.gov.cn/zcfb/zgdwjjmywg/art/2024/art_3840ffc4bd104de2aa673ccd74a646cc.html — “本公告自2024年9月15日起正式实施” (found)
- 2025-04-04: https://www.mofcom.gov.cn/zcfb/blgg/gg/2025/art/2025/art_5e663d0bfec7452dabd950d0f0e42153.html — “本公告自发布之日起正式实施” (found)
- 2025-10-09: https://www.mofcom.gov.cn/zcfb/blgg/gg/2025/art/2025/art_9510f263c3c246d8936fbfa684a58ca8.html — “本公告自2025年11月8日起正式实施” (found)

## Claims around controlled-mineral deposits (BLM MLRS, fetched 2026-10-23)

Box = ±0.15° around a district centre (JUDGEMENT: hand-placed, MRDS blocked).

| District | Mineral | Active | Filed/under review | Closed | Lapse ratio |
|---|---|---|---|---|---|
| Mountain Pass (CA) — REE | REE | 2,105 | 880 (42%) | 4,785 | 0.69 |
| Thacker Pass (NV) — lithium | Li | 2,273 | 10 (0%) | 8,136 | 0.78 |
| Stibnite (ID) — antimony/gold | Sb | 2,808 | 577 (21%) | 3,533 | 0.56 |
| Bear Lodge (WY) — REE | REE | 574 | 99 (17%) | 1,569 | 0.73 |
| Rhyolite Ridge (NV) — lithium/boron | Li | 1,642 | 333 (20%) | 6,831 | 0.81 |

Caveat: Public MLRS layer has LOC_DT null for every record (count where LOC_DT IS NOT NULL = 0, both layers, checked 23 Oct 2026). This MapServer has no dates; the BLM hub FeatureServers do (record 'Created'), and are used for the dated staking backtest (S17/S20) in the signal library.

**Read (JUDGEMENT):** Mountain Pass (42% of active claims still pending) and Stibnite (21%) show the heaviest fresh staking; Thacker Pass has ~0.4% pending against 8,136 closed claims — a lapse-dominated district. That fits the playbook (follow-on staking near a permitted controlled-mineral project) but is cross-sectional, not timed.

## Satellite: Sentinel-2 L2A scenes (Earth Search STAC)

| Site | Before (best ≤10% cloud) | After | scenes before/after |
|---|---|---|---|
| Mountain Pass (CA) — REE | S2B_11SPV_20241016_0_L2A | S2C_11SPV_20261001_0_L2A | 5/8 |
| Thacker Pass (NV) — lithium | S2A_11TMG_20240927_0_L2A | S2C_11TMG_20260907_0_L2A | 6/3 |
| Stibnite (ID) — antimony/gold | S2B_11TPK_20241108_0_L2A | S2C_11TPK_20261007_0_L2A | 13/13 |

Caveat: Whole-tile previews (110 km) — demonstrates the pipeline only; pit-scale change detection needs band COGs clipped to a site polygon (next step, rasterio not installed).

## Supply concentration (USGS MCS 2026, net import reliance / top import source)

| Mineral | Quoted line |
|---|---|
| Gallium | Gallium · 100% · 28%, CA · 22%, JP · 18%, CN · 16%, DE · 16%, OT |
| Antimony | Antimony · 91% · 55%, CN3 · 12%, BE · 8%, TH · 6%, IN · 19%, OT |
| Rare earths | Rare earths · 67% · 71%, CN3 · 13%, MY · 5%, EE 5%, JP 6%, OT |
| Germanium | Germanium · >50% · 41%, BE · 23%, CN · 17%, CA · 14%, DE · 5%, OT |
| Tungsten | Tungsten · >50% · 26%, CN3 · 14%, DE · 8%, BO · 8%, VN · 44%, OT |
| Graphite (natural) | Graphite (natural) · — · — · 71,000 · 100 · China · China · 1,400,000 · 78 · 1,800,000 |

Source: https://pubs.usgs.gov/periodicals/mcs2026/mcs2026.pdf

## Macro regime dashboard (Dalio-style)

| Pillar | Metric | Latest | Change | 20y pctile | Read (JUDGEMENT) | Source |
|---|---|---|---|---|---|---|
| Real rates | US 10y TIPS real yield | 2.77% (2026-10-20) | +1.03pp y/y | 99 | Restrictive | FRED DFII10 |
| Debt cycle (credit) | US HY OAS | 3.27% (2026-10-21) | +0.30pp y/y | 79 | Stress building | FRED BAMLH0A0HYM2 |
| Debt cycle (curve) | UST 10y–2y | 0.32pp (2026-10-21) | -0.21pp y/y | 27 | Re-steepening after inversion | FRED T10Y2Y |
| Currency debasement | Gold $/oz vs DXY, 1y | gold 4,061 (2026-10-22); DXY 101.6 | gold -0% / DXY +3% | 95 | Neutral | Yahoo GC=F, DX-Y.NYB |
| Reserve-currency share | USD share of FX reserves (IMF COFER, all reserves, post-2025Q3 method) | 56.7% (2026-Q2) | -2.2pp vs 2024-Q2 | — | Slow erosion | IMF COFER SDMX api.imf.org |
| Central-bank gold buying | WGC Gold Demand Trends (central banks, tonnes) | not ingested |  | — | GAP | WGC requires site download (Goldhub); not fetched this pass |
| Commodity super-cycle | Geo-mean(gold, copper, WTI) / S&P 500 | 0.018 (2026-10-22) |  | 13 | Commodities cheap vs equities | Yahoo GC=F, HG=F, CL=F, ^GSPC |
| Supply concentration | China share, controlled minerals (USGS MCS 2026) | see table |  | — | Extreme (Ga, graphite, REE, W) | USGS MCS 2026 |

## Gaps (honest)

- USGS MRDS/USMIN/NGDB bulk download: mrdata.usgs.gov returns 403 to the box (curl, 23 Oct) → deposit join uses hand-placed district centres (labelled).
- Geoscience Australia services.ga.gov.au 403; WA DMIRS/QLD, Ontario MLAS, BC MTO, GESTIM, BGS, EGDI, GEUS, Chile/Peru/DRC cadastres: not ingested this pass.
- BLM MLRS MapServer has no location dates; solved via hub FeatureServer 'Created' dates (2021+, MLRS-native serials). LR2000 legacy recordation dates still not ingested.
- NASA FIRMS MAP_KEY needs an email form (not submitted); no-key 7-day VIIRS CSV ingested; Black Marble night lights need Earthdata login.
- WGC central-bank gold: not fetched. SEDAR+/ASX owner mapping: not done.
- Internet Archive: search works (leads saved) but no deposit has been matched to a lapsed claim yet.

## Who pays for this layer (JUDGEMENT)

- Resource/royalty funds and critical-minerals desks (event playbook + claim-pressure map).
- Government/strategic buyers and DFIs tracking Western supply response.
- Credit desks holding miner/battery-chain paper: export-control shock → forced-seller map in the TRIAGE credit layer.

## TRIAGE Alpha Committee (adapted from AlphaAgents, arXiv:2508.11152)

Source paper: Zhao, Lyu, Jones, Garber, Pasquali, Mehta (BlackRock), *AlphaAgents: Large Language Model based Multi-Agents for Equity Portfolio Constructions*, arXiv:2508.11152v1, https://arxiv.org/html/2508.11152v1 (read in full 23 Oct 2026).

**What we kept from the paper:** role agents with data access restricted to their role (paper Table 1); the paper's coordinator prompt for debate ("every agent ... has a chance to speak at least twice. Each agent can not decide for the whole group ... You must invoke all agents before deciding to Terminate"); round-robin debate to consensus; explicit risk-neutral vs risk-averse profiles (§2.3); equal-weight portfolios from agent picks compared with single-agent portfolios and the benchmark using return and Sharpe (§3.2, §4.3); full debate logs kept for review.

**Role mapping:** paper Fundamental → *Forced Seller* (who must sell, from credit-spread shocks) and *LME* (CFTC managed-money positioning); paper Sentiment → *Signal/Radar* (trend/flow) and *Contrarian* (crowding); paper Valuation → *Valuation* (annualised return and volatility tools, exactly the paper's §2.2.3 formulas); added Macro (Dalio regime), which the paper names as future work.

**What we changed, and why (honest):** the agents are deterministic tool-based rules, not LLM calls. An LLM committee backtested on 2012–2026 would already 'know' those years from training data, so its backtest would be contaminated. The paper's prompts and our role prompts are stored in `committee.py` (PROMPTS) for a later LLM backend that runs only forward (live, paper-only). Debate rule: an agent whose conviction is below the mean conviction of disagreeing peers withdraws; nobody adopts a view without evidence; unresolved → majority, and the risk-averse profile takes no position on any dissent.

### Backtest — monthly, 22 cross-asset instruments, 2012-02-29 → 2026-09-30, long-only equal-weight, cash when no BUY

**risk-neutral, full period**

| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |
|---|---|---|---|---|
| Committee (debate) | 9.0% | 13.1% | 0.69 | -28.5% |
| Equal-weight benchmark | 8.5% | 13.2% | 0.65 | -29.1% |
| Single agent: signal | 10.4% | 19.6% | 0.53 | -44.5% |
| Single agent: valuation | 8.6% | 16.2% | 0.53 | -41.8% |
| Single agent: contrarian | -2.3% | 11.7% | -0.19 | -46.5% |
| Single agent: forced_seller | 0.1% | 0.4% | 0.26 | 0% |
| Single agent: lme | -4.1% | 17.9% | -0.23 | -63.4% |
| Single agent: macro | 1.0% | 2.5% | 0.39 | -1.6% |

**risk-neutral, 2021 onward (rules fixed before; treat as out-of-sample)**

| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |
|---|---|---|---|---|
| Committee (debate) | 10.2% | 14.9% | 0.68 | -28.5% |
| Equal-weight benchmark | 11.9% | 13.3% | 0.89 | -18.3% |
| Single agent: signal | 5.7% | 18.9% | 0.3 | -44.5% |
| Single agent: valuation | 12.6% | 17.3% | 0.73 | -31.6% |
| Single agent: contrarian | 2.6% | 10.2% | 0.26 | -10.5% |
| Single agent: forced_seller | 0.3% | 0.7% | 0.42 | 0% |
| Single agent: lme | -1.0% | 14.2% | -0.07 | -23.1% |
| Single agent: macro | 2.5% | 4.0% | 0.63 | -1.6% |

Committee BUY calls: 1988; share that beat the equal-weight month: 47%.

**risk-averse, full period**

| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |
|---|---|---|---|---|
| Committee (debate) | 7.4% | 14.0% | 0.53 | -38.5% |
| Equal-weight benchmark | 8.5% | 13.2% | 0.65 | -29.1% |
| Single agent: signal | 10.4% | 19.6% | 0.53 | -44.5% |
| Single agent: valuation | 6.3% | 10.0% | 0.63 | -27.6% |
| Single agent: contrarian | -2.3% | 11.7% | -0.19 | -46.5% |
| Single agent: forced_seller | 0.1% | 0.4% | 0.26 | 0% |
| Single agent: lme | -4.1% | 17.9% | -0.23 | -63.4% |
| Single agent: macro | 1.0% | 2.5% | 0.39 | -1.6% |

**risk-averse, 2021 onward (rules fixed before; treat as out-of-sample)**

| Portfolio | CAGR | Vol | Sharpe (no rf) | Max DD |
|---|---|---|---|---|
| Committee (debate) | 10.1% | 13.3% | 0.76 | -21.5% |
| Equal-weight benchmark | 11.9% | 13.3% | 0.89 | -18.3% |
| Single agent: signal | 5.7% | 18.9% | 0.3 | -44.5% |
| Single agent: valuation | 13.0% | 9.5% | 1.38 | -11.0% |
| Single agent: contrarian | 2.6% | 10.2% | 0.26 | -10.5% |
| Single agent: forced_seller | 0.3% | 0.7% | 0.42 | 0% |
| Single agent: lme | -1.0% | 14.2% | -0.07 | -23.1% |
| Single agent: macro | 2.5% | 4.0% | 0.63 | -1.6% |

Committee BUY calls: 1753; share that beat the equal-weight month: 47%.

**Honest result:** over the full period the risk-neutral committee edges the equal-weight benchmark (Sharpe 0.69 vs 0.65, max drawdown -28.5% vs -29.1%) and beats every single agent on Sharpe. From 2021 it **underperforms** the benchmark (Sharpe 0.68 vs 0.89), and the single Valuation agent is better than the committee (Sharpe 0.73; risk-averse 1.38). Only 47% of committee picks beat the equal-weight month. The paper's headline (multi-agent beats single agents and benchmark) is **not reproduced out-of-sample** here; debate mainly cuts drawdown versus single agents. Contrarian and LME agents lose money alone. This is why the product proof is the forward, hash-chained record, not this backtest.

### PAPER-ONLY live track record (hash-chained)

Ledger `track_record.jsonl`: 39 calls, chain verified = True. Each record holds entry (last public close), thesis (each agent's view), catalyst, exit rule, benchmark, previous hash and SHA-256 hash, logged in SGT. No trades placed; not advice to anyone.

| # | Kind | Instrument | Call | Entry | Entry date | Exit rule |
|---|---|---|---|---|---|---|
| 1 | cross-asset | SPY | BUY | 763.7 | 2026-10-22 | close at the next month-end committee or if th |
| 2 | cross-asset | EEM | SELL | 61.74 | 2026-10-22 | close at the next month-end committee or if th |
| 3 | cross-asset | I_HSI | SELL | 2.365e+04 | 2026-10-21 | close at the next month-end committee or if th |
| 4 | cross-asset | I_N225 | BUY | 6.462e+04 | 2026-10-21 | close at the next month-end committee or if th |
| 5 | cross-asset | I_STOXX50E | SELL | 6087 | 2026-10-22 | close at the next month-end committee or if th |
| 6 | cross-asset | COPX | SELL | 73.34 | 2026-10-22 | close at the next month-end committee or if th |
| 7 | cross-asset | SIL | SELL | 76.16 | 2026-10-22 | close at the next month-end committee or if th |
| 8 | cross-asset | URA | SELL | 34.15 | 2026-10-22 | close at the next month-end committee or if th |
| 9 | cross-asset | REMX | SELL | 51.63 | 2026-10-22 | close at the next month-end committee or if th |
| 10 | cross-asset | HYG | SELL | 77.1 | 2026-10-22 | close at the next month-end committee or if th |
| 11 | cross-asset | JNK | SELL | 92.56 | 2026-10-22 | close at the next month-end committee or if th |
| 12 | cross-asset | TLT | BUY | 81.64 | 2026-10-22 | close at the next month-end committee or if th |
| 13 | cross-asset | IEF | BUY | 91.24 | 2026-10-22 | close at the next month-end committee or if th |
| 14 | cross-asset | GLD | BUY | 370.5 | 2026-10-22 | close at the next month-end committee or if th |
| 15 | cross-asset | BTC-USD | SELL | 8.122e+04 | 2026-10-22 | close at the next month-end committee or if th |
| 16 | cross-asset | CL_F | BUY | 99.36 | 2026-10-22 | close at the next month-end committee or if th |
| 17 | cross-asset | HG_F | BUY | 6.418 | 2026-10-22 | close at the next month-end committee or if th |
| 18 | cross-asset | SI_F | BUY | 55.01 | 2026-10-22 | close at the next month-end committee or if th |
| 19 | cross-asset | NG_F | SELL | 2.819 | 2026-10-22 | close at the next month-end committee or if th |
| 20 | cross-asset | ZS_F | SELL | 1254 | 2026-10-22 | close at the next month-end committee or if th |
| 21 | cross-asset | ZW_F | BUY | 625.5 | 2026-10-22 | close at the next month-end committee or if th |
| 22 | credit-situation | Bigben Interactive — BIG.PA shares | WATCH | 0.069 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 23 | credit-situation | Nacon (56.72% owned by Bigben) — NACON.PA shares | WATCH | 0.053 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 24 | credit-situation | Agile Group — 6.875% senior perpetual (XS1785422 | AVOID (price > recovery) | 0.375 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 25 | credit-situation | BayWa / Kronos EKS €100m hybrid (DE000A351PD9) — | WATCH | 6 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 26 | credit-situation | Booster Precision Components (€60m bond NO001271 | WATCH | 39 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 27 | credit-situation | Zhenro Properties — 6158.HK shares | WATCH | 0.017 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 28 | credit-situation | KWG Group — 1813.HK shares | WATCH | 0.088 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 29 | credit-situation | Redco Properties — 1622.HK shares | WATCH | 0.141 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 30 | credit-situation | VPower Group — 1608.HK shares | WATCH | 0.031 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 31 | credit-situation | Branicks Group (€400m bond) — BRNK.DE shares | WATCH | 0.41 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 32 | credit-situation | China Aoyuan (secured assets) — 3883.HK shares | WATCH | 0.031 | 2026-10-22 | mark at catalyst date + 5 trading days; close  |
| 33 | committee-v2 | S6 HYG | FLAT (trigger not met) | 0 | 2026-10-23 | open only when trigger fires; hold 60d; costs  |
| 34 | committee-v2 | S8 EEM | FLAT (trigger not met) | 0 | 2026-10-23 | open only when trigger fires; hold 20d; costs  |
| 35 | committee-v2 | S13 BTC | FLAT (trigger not met) | 0 | 2026-10-23 | open only when trigger fires; hold 7d; costs p |
| 36 | committee-v2 | S15 EWI | FLAT (trigger not met) | 0 | 2026-10-23 | open only when trigger fires; hold 20d; costs  |
| 37 | committee-v2 | S16 REMX | FLAT (trigger not met) | 0 | 2026-10-23 | open only when trigger fires; hold 5d; costs p |
| 38 | committee-v2 | S21 SPY | FLAT (trigger not met) | 0 | 2026-10-23 | open only when trigger fires; hold 20d; costs  |
| 39 | committee-v2 | S23 SPY | FLAT (trigger not met) | 0 | 2026-10-23 | open only when trigger fires; hold 60d; costs  |

First hash 891dbead90cbf53a… → last hash eceda098e4ba71ae…. To make the record externally verifiable, publish each day's last hash somewhere timestamped (e.g. a public git commit or an OpenTimestamps proof) — a user action, not done.

### Monetisation (JUDGEMENT) — the track record is the product proof

1. **Signal subscription** (impersonal, same feed to all subscribers; no personalised recommendations): radar + committee calls + mining layer. Fits the publisher-style exclusions below only if it stays impersonal and regularly published.
2. **Model-portfolio licence** to managers/platforms who run the money themselves (B2B data/IP licence). Still check per jurisdiction whether the licensee relationship counts as advice.
3. **Later: SMA or fund** — needs a licence in each place the money is managed or marketed. The user must handle this with counsel; nothing here is legal advice.

| Jurisdiction | Source (fetched 23 Oct 2026) | Grade | Exact quote | What it means for TRIAGE |
|---|---|---|---|---|
| Singapore (MAS) | https://sso.agc.gov.sg/Act/SFA2001?ProvIds=Sc2- | PRIMARY (statute) | “fund management” means managing the property of, or operating, a collective investment scheme, or undertaking on behalf of a customer ... the management of a portfolio of capital markets products | An SMA or fund run from Singapore = regulated activity 'fund management' → capital markets services licence (or registered/licensed fund manager regime). Paid recommendations to Singapore clients may also be a financial advisory service under the Financial Advisers Act — FAA text not retrieved today (sso.agc.gov.sg timed out; mas.gov.sg licensing page in maintenance), so treat as OPEN. |
| United Kingdom (FCA) | https://www.legislation.gov.uk/ukpga/2000/8/section/19 | PRIMARY (statute) | No person may carry on a regulated activity in the United Kingdom, or purport to do so, unless he is— (a) an authorised person; or (b) an exempt person. | Managing an SMA/fund needs Part 4A permission. A non-personalised periodical/data service can fall in the RAO art. 54 exclusion (below) only if its principal purpose is not advice or leading persons to buy/sell; personal recommendations are carved out (art. 54(2A)). |
| United Kingdom (FCA) | https://www.legislation.gov.uk/uksi/2001/544/article/54 | PRIMARY (statute) | Paragraphs (1) and (2) do not apply to advice which is a personal recommendation falling within article 53(1A). | Signal subscriptions must stay non-personalised; FCA can certify a publication under art. 54(3). |
| United States (SEC) | https://www.law.cornell.edu/uscode/text/15/80b-2 | SECONDARY copy of statute (LII) | publisher of any bona fide newspaper, news magazine or business or financial publication of general and regular circulation | Advisers Act §202(a)(11)(D) publisher exclusion covers impersonal, regularly published research; an SMA or tailored advice requires SEC or state investment-adviser registration. |
| United States (CFTC) | https://www.law.cornell.edu/cfr/text/17/4.14 | SECONDARY copy of regulation (LII) | Providing commodity trading advice based on, or tailored to, the commodity interest or cash market positions or other circumstances or characteristics of particular clients | 17 CFR 4.14(a)(9): CTA registration exemption only if advice is not tailored and no client accounts are directed. Futures-based model portfolios or managed futures accounts → CTA/CPO registration with the CFTC/NFA. |

Gates before any money: (a) 12+ months of forward paper calls with the chain anchored publicly; (b) hit rate and excess return reported net of costs vs the stated benchmark; (c) a licensing opinion for each target jurisdiction.