"""London Strategic Edge (LSE) vault ingest for TRIAGE OS.

Read-only, public market data. Reimplements the documented REST calls of the
MIT `lse-data` client (not executed). Key comes from env LSE_API_KEY and is
never logged or written to disk.

Budget model (from /vault/usage on 23 Oct 2026):
  * synchronous REST (/series, /candles, /ref/*, /catalog): 60 calls/min,
    5,000 rows/call; does NOT consume export quota (verified: 0 exports after
    several /series calls).
  * bulk /export jobs: 5 per hour. Queued in exports_queue.json and only
    started when the hour window has room; resumable across runs.

Every stored payload carries retrieved_at (UTC ISO) and the last observation
date, so case files can show point-in-time provenance and staleness.

CLI:
  python3 lse_ingest.py catalog            # refresh catalog + usage
  python3 lse_ingest.py backdrop [--region UK|EU|JP|CA|AU]
  python3 lse_ingest.py queue-export DATASET [--symbol S] [--start D]
  python3 lse_ingest.py run-exports        # start/poll queued jobs within cap
"""
from __future__ import annotations
import argparse, datetime as dt, html, json, os, time, urllib.parse, urllib.request

VAULT = "https://api.londonstrategicedge.com/vault"
OUT = os.environ.get("LSE_OUT", "/workspace/triage_os_data/lse")
UA = "triage-os-lse-ingest (+research, read-only)"
SERIES_TTL_H = 12
EXPORT_CAP_HOUR = 5
MIN_INTERVAL_S = 1.1  # stays under 60 calls/min

# Backdrop panels per buyer region. Credit "indices" are index LEVELS
# (index points), not spreads/OAS: we report % changes and BBB-vs-AAA
# relative performance as a stress proxy, labelled as such.
PANELS = {
    "UK": {
        "credit": ["GBP_CORP", "GBP_CORP_AAA", "GBP_CORP_BBB", "GBP_CORP_BBB_7_10", "GBP_CORP_1_5", "EUR_LIQ_HY"],
        "curve": ["GBGB3M", "GBGB2Y", "GBGB5Y", "GBGB10Y", "GBGB30Y"],
        "funding": ["gbroiar"],
        "stress": ["unitedkinban", "gbrrhpb", "unitedkinmorapp"],
    },
    "EU": {
        "credit": ["EUR_CORP", "EUR_CORP_AAA", "EUR_CORP_BBB", "EUR_CORP_SUB", "EUR_LIQ_HY"],
        "curve": ["DEGB3M", "DEGB2Y", "DEGB10Y", "DEGB30Y", "ITGB3Y", "FRGB5Y"],
        "funding": ["emuevolvintrat"],
        "stress": ["eurbankruptcies", "germanyban", "franceban", "netherlandban", "spainban"],
    },
    "JP": {
        "credit": [],
        "curve": ["JPGB2Y", "JPGB10Y", "JPGB30Y"],
        "funding": ["japanintrat"],
        "stress": ["japanban"],
    },
    "CA": {"credit": [], "curve": ["CA3M", "CA5Y", "CA30Y"], "funding": [], "stress": ["canadaban", "canhpiy"]},
    "AU": {"credit": [], "curve": ["AU5Y"], "funding": ["australiaintrat"], "stress": ["australiaban"]},
}


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _key():
    k = os.environ.get("LSE_API_KEY", "").strip()
    if not k or "..." in k or " " in k:
        raise RuntimeError("LSE_API_KEY missing or placeholder")
    return k


class Client:
    def __init__(self, out=OUT, opener=None):
        self.out = out
        self.opener = opener  # test hook: fn(method, path, params, body) -> obj
        self._last = 0.0
        os.makedirs(os.path.join(out, "series"), exist_ok=True)

    # -- transport ----------------------------------------------------
    def _call(self, path, params=None, body=None):
        if self.opener:
            return self.opener("POST" if body is not None else "GET", path, params or {}, body)
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        qs = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(VAULT + path + ("?" + qs if qs else ""), data=data,
                                     headers={"x-api-key": _key(), "User-Agent": UA,
                                              **({"Content-Type": "application/json"} if data else {})})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    self._last = time.monotonic()
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                self._last = time.monotonic()
                if e.code == 429 and attempt < 3:
                    time.sleep(30 * (attempt + 1)); continue
                raise RuntimeError(f"LSE {path} HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")

    def _w(self, rel, obj):
        p = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        json.dump(obj, open(tmp, "w"))
        os.replace(tmp, p)
        return p

    def _r(self, rel):
        p = os.path.join(self.out, rel)
        return json.load(open(p)) if os.path.exists(p) else None

    # -- discovery ----------------------------------------------------
    def usage(self):
        u = self._call("/usage")
        u["retrieved_at"] = _now().isoformat()
        self._w("usage.json", u)
        return u

    def catalog(self, refresh=False):
        cached = self._r("catalog_meta.json")
        if cached and not refresh:
            return self._r("catalog.json")
        rows = self._call("/catalog")
        self._w("catalog.json", rows)
        self._w("catalog_meta.json", {"retrieved_at": _now().isoformat(), "n": len(rows)})
        return rows

    # -- series (no export quota) --------------------------------------
    def series(self, symbol, start=None, refresh=False):
        rel = f"series/{symbol.replace('/', '_')}.json"
        c = self._r(rel)
        if c and not refresh:
            age_h = (_now() - dt.datetime.fromisoformat(c["retrieved_at"])).total_seconds() / 3600
            if age_h < SERIES_TTL_H:
                return c
        # newest-first so the 5,000-row cap trims the distant past, not the present
        rows = self._call("/series", {"symbol": symbol, "start": start, "order": "desc", "limit": 5000})
        obs = sorted((r["date"], r["value"]) for r in rows if r.get("value") is not None)
        rec = {"symbol": symbol, "source": "London Strategic Edge vault /series",
               "retrieved_at": _now().isoformat(), "last_obs": obs[-1][0] if obs else None,
               "n": len(obs), "obs": obs}
        # point-in-time archive: one immutable snapshot per retrieval day
        self._w(f"pit/{_now():%Y-%m-%d}/{symbol.replace('/', '_')}.json", rec)
        self._w(rel, rec)
        return rec

    # -- exports (5/hour), queued and resumable -------------------------
    def _queue(self):
        return self._r("exports_queue.json") or {"jobs": [], "started": []}

    def queue_export(self, dataset, symbol=None, start=None, end=None, timeframe=None):
        q = self._queue()
        job = {"dataset": dataset, "symbol": symbol, "start": start, "end": end,
               "timeframe": timeframe, "format": "parquet", "status": "queued",
               "queued_at": _now().isoformat()}
        if not any({k: j.get(k) for k in ("dataset", "symbol", "start", "end", "timeframe")} ==
                   {k: job[k] for k in ("dataset", "symbol", "start", "end", "timeframe")}
                   for j in q["jobs"] if j["status"] in ("queued", "running")):
            q["jobs"].append(job)
        self._w("exports_queue.json", q)
        return q

    def exports_used_last_hour(self, q=None):
        q = q or self._queue()
        cut = _now() - dt.timedelta(hours=1)
        return sum(1 for t in q["started"] if dt.datetime.fromisoformat(t) > cut)

    def run_exports(self):
        q = self._queue()
        for j in q["jobs"]:
            if j["status"] == "queued":
                if self.exports_used_last_hour(q) >= EXPORT_CAP_HOUR:
                    break
                body = {k: j[k] for k in ("dataset", "symbol", "start", "end", "timeframe", "format") if j.get(k)}
                r = self._call("/export", body=body)
                j.update(status="running", job_id=r.get("job_id"), started_at=_now().isoformat())
                q["started"].append(j["started_at"])
            if j["status"] == "running" and j.get("job_id"):
                info = self._call(f"/export/{j['job_id']}")
                if info.get("status") == "ready":
                    j.update(status="ready", download=info.get("url") or info.get("download_url"))
                elif info.get("status") in ("failed", "expired"):
                    j["status"] = info["status"]
        self._w("exports_queue.json", q)
        return q


# -- backdrop ----------------------------------------------------------
def _at_or_before(obs, d):
    v = None
    for od, ov in obs:
        if od <= d:
            v = ov
        else:
            break
    return v


def summarise(rec, today=None):
    today = today or _now().date()
    obs = rec["obs"]
    if not obs:
        return {"symbol": rec["symbol"], "last": None, "stale_days": None}
    ld, lv = obs[-1]
    last = dt.date.fromisoformat(ld[:10])
    def chg(days):
        base = _at_or_before(obs, (last - dt.timedelta(days=days)).isoformat())
        return None if base in (None, 0) else base
    out = {"symbol": rec["symbol"], "last_date": ld[:10], "last": lv,
           "stale_days": (today - last).days, "retrieved_at": rec["retrieved_at"]}
    for lab, d in (("1m", 30), ("3m", 91), ("1y", 365)):
        b = chg(d)
        out["base_" + lab] = b
    return out


def stale_flag(s, freq_days=1):
    if s.get("stale_days") is None:
        return "NO DATA"
    # daily: >4 days without a print; monthly/quarterly series are dated at
    # period start and publish with a lag, so allow ~2 periods + 2 months.
    lim = 4 if freq_days <= 1 else 2 * freq_days + 60
    return "STALE" if s["stale_days"] > lim else "fresh"


def backdrop(region="UK", client=None, today=None):
    c = client or Client()
    cat = {r["symbol"]: r for r in (c.catalog() or [])}
    panel = PANELS[region]
    res = {"region": region, "built_at": _now().isoformat(), "groups": {}}
    for grp, syms in panel.items():
        rows = []
        for s in syms:
            try:
                rec = c.series(s)
            except Exception as e:  # keep building; record the failure
                rows.append({"symbol": s, "error": str(e)[:120]}); continue
            sm = summarise(rec, today)
            meta = cat.get(s, {})
            sm.update(name=meta.get("name", s), frequency=meta.get("frequency") or "daily",
                      dataset=meta.get("dataset"))
            fd = {"daily": 1, "weekly": 7, "monthly": 31, "quarterly": 92}.get(sm["frequency"], 1)
            sm["flag"] = stale_flag(sm, fd)
            rows.append(sm)
        res["groups"][grp] = rows
    c._w(f"backdrop_{region}.json", res)
    return res


def _pct(a, b):
    return None if a is None or b in (None, 0) else (a / b - 1) * 100


def _f(x, nd=2, suf=""):
    return "n/a" if x is None else f"{x:,.{nd}f}{suf}"


def backdrop_html(bd, retrieved_label=None):
    """HTML block for case files. Facts are LSE data; reads are judgement."""
    esc = html.escape
    retrieved = retrieved_label or bd["built_at"][:16].replace("T", " ") + " UTC"
    rows = []
    g = bd["groups"]
    for s in g.get("credit", []):
        if "error" in s: continue
        rows.append(f"<tr><td>{esc(s['name'])} <span class='small'>({esc(s['symbol'])}, index level)</span></td>"
                    f"<td class='num'>{_f(s['last'])}</td><td class='num'>{_f(_pct(s['last'], s.get('base_1m')), 2, '%')}</td>"
                    f"<td class='num'>{_f(_pct(s['last'], s.get('base_3m')), 2, '%')}</td><td class='num'>{_f(_pct(s['last'], s.get('base_1y')), 2, '%')}</td>"
                    f"<td>{s['last_date']} &middot; <b>{s['flag']}</b> ({s['stale_days']}d)</td></tr>")
    for grp in ("curve", "funding", "stress"):
        for s in g.get(grp, []):
            if "error" in s: continue
            d1m = None if s.get("base_1m") is None else s["last"] - s["base_1m"]
            d3m = None if s.get("base_3m") is None else s["last"] - s["base_3m"]
            d1y = None if s.get("base_1y") is None else s["last"] - s["base_1y"]
            unit = " (chg)" if grp == "stress" else " (chg, pp)"
            rows.append(f"<tr><td>{esc(s['name'])} <span class='small'>({esc(s['symbol'])}, {esc(s['frequency'])}{unit})</span></td>"
                        f"<td class='num'>{_f(s['last'], 3 if grp != 'stress' else 0)}</td><td class='num'>{_f(d1m, 2)}</td>"
                        f"<td class='num'>{_f(d3m, 2)}</td><td class='num'>{_f(d1y, 2)}</td>"
                        f"<td>{s['last_date']} &middot; <b>{s['flag']}</b> ({s['stale_days']}d)</td></tr>")
    # stress proxy: BBB vs AAA relative 3m performance
    by = {s["symbol"]: s for s in g.get("credit", []) if "error" not in s}
    proxy = ""
    lo, hi = ("GBP_CORP_BBB", "GBP_CORP_AAA") if bd["region"] == "UK" else ("EUR_CORP_BBB", "EUR_CORP_AAA")
    if lo in by and hi in by:
        rel = [_pct(by[lo]["last"], by[lo].get(k)) for k in ("base_3m",)] + [_pct(by[hi]["last"], by[hi].get("base_3m"))]
        if None not in rel:
            proxy = (f"<p class='small'><b>Stress proxy (derived, not a spread):</b> 3-month change, BBB index minus AAA index = "
                     f"<b>{rel[0]-rel[1]:+.2f} pp</b>. Negative means lower-rated credit underperformed.</p>")
    stale = [s["symbol"] for gg in g.values() for s in gg if s.get("flag") == "STALE"]
    errs = [s["symbol"] for gg in g.values() for s in gg if "error" in s]
    warn = ""
    if stale:
        warn += f"<p class='small'><b>Staleness:</b> {esc(', '.join(stale))} have no print within the expected window; treat as context, not live.</p>"
    if errs:
        warn += f"<p class='small'>Not retrieved: {esc(', '.join(errs))}.</p>"
    return (f"<h2>Market backdrop ({esc(bd['region'])})</h2>"
            f"<p class='small'>Source: London Strategic Edge (londonstrategicedge.com) vault, retrieved {esc(retrieved)}. "
            f"Credit rows are index levels from LSE's credit_indices set, not option-adjusted spreads; no issuer-level or UK-utility spread series exists in this source. "
            f"Each row shows its own last observation date.</p>"
            f"<table><tr><th>Series</th><th>Last</th><th>1m</th><th>3m</th><th>1y</th><th>Last obs / status</th></tr>{''.join(rows)}</table>"
            f"{proxy}{warn}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["catalog", "backdrop", "queue-export", "run-exports"])
    ap.add_argument("dataset", nargs="?")
    ap.add_argument("--region", default="UK", choices=sorted(PANELS))
    ap.add_argument("--symbol"); ap.add_argument("--start")
    a = ap.parse_args(argv)
    c = Client()
    if a.cmd == "catalog":
        rows = c.catalog(refresh=True); u = c.usage()
        print(len(rows), "datasets; exports this hour", u.get("exports_this_hour"), "/", u.get("exports_cap_hour"))
    elif a.cmd == "backdrop":
        bd = backdrop(a.region, c)
        for grp, rows in bd["groups"].items():
            for s in rows:
                print(grp, s.get("symbol"), s.get("last_date"), s.get("last"), s.get("flag"), s.get("error", ""))
    elif a.cmd == "queue-export":
        print(json.dumps(c.queue_export(a.dataset, a.symbol, a.start)["jobs"][-1]))
    else:
        q = c.run_exports(); print(sum(j["status"] == "queued" for j in q["jobs"]), "queued")


if __name__ == "__main__":
    main()
