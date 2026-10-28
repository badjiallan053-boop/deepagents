"""Live price layer (local background service). Polls Yahoo quote endpoint politely:
every 120 s for symbols whose market is open, every 30 min otherwise; batches of 40 symbols, >=1.5 s between calls,
exponential backoff on HTTP errors. Writes /workspace/triage_os_data/live.json (served at /api/live).
Computes: 25-day MA deviation (BNF kairi), new 250-day high on >=2x 50-day volume (CIS), paper-ledger mark-to-market.
Quotes can be delayed (Yahoo field exchangeDataDelayedBy, minutes) and are labelled per symbol. Paper only; not advice.
Usage: python3 live_service.py [--once]
"""
import json, os, sys, time, datetime, subprocess, math
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DATA = "/workspace/triage_os_data"; OUT = f"{DATA}/live.json"; CK = f"{DATA}/edge/yc_live.txt"; LEDGER = f"{DATA}/committee/track_record.jsonl"
HOURS = [  # suffix, tz, open, close
 ((".T",), "Asia/Tokyo", "09:00", "15:30"), ((".AX",), "Australia/Sydney", "10:00", "16:00"), ((".HK",), "Asia/Hong_Kong", "09:30", "16:00"),
 ((".JK",), "Asia/Jakarta", "09:00", "16:00"), ((".L",), "Europe/London", "08:00", "16:30"),
 ((".PA", ".AS", ".DE", ".MI", ".MC", ".OL", ".CO", ".ST", ".HE", ".SW", ".BR"), "Europe/Paris", "09:00", "17:30"), ((".TO", ".V"), "America/Toronto", "09:30", "16:00")]
def is_open(sym, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    for suf, tz, o, c in HOURS:
        if sym.endswith(suf): break
    else: tz, o, c = "America/New_York", "09:30", "16:00"
    l = now.astimezone(ZoneInfo(tz))
    return l.weekday() < 5 and o <= l.strftime("%H:%M") <= c
def sh(*a): return subprocess.run(list(a), capture_output=True, text=True, timeout=60).stdout
def crumb():
    sh("curl", "-s", "-c", CK, "-A", "Mozilla/5.0", "https://fc.yahoo.com"); return sh("curl", "-s", "-b", CK, "-A", "Mozilla/5.0", "https://query1.finance.yahoo.com/v1/test/getcrumb").strip()
def quotes(syms, c):
    out = {}
    for i in range(0, len(syms), 40):
        for attempt in range(3):
            try:
                j = json.loads(sh("curl", "-s", "-m", "30", "-b", CK, "-A", "Mozilla/5.0", f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={','.join(syms[i:i+40])}&crumb={c}"))
                for q in j["quoteResponse"]["result"]: out[q["symbol"]] = q
                break
            except Exception: time.sleep(5 * 2 ** attempt)
        time.sleep(1.5)
    return out
def universe():
    U = {}
    def add(t, why):
        if t and isinstance(t, str): U.setdefault(t.replace(".", "-") if t.count(".") and t.split(".")[-1] in ("A", "B") else t, set()).add(why)
    led = []
    if os.path.exists(LEDGER):
        for l in open(LEDGER):
            r = json.loads(l); t = r.get("ticker")
            if t and r.get("px") and r.get("kind") in ("bottleneck_watch", "edge_lab", "reorg_watch", "bnf_cis_watch"): led.append(r); add(t, "ledger")
    for p, key, why in ((f"{DATA}/bottleneck.json", "top", "bottleneck"), (f"{DATA}/bnf_cis.json", "live", "bnf_cis")):
        if os.path.exists(p):
            for r in json.load(open(p)).get(key, []): add(r.get("t"), why)
    return U, led
def hist(t):
    try:
        import bnf_cis as BC; return BC.pxv(t)
    except Exception: return []
def compute(U, led, Q):
    rows = []
    for t, why in U.items():
        q = Q.get(t, {}); px = q.get("regularMarketPrice"); H = hist(t)
        r = dict(t=t, why=sorted(why), px=px, cur=q.get("currency"), chg_pct=q.get("regularMarketChangePercent"), vol=q.get("regularMarketVolume"),
                 delayed_min=q.get("exchangeDataDelayedBy"), market_state=q.get("marketState"), quote_time=datetime.datetime.fromtimestamp(q["regularMarketTime"], datetime.timezone.utc).isoformat() if q.get("regularMarketTime") else None, open=is_open(t))
        if px and len(H) > 260:
            c = [x[1] for x in H if x[0] < datetime.date.today().isoformat()] + [px]; v = [x[2] for x in H][-50:]
            ma = sum(c[-25:]) / 25; r["kairi_pct"] = round(100 * (px / ma - 1), 1); r["bnf_trigger"] = r["kairi_pct"] <= -20
            av = sum(v) / len(v) if v else 0; r["cis_trigger"] = bool(px >= max(c[-251:-1]) and av and (q.get("regularMarketVolume") or 0) > 2 * av)
        rows.append(r)
    P = {r["t"]: r for r in rows}; mtm = []
    for x in led:
        r = P.get(x["ticker"], {}); now = r.get("px")
        if not now or not x.get("px"): continue
        sign = -1 if "SHORT" in str(x.get("call", "")) or "AVOID" in str(x.get("call", "")) else 1
        mtm.append(dict(ticker=x["ticker"], call=x.get("call"), kind=x["kind"], logged=x.get("logged_at"), entry=x["px"], now=now, pnl_pct=round(100 * sign * (now / x["px"] - 1), 1), kill=x.get("kill"), catalyst=x.get("catalyst")))
    return rows, mtm
def once(c=None):
    U, led = universe(); c = c or crumb(); now = datetime.datetime.now(datetime.timezone.utc)
    prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
    last = prev.get("last_poll", {}); due = []
    for t in U:
        age = (now - datetime.datetime.fromisoformat(last[t])).total_seconds() if t in last else 1e9
        if age >= (120 if is_open(t, now) else 1800): due.append(t)
    Q = {r["t"]: r for r in prev.get("rows", [])}; Qraw = quotes(due, c) if due else {}
    for t in due: last[t] = now.isoformat()
    old = {r["t"]: r for r in prev.get("rows", [])}
    rows, mtm = compute(U, led, {**{t: dict(regularMarketPrice=o.get("px"), currency=o.get("cur"), regularMarketChangePercent=o.get("chg_pct"), regularMarketVolume=o.get("vol"), exchangeDataDelayedBy=o.get("delayed_min"), marketState=o.get("market_state")) for t, o in old.items()}, **Qraw})
    J = dict(updated=now.isoformat(), polled=len(due), n=len(rows), note="Yahoo quotes; some exchanges are delayed (delayed_min). Paper ledger only; not advice.", rows=rows, mtm=mtm, last_poll=last)
    json.dump(J, open(OUT + ".tmp", "w"), default=str); os.replace(OUT + ".tmp", OUT); return J
if __name__ == "__main__":
    if "--once" in sys.argv: J = once(); print(J["n"], J["polled"], len(J["mtm"])); sys.exit(0)
    c = crumb()
    while True:
        try: once(c)
        except Exception as e: print("poll error", e, flush=True); time.sleep(60); c = crumb()
        time.sleep(60)
