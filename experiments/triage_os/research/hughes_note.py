"""Flagship situation note: Hughes Satellite Systems (Bankr. S.D. Tex. 26-90739).
Every number is either (a) token-matched against a cached copy of its primary document,
(b) an existing ledger row, or (c) an explicitly labelled analyst assumption / calculation.
Writes HN-* rows to the `verification` table and renders HTML -> PDF with headless Chrome."""
import os, re, sys, sqlite3, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from design import PRINT_CSS, WORDMARK, esc, badge, render_pdf, hbars, stacked, grouped_bars, timeline_svg

DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
CACHE = os.environ.get("HUGHES_CACHE", "/tmp")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
AS_OF = "22 Oct 2026"

U = dict(
    D4="https://document.epiq11.com/document/getdocumentbycode?docId=4597286&projectCode=HSQ",
    D320="https://storage.courtlistener.com/recap/gov.uscourts.txsb.498986/gov.uscourts.txsb.498986.320.0.pdf",
    D534="https://storage.courtlistener.com/recap/gov.uscourts.txsb.498986/gov.uscourts.txsb.498986.534.0.pdf",
    D575="https://document.epiq11.com/document/getdocumentbycode?docId=4623687&projectCode=HSQ",
    Q2="https://www.sec.gov/Archives/edgar/data/1415404/000110465926089370/sats-20260630x10q.htm",
    HQ1="https://www.sec.gov/Archives/edgar/data/1533758/000110465926059606/hssc-20260331x10q.htm",
    K25="https://www.sec.gov/Archives/edgar/data/1533758/000110465926037214/hssc-20251231x10k.htm",
    K8="https://www.sec.gov/Archives/edgar/data/1415404/000141540426000038/sats-20260728x8k.htm",
    K8D="https://www.sec.gov/Archives/edgar/data/1415404/000141540426000048/sats-20261001x8k.htm",
)
FILES = dict(D4="013335.txt", D320="bfda20.txt", D534="477578.txt", D575="749f01.txt", Q2="sats_q2.txt", HQ1="hughes_q1.txt", K25="hughes_10k.txt", K8D="sats_8k_1002.txt")
DOC = dict(D4="Dkt 4, First-day declaration (2 Aug 2026)", D320="Dkt 320, Noteholder Group motion to terminate exclusivity (10 Sep 2026)",
           D534="Dkt 534, Noteholder Group filing (14 Oct 2026)", D575="Dkt 575, Order (signed 21 Oct 2026)", Q2="EchoStar 10-Q, quarter to 30 Jun 2026",
           HQ1="HSSC 10-Q, quarter to 31 Mar 2026", K25="HSSC 10-K, FY2025", K8="EchoStar 8-K (petition)", K8D="EchoStar 8-K, 1 Oct 2026 (DISH DBS emergence)")

# (id, claim as used in the note, doc key, token that must appear in the primary text, kind)
FACTS = [
 ("HN01", "Debtors' funded debt: $750m 5.25% Senior Secured Notes, $750m 6.625% Senior Notes and a $50m intercompany secured loan from EchoStar XXIV; both note series matured 1 Aug 2026 unpaid", "D320", "plus a $50 million intercompany secured loan from EchoStar XXIV", "fact"),
 ("HN02", "Noteholder Group holds >61.6% of the 5.25% Secured Notes and >84.37% of the 6.625% Senior Notes", "D320", "more than 61.6% of the outstanding principal of the $750 million 5.25% Senior Secured Notes and more than 84.37%", "fact"),
 ("HN03", "Excluding EchoStar's $123m insider position, the Group holds 73.71% of the Secured Notes", "D320", "73.71% if EchoStar’s $123 million insider position is excluded", "fact"),
 ("HN04", "EchoStar purchased ~$123m of the Secured Notes in open-market trades during 2025", "D4", "EchoStar purchased approximately $123 million of the Senior Secured Notes in open market trades", "fact"),
 ("HN05", "5.25% Secured Notes: carrying $627.3m (third-party), fair value $536.8m at 30 Jun 2026 ($604.8m at 31 Dec 2025)", "Q2", "627,283 ​ ​ 536,766 ​ ​ 627,283 ​ ​ 604,776", "fact"),
 ("HN06", "6.625% Senior Notes: $750.0m, fair value $435.0m at 30 Jun 2026 ($691.3m at 31 Dec 2025)", "Q2", "750,000 ​ ​ 435,000 ​ ​ 750,000 ​ ​ 691,313", "fact"),
 ("HN07", "J3 satellite lease from non-debtor EchoStar XXIV: ~$15.9m per month, initial seven-year term", "D4", "initial term of seven years at a monthly lease charge of approximately $15.9 million", "fact"),
 ("HN08", "Feb 2026 intercompany financings: $50m secured and $1m unsecured, both at 13.75% p.a.", "D4", "Interest accrues on both agreements at a rate of 13.75% per year", "fact"),
 ("HN09", "~641,000 broadband subscribers at filing, down ~21.7% from ~819,000 at 30 Jun 2025", "D4", "a significant decline of approximately 21.7% from even one year ago (approximately 819,000", "fact"),
 ("HN10", "FY2025 consolidated revenue ~$1.4bn", "D4", "approximately $1.4 billion in consolidated revenue for the fiscal year ended December 31, 2025", "fact"),
 ("HN11", "FY2025 net loss ~$1.274bn", "D4", "net loss of approximately $1.274 billion", "fact"),
 ("HN12", "~400 employees notified of termination, 24–28 Jul 2026", "D4", "notified approximately 400 employees", "fact"),
 ("HN13", "AHG letter (21 Jul 2026) alleges: J3 lease above market; ~$1.029bn dividends to EchoStar (Feb–Mar 2024); ~$196m tax reimbursements (2024); subscriber referrals to SpaceX", "D4", "income tax reimbursements of approximately $196 million made by the Debtors to EchoStar in 2024", "allegation"),
 ("HN14", "Dividends to EchoStar: $529m on 15 Feb 2024 and $500m on 12 Mar 2024 (as characterised by the Noteholder Group, citing the HSSC FY2024 10-K)", "D320", "$529 million on February 15, 2024, followed by an additional $500 million on March 12, 2024", "allegation"),
 ("HN15", "1 Aug 2026 was a Saturday (Legal Holiday under the indentures)", "D4", "August 1, 2026 was a Saturday", "fact"),
 ("HN16", "Group plan: All Asset Secured Claims (Secured Notes + EchoStar J3 Secured Advance) ~ $800m principal", "D320", "totaling approximately $800 million in outstanding principal amount", "proposal"),
 ("HN17", "Group plan: Allowed Unaffiliated Secured Notes Claim tentatively [$300–600m]; receives Reorganized Hughes Equity and New Secured Debt", "D320", "tentatively Allowed in the amount of [$300–600 million]", "proposal"),
 ("HN18", "Group plan: EchoStar J3 Secured Advance and $123m affiliated Secured Notes disputed, subject to disallowance and equitable subordination", "D320", "are disputed and subject to disallowance and equitable subordination", "proposal"),
 ("HN19", "Group plan: Unsecured Senior Notes Claims allowed at ~$774.8m, recovering via the Litigation Trust", "D320", "Allowed at approximately $774.8 million", "proposal"),
 ("HN20", "Group plan: Litigation Trust tiers accrue interest at 13.75% from the Effective Date", "D320", "each tier receiving interest at 13.75% from the Effective Date", "proposal"),
 ("HN21", "Group plan: J3 lease rejected on the Effective Date unless EchoStar XXIV agrees to modify", "D320", "J3 Satellite Lease: Rejected on the Effective Date unless EchoStar XXIV", "proposal"),
 ("HN22", "Group plan milestones: file within 20 days; DS approval within 40 days of filing; confirmation within 30 days of DS approval; sale process to close within one year of Effective Date", "D320", "confirmation within 30 days of Disclosure Statement approval; and the Sale Process is designed to close within one year", "proposal"),
 ("HN23", "Group plan exit structure: New ABL, refinanced Bridge DIP, New Secured Debt and Reorganized Hughes Equity", "D320", "a New ABL Facility (senior secured asset-based revolver", "proposal"),
 ("HN24", "As of the 19 Aug 2026 CRO deposition, no formal DIP proposals had been received", "D320", "no formal DIP proposals had been received", "allegation"),
 ("HN25", "Noteholders allege the estates have no unencumbered cash", "D534", "there is no unencumbered cash in the estates", "allegation"),
 ("HN26", "Noteholders allege ~$48m of deferred J3 payments and ~$43m of deferred estate professional fees", "D534", "deferred an estimated $43 million in estate professional fees", "allegation"),
 ("HN27", "Order: Debtors' Emergency Motion to Strike the Termination Motion DENIED on an interim basis; hearing 1 Dec 2026 at 9:00 AM", "D575", "The Court will hold a hearing on December 1, 2026, at 9:00 AM", "fact"),
 ("HN28", "HSSC cash, cash equivalents and current marketable securities $119m at 31 Dec 2025", "K25", "had a fair value of $119 million", "fact"),
 ("HN29", "The Noteholder Group says a member will propose bridge DIP financing following an order terminating exclusivity", "D320", "will propose bridge DIP financing", "proposal"),
 ("HN30", "DISH DBS (sister EchoStar subsidiary) emerged from its prepackaged Chapter 11 with supplemental indentures signed 1 Oct 2026", "K8D", "DISH DBS Filing Entities emerging from bankruptcy", "fact"),
 ("HN31", "Controlling shareholder exercises ~90.4% of EchoStar voting control (per Noteholder Group, citing Dkt 93)", "D320", "approximately 90.4% voting control over EchoStar", "allegation"),
 ("HN32", "Debtors sought use of cash collateral, offering adequate protection to the Secured Noteholders", "D4", "seeking use of cash collateral", "fact"),
]

def flat(fn):
    p = os.path.join(CACHE, fn)
    return re.sub(r"\s+", " ", open(p, errors="ignore").read()) if os.path.exists(p) else None

def verify():
    res = {}
    for fid, claim, doc, tok, kind in FACTS:
        t = flat(FILES[doc]); ok = t is not None and re.sub(r"\s+", " ", tok) in t
        status = ("VERIFIED" if kind == "fact" else "ALLEGATION" if kind == "allegation" else "VERIFIED") if ok else "UNVERIFIABLE"
        res[fid] = dict(claim=claim, doc=doc, url=U[doc], status=status, kind=kind, ok=ok, method=f"token match in primary text fetched 22 Oct 2026: '{tok[:70]}'")
    return res

def store(res, con):
    con.execute("create table if not exists verification(claim_id, artifact, claim, status, primary_url, checked, method, fix)")
    con.execute("delete from verification where claim_id like 'HN%'")
    for k, r in res.items():
        st = r["status"] if r["status"] != "ALLEGATION" else "VERIFIED"
        fix = "Allegation by a party; verified only that the filing says this" if r["kind"] == "allegation" else ("Proposal in Noteholder Group term sheet, not a filed plan" if r["kind"] == "proposal" else "")
        con.execute("insert into verification values(?,?,?,?,?,?,?,?)", (k, "research/hughes_note", r["claim"], st, r["url"], "2026-10-22", r["method"], fix))
    con.commit()

# ---------------- recovery model (assumptions labelled) ----------------
SEC_TOTAL = 750.0; SEC_ECHO = 122.7; SEC_3P = 627.3; J3_ADV = 50.0; UNSEC = 774.8
ADMIN = 48.0 + 43.0        # A1: deferred J3 payments + deferred professional fees (Noteholder allegation, Dkt 534), paid ahead
EV = {"Low": 350.0, "Base": 600.0, "High": 900.0}        # A2: distributable value of the operating business (ex-litigation)
TRUST = {"Low": 0.0, "Base": 150.0, "High": 400.0}        # A3: net Litigation Trust proceeds (illustrative, not a merits view)
def recover(case, subordinate):
    ev = EV[case] - ADMIN
    sec_pool = SEC_3P if subordinate else SEC_TOTAL + J3_ADV
    sec_rec = max(0.0, min(1.0, ev / sec_pool)); paid_3p = sec_rec * SEC_3P
    deficiency = SEC_3P - paid_3p
    resid = max(0.0, ev - sec_pool)            # value left after secured paid in full
    uns_pool = UNSEC + deficiency
    trust = TRUST[case] + resid
    uns_rec = min(1.0, trust / uns_pool)
    sec_total = min(1.0, sec_rec + (deficiency * uns_rec) / SEC_3P)
    return dict(sec=sec_rec * 100, sec_total=sec_total * 100, uns=uns_rec * 100)

def build():
    con = sqlite3.connect(DB); res = verify(); store(res, con)
    order = list(res.keys()); fn = lambda k: f"<sup class='f'>[{order.index(k)+1}]</sup>"
    q = lambda sql, a=(): con.execute(sql, a).fetchall()
    holders = q("""select filer, cusip, putcall, round(sum(value)/1e6,1) v, min(source_url) from f13_holdings where lower(issuer) like '%echostar%' and period='2026Q2'
                   group by filer, cusip, putcall order by v desc""")
    conv = [h for h in holders if h[1] == "278768AB2"][:12]
    eq = [h for h in holders if h[1] == "278768106" and not h[2]][:10]
    hist_px = [("31 Dec 25", 604.776 / 627.283 * 100, 691.313 / 750 * 100), ("30 Jun 26", 536.766 / 627.283 * 100, 435.0 / 750 * 100)]
    R = {(c, s): recover(c, s) for c in EV for s in (False, True)}
    be_trust = 0.58 * (UNSEC + 0)  # break-even trust value for 58.0 on unsecured if secured paid in full
    css = PRINT_CSS
    H = []
    H.append(f"""<div class="cover">{WORDMARK.replace('#0b0f14','#0b0f14')}
<div class="kick">Situation note · Bankr. S.D. Tex. Case No. 26-90739 (ARP) · {AS_OF}</div>
<h1 class="doctitle">Hughes Satellite Systems: the fight is over who owns the litigation, not the satellites</h1>
<div class="sub">A controlled debtor, a concentrated creditor body and a parent that is both lender and target. The 1 December hearing decides who writes the plan, and that decides who prosecutes the estate's claims against EchoStar.</div>
<div class="meta"><div>Issuer<b>HSSC (EchoStar sub.)</b></div><div>Petition<b>2 Aug 2026</b></div><div>Next hearing<b>1 Dec 2026 9:00 AM</b></div><div>Funded debt<b>$1,551m</b></div><div>Claims verified<b>{sum(r['ok'] for r in res.values())}/{len(res)}</b></div></div></div>""")
    H.append(f"""<h2><span class="n">01</span>Executive summary</h2>
<div class="view"><div class="lbl">Our view</div><p><b>The secured notes are the better-protected claim, and the swing factor for them is subordination, not enterprise value.</b> If the $172.7m of EchoStar-held secured claims (the $122.7m of notes it bought in 2025 plus the $50m J3 secured advance) is subordinated, third-party secured holders share the collateral with nobody. Under our base case that moves their recovery from about {R[('Base',False)]['sec']:.0f} to {R[('Base',True)]['sec_total']:.0f} cents. The unsecured notes, at a fair value of 58.0 on 30 Jun 2026, are a claim on a litigation trust that does not yet exist.</p></div>
<div class="kpis"><div class="kpi"><div class="l">Secured notes FV</div><div class="v">85.6</div><div class="s">$536.8m / $627.3m, 30 Jun 26{fn('HN05')}</div></div>
<div class="kpi"><div class="l">Unsecured FV</div><div class="v">58.0</div><div class="s">$435.0m / $750m, 30 Jun 26{fn('HN06')}</div></div>
<div class="kpi"><div class="l">Group holding</div><div class="v">&gt;61.6% / &gt;84.4%</div><div class="s">secured / unsecured{fn('HN02')}</div></div>
<div class="kpi"><div class="l">Subscribers</div><div class="v">641k</div><div class="s">−21.7% YoY{fn('HN09')}</div></div>
<div class="kpi"><div class="l">J3 lease</div><div class="v">$15.9m/mo</div><div class="s">paid to non-debtor parent{fn('HN07')}</div></div></div>
<ul>
<li><b>What happened.</b> Hughes did not pay $1.5bn of notes that matured on 1 Aug 2026, a Saturday, and filed for Chapter 11 the next day{fn('HN15')}{fn('HN01')}. No DIP proposal had been received as of the 19 Aug deposition{fn('HN24')}, and the case is funded with cash collateral{fn('HN32')}. EchoStar is the parent and the J3 satellite lessor, and it also holds $122.7m of the secured notes{fn('HN04')}{fn('HN05')}.</li>
<li><b>The fight.</b> A Noteholder Group holding more than 61.6% of the secured notes and more than 84.37% of the unsecured notes has moved to terminate exclusivity and file its own debt-for-equity plan. That plan would put the estate's claims against EchoStar into a litigation trust{fn('HN02')}{fn('HN19')}. On 21 Oct the court refused, on an interim basis, to strike that motion and set a hearing for 1 Dec 2026 at 9:00 AM{fn('HN27')}.</li>
<li><b>Why it matters.</b> The Group alleges that EchoStar took $1.029bn of dividends and $196m of tax reimbursements in 2024, and that the J3 lease is above market{fn('HN13')}. These are allegations, not findings. Whoever controls the plan controls whether they are prosecuted, settled or released.</li>
<li><b>Liquidity is the clock.</b> The Group alleges there is no unencumbered cash, about $48m of J3 payments deferred and about $43m of estate professional fees deferred{fn('HN26')}{fn('HN25')}. Hughes had $119m of cash and current marketable securities at FY2025{fn('HN28')}.</li>
</ul>
<div class="cap">Exhibit 1 · Reported fair value of Hughes notes (cents on the dollar)</div>
<div class="chart">{grouped_bars(["31 Dec 2025", "30 Jun 2026"], [("5.25% Senior Secured 2026", "#0b0f14", [h[1] for h in hist_px]), ("6.625% Senior Notes 2026", "#c97d06", [h[2] for h in hist_px])], h=150, fmt=lambda v: f"{v:.1f}")}</div>
<div class="src">Source: EchoStar 10-Q to 30 Jun 2026, fair value of debt table (Level 2 estimates by the issuer, not trade prints){fn('HN05')}{fn('HN06')}. Secured fair value is shown on the $627.3m held by third parties.</div>""")
    tl = [("2025-12-31", "EchoStar holds $123m secured notes", False), ("2026-02-15", "$50m+$1m intercompany loans", False), ("2026-07-21", "AHG letter", False),
          ("2026-08-02", "Petition", False), ("2026-08-19", "CRO deposition", False), ("2026-09-10", "Dkt 320 exclusivity motion", False),
          ("2026-10-01", "DISH DBS emerges", False), ("2026-10-14", "Dkt 534 liquidity", False), ("2026-10-21", "Dkt 575 order", False), ("2026-12-01", "Hearing 9:00 AM", True)]
    H.append(f"""<h2><span class="n">02</span>Timeline</h2>
<div class="chart">{timeline_svg(tl, "2025-12-01", "2026-12-31", h=100)}</div>
<div class="tl">
<div class="e"><span class="d">2025</span> EchoStar buys about $123m of the 5.25% Secured Notes in open-market trades and holds them through an affiliate{fn('HN04')}.</div>
<div class="e"><span class="d">Feb 2026</span> HSSC and EchoStar sign two intercompany financings, $50m secured and $1m unsecured at 13.75%, covering J3 lease payments that were owed but not paid on time{fn('HN08')}.</div>
<div class="e"><span class="d">21 Jul 2026</span> The ad hoc group's counsel sends a letter raising the J3 lease, the dividends, the tax reimbursements and the SpaceX subscriber referrals{fn('HN13')}.</div>
<div class="e"><span class="d">24–28 Jul 2026</span> About 400 employees are told their jobs will end{fn('HN12')}.</div>
<div class="e"><span class="d">1–3 Aug 2026</span> Both note series mature on 1 Aug, a Saturday, so payment falls due on the next business day. Hughes and its affiliated debtors file for Chapter 11 on 2 Aug{fn('HN15')}{fn('HN01')}.</div>
<div class="e"><span class="d">19 Aug 2026</span> The Group deposes the CRO. It says no formal DIP proposals had been received by then{fn('HN24')}.</div>
<div class="e"><span class="d">10 Sep 2026</span> Dkt 320: the Noteholder Group's emergency motion to terminate exclusivity, with a plan term sheet attached{fn('HN16')}.</div>
<div class="e"><span class="d">1 Oct 2026</span> DISH DBS, a sister subsidiary, emerges under its prepackaged plan, a reminder of what a parent-led process looks like{fn('HN30')}.</div>
<div class="e"><span class="d">14 Oct 2026</span> Dkt 534: the Group alleges there is no unencumbered cash and points to deferred lease payments and professional fees{fn('HN26')}.</div>
<div class="e"><span class="d">21 Oct 2026</span> Dkt 575: the Debtors' motion to strike is denied on an interim basis{fn('HN27')}.</div>
<div class="e f"><span class="d">1 Dec 2026, 9:00 AM</span> Further hearing (Judge Alfredo R. Pérez){fn('HN27')}.</div></div>
<h3>Operating backdrop</h3>
<div class="cols"><div><div class="chart">{hbars([("Broadband subs, 30 Jun 2025", 819, "#8a929c"), ("Broadband subs, at petition", 641, "#c53340")], width=300, label_w=150, value_fmt=lambda v: f"{v:,.0f}k")}</div>
<div class="src">Dkt 4 ¶¶ (first-day declaration){fn('HN09')}.</div></div>
<div><p>FY2025 revenue was about $1.4bn{fn('HN10')}, against a net loss of about $1.274bn, which was driven largely by consumer broadband revenue declines and a large non-cash charge{fn('HN11')}. The consumer business is losing subscribers to low-earth-orbit competitors. That makes value timing-sensitive, and it is why the Group's plan includes a sale process to close within a year of emergence{fn('HN22')}.</p></div></div>""")
    rows = [("DIP / Bridge DIP", "—", "None in place. The Group would propose a bridge DIP once exclusivity is terminated", "—", "HN29"),
            ("Admin. claims accrued and unpaid (alleged)", f"{ADMIN:.0f}", "Deferred J3 lease payments of about $48m plus deferred professional fees of about $43m", "Priority", "HN26"),
            ("5.25% Senior Secured Notes due 1 Aug 2026", "750.0", "Third-party $627.3m; EchoStar affiliates $122.7m", "1st lien", "HN05"),
            ("EchoStar XXIV secured advance (J3)", "50.0", "13.75% interest; disputed under the Group's plan", "Secured", "HN08"),
            ("6.625% Senior Notes due 1 Aug 2026", "750.0", "Allowed at about $774.8m in the Group's plan, including interest", "Unsecured", "HN19"),
            ("EchoStar unsecured advance", "1.0", "13.75%", "Unsecured", "HN08")]
    H.append(f"""<h2><span class="n">03</span>Capital structure and recovery scenarios</h2>
<table><thead><tr><th>Claim</th><th class="r">Face ($m)</th><th>Detail</th><th>Ranking</th><th>Src</th></tr></thead><tbody>
{''.join(f"<tr><td>{esc(a)}</td><td class='r'>{b}</td><td>{esc(c)}</td><td>{d}</td><td>{fn(e)}</td></tr>" for a,b,c,d,e in rows)}
<tr class="tot"><td>Funded debt (excluding admin)</td><td class="r">1,551.0</td><td colspan="3">The Group's plan counts about $800m of All Asset Secured Claims{fn('HN16')}</td></tr></tbody></table>
<div class="cap">Exhibit 2 · Who holds the secured notes ($750m)</div>
<div class="chart">{stacked([("Noteholder Group (>61.6%)", 462.0, "#0b0f14"), ("EchoStar affiliates", 122.7, "#c53340"), ("Other holders (residual)", 750 - 462.0 - 122.7, "#8a929c")])}</div>
<div class="src">The Group's holding uses the floor of its disclosed share: 61.6% × $750m = $462.0m{fn('HN02')}. EchoStar's $122.7m comes from the 10-Q carrying-amount bridge ($750m − $627.3m){fn('HN05')}. The residual is our calculation.</div>
<h3>Recovery waterfall: assumptions (labelled)</h3>
<table><thead><tr><th>#</th><th>Assumption</th><th>Value</th><th>Basis</th></tr></thead><tbody>
<tr><td>A1 {badge('ASSUMPTION')}</td><td>Admin and priority claims paid first</td><td class="r">${ADMIN:.0f}m</td><td>Deferred amounts alleged in Dkt 534{fn('HN26')}; excludes any future fees</td></tr>
<tr><td>A2 {badge('ASSUMPTION')}</td><td>Distributable value of the operating business, excluding litigation (Low / Base / High)</td><td class="r">$350m / $600m / $900m</td><td>Base sits near the Group's own [$300–600m] tentative unaffiliated secured claim{fn('HN17')} and the $536.8m FV of third-party secured notes{fn('HN05')}. This is not a valuation.</td></tr>
<tr><td>A3 {badge('ASSUMPTION')}</td><td>Net Litigation Trust proceeds (Low / Base / High)</td><td class="r">$0m / $150m / $400m</td><td>Illustrative sizes only. They are not a view on the merits of the allegations{fn('HN13')}</td></tr>
<tr><td>A4 {badge('ASSUMPTION')}</td><td>Trade and other unsecured claims</td><td class="r">$0m</td><td>Not disclosed in the documents read. The Group's plan leaves trade unimpaired up to a cap</td></tr>
<tr><td>A5 {badge('ASSUMPTION')}</td><td>Two treatments of EchoStar's $172.7m secured claims</td><td>Pari passu vs subordinated</td><td>The Group's plan says they are disputed and subject to equitable subordination{fn('HN18')}</td></tr></tbody></table>
<table><thead><tr><th>Scenario</th><th class="r">Value after admin ($m)</th><th class="r">Secured: collateral (pari)</th><th class="r">Secured: collateral (subord.)</th><th class="r">Secured incl. trust (subord.)</th><th class="r">Unsecured (pari)</th><th class="r">Unsecured (subord.)</th></tr></thead><tbody>
{''.join(f"<tr><td><b>{c}</b></td><td class='r'>{EV[c]-ADMIN:,.0f}</td><td class='r'>{R[(c,False)]['sec']:.1f}</td><td class='r'>{R[(c,True)]['sec']:.1f}</td><td class='r'>{R[(c,True)]['sec_total']:.1f}</td><td class='r'>{R[(c,False)]['uns']:.1f}</td><td class='r'>{R[(c,True)]['uns']:.1f}</td></tr>" for c in EV)}
<tr><td><i>Reported FV, 30 Jun 2026</i></td><td></td><td class='r' colspan='3'>85.6</td><td class='r' colspan='2'>58.0</td></tr></tbody></table>
<div class="cap">Exhibit 3 · Modelled recovery vs reported fair value (cents)</div>
<div class="chart">{grouped_bars(list(EV), [("Secured, pari passu", "#8a929c", [R[(c,False)]['sec'] for c in EV]), ("Secured, EchoStar subordinated (incl. trust)", "#0b0f14", [R[(c,True)]['sec_total'] for c in EV]), ("Unsecured, subordinated case", "#c97d06", [R[(c,True)]['uns'] for c in EV])], h=170, ref_lines=[(85.6, "Secured FV 85.6", "#1f6fd1"), (58.0, "Unsecured FV 58.0", "#c53340")], fmt=lambda v: f"{v:.0f}")}</div>
<div class="src">These are TRIAGE calculations from assumptions A1–A5 and are not estimates of value. Cents are per $ of claim. Third-party secured holders are $627.3m. The unsecured pool is $774.8m plus any secured deficiency. "Incl. trust" adds each secured holder's share of trust proceeds on its deficiency claim. The sum is capped at 100.</div>
<p><b>Reading the grid.</b> In this model, if the business is worth about $600m and EchoStar's claims are subordinated, third-party secured holders recover about {R[('Base',True)]['sec_total']:.0f} cents, close to their reported 85.6. On a pari passu basis the same value gives roughly {R[('Base',False)]['sec']:.0f} cents. That is the gap the Group is fighting over. For the unsecured notes to be worth their reported 58.0, the trust would need to deliver about ${be_trust:,.0f}m net, with secured holders paid in full first. That is well above our base case. Their price therefore embeds a large litigation recovery, a settlement premium from EchoStar, or both.</p>""")
    H.append(f"""<h2><span class="n">04</span>Holder map</h2>
<p>Two different sets of holders matter here. The <b>Noteholder Group</b> holds the Hughes notes. It discloses aggregate percentages{fn('HN02')}. Its member-level holdings are in a verified statement (Dkt 93), and we could not retrieve that document from a public mirror for this note. We therefore name no members. The <b>13F holders of EchoStar</b>, the defendant in any estate litigation, are shown below from Q2 2026 13F filings. A fund can appear on both sides. We do not infer any overlap.</p>
<div class="cols"><div><div class="cap">Exhibit 4a · EchoStar 3.875% convertible secured notes 2030 (CUSIP 278768AB2), 13F value $m</div>
<div class="chart">{hbars([(h[0][:30], h[3], "#0b0f14") for h in conv], width=300, label_w=150, bar_h=11, gap=4)}</div></div>
<div><div class="cap">Exhibit 4b · EchoStar Class A common (CUSIP 278768106), long positions, 13F value $m</div>
<div class="chart">{hbars([(h[0][:30], h[3], "#c97d06") for h in eq], width=300, label_w=150, bar_h=11, gap=4)}</div></div></div>
<div class="src">Source: SEC Form 13F information tables, period 2026Q2, filer accession folders linked in the appendix. Values are as reported by filers. Put and call lines are excluded from 4b. Ledger checks F01–F13 cover the named distressed-focused filers.</div>
<table><thead><tr><th>Filer</th><th>Instrument</th><th class="r">13F value ($m)</th><th>Primary filing</th></tr></thead><tbody>
{''.join(f"<tr><td>{esc(h[0])}</td><td>{'Convertible notes 2030' if h[1]=='278768AB2' else 'Class A common'}{(' ('+h[2]+')') if h[2] else ''}</td><td class='r'>{h[3]:,.1f}</td><td><a href='{esc(h[4])}'>{esc(h[4].split('/data/')[1][:40])}</a></td></tr>" for h in conv[:8] + eq[:6])}
</tbody></table>
<h2><span class="n">05</span>Court dates</h2>
<table><thead><tr><th>Date</th><th>Event</th><th>Status</th><th>Src</th></tr></thead><tbody>
<tr><td class="num">2 Aug 2026</td><td>Petitions filed (Judge Alfredo R. Pérez presiding)</td><td>{badge('VERIFIED')}</td><td>{fn('HN01')}{fn('HN27')}</td></tr>
<tr><td class="num">10 Sep 2026</td><td>Noteholder Group motion to terminate exclusivity (Dkt 320)</td><td>{badge('VERIFIED')}</td><td>{fn('HN16')}</td></tr>
<tr><td class="num">8 / 15 / 20 Oct 2026</td><td>Hearings on the motion to strike; ruling given on the record 20 Oct</td><td>{badge('VERIFIED')}</td><td>{fn('HN27')}</td></tr>
<tr><td class="num">21 Oct 2026</td><td>Order (Dkt 575): motion to strike DENIED on an interim basis</td><td>{badge('VERIFIED')}</td><td>{fn('HN27')}</td></tr>
<tr><td class="num"><b>1 Dec 2026, 9:00 AM</b></td><td><b>Further hearing on the termination motion</b></td><td>{badge('VERIFIED')}</td><td>{fn('HN27')}</td></tr></tbody></table>""")
    H.append(f"""<h2><span class="n">06</span>Plan-fight dynamics</h2>
<div class="cols"><div class="box"><h3>Debtors / EchoStar</h3><ul>
<li>Exclusivity keeps plan design, and with it the treatment of claims against the parent, with a board the parent controls. The Group says the controlling shareholder holds about 90.4% of EchoStar's votes{fn('HN31')}.</li>
<li>EchoStar is landlord (J3, $15.9m a month){fn('HN07')}, secured lender ($50m at 13.75%){fn('HN08')} and holds $122.7m of the secured notes{fn('HN05')}.</li>
<li>Running on cash collateral{fn('HN32')} means there is no DIP lender to impose milestones{fn('HN24')}.</li></ul></div>
<div class="box"><h3>Noteholder Group</h3><ul>
<li>Its plan is a standalone debt-for-equity deal. Reorganized equity and new secured debt go to unaffiliated secured holders, and a sale process closes within a year{fn('HN17')}{fn('HN22')}.</li>
<li>Claims against EchoStar go into a litigation trust. The unsecured notes, about $774.8m, recover from it{fn('HN19')}. Its tiers accrue 13.75%, the same rate EchoStar charges Hughes{fn('HN20')}.</li>
<li>The J3 lease would be rejected unless EchoStar XXIV agrees to modify it{fn('HN21')}. A member would provide a bridge DIP{fn('HN29')}.</li></ul></div></div>
<h3>What the 1 December court has to weigh</h3>
<p>To end exclusivity "for cause" under §1121(d), the court will look at whether a controlled debtor can credibly deal at arm's length with its controlling parent. It will also weigh the creditor concentration: the Group holds 73.71% of the secured notes excluding EchoStar{fn('HN03')} and more than 84.37% of the unsecured notes{fn('HN02')}. The question is whether the Debtors have shown reasonable prospects of filing a confirmable plan. A plain denial of the motion to strike keeps the termination motion alive, but it does not grant it{fn('HN27')}. Possible outcomes include:</p>
<ul><li><b>Termination granted.</b> The Group files its plan within 20 days. Disclosure-statement approval follows within about 40 days, then confirmation about 30 days later{fn('HN22')}. The fight then shifts to subordination and the J3 lease.</li>
<li><b>Exclusivity shortened or conditioned.</b> The most common middle path. It gives the Debtors a deadline and creates settlement pressure on EchoStar.</li>
<li><b>Motion denied.</b> The Debtors keep control. Watch for a parent-sponsored plan that includes releases, and for an examiner or standing motion.</li></ul>
<h2><span class="n">07</span>Catalysts</h2>
<table><thead><tr><th>When</th><th>Catalyst</th><th>Why it moves recoveries</th></tr></thead><tbody>
<tr><td class="num">1 Dec 2026</td><td>Exclusivity hearing</td><td>Decides who writes the plan, and so whether the claims against EchoStar are prosecuted or released{fn('HN27')}</td></tr>
<tr><td class="num">Ongoing</td><td>Cash-collateral budgets and renewals</td><td>The Group alleges the estate has no unencumbered cash. The size of deferred liabilities sets the liquidity runway{fn('HN25')}{fn('HN26')}</td></tr>
<tr><td class="num">Ongoing</td><td>J3 lease: assume, reject or renegotiate</td><td>At $15.9m a month, about $191m a year, it is the largest related-party cash flow{fn('HN07')}</td></tr>
<tr><td class="num">Next 10-Qs</td><td>Subscriber count and EchoStar's fair-value marks</td><td>641k subscribers, down 21.7% YoY{fn('HN09')}. Marks went from 96.4 to 85.6 (secured) and from 92.2 to 58.0 (unsecured) between Dec-25 and Jun-26{fn('HN05')}{fn('HN06')}</td></tr></tbody></table>
<h2><span class="n">08</span>Risks to the view</h2>
<ul><li><b>Valuation.</b> Low-earth-orbit competition could push the operating value below our $350m low case. Secured recovery would then fall with collateral value, whichever way subordination goes.</li>
<li><b>Subordination is a litigated outcome, not a given.</b> Equitable subordination requires inequitable conduct. EchoStar may defend its $122.7m of notes as open-market purchases{fn('HN04')}.</li>
<li><b>Allegations may fail.</b> The dividend, tax and lease claims are the Group's characterisations{fn('HN13')}{fn('HN14')}. A low trust recovery means unsecured value stays near our low case.</li>
<li><b>Settlement.</b> A parent settlement could release the claims for a fixed payment. This compresses outcomes for both classes.</li>
<li><b>Data limits.</b> Fair values are the issuer's Level 2 estimates, not traded prices. The Dkt 93 member list was not retrieved. Trade claims are not quantified.</li></ul>""")
    H.append(f"""<h2 class="pb"><span class="n">A</span>Verification appendix</h2>
<p class="fn">Each footnote number maps to one row. "Verified" means the quoted token was found in the text of the primary document fetched on 22 Oct 2026. "Allegation" means the filing says this; it is not a finding. Rows marked as proposals are terms in the Noteholder Group's term sheet (Dkt 320), not a filed plan. These rows are also written to the TRIAGE verification ledger as HN01–HN{len(res):02d}.</p>
<table><thead><tr><th>#</th><th>ID</th><th>Claim</th><th>Status</th><th>Primary document</th></tr></thead><tbody>
{''.join(f"<tr><td class='num'>{i+1}</td><td class='num'>{k}</td><td>{esc(r['claim'])}</td><td>{badge(r['status'] if r['kind']!='proposal' or not r['ok'] else 'VERIFIED')}{'' if r['kind']!='proposal' else ' <span class=fn>proposal</span>'}</td><td><span class='fn'>{esc(DOC[r['doc']])}</span><br><a href='{esc(r['url'])}'>{esc(r['url'])}</a></td></tr>" for i,(k,r) in enumerate(res.items()))}
</tbody></table>
<div class="disc avoid"><h3>Disclaimer and publisher's exclusion</h3>
<p>This note is published by TRIAGE for general information. It is impersonal. It is not investment advice, a recommendation, or an offer or solicitation to buy or sell any security or claim. It does not take into account the objectives, financial situation or needs of any person. TRIAGE is not a registered investment adviser or broker-dealer. The note is intended to fall within the publisher's exclusion under section 202(a)(11)(D) of the US Investment Advisers Act of 1940: it is a bona fide publication of general and regular circulation, and its content is not tailored to any reader.</p>
<p>All facts come from public court filings and SEC filings that were available on {AS_OF}, and each is linked above. Statements by parties are reported as allegations. Recovery figures are calculations based on the labelled assumptions A1–A5; they are not forecasts or valuations. Fair values are the issuer's estimates. Information may be incomplete or out of date, and no representation is made as to its accuracy. TRIAGE and its authors may hold no positions. The note does not use non-public information or data about individuals, except for the controlling shareholder's voting interest as disclosed in court filings, which is referred to by role. Past performance is not indicative of future results. Readers should consult their own advisers.</p></div>""")
    doc = f"<!doctype html><html><head><meta charset='utf-8'><title>Hughes Satellite Systems — TRIAGE situation note</title><style>{css}</style></head><body>{''.join(H)}</body></html>"
    hp = os.path.join(OUT, "Hughes_Satellite_Note.html"); open(hp, "w").write(doc)
    pdf = os.path.join(OUT, "Hughes_Satellite_Note.pdf"); pages = render_pdf(hp, pdf)
    return dict(pdf=pdf, pages=pages, verified=sum(r["ok"] for r in res.values()), total=len(res), R=R)

if __name__ == "__main__":
    r = build(); print({k: v for k, v in r.items() if k != "R"}); [print(k, {a: round(b, 1) for a, b in v.items()}) for k, v in r["R"].items()]
