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