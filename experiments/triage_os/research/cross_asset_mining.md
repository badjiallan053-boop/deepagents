# TRIAGE Cross-Asset Radar — Mining + Land layer and macro regime

_As of 23 Oct 2026 (SGT). Public data only. Facts carry source + fetch date; **JUDGEMENT** marks our reads. Nothing sent._

## What this layer does

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

Caveat: Public MLRS layer has LOC_DT null for every record (count where LOC_DT IS NOT NULL = 0, both layers, checked 23 Oct 2026). Dated staking surges therefore cannot be backtested from this endpoint; 'Filed/Under Review' share is used as a live proxy for fresh staking.

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
- BLM MLRS public layer has no location dates → staking-surge backtest impossible from it; needs MLRS bulk reports (reports.blm.gov) or county recorder data.
- NASA FIRMS needs a free MAP_KEY (registration = account creation, not done); VIIRS night lights not ingested.
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

Ledger `track_record.jsonl`: 32 calls, chain verified = True. Each record holds entry (last public close), thesis (each agent's view), catalyst, exit rule, benchmark, previous hash and SHA-256 hash, logged in SGT. No trades placed; not advice to anyone.

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

First hash 891dbead90cbf53a… → last hash ce04c096409fd7d7…. To make the record externally verifiable, publish each day's last hash somewhere timestamped (e.g. a public git commit or an OpenTimestamps proof) — a user action, not done.

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