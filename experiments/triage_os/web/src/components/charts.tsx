import { cn, fmtM, fmtPx } from "../lib"
import { SourceLink, VBadge } from "./ui"

export function Sparkline({ pts, w = 96, h = 22, base = 100 }: { pts: [string, number | null][]; w?: number; h?: number; base?: number }) {
  const v = pts.filter(p => p[1] != null) as [string, number][]
  if (v.length < 2) return <span className="text-[10px] text-dim">n/a</span>
  const ys = v.map(p => p[1]); const lo = Math.min(...ys, base - 5), hi = Math.max(...ys, base)
  const x = (i: number) => 1 + (i / (v.length - 1)) * (w - 2), y = (n: number) => h - 2 - ((n - lo) / (hi - lo || 1)) * (h - 4)
  const d = v.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("")
  const down = ys[ys.length - 1] < ys[0]
  return <svg width={w} height={h} className="overflow-visible"><title>{v.map(p => `${p[0]}: ${p[1].toFixed(1)}`).join("\n")}</title>
    <line x1={0} x2={w} y1={y(base)} y2={y(base)} stroke="#262f3a" strokeDasharray="2 2" />
    <path d={d} fill="none" stroke={down ? "#ef4d5a" : "#2fbf71"} strokeWidth={1.4} />
    <circle cx={x(v.length - 1)} cy={y(ys[ys.length - 1])} r={2} fill={down ? "#ef4d5a" : "#2fbf71"} />
  </svg>
}

export function MarkChart({ series, h = 180 }: { series: Record<string, { period: string; mark: number }[]>; h?: number }) {
  const names = Object.keys(series); const all = names.flatMap(n => series[n])
  if (!all.length) return <div className="p-6 text-center text-[12px] text-dim">No BDC marks reported for this borrower in the 13-quarter window.</div>
  const periods = [...new Set(all.map(r => r.period))].sort(); const W = 640, P = { l: 34, r: 60, t: 10, b: 22 }
  const lo = Math.max(0, Math.floor(Math.min(...all.map(r => r.mark)) / 10) * 10), hi = 100
  const x = (p: string) => P.l + (periods.indexOf(p) / Math.max(1, periods.length - 1)) * (W - P.l - P.r)
  const y = (m: number) => P.t + (1 - (m - lo) / (hi - lo || 1)) * (h - P.t - P.b)
  const colors = ["#f5a524", "#4ea1ff", "#a78bfa", "#2fbf71", "#ef4d5a"]
  return <svg viewBox={`0 0 ${W} ${h}`} className="w-full">
    {[lo, (lo + hi) / 2, hi].map(t => <g key={t}><line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} stroke="#1c232c" /><text x={P.l - 6} y={y(t) + 3} textAnchor="end" className="fill-dim font-mono text-[9px]">{t.toFixed(0)}</text></g>)}
    {periods.map((p, i) => (i % 2 === 0 || i === periods.length - 1) && <text key={p} x={x(p)} y={h - 6} textAnchor="middle" className="fill-dim font-mono text-[9px]">{p.slice(2, 7).replace("-", "/")}</text>)}
    {names.map((n, k) => { const s = series[n]; const d = s.map((r, i) => `${i ? "L" : "M"}${x(r.period)},${y(r.mark)}`).join(""); const last = s[s.length - 1]
      return <g key={n}><path d={d} fill="none" stroke={colors[k % 5]} strokeWidth={1.6} />{s.map(r => <circle key={r.period} cx={x(r.period)} cy={y(r.mark)} r={1.8} fill={colors[k % 5]} />)}
        <text x={x(last.period) + 6} y={y(last.mark) + 3} className="font-mono text-[10px]" fill={colors[k % 5]}>{n} {last.mark.toFixed(1)}</text></g> })}
  </svg>
}

export type Tranche = { tranche: string; amount_usd_m: number | string; coupon?: string; maturity?: string; lien?: string; mark?: string; holder?: string; source_url?: string; status?: string; issuer?: string; as_of?: string }
const rank = (t: Tranche) => { const l = `${t.lien} ${t.tranche}`.toLowerCase(); return l.includes("dip") ? 0 : /\babl\b/.test(l) || l.includes("revolv") ? 1 : l.includes("1st") || l.includes("first") || (l.includes("secured") && !l.includes("unsecured")) ? 2 : l.includes("2nd") || l.includes("second") ? 3 : l.includes("unsecured") || l.includes("senior notes") ? 4 : l.includes("sub") ? 5 : 6 }
export function Waterfall({ rows }: { rows: Tranche[] }) {
  const t = rows.map(r => ({ ...r, amt: Number(r.amount_usd_m) || 0 })).filter(r => r.amt > 0).sort((a, b) => rank(a) - rank(b))
  if (!t.length) return <div className="p-6 text-center text-[12px] text-dim">No tranche-level debt disclosed in the primary filings read for this situation.</div>
  const total = t.reduce((s, r) => s + r.amt, 0); let cum = 0
  const tones = ["bg-info", "bg-info/70", "bg-amber", "bg-amber/70", "bg-violet", "bg-down/70", "bg-mute"]
  return <div className="flex flex-col">
    <div className="grid grid-cols-[minmax(0,1fr)_92px_92px_220px_96px] gap-x-3 border-b border-line2 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-dim"><span>Tranche (priority order)</span><span className="text-right">Face</span><span className="text-right">Cumulative</span><span>Stack</span><span className="text-right">Source</span></div>
    {t.map((r, i) => { const s0 = cum / total; cum += r.amt; const s1 = cum / total
      return <div key={i} className="grid grid-cols-[minmax(0,1fr)_92px_92px_220px_96px] items-center gap-x-3 border-b border-line/70 px-3 py-1.5">
        <div className="min-w-0"><div className="truncate text-[12px] text-ink">{r.tranche} <span className="text-mute">{r.coupon && r.coupon !== "n/d" ? r.coupon : ""} {r.maturity && r.maturity !== "n/d" ? `· ${r.maturity.slice(0, 7)}` : ""}</span></div>
          <div className="flex items-center gap-2 truncate text-[10.5px] text-dim">{r.lien}{r.mark ? <span className="text-amber">· {r.mark}</span> : null}{r.holder ? <span className="truncate">· {r.holder}</span> : null}</div></div>
        <div className="num text-right text-[12px]">{fmtM(r.amt)}</div>
        <div className="num text-right text-[11px] text-mute">{fmtM(cum, 0)}</div>
        <div className="relative h-3 rounded-[1px] bg-line"><div className={cn("absolute h-3 rounded-[1px]", tones[rank(r)])} style={{ left: `${s0 * 100}%`, width: `${Math.max(0.6, (s1 - s0) * 100)}%` }} /></div>
        <div className="flex items-center justify-end gap-1.5">{r.source_url && <SourceLink s={{ title: `${r.issuer ?? ""} — ${r.tranche}`, url: r.source_url, status: r.status, detail: `${fmtM(r.amt)} ${r.coupon ?? ""} ${r.maturity ?? ""}; as of ${r.as_of ?? "n/d"}`, checked: r.as_of }}>{"src"}</SourceLink>}<VBadge status={r.status} compact /></div>
      </div> })}
    <div className="flex justify-between px-3 py-2 text-[11px] text-mute"><span>Total disclosed debt</span><span className="num text-ink">{fmtM(total)}</span></div>
  </div>
}

export type TL = { date: string; what: string; url?: string; status?: string; kind?: string }
export function Timeline({ items, today = "2026-10-22" }: { items: TL[]; today?: string }) {
  const s = [...items].sort((a, b) => a.date.localeCompare(b.date))
  return <ol className="relative ml-2 border-l border-line2">
    {s.map((e, i) => { const fut = e.date > today
      return <li key={i} className="relative pb-3 pl-4 last:pb-0">
        <span className={cn("absolute -left-[5px] top-1 h-[9px] w-[9px] rounded-full border", fut ? "border-amber bg-bg" : "border-info bg-info")} />
        <div className="flex items-baseline gap-2"><span className={cn("num text-[11px]", fut ? "text-amber" : "text-mute")}>{e.date}</span>{fut && <span className="text-[9.5px] font-semibold uppercase tracking-wider text-amber">upcoming</span>}</div>
        <div className="mt-0.5 text-[12px] leading-snug text-ink/95">{e.what}</div>
        {e.url && <div className="mt-1 flex items-center gap-2"><SourceLink s={{ title: e.what, url: e.url, status: e.status, checked: "2026-10-22" }} />{e.status && <VBadge status={e.status} compact />}</div>}
      </li> })}
  </ol>
}
export { fmtPx }
