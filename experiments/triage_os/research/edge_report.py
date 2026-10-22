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
def tbl(R):
    out = ["| Test | Status | IS n / prec / mean / median | OOS n / prec / mean / median | OOS t |", "|---|---|---|---|---|"]
    for k, v in R.items():
        i, o = v["IS"], v["OOS"]
        out.append(f"| {k} | **{v['status']}** | {i.get('n')} / {i.get('precision','–')}% / {i.get('mean','–')}% / {i.get('median','–')}% | {o.get('n')} / {o.get('precision','–')}% / {o.get('mean','–')}% / {o.get('median','–')}% | {o.get('t','–')} |")
    return out
def addendum():
    RW = json.load(open("/workspace/triage_os_data/reorg_ww.json")); BN = json.load(open("/workspace/triage_os_data/bnf_cis.json")); AD = json.load(open("/workspace/triage_os_data/edge_addendum.json"))
    c = RW["counts"]; S = RW["survivorship"]
    L = ["", "## 6. Post-reorganisation equity, worldwide (M3 expanded)", "",
         f"**Event set:** {c['events']} events with a dated, priced new equity (by region: {', '.join(f'{k} {v}' for k, v in c['by_region'].items())}). That is far short of the 150 target. From {c['ciks']} US filers found in EDGAR full-text search, {c['no_date']} had no confirmation/effective 8-K we could date, {c['old_equity_continued']} kept their old equity, and **{c['missing']} are MISSING**: new equity was registered (Form 8-A) but there is no current ticker or Yahoo price (delisted, went dark, renamed).",
         "",
         "**Dating:**",
         "- Confirmation is the first 8-K Item 1.03 citing the confirmation order (filed within 4 business days of the order). CourtListener dockets were not queried.",
         "- The effective date is the next 8-K with Item 5.01/3.03/2.01.",
         "- Non-US events (11) are a curated JUDGEMENT list (France sauvegarde, Norway, Japan JAL, Indonesia Garuda, HK Sunac) and need primary verification.", ""] + tbl(RW["results"])
    L += ["", f"**Survivorship sensitivity:** with missing names excluded, day-5/250d is **{S['excluded']['status']}**. With the {c['missing']} missing names set to -100%, it is **{S['missing_as_minus100']['status']}** (OOS mean {S['missing_as_minus100']['OOS'].get('mean')}%).",
          "",
          "**Verdict: M3 does not pass.** The day-0 'KEPT' rows have t-statistics of 0.02–1.2. That is noise that only passes the mechanical rule, and it flips to KILLED under the survivorship test.",
          "",
          "**Best sub-signal:** insider open-market buying within 90 days of first trade (OOS 5 events, 80% wins, +18.5% vs -23.0% for no insider buy). Directionally consistent with the Klarman 'orphan' story, but UNTESTED (n < 8).",
          "",
          "**Not testable with free data:** creditor ownership above 50% and backstop flags come from 8-K text and cover too few events; sell-side coverage counts and CLO forced-selling flows are not available.",
          "",
          "**Upcoming emergences worldwide** (paper WATCH, calendar only, mechanism vetoed; existing equity is usually diluted 90–100%):", "", "| Ticker | Company | Country | Date | Event | Last px |", "|---|---|---|---|---|---|"]
    L += [f"| {e['t']} | {e['name']} | {e['country']} | {e['date']} | {e['why']} | {e['px']} |" for e in AD["emergences"]]
    u = BN["universe"]
    L += ["", "## 7. BNF and CIS rebuilt", "",
          "**Sources:** BNF (Takashi Kotegawa) is known from his rare press interviews (Nikkei and Weekly SPA!, summarised in Japanese trading books). CIS is known from his book 『一億円稼ぐ…』 and X posts. Both are labelled C: secondary, not primary-verified this pass.",
          "",
          "**Rules tested:**",
          "- BNF: buy when the close is 20/25/30% or more below its 25-day average (kairi-ritsu), hold 1–5 days.",
          "- CIS: buy a new 250-day closing high on at least 2x the 50-day volume, exit on a 7% trailing stop (max 60 days).",
          "",
          f"**Test setup:** entry at the next close; costs 25bp (JP large), 40bp (JP small), 10bp (US), 20bp (EU), 30bp (HK), 75bp (US small). Universe: JP TOPIX Core30/Large70/Mid400 ({u['jp_big']}), Small1 ({u['jp_small1']}), US large ({u['us']}), EU large ({u['eu']}), HK large ({u['hk']}), and our US event/distressed universe ({u['dist']}). Out-of-sample from 2021.", ""] + tbl(BN["results"])
    L += ["", "**Honest reading:**",
          "- BNF holds in Japanese large and mid caps on a 5-day hold. The deepest discount does best: -30% gives 72 OOS events, 69% wins, +3.9%, t = 3.5; -25% gives 174 events, +2.9%, t = 4.05. It also holds in HK.",
          "- It fails in EU, in the US distressed universe (the mean is driven by bad-tick outliers; the median is negative), and on 1-day holds.",
          "- **Survivorship is the main risk.** The JP universe is today's TOPIX members, which excludes exactly the names that kept falling. Mean-reversion results are biased upward, so treat them as an upper bound.",
          "- **Multiple testing:** 20 variants were run. The two strongest (t of 3.5 and 4.05) would survive a Bonferroni cut at 5%. The -20% variants would not.",
          "- **CIS is KILLED everywhere out of sample** (38–39% wins, negative medians), despite strong in-sample t-values (7.5–8.1). The simple breakout rule decayed after 2021.",
          "",
          "**Live BNF triggers today** (logged as paper WATCH with a 5-day exit and a kill rule): " + ", ".join(f"{x['t']} (kairi {x['kairi']}%, {x['variant']})" for x in AD["bnf_live"]) + ". Context only (FRAGILE or KILLED variants): " + ", ".join(f"{x['t']} {x['kind']}" for x in BN["live"] if not (x["kind"] == "BNF" and x["region"] in ("JP", "HK"))) + ".",
          "", "## 8. Data joins and point-in-time", "", "**China exports (UN Comtrade public preview; data available through the month shown), joined to the export-control names:**", "", "| HS | Product | Our names | Last month | Last 12m kg | Prior 12m kg | YoY |", "|---|---|---|---|---|---|---|"]
    L += [f"| {r['hs']} | {r['desc']} | {r['names']} | {r['last_month']} | {r['kg_last12']:,} | {r['kg_prior12'] or 0:,} | {r['yoy_pct']}% |" for r in AD["comtrade"]]
    h = AD["h41"]
    L += ["", "**Comtrade notes:**",
          "- The preview stops at Dec 2024 (Sep 2024 for antimony), so it captures the 2023–24 export controls, not 2025–26.",
          "- Antimony exports fell 39% year on year and graphite 25%, consistent with the controls.",
          "- Tungsten rose 18% and gallium/germanium rose 5%.",
          "",
          f"**Point-in-time Fed balance sheet:** ALFRED refused this box again. Fallback: the Fed's own H.4.1 release archive (each release is what the public saw that Thursday). {h.get('releases')} weekly releases parsed so far ({h.get('first')} to {h.get('last')}), fetch still running. The S21 point-in-time re-test runs once the archive reaches 2026.",
          "", "## 9. Gaps and access notes", "",
          "- **London Strategic Edge:** the free key is issued only through the website sign-up at https://londonstrategicedge.com/data. There is no programmatic issuance in the client (lse-data, MIT). Stopped for the user. Once a key is saved under /workspace/triage_os_data/.secrets, LSE can fill the survivorship gap (delisted US names back to 2003), add options greeks and insider data, and cross-check macro history.",
          "- **This pass (5):** see section 10.",
          "- **Live layer:** live_service.py polls Yahoo every 2 min in market hours and every 30 min otherwise. Quotes may be delayed 15–20 min (shown per symbol). Served at /api/live and in the Live tab."]
    return L + pass5()
def pass5():
    P5 = "/workspace/triage_os_data/pead.json"; pe = json.load(open(P5)) if os.path.exists(P5) else {}
    L = ["", "## 10. Pass 5: free substitutes, non-US insiders, connector checks (23 Oct 2026, 04:47–05:10 SGT)", "",
         "| Test | Status | IS n / prec / mean / median | OOS n / prec / mean / median | OOS t | Coverage |", "|---|---|---|---|---|---|"]
    for k, lab in (("long_top_decile", "PEAD long, top-decile SUE (60d vs IWM, 20bp)"), ("short_bottom_decile", "PEAD short, bottom-decile SUE (60d vs IWM, 20bp)")):
        v = pe.get(k)
        if v: i, o = v["IS"], v["OOS"]; L.append(f"| {lab} | **{v['status']}** | {i['n']} / {i['precision']}% / {i['mean']}% / {i['median']}% | {o['n']} / {o['precision']}% / {o['mean']}% / {o['median']}% | {o['t']} | {v['coverage']}% |")
    L += ["", "- **PEAD build:** SEC XBRL frames (EarningsPerShareBasic, quarterly), surprise = seasonal random walk scaled by the stdev of the last 8 seasonal changes; dated by the 10-Q filing date from form.idx; decile within filing month. Q4 is omitted (10-K frames are annual). The short leg is KEPT before borrow costs; tickers come from today's SEC list, so dead firms are missing and the short result is biased DOWN (conservative). The long leg is KILLED.",
          "- **Fallen angels, index deletions, merger arb:** NOT built. S&P and Moody's press-release archives need a login; S&P DJI/FTSE Russell notice pages are JS-only; merger-arb targets are exactly the names Yahoo drops on completion, so a test without delisted prices would be meaningless. LSE was meant to fix that (below).",
          "- **London Strategic Edge:** LSE_API_KEY is set, but its value is a template line (an 'export ...=\"lse_...\"' with a '...' placeholder and a comment), not a key. The API answered 'invalid api key' on /vault/usage. 0 of 10 hourly downloads used. Survivorship, greeks and insider data via LSE were NOT done.",
          "- **UK PDMR (Investegate company pages, FTSE 100 sample, 2020–2026):** scraping runs in the background at about 1 request/s; the cluster test is pending. The search page is reCAPTCHA-protected and was not bypassed. The purchase parser is noisy (award and acquisition wording).",
          "- **Apify (spend log):** Japan 5% large-holder filings, Oct 1–22 2026, 37 rows (11 flagged potential activist), about $1.85. ASX announcements for 20 critical-minerals names, 50 rows (2 'Final Director's Interest Notice', no 3Y buys), about $0.25. **Total about $2.10 of $15.** These are recent snapshots only, so they cannot backtest; none of the 37 Japan issuers is a BNF watch, so the BNF-JP insider filter is UNTESTED. Historical EDINET needs a free key, which requires a sign-up.",
          "- **Crustdata (18 of 300 credits; the account balance was only 30, now 12):** headcount YoY: SoftBank +6.7%, SMIC +1.3%, Kokusai +9.0%, Furukawa +7.0%, Coherent +8.2%, Lumentum +3.8%, Lynas +5.2%. Kioxia and SUMCO matched European sales subsidiaries, so ignore them. Web traffic MoM (from Crustdata, standing in for Ahrefs): SMIC +11%, Lynas +12%, Kokusai −14%, SUMCO −33% (subsidiary site).",
          "- **X crowding (7-day post counts, free):** Furukawa about 2.8k with a step-up from Oct 19; Lynas about 1.5k with a spike on Oct 21–22; SUMCO rising; Coherent high and steady; SMIC and Kokusai quiet. Judgement only; not a tested signal.",
          "- **Not run:** Apollo/Clay headcount (redundant with Crustdata, saves credits), Ahrefs (Crustdata traffic used instead), Context monitors (creating monitors is a persistent external setup; left for the user to approve).",
          "- **TOPIX survivorship:** NOT fixed. Yahoo has no prices for delisted .T names, so a rebuilt membership list cannot be priced without LSE or J-Quants. The BNF JP result keeps its survivorship caveat (long-side, biased UP)."]
    return L
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
    L += addendum()
    m = "\n".join(L); open(os.path.join(HERE, "edge_lab.md"), "w").write(m)
    from design import report_from_markdown
    report_from_markdown(m, "TRIAGE Edge Lab", "Research · 23 Oct 2026", "How the big funds find edge, and what survives our tests on free public data",
        [("Mechanisms", f"{len(R)} tested or scoped, 1 kept"), ("Data", "EDGAR idx 2018–2026, Form 4 bulk, 8-K full text"), ("Rules", "PIT filing dates · costs · OOS ≥ 2022")],
        os.path.join(HERE, "TRIAGE_Edge_Lab.html"), os.path.join(HERE, "TRIAGE_Edge_Lab.pdf"))
    json.dump(dict(playbook=[dict(zip(["fund", "mechanism", "data", "free", "source", "grade"], p)) for p in PLAY], results=R, overlooked=[dict(zip(["item", "why", "status"], o)) for o in OVER], live=LIVE["live"], lockups=LIVE["lockups"][:15], spinoffs=LIVE["spinoffs"], pass5=pass5()), open("/workspace/triage_os_data/edge_app.json", "w"), indent=1, default=str)
if __name__ == "__main__": main()
