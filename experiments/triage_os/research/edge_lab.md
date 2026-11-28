# TRIAGE Edge Lab: how the big funds find edge and what survives our tests

*As of 23 Oct 2026 (SGT). Public data, research only, not investment advice, paper ledger only. A grade means a primary document was read this pass; B means a book or the fund's own filings; C means secondary or judgement.*

**Bottom line.** Of seven mechanisms we could rebuild from free SEC data, **one survives** our rules (late-filer SHORT/AVOID). It is hard to trade because borrow is scarce. Spin-offs are FRAGILE, post-reorganisation equity is UNTESTED (too few clean events), and insider clusters, activist 13Ds and lockup shorts are KILLED. Merger arb, earnings drift and fallen angels need paid data.

## 1. The big-funds playbook

| Fund | Repeatable mechanism | Data it needs | Free public equivalent? | Primary source | Grade |
|---|---|---|---|---|---|
| Elliott | Holdouts and legal leverage: buy defaulted claims cheap, enforce contract terms (pari passu) until paid; activism in governance-weak firms | Bond indentures, court dockets, 13D | Partly: CourtListener/RECAP, EDGAR 13D, indentures in 8-K exhibits. PACER fees and docket depth are limits | https://www.govinfo.gov/content/pkg/USCOURTS-ca2-12-00109/pdf/USCOURTS-ca2-12-00109-0.pdf | A |
| Baupost / Klarman | Orphans: securities sold for non-economic reasons (post-reorg equity, spin-offs, claims, index exits) | Emergence dates, Form 10s, claims registers | Yes for emergences and spin-offs (EDGAR); claims prices are not free | Margin of Safety (1991, book); M2/M3 below | B |
| Oaktree / Apollo | Create control: buy the fulcrum tranche, then use LMEs/uptiers or the plan to take the equity | Credit agreements, lender groups, plan documents | Partly: 8-K credit agreements, our control maps. Loan prices are not free | https://www.ca5.uscourts.gov/opinions/pub/23/23-20181-CV0.pdf (Serta: uptier not an 'open market purchase') | A |
| Millennium / Citadel pods | Many small event edges with tight risk: index adds, spin-offs, lockups, merger arb, earnings drift | Index changes, deal terms, consensus estimates, borrow | Partly: EDGAR events are free; consensus, borrow and index history are paid | No public primary source (labelled JUDGEMENT); academic anchors: Field & Hanka 2001 JF (lockups), Mitchell & Pulvino 2001 JF (merger arb), Bernard & Thomas 1989 (PEAD) | C |
| Glencore / Trafigura / Vitol | Physical arbitrage: own storage and freight, earn location, time (contango) and quality spreads | Inventories, freight rates, forward curves | Partly: EIA stocks, SHFE/LME weekly stocks (SHFE in our v4), Comtrade flows. Freight and physical premia are paid | Company annual reports (e.g. Trafigura annual report); JUDGEMENT on the mechanism | B |
| Renaissance | Many weak, uncorrelated signals with clean data, careful costs and no single big bet | Tick data, corporate actions, clean histories | Partly: daily data free, survivorship-free history not free | Zuckerman, The Man Who Solved the Market (2019, book) | C |
| Burry | Read the documents nobody reads (prospectus tapes, filings), then buy cheap convex protection (CDS) | Prospectuses, 10-K/10-Q footnotes, CDS | Yes for documents (EDGAR full text); CDS not free | Scion 13F filings on EDGAR; Lewis, The Big Short (book) | B |
| Ackman | Asymmetric hedges: buy protection when it is near its cheapest (CDX IG ~50bp) before a regime break | CDS index spreads, macro triggers | Partly: FRED ICE OAS (3-year public window only) | https://pershingsquareholdings.com/wp-content/uploads/2020/03/Pershing-Square-Capital-Management-L.P.-Releases-Letter-to-Investors-March-26-2020.pdf ($27m cost, >$2.6bn proceeds) | A |
| Druckenmiller / Soros | Regime shifts: liquidity and policy turns, reflexive feedback loops; size up when right | Central-bank balance sheets, FX, policy | Yes: FRED/ALFRED (point-in-time vintages throttled this session) | Soros, The Alchemy of Finance (1987, book) | B |
| Bridgewater | Debt-cycle mechanics: debt service vs income, policy levers, deleveraging phases | Credit growth, debt service, rates | Yes: BIS, FRED, IMF | https://www.bridgewater.com/research-and-insights/a-template-for-understanding-big-debt-crises (Dalio, Big Debt Crises, free PDF) | B |

## 2. Backtests (filing-date point-in-time, costs, IS < 2022 ≤ OOS, one event per ticker per window)

| Mechanism | Status | Events found | Priced (coverage) | IS n / prec / mean / median | OOS n / prec / mean / median | OOS t |
|---|---|---|---|---|---|---|
| M1 insider cluster buys (>=3 insiders, >=$100k, 14d) | **KILLED** | 900 | 614 (68%) | 250 / 47% / -1.06% / -2.47% | 355 / 41% / -1.91% / -7.26% | -0.84 |
| M1b insider clusters in distressed names (price <=60% of 6m high) | **KILLED** | 175 | 175 (100%) | 59 / 51% / 8.41% / 0.77% | 116 / 44% / 2.3% / -12.09% | 0.46 |
| M2 spin-offs (Form 10-12B spinco, 250d) | **FRAGILE (IS disagrees)** | 114 | 91 (80%) | 43 / 47% / 104.46% / -4.94% | 48 / 52% / 45.95% / 4.13% | 1.28 |
| M3 post-reorganization equity (8-K 'emerged from chapter 11', 250d) | **UNTESTED (n_oos=6)** | 18 | 13 (72%) | 7 / 43% / 13.89% / -2.3% | 6 / 67% / 11.97% / 16.16% | 0.49 |
| M4 activist 13D initial filings (120d) | **KILLED** | 700 | 629 (90%) | 323 / 41% / -1.75% / -8.97% | 280 / 34% / 1.1% / -13.16% | 0.12 |
| M5 NT 10-K late filers, SHORT (120d) | **KEPT** | 700 | 615 (88%) | 297 / 60% / 5.98% / 10.19% | 318 / 67% / 14.93% / 15.0% | 5.4 |
| M6 IPO lockup expiry window, SHORT (day 173 -> +10 trading days) | **KILLED** | 700 | 648 (93%) | 272 / 57% / 2.23% / 1.78% | 376 / 54% / -1.14% / 1.01% | -0.66 |
| M7 merger-arb spread | **UNTESTED (data)** | – | – | Targets delist on completion, so Yahoo drops most of them, and offer prices are not in a free structured feed. A survivorship-clean test needs CRSP-style delisting returns. | | |
| M8 earnings-revision / PEAD | **UNTESTED (data)** | – | – | No free point-in-time consensus estimates. A price-reaction proxy is possible but was not run this pass. | | |
| M9 fallen angels / forced IG selling | **UNTESTED (data)** | – | – | No free point-in-time rating-action history; agency press releases are not bulk-downloadable without registration. | | |

**How to read this.**
- Means are skewed by a few huge winners; check the medians.
- Spin-off OOS mean +46% vs median +4% is a handful of multi-baggers, not a reliable edge. In-sample precision of 47% makes it FRAGILE.
- **Late-filer short:** borrow cost decides it. OOS excess after a 100bp cost: 14.93%. After borrow at 5% / 20% / 50% a year: 5%/yr: 12.53%, 20%/yr: 5.33%, 50%/yr: -9.07%. Most of these names are sub-$1, often not borrowable. Treat it as an **AVOID / risk** signal, not a trade.
- **Survivorship:** Yahoo drops delisted tickers. Coverage is 68–93%. Missing names are disproportionately failures, so long results are biased UP and the short result is biased DOWN (conservative).
- **Insider clusters killed:** the academic edge (Cohen-Malloy-Pomorski) uses 'opportunistic' insiders and pre-2010 data. Our simple ≥3-insider rule over 2018–2026 loses money vs IWM after 50bp.
- **Lockup short:** worked in-sample (t = 2.55) and failed OOS. It looks arbitraged away, as the literature predicts.
- **Post-reorg equity:** the 'new equity' filter leaves 13 clean events. Our EDGAR text-search dating is too coarse; it needs court confirmation dates (our Ch11 data) to reach n ≥ 8 OOS.

## 3. What we were overlooking (audit) and what we built

| Item | Why a billionaire sees it | Status |
|---|---|---|
| Deadlines that force behaviour | SEC Rule 12b-25: a late filer gets 15 days (10-K) or 5 days (10-Q). Missing it leads to exchange deficiency notices and loss of S-3 eligibility, which forces dilutive financing. Public on EDGAR, but rarely aggregated. | IMPLEMENTED: O2 late-filer watch + M5 backtest (KEPT on the short side, borrow-sensitive) |
| Supply released on a fixed date | IPO lockups end around day 180. The S-1 states it; nobody aggregates it for small IPOs. | IMPLEMENTED: O1 forward lockup calendar (the backtest decayed: IS works, OOS fails) |
| Public but not joined | Insider buying, a new activist 13D and our restructuring calendar sit in separate databases. Joining them is the edge a desk with time has. | IMPLEMENTED: O3 convergence screen (1 hit, a closed-end fund self-filing, so not meaningful today) |
| Second-order effects | China export-control suspension expires 27 Nov 2026 (MOFCOM Ann. 72/2025) → US defence primes need non-China Sb/Ga/Ge → small Western suppliers (Bottleneck Hunt). | Already in Bottleneck Hunt |
| Schedule 13D form-type change | EDGAR now files new 13Ds as 'SCHEDULE 13D'. Screens still keyed to 'SC 13D' silently miss 2025+ activism. We found this in our own pipeline. | FIXED in the live layer; M4 backtest is 2018-2024 only |

## 4. Live list (only from the mechanism that passed)

Paper AVOID / SHORT-WATCH calls from M5 (NT 10-K filed in the last 60 days, priced this week). Each is in the hash-chained ledger. **Kill condition for every row:** the company files its 10-K within the 12b-25 extension AND the stock beats IWM by >20% within 60 days of the NT filing.

| Ticker | Company | NT filed | Last px | Deadline | Window end | Source |
|---|---|---|---|---|---|---|
| AWCA | Awaysis Capital, Inc. | 2026-09-29 | 0.035 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/1021917/0001493152-26-044681.txt |
| CBLO | C2 Blockchain, Inc. | 2026-09-29 | 0.0298 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/1882781/0001882781-26-000044.txt |
| GTLL | GLOBAL TECHNOLOGIES LTD | 2026-09-29 | 0.0001 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/932021/0001493152-26-044925.txt |
| HSCT | HOOPS SCOUTING USA | 2026-09-29 | 0.39 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/1721056/0001477932-26-005903.txt |
| LNAI | Lunai Bioworks Inc. | 2026-09-29 | 0.47 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/1527728/0001731122-26-001299.txt |
| NVA-WT | Nova Minerals Corp | 2026-09-29 | 5.97 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/1852551/0001493152-26-044708.txt |
| SGLY | Singularity Future Technology Ltd. | 2026-09-29 | 0.4142 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/1422892/0001213900-26-104272.txt |
| VIPZ | VIP Play, Inc. | 2026-09-29 | 0.189 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/1832161/0001493152-26-044847.txt |
| VISM | VISIUM TECHNOLOGIES, INC. | 2026-09-29 | 0.0007 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-14 | 2027-03-22 | https://www.sec.gov/Archives/edgar/data/1082733/0001654954-26-008617.txt |
| ALDS | APPlife Digital Solutions Inc | 2026-09-28 | 0.09 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-13 | 2027-03-21 | https://www.sec.gov/Archives/edgar/data/1755101/0001096906-26-001457.txt |
| ADVB | Advanced Biomed Inc. | 2026-09-28 | 3.46 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-13 | 2027-03-21 | https://www.sec.gov/Archives/edgar/data/1941029/0001213900-26-104071.txt |
| BNET | BION ENVIRONMENTAL TECHNOLOGIES INC | 2026-09-28 | 0.247 | 15 calendar-day extension (Rule 12b-25) ends 2026-10-13 | 2027-03-21 | https://www.sec.gov/Archives/edgar/data/875729/0001079973-26-001291.txt |

### Context lists (not ledger calls: mechanisms not KEPT)

**Upcoming lockup expiries (O1), next 75 days:**

| Ticker | Company | IPO | Est. expiry | Since IPO |
|---|---|---|---|---|
| PS | PERSHING SQUARE INC. | 2026-04-29 | 2026-10-26 | 86% |
| PSUS | Pershing Square USA, Ltd. | 2026-04-29 | 2026-10-26 | -10% |
| AVLN | Avalyn Pharma Inc. | 2026-04-30 | 2026-10-27 | -8% |
| SBMT | SILVER BOW MINING CORP. | 2026-04-30 | 2026-10-27 | -41% |
| COAG | Hemab Therapeutics Holdings, Inc. | 2026-05-01 | 2026-10-28 | 2% |
| SPTX | Seaport Therapeutics, Inc. | 2026-05-01 | 2026-10-28 | 5% |
| REA | Rare Earths Americas, Inc. | 2026-05-05 | 2026-11-01 | -62% |
| HAWK | HawkEye 360, Inc. | 2026-05-07 | 2026-11-03 | -66% |
| SUJA | SUJA LIFE, INC. | 2026-05-07 | 2026-11-03 | -46% |
| MOBI | Mobia Medical, Inc. | 2026-05-08 | 2026-11-04 | -10% |
| ODTX | Odyssey Therapeutics, Inc. | 2026-05-08 | 2026-11-04 | 16% |
| FRVO | Fervo Energy Co | 2026-05-13 | 2026-11-09 | -77% |
| GMRS | GMR Solutions Inc. | 2026-05-13 | 2026-11-09 | -23% |
| AIAI | AIAI Holdings Corp | 2026-05-14 | 2026-11-10 | -86% |
| BXDC | Blackstone Digital Infrastructure Trust Inc. | 2026-05-14 | 2026-11-10 | -20% |

**Spin-offs in registration (Form 10 filed in the last 150 days; FRAGILE mechanism):**

- Vylor Inc. (VYLR): first filed 2026-06-29, https://www.sec.gov/Archives/edgar/data/2128626/0001193125-26-288697.txt
- ADI GLOBAL DISTRIBUTION INC. (ADIG): first filed 2026-06-04, https://www.sec.gov/Archives/edgar/data/2105139/0001213900-26-065286.txt
- Honeywell Aerospace Inc. (HONA): first filed 2026-06-08, https://www.sec.gov/Archives/edgar/data/2089271/0001628280-26-041399.txt
- Midera Food Processing, Inc. (MFP): first filed 2026-05-27, https://www.sec.gov/Archives/edgar/data/2088281/0001193125-26-241891.txt
- Mobility Global Inc. (MBGL): first filed 2026-05-27, https://www.sec.gov/Archives/edgar/data/2090312/0001104659-26-066592.txt
- ALEXANDER TECH CORP (no ticker yet): first filed 2026-07-30, https://www.sec.gov/Archives/edgar/data/1347491/0001347491-26-000004.txt
- Archer SpinCo, Inc. (AXM): first filed 2026-09-15, https://www.sec.gov/Archives/edgar/data/2130999/0001193125-26-391224.txt
- MSGS Spinco, Inc. (MSGR): first filed 2026-08-14, https://www.sec.gov/Archives/edgar/data/2132873/0001193125-26-352589.txt
- Private Bancorp of America, Inc. (PBAM): first filed 2026-07-13, https://www.sec.gov/Archives/edgar/data/1705284/0001193125-26-302001.txt
- Trinzic, Inc. (TZIC): first filed 2026-09-30, https://www.sec.gov/Archives/edgar/data/2101664/0001140361-26-038098.txt
- West Coast Community Bancorp (WCCB): first filed 2026-08-31, https://www.sec.gov/Archives/edgar/data/2105965/0001628280-26-059592.txt
- BioStem Technologies, Inc. (BSEM): first filed 2026-07-24, https://www.sec.gov/Archives/edgar/data/1658678/0001213900-26-081252.txt

**Live open-market insider clusters (≥3 insiders, ≥$100k, 21 days; KILLED mechanism, shown for transparency):** BPRE (3 insiders, $23,285,979), ACCV (5 insiders, $4,098,600), HEI-A (8 insiders, $1,400,595), AGMB (3 insiders, $311,170), DX-PD (3 insiders, $267,230), IMSRW (3 insiders, $112,279)

## 5. Gaps

- **Non-US insider data:** UK RNS director dealings, ASX Appendix 3Y and Japan large-holder reports are not ingested. There is no free bulk feed; the RNS and ASX pages need scraping, deferred to stay within the Apify cap. Crustdata/Apify spend: $0.
- **Merger arb, PEAD, fallen angels:** need paid data (delisting returns, consensus estimates, rating history).
- **Index deletions:** S&P/Russell change history is not free.
- **Post-reorg dating:** emergence is dated from 8-K text, not from confirmation orders.
- **ALFRED:** point-in-time vintages still fail (the host keeps refusing this box), so the macro point-in-time rebuild is still pending.
- **UN Comtrade:** 213 monthly China-export rows (2022+) arrived. They are not yet joined to signals.
- **Form 4 bulk data** stops at 2026Q1; the live layer reads filings directly.

## 6. Post-reorganisation equity, worldwide (M3 expanded)

**Event set:** 41 events with a dated, priced new equity (by region: US 30, FR 6, NO 1, JP 1, ID 1, HK 1, NO/US 1). That is far short of the 150 target. From 605 US filers found in EDGAR full-text search, 244 had no confirmation/effective 8-K we could date, 63 kept their old equity, and **40 are MISSING**: new equity was registered (Form 8-A) but there is no current ticker or Yahoo price (delisted, went dark, renamed).

**Dating:**
- Confirmation is the first 8-K Item 1.03 citing the confirmation order (filed within 4 business days of the order). CourtListener dockets were not queried.
- The effective date is the next 8-K with Item 5.01/3.03/2.01.
- Non-US events (11) are a curated JUDGEMENT list (France sauvegarde, Norway, Japan JAL, Indonesia Garuda, HK Sunac) and need primary verification.

| Test | Status | IS n / prec / mean / median | OOS n / prec / mean / median | OOS t |
|---|---|---|---|---|
| ALL from day 0, 20d | **KILLED** | 21 / 67% / 104.55% / 11.85% | 20 / 55% / -0.01% / 1.01% | -0.0 |
| ALL from day 0, 60d | **KEPT** | 21 / 62% / 88.01% / 10.21% | 19 / 63% / 0.09% / 3.69% | 0.02 |
| ALL from day 0, 120d | **KEPT** | 21 / 52% / 106.46% / 4.05% | 18 / 67% / 8.61% / 15.9% | 1.24 |
| ALL from day 0, 250d | **KEPT** | 21 / 52% / 126.27% / 8.29% | 16 / 69% / 10.07% / 16.97% | 0.93 |
| ALL from day 5, 20d | **KEPT** | 21 / 57% / 13.32% / 1.44% | 19 / 63% / 3.17% / 2.54% | 1.99 |
| ALL from day 5, 60d | **FRAGILE (IS disagrees)** | 21 / 48% / 3.82% / -3.72% | 18 / 78% / 5.82% / 12.35% | 1.06 |
| ALL from day 5, 120d | **FRAGILE (IS disagrees)** | 21 / 33% / 6.51% / -7.16% | 17 / 65% / 10.96% / 20.72% | 1.35 |
| ALL from day 5, 250d | **FRAGILE (IS disagrees)** | 21 / 38% / 9.24% / -22.27% | 14 / 71% / 12.28% / 22.85% | 0.94 |
| US only, day 5, 250d | **UNTESTED (n_oos=7)** | 18 / 39% / 17.65% / -18.65% | 7 / 71% / 12.08% / 21.29% | 0.49 |
| Non-US (curated), day 5, 250d | **UNTESTED (n_oos=7)** | 3 / 33% / -41.22% / -50.15% | 7 / 71% / 12.47% / 24.42% | 1.14 |
| Small (first-20d $ volume below median), day 5, 250d | **UNTESTED (n_oos=5)** | 13 / 31% / 27.78% / -22.27% | 5 / 100% / 42.76% / 43.65% | 3.8 |
| Large (above median), day 5, 250d | **KILLED** | 8 / 50% / -20.89% / -30.29% | 9 / 56% / -4.66% / 11.14% | -0.27 |
| Creditor ownership >50% (8-K text), day 5, 250d | **UNTESTED (n_oos=3)** | 1 / 0% / -102.59% / -102.59% | 3 / 100% / 49.64% / 68.04% | 2.58 |
| Backstop mentioned, day 5, 250d | **UNTESTED (n_oos=3)** | 9 / 44% / -8.09% / -15.03% | 3 / 100% / 48.16% / 65.29% | 2.6 |
| No backstop mentioned, day 5, 250d | **UNTESTED (n_oos=4)** | 9 / 33% / 43.38% / -22.27% | 4 / 50% / -14.97% / -15.81% | -0.4 |
| SUB insider open-market buy within 90d of first trade, entry day 90 -> 250d | **UNTESTED (n_oos=5)** | 7 / 57% / 2.6% / 17.51% | 5 / 80% / 18.48% / 25.85% | 1.05 |
| SUB no insider buy, entry day 90 -> 250d | **UNTESTED (n_oos=3)** | 11 / 36% / -16.25% / -17.57% | 3 / 33% / -22.96% / -27.7% | -0.73 |
| SUB orphan dump: first 20d excess return < -20%, entry day 20 -> 250d | **UNTESTED (n_oos=0)** | 2 / 0% / -36.06% / -36.06% | 0 / –% / –% / –% | – |
| SUB no early dump, entry day 20 -> 250d | **FRAGILE (IS disagrees)** | 19 / 47% / -11.38% / -1.84% | 16 / 69% / 9.14% / 11.11% | 0.76 |

**Survivorship sensitivity:** with missing names excluded, day-5/250d is **FRAGILE (IS disagrees)**. With the 40 missing names set to -100%, it is **KILLED** (OOS mean -53.77%).

**Verdict: M3 does not pass.** The day-0 'KEPT' rows have t-statistics of 0.02–1.2. That is noise that only passes the mechanical rule, and it flips to KILLED under the survivorship test.

**Best sub-signal:** insider open-market buying within 90 days of first trade (OOS 5 events, 80% wins, +18.5% vs -23.0% for no insider buy). Directionally consistent with the Klarman 'orphan' story, but UNTESTED (n < 8).

**Not testable with free data:** creditor ownership above 50% and backstop flags come from 8-K text and cover too few events; sell-side coverage counts and CLO forced-selling flows are not available.

**Upcoming emergences worldwide** (paper WATCH, calendar only, mechanism vetoed; existing equity is usually diluted 90–100%):

| Ticker | Company | Country | Date | Event | Last px |
|---|---|---|---|---|---|
| BIG.PA | Bigben Interactive | FR | 2026-12-09 | plan hearing (proceeding extended to 17 Dec 2026) | 0.0689999982714653 |
| NACON.PA | Nacon | FR | 2027-03-02 | end of extended observation period | 0.05290000140666962 |
| 3383.HK | Agile Group | HK/CN | 2026-11-16 | RSA launch (JUDGEMENT date) | 0.14300000667572021 |
| BRNK.DE | Branicks Group | DE | 2027-03-31 | plan effective by end-2026 or 31 Mar 2027 at the latest | 0.4099999964237213 |
| 1B0.SI | mm2 Asia | SG | 2026-11-04 | scheme meetings; moratorium to 21 Nov | 0.003000000026077032 |
| 6158.HK | Zhenro Properties | HK/CN | 2026-11-09 | adjourned petition hearing | 0.017000000923871994 |
| 1813.HK | KWG Group | HK/CN | 2027-03-31 | scheme timetable not announced (JUDGEMENT window) | 0.08799999952316284 |
| 1622.HK | Redco Properties | HK/CN | 2027-03-31 | sanction hearing not announced (JUDGEMENT window) | 0.14100000262260437 |
| 1608.HK | VPower Group | HK | 2027-03-31 | meeting notice to follow (JUDGEMENT window) | 0.03099999949336052 |
| FOOD.TO | Goodfood Market | CA | 2027-03-31 | SISP milestones (JUDGEMENT window) | 0.029999999329447746 |

## 7. BNF and CIS rebuilt

**Sources:** BNF (Takashi Kotegawa) is known from his rare press interviews (Nikkei and Weekly SPA!, summarised in Japanese trading books). CIS is known from his book 『一億円稼ぐ…』 and X posts. Both are labelled C: secondary, not primary-verified this pass.

**Rules tested:**
- BNF: buy when the close is 20/25/30% or more below its 25-day average (kairi-ritsu), hold 1–5 days.
- CIS: buy a new 250-day closing high on at least 2x the 50-day volume, exit on a 7% trailing stop (max 60 days).

**Test setup:** entry at the next close; costs 25bp (JP large), 40bp (JP small), 10bp (US), 20bp (EU), 30bp (HK), 75bp (US small). Universe: JP TOPIX Core30/Large70/Mid400 (491), Small1 (482), US large (98), EU large (50), HK large (40), and our US event/distressed universe (1500). Out-of-sample from 2021.

| Test | Status | IS n / prec / mean / median | OOS n / prec / mean / median | OOS t |
|---|---|---|---|---|
| BNF JP large/mid kairi<=-20% hold 1d | **KILLED** | 918 / 51% / 0.07% / 0.03% | 451 / 37% / -0.6% / -1.18% | -3.06 |
| BNF JP large/mid kairi<=-20% hold 3d | **KILLED** | 918 / 52% / 0.29% / 0.36% | 450 / 48% / 0.56% / -0.29% | 1.7 |
| BNF JP large/mid kairi<=-20% hold 5d | **KEPT** | 918 / 52% / 0.69% / 0.39% | 448 / 52% / 1.13% / 0.34% | 2.76 |
| BNF JP large/mid kairi<=-25% hold 1d | **KILLED** | 374 / 42% / -0.57% / -0.68% | 175 / 49% / 0.69% / -0.32% | 1.85 |
| BNF JP large/mid kairi<=-25% hold 3d | **FRAGILE (IS disagrees)** | 374 / 47% / -0.38% / -0.43% | 175 / 57% / 1.94% / 1.03% | 3.15 |
| BNF JP large/mid kairi<=-25% hold 5d | **KEPT** | 374 / 53% / 1.27% / 0.71% | 174 / 61% / 2.87% / 1.81% | 4.05 |
| BNF JP large/mid kairi<=-30% hold 1d | **KILLED** | 137 / 45% / 0.2% / -1.16% | 72 / 50% / 1.09% / 0.25% | 1.67 |
| BNF JP large/mid kairi<=-30% hold 3d | **KEPT** | 137 / 52% / 0.81% / 0.33% | 72 / 58% / 2.14% / 0.54% | 2.31 |
| BNF JP large/mid kairi<=-30% hold 5d | **KEPT** | 137 / 58% / 3.65% / 2.73% | 72 / 69% / 3.92% / 3.15% | 3.5 |
| BNF US large kairi<=-20% hold 3d | **KILLED** | 266 / 39% / -2.11% / -1.87% | 271 / 51% / 0.74% / 0.14% | 1.62 |
| BNF US large kairi<=-20% hold 5d | **FRAGILE (IS disagrees)** | 266 / 43% / -2.4% / -1.86% | 271 / 57% / 1.42% / 1.19% | 2.77 |
| BNF EU large kairi<=-20% hold 3d | **KILLED** | 133 / 52% / 0.85% / 0.12% | 41 / 49% / -0.02% / -1.25% | -0.02 |
| BNF EU large kairi<=-20% hold 5d | **KILLED** | 133 / 50% / 0.44% / 0.18% | 41 / 49% / 0.02% / -0.25% | 0.02 |
| BNF HK large kairi<=-20% hold 3d | **KEPT** | 96 / 68% / 2.44% / 2.15% | 151 / 52% / 1.72% / 0.36% | 1.98 |
| BNF HK large kairi<=-20% hold 5d | **KEPT** | 96 / 67% / 3.13% / 2.32% | 151 / 54% / 2.21% / 0.71% | 2.55 |
| BNF distressed/event universe (US small) kairi<=-20% hold 3d | **KILLED** | 6322 / 43% / 36.34% / -0.97% | 17459 / 43% / 21.01% / -1.29% | 2.06 |
| BNF distressed/event universe (US small) kairi<=-20% hold 5d | **KILLED** | 6322 / 45% / 38.56% / -1.0% | 17386 / 43% / 27.57% / -1.65% | 2.49 |
| CIS JP large/mid breakout on 2x volume, 7% trailing stop | **KILLED** | 3597 / 44% / 1.99% / -1.09% | 2434 / 39% / -0.59% / -2.28% | -0.98 |
| CIS JP small1 breakout on 2x volume, 7% trailing stop | **KILLED** | 4532 / 41% / 1.98% / -1.95% | 2864 / 39% / -0.75% / -2.31% | -1.23 |
| CIS US large breakout on 2x volume, 7% trailing stop | **KILLED** | 637 / 46% / 1.4% / -0.89% | 365 / 38% / 0.37% / -2.11% | 0.69 |

**Honest reading:**
- BNF holds in Japanese large and mid caps on a 5-day hold. The deepest discount does best: -30% gives 72 OOS events, 69% wins, +3.9%, t = 3.5; -25% gives 174 events, +2.9%, t = 4.05. It also holds in HK.
- It fails in EU, in the US distressed universe (the mean is driven by bad-tick outliers; the median is negative), and on 1-day holds.
- **Survivorship is the main risk.** The JP universe is today's TOPIX members, which excludes exactly the names that kept falling. Mean-reversion results are biased upward, so treat them as an upper bound.
- **Multiple testing:** 20 variants were run. The two strongest (t of 3.5 and 4.05) would survive a Bonferroni cut at 5%. The -20% variants would not.
- **CIS is KILLED everywhere out of sample** (38–39% wins, negative medians), despite strong in-sample t-values (7.5–8.1). The simple breakout rule decayed after 2021.

**Live BNF triggers today** (logged as paper WATCH with a 5-day exit and a kill rule): 285A.T (kairi -24.1%, JP kairi<=-20% 5d), 3436.T (kairi -22.5%, JP kairi<=-20% 5d), 5801.T (kairi -22.6%, JP kairi<=-20% 5d), 6525.T (kairi -23.4%, JP kairi<=-20% 5d), 9984.T (kairi -25.7%, JP kairi<=-25% 5d), 0981.HK (kairi -20.4%, HK kairi<=-20% 5d). Context only (FRAGILE or KILLED variants): 6532.T CIS, 9889.T CIS, INTC BNF, ROKU CIS, BIIB CIS, KSS CIS.

## 8. Data joins and point-in-time

**China exports (UN Comtrade public preview; data available through the month shown), joined to the export-control names:**

| HS | Product | Our names | Last month | Last 12m kg | Prior 12m kg | YoY |
|---|---|---|---|---|---|---|
| 811292 | Ga/Ge/In/Nb/Re unwrought & powders | Ga/Ge (LPTH germanium-free optics; 5N Plus) | 202412 | 1,763,062 | 1,681,614 | 5% |
| 8110 | antimony | antimony (UAMY, LRV.AX) | 202409 | 3,502,515 | 5,702,110 | -39% |
| 2846 | rare-earth compounds | rare-earth compounds (UCU.V, ARA.TO, IXR.AX, AREC) | 202412 | 46,538,472 | 42,856,133 | 9% |
| 280530 | rare-earth metals | rare-earth metals (UCU.V, ARA.TO) | 202412 | 8,906,067 | 9,452,796 | -6% |
| 250410 | natural graphite powder/flakes | natural graphite (GPH.V) | 202412 | 126,257,972 | 169,439,148 | -25% |
| 810194 | tungsten unwrought | tungsten (TUN.L, GMET.L) | 202412 | 1,145,859 | 967,952 | 18% |

**Comtrade notes:**
- The preview stops at Dec 2024 (Sep 2024 for antimony), so it captures the 2023–24 export controls, not 2025–26.
- Antimony exports fell 39% year on year and graphite 25%, consistent with the controls.
- Tungsten rose 18% and gallium/germanium rose 5%.

**Point-in-time Fed balance sheet:** ALFRED refused this box again. Fallback: the Fed's own H.4.1 release archive (each release is what the public saw that Thursday). 345 weekly releases parsed so far (2015-01-01 to 2021-08-12), fetch still running. The S21 point-in-time re-test runs once the archive reaches 2026.

## 9. Gaps and access notes

- **London Strategic Edge:** the free key is issued only through the website sign-up at https://londonstrategicedge.com/data. There is no programmatic issuance in the client (lse-data, MIT). Stopped for the user. Once a key is saved under /workspace/triage_os_data/.secrets, LSE can fill the survivorship gap (delisted US names back to 2003), add options greeks and insider data, and cross-check macro history.
- **This pass (5):** see section 10.
- **Live layer:** live_service.py polls Yahoo every 2 min in market hours and every 30 min otherwise. Quotes may be delayed 15–20 min (shown per symbol). Served at /api/live and in the Live tab.

## 10. Pass 5: free substitutes, non-US insiders, connector checks (23 Oct 2026, 04:47–05:10 SGT)

| Test | Status | IS n / prec / mean / median | OOS n / prec / mean / median | OOS t | Coverage |
|---|---|---|---|---|---|
| PEAD long, top-decile SUE (60d vs IWM, 20bp) | **KILLED** | 244 / 46% / 0.57% / -1.07% | 556 / 45% / -0.38% / -2.69% | -0.31 | 89% |
| PEAD short, bottom-decile SUE (60d vs IWM, 20bp) | **KEPT** | 232 / 59% / 1.77% / 3.98% | 548 / 59% / 3.33% / 4.45% | 2.69 | 88% |

- **PEAD build:** SEC XBRL frames (EarningsPerShareBasic, quarterly), surprise = seasonal random walk scaled by the stdev of the last 8 seasonal changes; dated by the 10-Q filing date from form.idx; decile within filing month. Q4 is omitted (10-K frames are annual). The short leg is KEPT before borrow costs; tickers come from today's SEC list, so dead firms are missing and the short result is biased DOWN (conservative). The long leg is KILLED.
- **Fallen angels, index deletions, merger arb:** NOT built. S&P and Moody's press-release archives need a login; S&P DJI/FTSE Russell notice pages are JS-only; merger-arb targets are exactly the names Yahoo drops on completion, so a test without delisted prices would be meaningless. LSE was meant to fix that (below).
- **London Strategic Edge:** LSE_API_KEY is set, but its value is a template line (an 'export ...="lse_..."' with a '...' placeholder and a comment), not a key. The API answered 'invalid api key' on /vault/usage. 0 of 10 hourly downloads used. Survivorship, greeks and insider data via LSE were NOT done.
- **UK PDMR (Investegate company pages, FTSE 100 sample, 2020–2026):** scraping runs in the background at about 1 request/s; the cluster test is pending. The search page is reCAPTCHA-protected and was not bypassed. The purchase parser is noisy (award and acquisition wording).
- **Apify (spend log):** Japan 5% large-holder filings, Oct 1–22 2026, 37 rows (11 flagged potential activist), about $1.85. ASX announcements for 20 critical-minerals names, 50 rows (2 'Final Director's Interest Notice', no 3Y buys), about $0.25. **Total about $2.10 of $15.** These are recent snapshots only, so they cannot backtest; none of the 37 Japan issuers is a BNF watch, so the BNF-JP insider filter is UNTESTED. Historical EDINET needs a free key, which requires a sign-up.
- **Crustdata (18 of 300 credits; the account balance was only 30, now 12):** headcount YoY: SoftBank +6.7%, SMIC +1.3%, Kokusai +9.0%, Furukawa +7.0%, Coherent +8.2%, Lumentum +3.8%, Lynas +5.2%. Kioxia and SUMCO matched European sales subsidiaries, so ignore them. Web traffic MoM (from Crustdata, standing in for Ahrefs): SMIC +11%, Lynas +12%, Kokusai −14%, SUMCO −33% (subsidiary site).
- **X crowding (7-day post counts, free):** Furukawa about 2.8k with a step-up from Oct 19; Lynas about 1.5k with a spike on Oct 21–22; SUMCO rising; Coherent high and steady; SMIC and Kokusai quiet. Judgement only; not a tested signal.
- **Not run:** Apollo/Clay headcount (redundant with Crustdata, saves credits), Ahrefs (Crustdata traffic used instead), Context monitors (creating monitors is a persistent external setup; left for the user to approve).
- **TOPIX survivorship:** NOT fixed. Yahoo has no prices for delisted .T names, so a rebuilt membership list cannot be priced without LSE or J-Quants. The BNF JP result keeps its survivorship caveat (long-side, biased UP).

## 11. Portfolio: can the KEPT edges make a Sharpe-2 book? (No.)

**Bottom line.** Combined, beta-hedged and vol-targeted, the book **loses money out of sample**: the core book has a net OOS Sharpe of −0.55 (gross −0.01), and adding Taiwan, Korea and Australia gives −0.75. **No combination reaches a Sharpe of 2.** Only BNF Japan has a positive net OOS Sharpe: 1.99 on the days it is invested, which is about **0.7 in calendar time** (it holds positions on only about 13% of OOS days), and it is survivorship-biased upward.

| Sleeve | Trades | IS net Sharpe | OOS gross | OOS net | OOS net max DD |
|---|---|---|---|---|---|
| BNF JP (TOPIX L/M, -25%, 5d) | 513 | 0.46 | 1.58 | 1.36 | -13.8% |
| BNF HK (-20%, 5d) | 239 | 3.24 | 0.03 | -0.15 | -40.2% |
| BNF TW (top-120 by value, -20%, 5d) NEW | 507 | -0.45 | 0.06 | -0.53 | -40.1% |
| BNF KR (40 large, -20%, 5d) NEW | 142 | -0.09 | 0.38 | -0.01 | -29.2% |
| BNF AU (44 large, -20%, 5d) NEW | 133 | 0.11 | -1.87 | -2.01 | -39.8% |
| PEAD short (bottom decile, 60d) | 4204 | 0.14 | 0.22 | -0.11 | -27.1% |
| Late-filer short overlay (120d) | 1316 | -2.63 | -0.99 | -1.85 | -70.8% |

| Book | IS net Sharpe | OOS gross Sharpe | OOS net Sharpe | OOS net return / vol | Max DD | Bootstrap 95% | Deflated Sharpe P (N=60) |
|---|---|---|---|---|---|---|---|
| Core (KEPT edges: BNF JP, BNF HK, PEAD short, late-filer short) | -0.16 | -0.01 | -0.55 | -5.04% / 9.08% | -32.6% | [-1.29, 0.12] | 0.0 |
| Core + new markets (TW, KR, AU) | -0.17 | -0.16 | -0.75 | -6.61% / 8.8% | -34.3% | [-1.44, -0.13] | 0.0 |
| BNF JP alone (the only sleeve with positive net OOS) | 0.79 | 2.19 | 1.99 | 27.08% / 13.62% | -5.6% | [0.15, 3.43] | 0.785 |

- **Walk-forward (BNF JP, net Sharpe by year, active days):** 2014: -1.55, 2016: -2.73, 2018: 1.84, 2020: -2.25, 2022: 1.14, 2024: 3.81, 2026: 1.26. Blank years had too few active days. The sign flips from year to year, and 2016 and 2020 were bad.
- **Why the event-study winners died in the book.** Measured as daily P&L with borrow, a 20% name cap and vol targeting: the late-filer short is wrecked by squeezes in micro-caps (net −1.85), and the PEAD short's +3.3% mean per event turns into a net Sharpe of −0.11 once overlapping 60-day positions, a 3% a year borrow fee and costs are added. BNF HK, which was KEPT on event means, is flat out of sample.
- **Breadth did not help.** The new sleeves are uncorrelated (|ρ| ≤ 0.21), but Taiwan, Korea and Australia BNF are ≤ 0 net out of sample, and averaging in negative-Sharpe sleeves lowers the book's Sharpe.
- **Capacity:** median BNF ADV is $28.4m, which gives about $7.1m at 5% of ADV. The shorts are micro-cap and borrow-limited.
- **Costs used:** spread of 15–45bp per round trip (includes the TW and KR sell taxes), plus square-root impact (100bp at 100% of ADV for a $250k ticket), plus borrow of 3% a year (PEAD) or 20% a year (late filers).
- **What a Sharpe of 2 would need:** about 10 or more independent, positively-performing sleeves at about 0.6 Sharpe each, or intraday or overnight execution on BNF Japan (not tested; needs open prices), point-in-time universes with dead names (CRSP, J-Quants), and real borrow data. On free data we have one weak edge, not a book.
- **Not done:** PEAD outside the US (no free earnings-date feed was found that was worth the Apify spend), overnight/intraday split, and KOSPI beyond 40 large caps.

### London Strategic Edge (key verified)

- **Survivorship: NOT fixable with LSE.** All 3,982 catalog stocks still trade in 2026; it has no delisted US names. SIVB, FRC and LEH return no data, and 'BBBY' back to 2003 is Overstock's history under the reused ticker. Japan and Hong Kong are about 50 large caps only, so it cannot help with dead names. No status flipped; the survivorship caveats stand.
- **Insider trades:** LSE's records link to SEC Form 4 filings (the same source as our bulk files) and start in 2014, so they add nothing new. The M1 re-test would be identical and was not re-run.
- **Options (context, contracts updated on 22 Oct):** COHR: ATM IV 84.5%, 25-delta skew -0.8 vol pts; MP: ATM IV 65.6%, 25-delta skew -3.2 vol pts. LITE had no fresh contracts. IV rank was not computed (it needs an IV history pull). Data is used locally and not redistributed.
- **Usage:** about 5MB of 50GB this month; 0 of 5 exports this hour (the plan cap is 5 an hour, not 10).

### S21 point-in-time (H.4.1 release dates)

- 615 weekly releases (2015-01-02 to 2026-10-22) and 98 triggers. OOS (2019+): n=26, precision 77%, mean excess 1.33%, t=0.77. It passes the rule mechanically (KEPT), but it is **not significant**, and the in-sample window is empty because H.4.1 parsing starts in 2015. Worst trade: 2020-02-21, −31.8%. Treat it as weak.