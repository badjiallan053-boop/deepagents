"""Build the TRIAGE OS master report (markdown + charts + PDF). All facts unverified; public sources only."""
import json, os, subprocess, sqlite3
OUT = os.environ.get("TRIAGE_OUT", "/workspace/triage_os_data")
CH = os.path.join(OUT, "master")

SIGNALS = [  # name, precision %, median lead days, n hits / n fired, note
    ("BDC mark cliff (cross-BDC)", 33.3, 91, "base rate 1.2%, ~28x lift"),
    ("8-K 2.04 + 3.01 combo", 23.0, 51, "51 of 222"),
    ("8-K 2.04 alone", 14.6, 56, "acceleration"),
    ("8-K 3.01 alone", 4.8, 200, "delisting notice"),
    ("NT 10-K", 3.9, 197, "late filing"),
    ("4.01 + NT combo", 3.1, None, ""),
    ("Sale-leaseback", 2.6, None, ""),
    ("Covenant waiver", 2.4, None, ""),
    ("4.01 auditor change", 2.0, 265, ""),
]
SCEN = {"Conservative": [5, 20, 45, 70], "Base": [12, 45, 100, 160], "Bull": [25, 90, 200, 320]}  # cumulative $k by month 3,6,9,12

def unit_rev(s):  # assumptions only
    return s

def charts():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    os.makedirs(CH, exist_ok=True)
    n = [s[0] for s in SIGNALS]; p = [s[1] for s in SIGNALS]
    fig, ax = plt.subplots(figsize=(8, 4)); ax.barh(n[::-1], p[::-1], color="#2b6cb0")
    ax.set_xlabel("Backtest precision % (2019-2026)"); ax.set_title("Signal precision"); fig.tight_layout()
    fig.savefig(f"{CH}/signals.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 3.5))
    for k, v in SCEN.items(): ax.plot([3, 6, 9, 12], v, marker="o", label=k)
    ax.set_xlabel("Month"); ax.set_ylabel("Cumulative revenue $k (assumption)"); ax.legend(); ax.set_title("Revenue scenarios (assumptions)")
    fig.tight_layout(); fig.savefig(f"{CH}/forecast.png", dpi=130); plt.close(fig)
    bdc = [("ICMB", 145), ("KBDC", 150), ("CION", 157), ("TCPC", 161), ("MFIC", 163)]
    fig, ax = plt.subplots(figsize=(6, 3)); ax.bar([b[0] for b in bdc], [b[1] for b in bdc], color="#c53030")
    ax.axhline(150, ls="--", c="k"); ax.set_ylabel("Asset coverage %"); ax.set_title("BDCs below 170% coverage")
    fig.tight_layout(); fig.savefig(f"{CH}/bdc.png", dpi=130); plt.close(fig)
    hc = [("Medallia*", 44.6), ("Barracuda", 5.5), ("Loparex", 3.1), ("symplr", 1.4), ("Convey", 0.5), ("Scaled Agile", -1.3), ("Cornerstone", -4.3)]
    fig, ax = plt.subplots(figsize=(6, 3)); ax.bar([h[0] for h in hc], [h[1] for h in hc], color=["#999" if h[1] > 20 else "#2f855a" if h[1] >= 0 else "#c53030" for h in hc])
    ax.set_ylabel("12m headcount growth %"); ax.set_title("Private borrowers (Crustdata 22 Oct 2026)"); plt.xticks(rotation=30)
    fig.tight_layout(); fig.savefig(f"{CH}/headcount.png", dpi=130); plt.close(fig)

def db_counts(db=os.path.join(OUT, "triage.db")):
    out = {}
    if not os.path.exists(db): return out
    c = sqlite3.connect(db, timeout=120)
    for t in ["signals", "bdc_marks", "bdc_marks_hist", "holdings_graph", "f13_holdings", "lei_entities", "world_situations", "signals2", "cmbs_loans"]:
        try: out[t] = c.execute(f"select count(*) from {t}").fetchone()[0]
        except Exception: out[t] = None
    return out

def render(md_path, pdf_path):
    import markdown
    html = markdown.markdown(open(md_path).read(), extensions=["tables"])
    css = "body{font-family:Helvetica,Arial;font-size:10.5pt;margin:28px}table{border-collapse:collapse;font-size:9pt}td,th{border:1px solid #bbb;padding:3px 6px}h1{color:#1a365d}h2{color:#2b6cb0;border-bottom:1px solid #ccc;page-break-before:auto}img{max-width:95%}"
    hp = md_path.replace(".md", ".html")
    open(hp, "w").write(f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{html}</body></html>")
    subprocess.run(["google-chrome", "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", f"file://{hp}"], check=True, capture_output=True, timeout=180)
