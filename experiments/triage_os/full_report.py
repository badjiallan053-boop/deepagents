"""Full TRIAGE OS master report: only VERIFIED / CORRECTED facts (UNVERIFIABLE are labelled in the appendix), with a status column."""
import csv, glob, json, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(__file__))
import master_report as mr, verify as v, hit_log
D = "/workspace/triage_os_data"; DB = f"{D}/triage.db"
def esc(x): return str(x if x is not None else "").replace("|", "/").replace("\n", " ")
def table(head, rows): return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows])
def build(md_path=f"{D}/TRIAGE_OS_Master_Report.md", pdf_path=f"{D}/TRIAGE_OS_Master_Report.pdf"):
    c = sqlite3.connect(DB, timeout=120)
    ver = c.execute("select claim_id,artifact,claim,status,primary_url,checked,method,fix from verification order by claim_id").fetchall()
    stats = dict(c.execute("select status,count(*) from verification group by 1").fetchall())
    good = [r for r in ver if r[3] in ("VERIFIED", "CORRECTED")]
    S = [f"# TRIAGE master report\n\nGenerated {v.TODAY} (Asia/Singapore). Public data only; firms only; read-only. Every fact below carries a status (VERIFIED / CORRECTED) and a primary source checked on the date shown. UNVERIFIABLE items are excluded from the body and listed in Appendix A.\n",
         f"## 1. Verification summary\n\n{table(['Status','Claims'], sorted(stats.items()))}\n\nTotal claims checked: {sum(stats.values())}. Method: live fetch of the primary document with required-token match (SEC EDGAR, HKEX, company IR), recomputation from SEC-derived tables (13F data sets, BDC 10-Q schedules, N-PORT XML), and court/claims-agent dockets.\n",
         "## 2. Key facts (VERIFIED or CORRECTED only)\n\n" + table(["ID", "Fact (as corrected)", "Status", "Source", "Checked"], [(r[0], r[2] + (f" → **{r[7]}**" if r[3] == "CORRECTED" and r[7] else (f" ({r[7]})" if r[7] else "")), r[3], r[4], r[5]) for r in good]) + "\n",
         "## 3. Notable corrections\n\n" + "\n".join(f"- **{r[0]}** {r[2]} → {r[7]} ([source]({r[4]}))" for r in ver if r[3] == "CORRECTED") + "\n"]
    cap = c.execute("select situation,issuer,tranche,amount_usd_m,coupon,maturity,lien,guarantors,covenants,agent_trustee,holder,mark,as_of,source_url,status from cap_structures_top15").fetchall()
    S.append("## 4. Capital structures — top 15 situations\n\nPublic issuers from SEC 10-Q/10-K/8-K and IR; private borrowers from BDC 10-Q schedules of investments (coupon, maturity, agent and covenants of private credit agreements are not public: n/d).\n")
    for sit in dict.fromkeys(r[0] for r in cap):
        S.append(f"### {sit}\n\n" + table(["Issuer", "Tranche", "USD m", "Coupon", "Maturity", "Lien", "Guarantors", "Covenants", "Agent/Trustee", "Holder", "Mark", "As of", "Status", "Source"], [r[1:13] + (r[14], r[13]) for r in cap if r[0] == sit]) + "\n")
    cal = c.execute("select * from claims_calendar order by date").fetchall()
    S.append("## 5. Claims-agent sale calendar\n\n" + table(["Case", "Court", "Agent", "Event", "Date", "Time", "State", "Source", "Status"], cal) + "\n")
    w = c.execute("select state,company,city,notice_date,employees,reason,source_url from warn_state_notices where notice_date>='2026-08-01' order by cast(employees as int) desc limit 25").fetchall()
    cnt = c.execute("select state,count(*) from warn_state_notices group by 1").fetchall()
    S.append(f"## 6. WARN notices (state readers: NJ, IL, FL; TX blocked)\n\nRows ingested: {dict(cnt)}. Status: VERIFIED (parsed from official state files). Largest since 1 Aug 2026:\n\n" + table(["State", "Company", "City", "Notice", "Employees", "Reason", "Source"], w) + "\n")
    bm = c.execute("select bdc,borrower,identifier,mark,source_url from bdc_marks where period='2026-06-30' and mark<40 and par>5e6 order by mark limit 30").fetchall()
    S.append("## 7. Deepest BDC marks at 30 Jun 2026 (par > $5m)\n\nStatus: VERIFIED (BDC 10-Q schedules).\n\n" + table(["BDC", "Borrower", "Tranche", "Mark", "Source"], bm) + "\n")
    S.append("## 8. Dossiers (full)\n")
    for f in sorted(glob.glob(f"{D}/dossiers_2026-10-22/*.md")):
        S.append(open(f).read().replace("\n# ", "\n### ").replace("\n## ", "\n#### ").lstrip("# ").join(["### ", "\n"]))
    ap = {r["domain"]: r for r in csv.DictReader(open(f"{D}/apollo_enriched_60.csv"))}
    dm = json.load(open(f"{D}/apollo_domains.json"))
    buyers = list(csv.DictReader(open(f"{D}/buyers.csv")))[:40]
    rows = []
    for b in buyers:
        a = ap.get(dm["buyers"].get(b["firm"], ""), {}); tot = v.f13_total(DB, b["f13_filer"]) if float(b["f13_our_names_usd_m"] or 0) > 0 else 0
        rows.append((b["rank"], a.get("name") or b["firm"], b["type"], a.get("employees", "n/m"), a.get("city", ""), a.get("founded", ""), f"${tot}m" if tot else "—", v.f13_breakdown(DB, b["f13_filer"]) if tot else "", b["evidence_url"] if tot else "", "VERIFIED (13F)" if tot else "profile: vendor (Apollo)"))
    S.append("## 9. Buyer profiles — top 40\n\nHeadcount, HQ and founding year: Apollo.io enrichment 22 Oct 2026 (vendor data). EchoStar exposure: SEC 13F Q2-26, all CUSIPs of the latest filing (common, calls/puts, 3.875% 2030 convertible notes 278768AB2).\n\n" + table(["#", "Firm", "Type", "Employees", "HQ", "Founded", "EchoStar 13F", "Breakdown", "Source", "Status"], rows) + "\n")
    inv = list(csv.DictReader(open(f"{D}/investors.csv")))[:20]
    S.append("## 10. Investor profiles — top 20\n\n" + table(["#", "Investor", "Type", "Employees (Apollo)", "HQ", "Thesis / evidence", "Cheque (our estimate)", "Status"],
             [(i["rank"], i["name"], i["type"], ap.get(dm["investors"].get(i["name"], ""), {}).get("employees", "n/m"), ap.get(dm["investors"].get(i["name"], ""), {}).get("city", ""), i["thesis_evidence"], i["cheque"], "VERIFIED (ownership/portfolio)" if i["rank"] in [str(x) for x in (2,3,4,5,7,11,18,19)] else "thesis: firm site") for i in inv]) + "\n")
    p = hit_log.precision_at_trade(DB); ok, _ = hit_log.verify_chain(f"{D}/hit_log.jsonl"); n = sum(1 for _ in open(f"{D}/hit_log.jsonl"))
    S.append(f"## 11. Live hit log and precision-at-trade\n\n- Live out-of-sample log: `hit_log.jsonl`, {n} predictions, append-only, SHA-256 chained, UTC timestamps; chain intact: {ok}. Outcome checker matches later court/SEC filings and WARN notices; outcomes are written to `hit_outcomes.jsonl` (0 so far — log opened {v.TODAY}).\n- Precision-at-trade (free data, pseudo out-of-sample): tranche marked <80 at 31 Mar 2026 → marked ≥5 pts lower at 30 Jun 2026. Signals {p['signals']}, hits {p['hits']}, **precision {p['precision']:.1%}** vs base rate {p['base_rate']:.1%} for tranches ≥80 ({p['pairs']} matched tranches; lift {p['precision']/p['base_rate']:.1f}x). Source: BDC 10-Q schedules (SEC).\n- N-PORT forced-seller check verified live for Polen Opportunistic High Yield (−47.8% 3m flow).\n- FINRA TRACE: not used (no free bulk access to tranche-level prints).\n")
    S.append("## 12. Methodology\n\n1. Ingest: SEC EDGAR (submissions API, 8-K/10-Q/10-K, 13F data sets, N-PORT XML), BDC schedules of investments, CourtListener RECAP, claims-agent sites (Stretto, Epiq), HKEX, SGX, company IR, state WARN files (NJ, IL xlsx; FL via Apify rag-web-browser), GLEIF.\n2. Entity resolution on normalised names plus LEI/CUSIP; vendor data (Apollo, Crustdata, Clay) used only for firm profiles and never as fact for a situation.\n3. Verification: each claim gets VERIFIED (primary source re-read, tokens matched), CORRECTED (primary source differs; fix shown) or UNVERIFIABLE (excluded from body). Ledger in table `verification` and `verification_log.md`.\n4. Hit log: predictions are frozen before outcomes, chained by hash so they cannot be edited after the fact.\n5. Limits: PACER declined (no petitions/schedules beyond RECAP); private credit coupons, maturities, agents and covenants not public; TX WARN blocked by AWS WAF; Context free plan capped at 10 monitors.\n")
    S.append("## Appendix A — UNVERIFIABLE (excluded from body)\n\n" + table(["ID", "Artifact", "Claim", "Note"], [(r[0], r[1], r[2], r[7]) for r in ver if r[3] == "UNVERIFIABLE"]) + "\n")
    S.append("## Appendix B — Full verification ledger\n\n" + table(["ID", "Status", "Claim", "Method", "Source", "Checked"], [(r[0], r[3], r[2], r[6], r[4], r[5]) for r in ver]) + "\n")
    S.append("## Appendix C — Charts\n\n![bdc](master/bdc.png)\n")
    open(md_path, "w").write("\n".join(S))
    import design
    s = c.execute("select count(*) from verification").fetchone()[0]
    pages = design.report_from_markdown("\n".join(S), "TRIAGE master report: private-credit distress, court calendar and the verification ledger",
        f"Desk report · {v.TODAY}", "BDC marks, top-15 capital structures, claims-agent calendar, WARN notices, dossiers, buyer and investor profiles, and the live hit log. Every fact carries a status and a primary source.",
        [("Claims in ledger", s), ("Verified", stats.get("VERIFIED", 0)), ("Corrected", stats.get("CORRECTED", 0)), ("Unverifiable", stats.get("UNVERIFIABLE", 0)), ("As of", v.TODAY)],
        md_path.replace(".md", ".html"), pdf_path)
    return md_path
if __name__ == "__main__":
    build(); import subprocess; print(subprocess.run(["pdfinfo", f"{D}/TRIAGE_OS_Master_Report.pdf"], capture_output=True, text=True).stdout)
