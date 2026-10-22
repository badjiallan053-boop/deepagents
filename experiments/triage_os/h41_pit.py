"""Point-in-time Fed balance sheet from the H.4.1 release archive (federalreserve.gov/releases/h41/YYYYMMDD/).
Each release is what the public saw that Thursday: Wednesday-level Total assets (~WALCL) and Reverse repurchase agreements
(all RRP incl. foreign official, a superset of RRPONTSYD; labelled). Fallback for ALFRED, which refuses this box."""
import re, json, os, datetime, subprocess, time
OUT = "/workspace/triage_os_data/xasset/v4/h41_pit.json"
def num(s): return float(s.replace(",", ""))
def parse(t):
    t = re.sub(r"<[^>]+>", "", t); ta = rr = None
    for l in t.splitlines():
        if ta is None and re.match(r"\s*Total assets\b", l):
            m = re.findall(r"\b\d{1,3}(?:,\d{3})+\b", l)
            if m: ta = num(m[0])
        if rr is None and re.match(r"\s*Reverse repurchase agreements", l):
            m = re.findall(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+\b(?=\s*$)", l)
            if m: rr = num(m[-1])
    return ta, rr
def main():
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    d = datetime.date(2015, 1, 1)
    while d.weekday() != 3: d += datetime.timedelta(days=1)
    while d <= datetime.date.today():
        k = d.isoformat()
        if k not in out:
            for dd in (d, d - datetime.timedelta(days=1), d + datetime.timedelta(days=1)):
                t = subprocess.run(["curl", "-s", "-m", "30", "-A", "Mozilla/5.0", f"https://www.federalreserve.gov/releases/h41/{dd:%Y%m%d}/"], capture_output=True, text=True).stdout
                time.sleep(0.7)
                if "Total assets" in t:
                    ta, rr = parse(t); out[k] = dict(release=dd.isoformat(), total_assets_m=ta, rrp_m=rr); break
            json.dump(out, open(OUT, "w"))
        d += datetime.timedelta(days=7)
    print("h41 releases", sum(1 for v in out.values() if v.get("total_assets_m")))
if __name__ == "__main__": main()
