"""Mining + land layer (free public data only, read-only).
BLM MLRS ArcGIS REST (active + closed claims located per year around key US deposits of controlled minerals),
Sentinel-2 L2A via Earth Search STAC (scene metadata + preview images for activity change), IMF COFER (SDMX 2.1),
USGS MCS 2026 (supply concentration), Internet Archive (historical reports, lead source only)."""
import os, json, time, urllib.request, urllib.parse, datetime, re, io
O = "/workspace/triage_os_data/xasset/mining"; os.makedirs(O, exist_ok=True)
UA = {"User-Agent": "TRIAGE-OS research arslane.souici@example.com"}
def get(u, t=60, data=None, hdr=None):
    h = dict(UA); h.update(hdr or {})
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, data=data, headers=h), timeout=t).read()
        except Exception as e: err = e; time.sleep(2 * (i + 1))
    raise err
# approximate district centres (JUDGEMENT: hand-placed from public descriptions; ±0.15° box)
SITES = {"Mountain Pass (CA) — REE": (-115.53, 35.48, "REE", "MP"), "Thacker Pass (NV) — lithium": (-118.05, 41.71, "Li", "LAC"),
         "Stibnite (ID) — antimony/gold": (-115.33, 44.91, "Sb", "PPTA"), "Bear Lodge (WY) — REE": (-104.45, 44.48, "REE", "RER.V"),
         "Rhyolite Ridge (NV) — lithium/boron": (-117.98, 37.97, "Li", "INR.AX")}
BLM = "https://nlsdbpubgis.blm.gov/arcgis/rest/services/mining_claims/MiningClaims/MapServer"
def blm():
    """Download claim attributes (active layer 1 + closed layer 2) per site box, paged; analysis done in mining_signals.py."""
    out = {}
    for name, (x, y, mineral, tk) in SITES.items():
        env = f"{x-.15},{y-.15},{x+.15},{y+.15}"; recs = []
        for layer in (1, 2):
            off = 0
            while True:
                q = urllib.parse.urlencode({"where": "1=1", "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "LOC_DT,CSE_NR,CSE_DISP,CSE_NAME,CSE_TYPE_NR,RCRD_ACRS", "returnGeometry": "false", "resultOffset": off, "resultRecordCount": 2000, "orderByFields": "OBJECTID", "f": "json"})
                j = json.loads(get(f"{BLM}/{layer}/query?{q}", 120)); fs = j.get("features", [])
                recs += [dict(f["attributes"], layer=layer) for f in fs]; off += len(fs)
                if not fs or not j.get("exceededTransferLimit"): break
        out[name] = dict(lon=x, lat=y, mineral=mineral, ticker=tk, records=recs)
        print(name, len(recs), sum(1 for r in recs if r["LOC_DT"]), flush=True)
    json.dump(dict(source=BLM, fetched=datetime.datetime.now().isoformat(timespec="seconds"), sites=out), open(f"{O}/blm_claims.json", "w"))

STAC = "https://earth-search.aws.element84.com/v1/search"
def stac():
    out = {}
    for name, (x, y, m, tk) in list(SITES.items())[:3]:
        res = {}
        for label, dt in [("2024-autumn", "2024-09-01T00:00:00Z/2024-11-15T00:00:00Z"), ("2026-autumn", "2026-09-01T00:00:00Z/2026-10-22T00:00:00Z")]:
            body = json.dumps({"collections": ["sentinel-2-l2a"], "intersects": {"type": "Point", "coordinates": [x, y]}, "datetime": dt,
                               "query": {"eo:cloud_cover": {"lt": 10}}, "limit": 50, "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}]}).encode()
            j = json.loads(get(STAC, data=body, hdr={"Content-Type": "application/json"}))
            feats = j.get("features", [])
            best = feats[0] if feats else None
            entry = dict(n_scenes=len(feats), best_id=best and best["id"], best_date=best and best["properties"]["datetime"][:10], cloud=best and best["properties"]["eo:cloud_cover"])
            if best:
                th = best["assets"].get("thumbnail", {}).get("href")
                if th:
                    fn = f"{O}/s2_{tk}_{label}.jpg"
                    try: open(fn, "wb").write(get(th)); entry["thumb"] = fn; entry["thumb_url"] = th
                    except Exception as e: entry["thumb_err"] = str(e)
            res[label] = entry
        out[name] = res; print(name, res, flush=True)
    json.dump(dict(source=STAC, fetched=datetime.datetime.now().isoformat(timespec="seconds"), sites=out), open(f"{O}/stac_s2.json", "w"), indent=1)

def cofer():
    x = get("https://api.imf.org/external/sdmx/2.1/data/IMF.STA,COFER", 120).decode()
    open(f"{O}/cofer.xml", "w").write(x); print("cofer bytes", len(x))

def archive():
    out = {}
    for q in ['antimony AND Idaho AND mediatype:texts AND date:[1900-01-01 TO 1960-12-31]', '"rare earth" AND mediatype:texts AND (geological OR bulletin) AND date:[1940-01-01 TO 1970-12-31]',
              'lithium AND Nevada AND mediatype:texts AND date:[1900-01-01 TO 1975-12-31]', 'tungsten AND mediatype:texts AND "Bureau of Mines" AND date:[1900-01-01 TO 1960-12-31]']:
        u = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode({"q": q, "fl[]": ["identifier", "title", "date"], "rows": 15, "output": "json"}, doseq=True)
        try: out[q] = json.loads(get(u))["response"]
        except Exception as e: out[q] = str(e)
        print(q, (out[q].get("numFound") if isinstance(out[q], dict) else out[q]), flush=True)
    json.dump(out, open(f"{O}/archive_leads.json", "w"), indent=1)

if __name__ == "__main__":
    import sys
    for s in (sys.argv[1:] or ["blm", "stac", "cofer", "archive"]):
        try: globals()[s]()
        except Exception as e: print("STEP ERR", s, e)
