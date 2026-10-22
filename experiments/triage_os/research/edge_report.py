"""Builds research/edge_lab.md + 'TRIAGE Edge Lab' PDF/HTML from edge_lab.json and edge_live.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
LAB = json.load(open("/workspace/triage_os_data/edge_lab.json")); LIVE = json.load(open("/workspace/triage_os_data/edge_live.json"))
PLAY = [  # fund, mechanism, data, free equivalent, primary source, grade
 ("Elliott", "Holdouts and legal leverage: buy defaulted claims cheap, enforce contract terms (pari passu) until paid; activism in governance-weak firms", "Bond indentures, court dockets, 13D", "Partly: CourtListener/RECAP, EDGAR 13D, indentures in 8-K exhibits. PACER fees and docket depth are limits", "https://www.govinfo.gov/content/pkg/USCOURTS-ca2-12-00109/pdf/USCOURTS-ca2-12-00109-0.pdf", "A"),
 ("Baupost / Klarman", "Orphans: securities sold for non-economic reasons (post-reorg equity, spin-offs, claims, index exits)", "Emergence dates, Form 10s, claims registers", "Yes for emergences and spin-offs (EDGAR); claims prices are not free", "Margin of Safety (1991, book); M2/M3 below", "B"),
 ("Oaktree / Apollo", "Create control: buy the fulcrum tranche, then use LMEs/uptiers or the plan to take the equity", "Credit agreements, lender groups, plan documents", "Partly: 8-K credit agreements, our control maps. Loan prices are not free", "https://www.ca5.uscourts.gov/opinions/pub/23/23-20181-CV0.pdf (Serta: uptier not an 'open market purchase')", "A"),
 ("Millennium / Citadel pods", "Many small event edges with tight risk: index adds, spin-offs, lockups, merger arb, earnings drift", "Index changes, deal terms, consensus estimates, borrow", "Partly: EDGAR events are free; consensus, borrow and index history are paid", "No public primary source (labelled JUDGEMENT); academic anchors: Field & Hanka 2001 JF (lockups), Mitchell & Pulvino 2001 JF (merger arb), Bernard & Thomas 1989 (PEAD)", "C"),
 ("Glencore / Trafigura / Vitol", "Physical arbitrage: own storage and freight, earn location, time (contango) and quality spreads", "Inventories, freight rates, forward curves", "Partly: EIA stocks, SHFE/LME weekly stocks (SHFE in our v4), Comtrade flows. Freight and physical premia are paid", "Company annual reports (e.g. Trafigura annual report); JUDGEMENT on the mechanism", "B"),
 ("Renaissance", "Many weak, uncorrelated signals with clean data, careful costs and no single big bet", "Tick data, corporate actions, clean histories", "Partly: daily data free, survivorship-free history not free", "Zuckerman, The Man Who Solved the Market (2019, book)", "C"),
 ("Burry", "Read the documents nobody reads (prospectus tapes, filings), then buy cheap convex protection (CDS)", "Prospectuses, 10-K/10-Q footnotes, CDS", "Yes for documents (EDGAR full text); CDS not free", "Scion 13F filings on EDGAR; Lewis, The Big Short (book)", "B"),
 ("Ackman", "Asymmetric hedges: buy protection when it is near its cheapest (CDX IG ~50bp) before a regime break", "CDS index spreads, macro triggers", "Partly: FRED ICE OAS (3-year public window only)", "https://pershingsquareholdings.com/wp-content/uploads/2020/03/Pershing-Square-Capital-Management-L.P.-Releases-Letter-to-Investors-March-26-2020.pdf ($27m cost, >$2.6bn proceeds)", "A"),
 ("Druckenmiller / Soros", "Regime shifts: liquidity and policy turns, reflexive feedback loops; size up when right", "Central-bank balance sheets, FX, policy", "Yes: FRED/ALFRED (point-in-time vintages throttled this session)", "Soros, The Alchemy of Finance (1987, book)", "B"),
 ("Bridgewater", "Debt-cycle mechanics: debt service vs income, policy levers, deleveraging phases", "Credit growth, debt service, rates", "Yes: BIS, FRED, IMF", "https://www.bridgewater.com/research-and-insights/a-template-for-understanding-big-debt-crises (Dalio, Big Debt Crises, free PDF)", "B"),
]
OVER = [
 ("Deadlines that force behaviour", "SEC Rule 12b-25: a late filer gets 15 days (10-K) or 5 days (10-Q). Missing it leads to exchange deficiency notices and loss of S-3 eligibility, which forces dilutive financing. Public on EDGAR, but rarely aggregated.", "IMPLEMENTED: O2 late-filer watch + M5 backtest (KEPT on the short side, borrow-sensitive)"),
 ("Supply released on a fixed date", "IPO lockups end around day 180. The S-1 states it; nobody aggregates it for small IPOs.", "IMPLEMENTED: O1 forward lockup calendar (the backtest decayed: IS works, OOS fails)"),
 ("Public but not joined", "Insider buying, a new activist 13D and our restructuring calendar sit in separate databases. Joining them is the edge a desk with time has.", "IMPLEMENTED: O3 convergence screen (1 hit, a closed-end fund self-filing, so not meaningful today)"),
 ("Second-order effects", "China export-control suspension expires 27 Nov 2026 (MOFCOM Ann. 72/2025) → US defence primes need non-China Sb/Ga/Ge → small Western suppliers (Bottleneck Hunt).", "Already in Bottleneck Hunt"),
 ("Schedule 13D form-type change", "EDGAR now files new 13Ds as 'SCHEDULE 13D'. Screens still keyed to 'SC 13D' silently miss 2025+ activism. We found this in our own pipeline.", "FIXED in the live layer; M4 backtest is 2018-2024 only"),
]
def pct(v): return "–" if v is None else f"{v}"
def main():
    R = LAB["results"]; L = ["# TRIAGE Edge Lab: how the big funds find edge and what survives our tests", "",
        "*As of 23 Oct 2026 (SGT). Public data, research only, not investment advice, paper ledger only. A grade means a primary document was read this pass; B means a book or the fund's own filings; C means secondary or judgement.*", "",
        "**Bottom line.** Of seven mechanisms we could rebuild from free SEC data, **one survives** our rules (late-filer SHORT/AVOID). It is hard to trade because borrow is scarce. Spin-offs are FRAGILE, post-reorganisation equity is UNTESTED (too few clean events), and insider clusters, activist 13Ds and lockup shorts are KILLED. Merger arb, earnings drift and fallen angels need paid data.", "",
        "## 1. The big-funds playbook", "", "| Fund | Repeatable mechanism | Data it needs | Free public equivalent? | Primary source | Grade |", "|---|---|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {d} | {e} | {g} |" for a, b, c, d, e, g in PLAY]
    L += ["", "## 2. Backtests (filing-date point-in-time, costs, IS < 2022 ≤ OOS, one event per ticker per window)", "",
          "| Mechanism | Status | Events found | Priced (coverage) | IS n / prec / mean / median | OOS n / prec / mean / median | OOS t |", "|---|---|---|---|---|---|---|"]
    for k, v in R.items():
        if "IS" not in v: L.append(f"| {k} | **{v['status']}** | – | – | {v['note']} | | |"); continue
        i, o = v["IS"], v["OOS"]
        L.append(f"| {k} | **{v['status']}** | {v['events_found']} | {v['priced']} ({v['coverage']}%) | {i.get('n')} / {pct(i.get('precision'))}% / {pct(i.get('mean'))}% / {pct(i.get('median'))}% | {o.get('n')} / {pct(o.get('precision'))}% / {pct(o.get('mean'))}% / {pct(o.get('median'))}% | {pct(o.get('t'))} |")
    m5 = R["M5 NT 10-K late filers, SHORT (120d)"]
    L += ["", "**How to read this.**",
          "- Means are skewed by a few huge winners; check the medians.",
          "- Spin-off OOS mean +46% vs median +4% is a handful of multi-baggers, not a reliable edge. In-sample precision of 47% makes it FRAGILE.",
          f"- **Late-filer short:** borrow cost decides it. OOS excess after a 100bp cost: {m5['OOS']['mean']}%. After borrow at 5% / 20% / 50% a year: {', '.join(f'{k}: {v}%' for k, v in m5.get('borrow_sensitivity', {}).items())}. Most of these names are sub-$1, often not borrowable. Treat it as an **AVOID / risk** signal, not a trade.",
          "- **Survivorship:** Yahoo drops delisted tickers. Coverage is 68–93%. Missing names are disproportionately failures, so long results are biased UP and the short result is biased DOWN (conservative).",
          "- **Insider clusters killed:** the academic edge (Cohen-Malloy-Pomorski) uses 'opportunistic' insiders and pre-2010 data. Our simple ≥3-insider rule over 2018–2026 loses money vs IWM after 50bp.",
          "- **Lockup short:** worked in-sample (t = 2.55) and failed OOS. It looks arbitraged away, as the literature predicts.",
          "- **Post-reorg equity:** the 'new equity' filter leaves 13 clean events. Our EDGAR text-search dating is too coarse; it needs court confirmation dates (our Ch11 data) to reach n ≥ 8 OOS.", "",
          "## 3. What we were overlooking (audit) and what we built", "", "| Item | Why a billionaire sees it | Status |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in OVER]
    L += ["", "## 4. Live list (only from the mechanism that passed)", "",
          "Paper AVOID / SHORT-WATCH calls from M5 (NT 10-K filed in the last 60 days, priced this week). Each is in the hash-chained ledger. **Kill condition for every row:** the company files its 10-K within the 12b-25 extension AND the stock beats IWM by >20% within 60 days of the NT filing.", "",
          "| Ticker | Company | NT filed | Last px | Deadline | Window end | Source |", "|---|---|---|---|---|---|---|"]
    for r in LIVE["live"]: L.append(f"| {r['ticker']} | {r['company']} | {r['filed']} | {r['last_px']:.4g} | {r['deadline_note']} | {r['window_end']} | {r['src']} |")
    L += ["", "### Context lists (not ledger calls: mechanisms not KEPT)", "", "**Upcoming lockup expiries (O1), next 75 days:**", "", "| Ticker | Company | IPO | Est. expiry | Since IPO |", "|---|---|---|---|---|"]
    L += [f"| {r['ticker']} | {r['company']} | {r['ipo']} | {r['lockup_expiry_est']} | {r['ret_since_ipo']}% |" for r in LIVE["lockups"][:15]]
    L += ["", "**Spin-offs in registration (Form 10 filed in the last 150 days; FRAGILE mechanism):**", ""] + [f"- {r['company']} ({r['ticker'] or 'no ticker yet'}): first filed {r['first_filed']}, {r['src']}" for r in LIVE["spinoffs"]]
    L += ["", "**Live open-market insider clusters (≥3 insiders, ≥$100k, 21 days; KILLED mechanism, shown for transparency):** " + ", ".join(f"{r['ticker']} ({r['insiders']} insiders, ${r['value_usd']:,})" for r in LIVE["insider_clusters"]), "",
          "## 5. Gaps", "",
          "- **Non-US insider data:** UK RNS director dealings, ASX Appendix 3Y and Japan large-holder reports are not ingested. There is no free bulk feed; the RNS and ASX pages need scraping, deferred to stay within the Apify cap. Crustdata/Apify spend: $0.",
          "- **Merger arb, PEAD, fallen angels:** need paid data (delisting returns, consensus estimates, rating history).",
          "- **Index deletions:** S&P/Russell change history is not free.",
          "- **Post-reorg dating:** emergence is dated from 8-K text, not from confirmation orders.",
          "- **ALFRED:** point-in-time vintages still fail (the host keeps refusing this box), so the macro point-in-time rebuild is still pending.",
          "- **UN Comtrade:** 213 monthly China-export rows (2022+) arrived. They are not yet joined to signals.",
          "- **Form 4 bulk data** stops at 2026Q1; the live layer reads filings directly."]
    m = "\n".join(L); open(os.path.join(HERE, "edge_lab.md"), "w").write(m)
    from design import report_from_markdown
    report_from_markdown(m, "TRIAGE Edge Lab", "Research · 23 Oct 2026", "How the big funds find edge, and what survives our tests on free public data",
        [("Mechanisms", f"{len(R)} tested or scoped, 1 kept"), ("Data", "EDGAR idx 2018–2026, Form 4 bulk, 8-K full text"), ("Rules", "PIT filing dates · costs · OOS ≥ 2022")],
        os.path.join(HERE, "TRIAGE_Edge_Lab.html"), os.path.join(HERE, "TRIAGE_Edge_Lab.pdf"))
    json.dump(dict(playbook=[dict(zip(["fund", "mechanism", "data", "free", "source", "grade"], p)) for p in PLAY], results=R, overlooked=[dict(zip(["item", "why", "status"], o)) for o in OVER], live=LIVE["live"], lockups=LIVE["lockups"][:15], spinoffs=LIVE["spinoffs"]), open("/workspace/triage_os_data/edge_app.json", "w"), indent=1, default=str)
if __name__ == "__main__": main()
