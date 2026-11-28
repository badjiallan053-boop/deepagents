"""Landing page in the TRIAGE design system (dark, terminal-grade). Numbers come from the DB at build time."""
import os, sqlite3, html, json
DB = os.environ.get("TRIAGE_DB", "/workspace/triage_os_data/triage.db")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "landing", "index.html")
def build(out=OUT):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); q = lambda s: c.execute(s).fetchall()
    st = dict(q("select status,count(*) from verification group by 1")); tot = sum(st.values())
    dist = q("""select borrower, bdc, round(sum(fv)*100.0/sum(par),1) m, round(sum(par)/1e6,1) p, min(source_url) from bdc_marks where period='2026-06-30' and par>0
                and borrower not like 'Investment%' and borrower not like 'Senior Secured%' and borrower not like 'Portfolio Company%' and length(borrower_key)>3
                group by borrower_key, bdc having m between 15 and 75 and count(*)<40 order by sum(par) desc limit 8""")
    import sys; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")); os.environ.setdefault("TRIAGE_DB", DB)
    import server; n_dist = sum(1 for d in server.distressed() if d["qa"] == "ok")  # same definition as the terminal
    hits = sum(1 for _ in open(os.environ.get("TRIAGE_HITLOG", "/workspace/triage_os_data/hit_log.jsonl")))
    rows = "".join(f"<tr><td>{html.escape(b[:46])}</td><td><span class='tag'>{l}</span></td><td class='n'>${p:,.1f}m</td><td class='n {'dn' if m < 50 else 'am'}'>{m:.1f}</td><td class='n'><a href='{html.escape(u)}'>10-Q ↗</a></td></tr>" for b, l, m, p, u in dist)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TRIAGE · Special situations intelligence, sourced to the filing</title>
<link rel="icon" href="/favicon.svg"><style>
:root{{--bg:#07090c;--panel:#0d1117;--line:#1c232c;--line2:#262f3a;--ink:#d7dde4;--mute:#7d8794;--dim:#4f5966;--amber:#f5a524;--up:#2fbf71;--down:#ef4d5a;--info:#4ea1ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 Inter,'IBM Plex Sans',Arial,sans-serif;font-feature-settings:"tnum" 1}}
a{{color:var(--info);text-decoration:none}}.mono,.n{{font-family:'JetBrains Mono','IBM Plex Mono',monospace}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 28px}}
header{{border-bottom:1px solid var(--line);background:rgba(13,17,23,.92);position:sticky;top:0;z-index:5}}header .wrap{{display:flex;align-items:center;height:56px;gap:28px}}
.wm{{display:flex;align-items:center;gap:9px;font:700 15px 'JetBrains Mono';letter-spacing:.32em;color:#fff}}
nav{{display:flex;gap:22px;font-size:13px}}nav a{{color:var(--mute)}}nav a:hover{{color:var(--ink)}}
.cta{{margin-left:auto;background:var(--amber);color:#07090c;font-weight:600;padding:8px 14px;border-radius:3px;font-size:13px}}
.hero{{padding:76px 0 40px;border-bottom:1px solid var(--line);background:radial-gradient(1000px 400px at 75% 0%,rgba(245,165,36,.08),transparent)}}
.kick{{color:var(--amber);font:600 11px Inter;letter-spacing:.18em;text-transform:uppercase}}
h1{{font:600 46px/1.08 'Inter Tight',Inter,sans-serif;letter-spacing:-.02em;margin:14px 0 18px;max-width:900px;color:#fff}}
.lead{{font-size:18px;color:#aab3bd;max-width:760px;margin:0 0 28px}}
.btn{{display:inline-block;padding:11px 18px;border-radius:3px;font-weight:600;font-size:14px}}.btn.p{{background:var(--amber);color:#07090c}}.btn.g{{border:1px solid var(--line2);color:var(--ink);margin-left:10px}}
.strip{{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid var(--line);background:var(--panel);margin-top:48px}}
.strip div{{padding:16px 18px;border-right:1px solid var(--line)}}.strip div:last-child{{border:0}}
.strip .l{{font:600 10px Inter;letter-spacing:.12em;text-transform:uppercase;color:var(--dim)}}.strip .v{{font:600 26px 'JetBrains Mono';margin-top:6px;color:#fff}}.strip .s{{font-size:12px;color:var(--mute)}}
section{{padding:64px 0;border-bottom:1px solid var(--line)}}h2{{font:600 26px 'Inter Tight',Inter;margin:8px 0 10px;color:#fff;letter-spacing:-.01em}}.sub{{color:var(--mute);max-width:760px;margin:0 0 28px}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:22px}}
.card h3{{margin:0 0 8px;font-size:15px;color:#fff}}.card p{{margin:0;color:var(--mute);font-size:13.5px}}.card .k{{font:600 10px Inter;letter-spacing:.14em;color:var(--amber);text-transform:uppercase;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--panel);border:1px solid var(--line)}}th{{text-align:left;font:600 10px Inter;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);padding:10px 12px;border-bottom:1px solid var(--line2);background:#11161d}}
td{{padding:9px 12px;border-bottom:1px solid var(--line)}}td.n{{text-align:right}}.dn{{color:var(--down)}}.am{{color:var(--amber)}}
.tag{{font:500 10px 'JetBrains Mono';border:1px solid var(--line2);color:var(--mute);padding:1px 6px;border-radius:2px}}
.note{{display:grid;grid-template-columns:1.2fr 1fr;gap:28px;align-items:center}}.shot{{border:1px solid var(--line2);border-radius:3px;width:100%;display:block}}
.badge{{display:inline-flex;gap:6px;align-items:center;font:600 10px Inter;letter-spacing:.1em;text-transform:uppercase;padding:3px 8px;border-radius:2px;border:1px solid}}.v{{color:var(--up);border-color:rgba(47,191,113,.4)}}.c{{color:var(--amber);border-color:rgba(245,165,36,.4)}}.u{{color:var(--mute);border-color:var(--line2)}}
footer{{padding:36px 0 60px;color:var(--dim);font-size:12px}}footer p{{max-width:900px}}
</style></head><body>
<header><div class="wrap"><span class="wm"><svg width="22" height="22" viewBox="0 0 32 32"><rect width="32" height="32" rx="5" fill="#f5a524"/><path d="M8 9h16v3h-6.5v12h-3V12H8z" fill="#07090c"/></svg>TRIAGE</span>
<nav><a href="#terminal">Terminal</a><a href="#research">Research</a><a href="#verification">Verification</a><a href="#coverage">Coverage</a></nav><a class="cta" href="/#/overview">Open the terminal</a></div></header>
<div class="hero"><div class="wrap"><div class="kick">Special situations intelligence · as of 22 Oct 2026</div>
<h1>Private-credit distress, court dockets and holder maps, each one sourced to the filing.</h1>
<p class="lead">TRIAGE joins BDC loan marks, Chapter 11 dockets, 13F holders and eleven public registries on company identity. Every number links to the primary document it came from and carries a verification status.</p>
<a class="btn p" href="/research/Hughes_Satellite_Note.pdf">Read the Hughes Satellite note</a><a class="btn g" href="/#/overview">Explore the terminal</a>
<div class="strip"><div><div class="l">BDC positions &lt; 75</div><div class="v">{n_dist:,}</div><div class="s">par-weighted, 30 Jun 2026</div></div>
<div><div class="l">Claims verified</div><div class="v">{st.get('VERIFIED',0)}/{tot}</div><div class="s">{st.get('CORRECTED',0)} corrected after re-read</div></div>
<div><div class="l">Registry rows joined</div><div class="v">3.0m+</div><div class="s">ICIJ, OFAC/UK, Form D, 5500, FAA, EPA, ADV, PSC</div></div>
<div><div class="l">Signal log</div><div class="v">{hits:,}</div><div class="s">sha256-chained, append-only</div></div>
<div><div class="l">Next catalyst</div><div class="v">1 Dec</div><div class="s">Hughes exclusivity hearing</div></div></div></div></div>
<section id="terminal"><div class="wrap"><div class="kick">The terminal</div><h2>Dense, sortable, sourced</h2><p class="sub">Sort and filter tables of marks. Each row has a 13-quarter sparkline, a capital-structure waterfall per situation, a case timeline, a force-directed relationship graph and a Ctrl-K command palette. Click any figure to open its primary source.</p>
<img class="shot" src="/screens/01_overview.png" alt="TRIAGE terminal overview"></div></section>
<section id="coverage"><div class="wrap"><div class="kick">Live from the latest 10-Qs</div><h2>Largest distressed BDC positions</h2><p class="sub">Par-weighted mark is fair value divided by par, taken from 30 Jun 2026 Schedules of Investments. Each row links to its filing.</p>
<table><thead><tr><th>Borrower</th><th>Lender</th><th style="text-align:right">Par</th><th style="text-align:right">Mark</th><th style="text-align:right">Source</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section id="research"><div class="wrap note"><div><div class="kick">Flagship research · 22 Oct 2026</div><h2>Hughes Satellite: the fight is over who owns the litigation, not the satellites</h2>
<p class="sub">Covers the capital structure and recovery scenarios with labelled assumptions, the holder map, the 1 Dec exclusivity hearing, plan-fight dynamics, catalysts and risks. The appendix maps every footnote to a docket entry or SEC filing.</p><a class="btn p" href="/research/Hughes_Satellite_Note.pdf">Download the PDF</a><a class="btn g" href="/research/TRIAGE_Master_Report.pdf">Master report</a></div>
<img class="shot" src="/screens/note_p1.png" alt="Hughes note, page 1"></div></section>
<section id="verification"><div class="wrap"><div class="kick">Verification</div><h2>We publish our corrections</h2><p class="sub">Each claim is re-fetched from its primary source and token-matched. When the source disagrees, the claim is corrected in the open. The ledger is part of the product.</p>
<div class="g3"><div class="card"><div class="k">Verified</div><h3><span class="badge v">● {st.get('VERIFIED',0)} claims</span></h3><p>The token was found in the primary SEC, court or registry document on the date checked.</p></div>
<div class="card"><div class="k">Corrected</div><h3><span class="badge c">● {st.get('CORRECTED',0)} claims</span></h3><p>The primary source disagreed with the claim. The fix is shown next to the original. For example, the Hughes exclusivity status was corrected to Dkt 575.</p></div>
<div class="card"><div class="k">Open</div><h3><span class="badge u">● {st.get('UNVERIFIABLE',0)} claims</span></h3><p>Unverifiable from public sources, so they are left out of research bodies and listed in appendices.</p></div></div></div></section>
<footer><div class="wrap"><p><b>Publisher's exclusion.</b> TRIAGE publishes impersonal research of general and regular circulation. It is not investment advice, a recommendation, or an offer to buy or sell any security. TRIAGE covers companies only, uses public sources only, and does not use personal data.</p><p class="mono">© 2026 TRIAGE · Built on public filings: SEC EDGAR, CourtListener RECAP, Epiq, state and federal registries.</p></div></footer>
</body></html>"""
    os.makedirs(os.path.dirname(out), exist_ok=True); open(out, "w").write(page); return out
if __name__ == "__main__": print(build())
