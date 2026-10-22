"""S21 (Fed net liquidity impulse) re-tested point-in-time on the Fed's own weekly H.4.1 releases (2015-2026).
Net liquidity = H.4.1 total assets - reverse repurchase agreements (H.4.1 RRP includes the foreign official pool; FRED RRPONTSYD does not), $bn.
Trigger: rise > $200bn vs 13 releases earlier, dated on the RELEASE date (Thursday 16:30 ET, so entry is at the next close at the earliest).
Same study() call as the final-data version for comparison."""
import json, signals as S
H = json.load(open("/workspace/triage_os_data/xasset/v4/h41_pit.json"))
rows = sorted((v["release"], v["total_assets_m"] / 1e3 - (v["rrp_m"] or 0) / 1e3) for v in H.values() if v.get("total_assets_m"))
trig = [(rows[i][0], 0) for i in range(13, len(rows)) if rows[i][1] - rows[i - 13][1] > 200]
pit = S.study("S21", S.PX("SPY"), trig, 1, 20, 0, 10)
json.dump(dict(releases=len(rows), first=rows[0][0], last=rows[-1][0], triggers=len(trig), result=pit), open("/workspace/triage_os_data/s21_h41.json", "w"), indent=1, default=str)
print(len(rows), len(trig), {k: pit.get(k) for k in ("status", "IS", "OOS")} if isinstance(pit, dict) else pit)
