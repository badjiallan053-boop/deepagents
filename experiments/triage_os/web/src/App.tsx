import { Fragment, useEffect, useMemo, useState } from "react"
import { Activity, ChevronRight, Command as Cmd, FileText, Gavel, LayoutDashboard, Network, ScrollText, ShieldCheck, TrendingDown, Waypoints, ExternalLink, Crosshair, Radar, Globe2 } from "lucide-react"
import { cn, fmtChg, fmtInt, fmtM, fmtPx, fmtPct, host, useApi } from "./lib"
import { Card, DataTable, SourceProvider, SourceLink, Stat, Tag, VBadge, Wordmark, Button, statusKey, useSource, type Col } from "./components/ui"
import { MarkChart, Sparkline, Timeline, Waterfall, type Tranche } from "./components/charts"
import Graph, { GRAPH_COLORS, type GNode, type GEdge } from "./components/Graph"
import Palette from "./components/Palette"

type Fact = { claim_id: string; claim: string; status: string; primary_url: string; checked: string; fix: string }
type Sit = { key: string; title: string; timeline: { date: string; what: string; url: string; status: string }[]; facts: Fact[] }
type Dist = { borrower: string; bdc: string; mark: number; min_mark: number; par_m: number; fv_m: number; tranches: number; source_url: string; hist: [string, number | null][]; chg_q: number | null; qa: string }
type Ver = Fact & { artifact: string; method: string }
type Edge = { edge_id: string; type: string; src: string; dst: string; detail: string; value: number; match: string; source_url: string; status: string }
type Hit = { seq: number; ts_utc: string; entity: string; kind: string; prediction: string; value: number; source_url: string; hash: string }

const NAV = [
  { r: "home", label: "Credit & Forced Sellers", icon: Crosshair },
  { r: "overview", label: "Overview", icon: LayoutDashboard },
  { r: "situations", label: "Situations", icon: Gavel },
  { r: "marks", label: "Marks monitor", icon: TrendingDown },
  { r: "control", label: "Control", icon: Crosshair },
  { r: "systemic", label: "Systemic radar", icon: Radar },
  { r: "world", label: "World", icon: Globe2 },
  { r: "edge", label: "Edge Lab", icon: ShieldCheck },
  { r: "bottleneck", label: "Bottleneck Hunt", icon: Network },
  { r: "signals", label: "Signal Library", icon: Activity },
  { r: "radar", label: "Cross-Asset Radar", icon: Globe2 },
  { r: "committee", label: "Alpha Committee", icon: Gavel },
  { r: "graph", label: "Relationship graph", icon: Waypoints },
  { r: "edges", label: "Cross-dataset edges", icon: Network },
  { r: "verify", label: "Verification ledger", icon: ShieldCheck },
  { r: "hitlog", label: "Signal hit log", icon: ScrollText },
  { r: "research", label: "Research", icon: FileText },
]
const MARK_KW: Record<string, string> = { medallia: "Medallia", omnis: "Omnis", truefood: "True Food" }
const SIT_META: Record<string, { court: string; stage: string }> = { hughes: { court: "Bankr. S.D. Tex.", stage: "Ch. 11 · exclusivity contested" } }

function useRoute(): [string, (r: string) => void] {
  const get = () => decodeURIComponent(location.hash.replace(/^#\/?/, "")) || "home"
  const [r, setR] = useState(get())
  useEffect(() => { const h = () => setR(get()); window.addEventListener("hashchange", h); return () => window.removeEventListener("hashchange", h) }, [])
  return [r, (n: string) => { location.hash = "/" + n }]
}

export default function App() {
  const [route, go] = useRoute(); const [pal, setPal] = useState(false)
  const { data: sits } = useApi<Sit[]>("/api/situations")
  const { data: stats } = useApi<Record<string, any>>("/api/stats")
  const [base, qs] = route.split("?"); const params = new URLSearchParams(qs || "")
  const top = base.split("/")[0]
  useEffect(() => { if (params.get("palette") === "1") setPal(true) }, [route])
  return <SourceProvider>
    {params.get("src") && sits && <OpenSource id={params.get("src")!} sits={sits} />}
    <div className="flex h-full flex-col">
      <header className="flex h-11 shrink-0 items-center gap-4 border-b border-line bg-panel px-4">
        <a href="#/home"><Wordmark /></a>
        <span className="h-4 w-px bg-line2" />
        <span className="text-[11px] uppercase tracking-[0.14em] text-mute">Special Situations Terminal</span>
        <button onClick={() => setPal(true)} className="ml-6 flex h-7 w-[380px] items-center gap-2 rounded-[3px] border border-line2 bg-bg px-2.5 text-[12px] text-dim hover:border-amber/50"><Cmd size={13} />Search issuers, holders, situations…<kbd className="ml-auto rounded border border-line2 px-1 font-mono text-[10px]">Ctrl K</kbd></button>
        <div className="ml-auto flex items-center gap-4 text-[11px] text-mute">
          {stats && <span className="flex items-center gap-1.5"><ShieldCheck size={13} className="text-up" /><span className="num">{stats.verification_status?.VERIFIED ?? 0}/{stats.verification ?? 0}</span> verified</span>}
          <span className="flex items-center gap-1.5"><Activity size={13} className="text-up" />Data as of <span className="num text-ink">22 Oct 2026</span></span>
          <Tag tone="amber">Read-only · public sources</Tag>
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <nav className="flex w-[208px] shrink-0 flex-col border-r border-line bg-panel py-2">
          {NAV.map(n => <a key={n.r} href={`#/${n.r}`} className={cn("mx-2 flex h-8 items-center gap-2.5 rounded-[3px] px-2.5 text-[12.5px]", top === n.r || (n.r === "situations" && top === "situation") ? "bg-line text-ink" : "text-mute hover:bg-line/50 hover:text-ink")}><n.icon size={14} className={top === n.r ? "text-amber" : ""} />{n.label}</a>)}
          <div className="mx-4 mb-2 mt-5 text-[10px] font-semibold uppercase tracking-[0.12em] text-dim">Live situations</div>
          <div className="flex-1 overflow-auto">{sits?.map(s => <a key={s.key} href={`#/situation/${s.key}`} className={cn("mx-2 flex h-7 items-center gap-2 rounded-[3px] px-2.5 text-[11.5px]", route === `situation/${s.key}` ? "bg-line text-ink" : "text-mute hover:text-ink")}><span className={cn("h-1.5 w-1.5 rounded-full", s.timeline.some(t => t.date > "2026-10-22") ? "bg-amber" : "bg-dim")} /><span className="truncate">{s.title}</span></a>)}</div>
          <div className="border-t border-line px-4 pt-2 text-[10px] leading-relaxed text-dim">Companies only. Public, primary sources. Not investment advice.</div>
        </nav>
        <main className="min-w-0 flex-1 overflow-auto">
          {top === "home" && <Home />}
          {top === "bottleneck" && <Bottleneck />}
          {top === "edge" && <EdgeLab />}
          {top === "overview" && <Overview sits={sits} stats={stats} />}
          {top === "situations" && <Situations sits={sits} />}
          {top === "situation" && sits && <SituationView s={sits.find(s => s.key === base.split("/")[1]) ?? sits[0]} />}
          {top === "marks" && <Marks />}
          {top === "control" && <Control />}
          {top === "systemic" && <Systemic />}
          {top === "world" && <World />}
          {top === "signals" && <Signals />}
          {top === "radar" && <XRadar />}
          {top === "committee" && <Committee />}
          {top === "graph" && <GraphView q={params.get("q") ?? ""} />}
          {top === "edges" && <Edges />}
          {top === "verify" && <Verify />}
          {top === "hitlog" && <HitLog />}
          {top === "research" && <Research />}
        </main>
      </div>
    </div>
    <Palette open={pal} setOpen={setPal} go={go} situations={sits ?? []} />
  </SourceProvider>
}

function OpenSource({ id, sits }: { id: string; sits: Sit[] }) {
  const open = useSource()
  useEffect(() => { const f = sits.flatMap(s => s.facts).find(f => f.claim_id === id); if (f) open({ title: f.claim, url: f.primary_url, status: f.status, checked: f.checked, detail: f.fix || undefined }) }, [id])
  return null
}

function PageHead({ kicker, title, sub, right }: { kicker: string; title: string; sub?: string; right?: React.ReactNode }) {
  return <div className="flex items-end justify-between border-b border-line px-5 pb-3 pt-4">
    <div><div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-amber">{kicker}</div><h1 className="mt-1 text-[19px] font-semibold tracking-tight text-ink">{title}</h1>{sub && <p className="mt-0.5 max-w-[860px] text-[12px] text-mute">{sub}</p>}</div>{right}</div>
}

// ---------------- Overview ----------------
function Overview({ sits, stats }: { sits: Sit[] | null; stats: Record<string, any> | null }) {
  const { data: dist } = useApi<Dist[]>("/api/distressed")
  const { data: hl } = useApi<{ count: number; chain_ok: boolean }>("/api/hitlog")
  const clean = (dist ?? []).filter(d => d.qa === "ok")
  const vs = stats?.verification_status ?? {}
  const upcoming = (sits ?? []).flatMap(s => s.timeline.filter(t => t.date > "2026-10-22").map(t => ({ ...t, sit: s }))).sort((a, b) => a.date.localeCompare(b.date))
  const seen = new Set<string>(); const up = upcoming.filter(u => { const k = u.sit.key + u.date; if (seen.has(k)) return false; seen.add(k); return true })
  return <div>
    <PageHead kicker="Desk overview · 22 Oct 2026" title="Distress across private credit, courts and registries" sub="BDC Schedule of Investments marks, Chapter 11 dockets, 13F holders and 11 public registries joined on company identity. Every figure links to the primary document it was read from." />
    <div className="grid grid-cols-6 border-b border-line bg-panel">
      <Stat label="BDC positions < 75" value={fmtInt(clean.length)} sub="par-weighted, 30 Jun 2026" tone="amber" />
      <Stat label="Par at risk" value={fmtM(clean.reduce((s, d) => s + d.par_m, 0) / 1000, 2).replace("m", "bn")} sub={`${new Set(clean.map(d => d.bdc)).size} BDCs reporting`} />
      <Stat label="Marked down QoQ" value={fmtInt(clean.filter(d => (d.chg_q ?? 0) < -5).length)} sub="> 5 pts in Q2 2026" tone="down" />
      <Stat label="Live situations" value={fmtInt(sits?.length)} sub={`${up.length} dated catalysts ahead`} />
      <Stat label="Verification" value={fmtPct((vs.VERIFIED ?? 0) / (stats?.verification || 1), 0)} sub={`${vs.CORRECTED ?? 0} corrected · ${vs.UNVERIFIABLE ?? 0} open`} tone="up" />
      <Stat label="Signal log" value={fmtInt(hl?.count)} sub={hl?.chain_ok ? "sha256 chain intact" : "chain check pending"} />
    </div>
    <div className="grid grid-cols-[minmax(0,1fr)_400px] gap-3 p-3">
      <Card title="Largest distressed BDC positions" right="Par-weighted mark · 30 Jun 2026 10-Q/10-K" pad={false}>
        <DistTable rows={clean.slice(0, 120)} maxHeight={520} />
      </Card>
      <div className="flex flex-col gap-3">
        <Card title="Catalyst calendar" right="Court & maturity dates">
          <div className="flex flex-col">{up.slice(0, 8).map((u, i) => <a key={i} href={`#/situation/${u.sit.key}`} className="flex gap-3 border-b border-line/70 py-2 last:border-0 hover:bg-line/30">
            <div className="w-[64px] shrink-0"><div className="num text-[13px] font-semibold text-amber">{new Date(u.date + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}</div><div className="num text-[10px] text-dim">{u.date.slice(0, 4)}</div></div>
            <div className="min-w-0"><div className="truncate text-[11px] font-semibold text-ink">{u.sit.title}</div><div className="line-clamp-2 text-[11.5px] text-mute">{u.what}</div></div></a>)}</div>
        </Card>
        <Card title="Flagship research" right="Published 22 Oct 2026">
          <a href="/research/Hughes_Satellite_Note.pdf" target="_blank" className="group block">
            <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-amber">Situation note · Case 26-90739</div>
            <div className="mt-1 text-[15px] font-semibold leading-snug text-ink group-hover:underline">Hughes Satellite: the fight is over who owns the litigation, not the satellites</div>
            <div className="mt-1.5 text-[12px] leading-relaxed text-mute">Capital structure, recovery scenarios, holder map and the 1 Dec 2026 exclusivity hearing. Every number footnoted to the docket or SEC filing.</div>
            <div className="mt-2 flex items-center gap-1 text-[11px] text-info">Open PDF <ExternalLink size={11} /></div>
          </a>
        </Card>
        <Card title="Ledger status" right={`${stats?.verification ?? 0} claims`}>
          <div className="flex h-2 overflow-hidden rounded-[1px]">{(["VERIFIED", "CORRECTED", "UNVERIFIABLE", "FALSE_POSITIVE"] as const).map(k => <div key={k} style={{ width: `${((vs[k] ?? 0) / (stats?.verification || 1)) * 100}%` }} className={{ VERIFIED: "bg-up", CORRECTED: "bg-amber", UNVERIFIABLE: "bg-line2", FALSE_POSITIVE: "bg-down" }[k]} />)}</div>
          <div className="mt-2 grid grid-cols-2 gap-1.5">{(["VERIFIED", "CORRECTED", "UNVERIFIABLE", "FALSE_POSITIVE"] as const).map(k => <div key={k} className="flex items-center justify-between"><VBadge status={k} /><span className="num text-[12px]">{vs[k] ?? 0}</span></div>)}</div>
        </Card>
      </div>
    </div>
  </div>
}

function DistTable({ rows, maxHeight }: { rows: Dist[]; maxHeight?: number }) {
  const cols: Col<Dist>[] = [
    { key: "b", label: "Borrower", sort: r => r.borrower, text: r => `${r.borrower} ${r.bdc}`, render: r => <span className="block max-w-[340px] truncate text-ink" title={r.borrower}>{r.borrower.replace(/\s+\d+$/, "")}</span> },
    { key: "bdc", label: "Lender", sort: r => r.bdc, render: r => <Tag>{r.bdc}</Tag> },
    { key: "par", label: "Par", align: "right", sort: r => r.par_m, render: r => <span className="num">{fmtM(r.par_m)}</span> },
    { key: "mk", label: "Mark", align: "right", sort: r => r.mark, render: r => <span className={cn("num font-semibold", r.mark < 50 ? "text-down" : "text-amber")}>{fmtPx(r.mark)}</span> },
    { key: "chg", label: "Δ QoQ", align: "right", sort: r => r.chg_q, render: r => <span className={cn("num", (r.chg_q ?? 0) < 0 ? "text-down" : "text-up")}>{fmtChg(r.chg_q)}</span> },
    { key: "h", label: "13-qtr history", align: "center", render: r => <Sparkline pts={r.hist} /> },
    { key: "s", label: "Source", align: "right", render: r => <SourceLink s={{ title: `${r.borrower} — ${r.bdc} Schedule of Investments`, url: r.source_url, status: "VERIFIED", checked: "2026-06-30", detail: `Par ${fmtM(r.par_m)}, fair value ${fmtM(r.fv_m)} across ${r.tranches} line(s); par-weighted mark ${fmtPx(r.mark)}, lowest line ${fmtPx(r.min_mark)}.` }}>SOI</SourceLink> },
  ]
  return <DataTable rows={rows} cols={cols} initialSort={{ key: "par", dir: -1 }} filterPlaceholder="Filter borrower or BDC" maxHeight={maxHeight} />
}

// ---------------- Marks ----------------
function Marks() {
  const { data } = useApi<Dist[]>("/api/distressed"); const [bdc, setBdc] = useState("ALL")
  const ok = (data ?? []).filter(d => d.qa === "ok")
  const bdcs = useMemo(() => [...new Set(ok.map(d => d.bdc))].sort(), [data])
  const rows = ok.filter(d => bdc === "ALL" || d.bdc === bdc)
  const held = (data ?? []).length - ok.length
  return <div><PageHead kicker="Private credit" title="Distressed marks monitor" sub={`Positions marked below 75 (par-weighted fair value ÷ par) in the 30 Jun 2026 BDC Schedules of Investments, with up to 13 quarters of history from the same filings. ${held} lines with currency or unit anomalies are held back for review.`} />
    <div className="flex flex-wrap gap-1 border-b border-line px-5 py-2">{["ALL", ...bdcs].map(k => <Button key={k} variant={bdc === k ? "outline" : "ghost"} onClick={() => setBdc(k)} className="h-6 px-2 font-mono text-[10.5px]">{k === "ALL" ? "All lenders" : k}</Button>)}</div>
    <div className="p-3"><Card pad={false}><DistTable rows={rows} maxHeight={700} /></Card></div>
  </div>
}

// ---------------- Cross-Asset Radar: Mining + Land, Macro ----------------
type MLeg = { ticker: string; bench: string; x1: number | null; x5: number | null; x20: number | null }
type MJ = { asof: string; events: { date: string; what: string; url: string; quote: string; found: boolean; legs: MLeg[] }[]; event_summary: Record<string, { n: number; mean: number; median: number; hit: number }>;
  claims: { fetched: string; caveat: string; sites: { site: string; mineral: string; active: number; filed_pending: number; closed: number; lapse_ratio: number; pending_share: number }[] };
  sat: { caveat: string; scenes: { site: string; before?: string; after?: string }[] }; concentration: { source: string; rows: { mineral: string; quote: string }[] };
  regime: { pillar: string; metric: string; value: string; change: string; pctile: number | null; read: string; src: string }[]; gaps: string[] }
function XRadar() {
  const { data: J } = useApi<MJ>("/api/mining")
  if (!J || !J.regime) return <div className="p-6 text-mute">Loading…</div>
  const f = (z: number | null) => z === null ? "n/a" : `${z > 0 ? "+" : ""}${z.toFixed(1)}%`
  return <div className="space-y-5 p-6">
    <PageHead kicker={`Cross-Asset Radar · Mining + Land · ${J.asof}`} title="Export controls, claims, satellites and the macro regime" sub="Public data only. MOFCOM primary text, BLM MLRS claims, Earth Search Sentinel-2, USGS MCS 2026, IMF COFER, FRED. Reads marked as judgement; gaps listed." right={<a href="/research/TRIAGE_Cross_Asset_Radar.pdf" target="_blank" className="text-[12px] text-info">Open PDF</a>} />
    <Card title="Macro regime (Dalio-style)"><table className="w-full text-[12px]"><tbody>{J.regime.map(d => <tr key={d.pillar} className="border-t border-line"><td className="py-1 pr-3 text-ink">{d.pillar}</td><td className="pr-3 text-mute">{d.metric}</td><td className="pr-3">{d.value}</td><td className="pr-3">{d.change}</td><td className="pr-3">{d.pctile ?? "—"}</td><td><Tag>{d.read}</Tag></td></tr>)}</tbody></table></Card>
    <Card title="Event study: equities after Chinese export controls (excess return)"><table className="w-full text-[12px]"><tbody>{J.events.flatMap(e => e.legs.map(l => <tr key={e.date + l.ticker} className="border-t border-line"><td className="py-1 pr-3"><a className="text-info" href={e.url} target="_blank">{e.date}</a> {e.what}</td><td className="pr-3">{l.ticker}</td><td className="pr-3">{f(l.x1)}</td><td className="pr-3">{f(l.x5)}</td><td>{f(l.x20)}</td></tr>))}</tbody></table>
      <div className="mt-2 text-[12px] text-mute">{Object.entries(J.event_summary).map(([k, v]) => `${k.slice(1)}d: mean ${v.mean}% · median ${v.median}% · ${v.hit}% positive (n=${v.n})`).join("  |  ")} — small n, overlapping legs.</div></Card>
    <Card title={`Claims around controlled-mineral deposits (BLM MLRS, ${J.claims.fetched})`}><table className="w-full text-[12px]"><tbody>{J.claims.sites.map(s => <tr key={s.site} className="border-t border-line"><td className="py-1 pr-3">{s.site}</td><td className="pr-3">active {s.active}</td><td className="pr-3">pending {s.filed_pending} ({Math.round(100 * s.pending_share)}%)</td><td className="pr-3">closed {s.closed}</td><td>lapse {s.lapse_ratio}</td></tr>)}</tbody></table><div className="mt-2 text-[12px] text-mute">{J.claims.caveat}</div></Card>
    <Card title="Supply concentration (USGS MCS 2026)"><ul className="text-[12px]">{J.concentration.rows.map(r => <li key={r.mineral}><b>{r.mineral}</b>: {r.quote}</li>)}</ul></Card>
    <Card title="Gaps"><ul className="list-disc pl-5 text-[12px] text-mute">{J.gaps.map(g => <li key={g}>{g}</li>)}</ul></Card>
  </div>
}

// ---------------- Signal Library ----------------
type SAgg = { n: number; precision?: number; mean_excess?: number; t_stat?: number | null }
type SSig = { id: string; cls: string; asset: string; mechanism: string; trigger: string; data: string; buyer: string; h: number; status: string; in_sample: SAgg; oos: SAgg; oos_start: string; live: { fired: boolean; detail: string }; worst_oos: { date: string; x: number }[] }
type SJ = { signals: SSig[]; v2: Record<string, any>; gaps: { gap: string; why: string; source: string; status: string }[]; agents: { name: string; charter: string }[] }
function Signals() {
  const { data: J } = useApi<SJ>("/api/signals")
  const [open, setOpen] = useState<string | null>(null)
  if (!J || !J.signals) return <div className="p-6 text-mute">Loading…</div>
  const a = (x: SAgg) => !x.n ? "—" : `${x.n} · ${x.precision}% · ${x.mean_excess! > 0 ? "+" : ""}${x.mean_excess}% · t=${x.t_stat ?? "—"}`
  const tone = (s: string) => s === "KEPT" ? "text-ok" : s.startsWith("KILLED") ? "text-bad" : "text-amber"
  const v2 = J.v2
  return <div className="space-y-5 p-6">
    <PageHead kicker="Signal library · 23 Oct 2026" title={`${J.signals.length} signals tested — ${J.signals.filter(s => s.status === "KEPT").length} kept`} sub="Event study per signal: publication-lagged entry, drift-adjusted excess, costs deducted, OOS from 2019 (crypto 2023). Kill rule applied without re-tuning." right={<a href="/research/TRIAGE_Cross_Asset_Radar.pdf" target="_blank" className="text-[12px] text-info">Open PDF</a>} />
    <Card title="Signals (click a row for mechanism and worst OOS events)"><table className="w-full text-[12px]"><thead><tr className="text-mute"><td>ID</td><td>Class</td><td>Trigger</td><td>IS n·prec·mean·t</td><td>OOS n·prec·mean·t</td><td>Verdict</td><td>Live</td></tr></thead><tbody>{J.signals.map(s => <Fragment key={s.id}><tr className="cursor-pointer border-t border-line" onClick={() => setOpen(open === s.id ? null : s.id)}><td className="py-1 pr-2">{s.id}</td><td className="pr-2">{s.cls}</td><td className="pr-2">{s.trigger}</td><td className="pr-2">{a(s.in_sample)}</td><td className="pr-2">{a(s.oos)}</td><td className={cn("pr-2 font-medium", tone(s.status))}>{s.status}</td><td>{s.live.fired ? <Tag>FIRED</Tag> : ""} <span className="text-mute">{s.live.detail}</span></td></tr>{open === s.id && <tr><td colSpan={7} className="bg-line/30 p-2 text-[12px]"><b>Mechanism:</b> {s.mechanism}<br /><b>Data:</b> {s.data} · <b>Buyer:</b> {s.buyer}<br /><b>Worst OOS:</b> {JSON.stringify(s.worst_oos)}</td></tr>}</Fragment>)}</tbody></table></Card>
    <Card title="Committee v2 (signals only, net of costs) vs benchmark — OOS 2019+"><table className="w-full text-[12px]"><tbody>{Object.entries(v2).filter(([k]) => k.includes("|") && !k.endsWith("2022+")).map(([k, v]: [string, any]) => <tr key={k} className="border-t border-line"><td className="py-1 pr-3">{k}</td><td className="pr-3">CAGR {v.cagr}%</td><td className="pr-3">vol {v.vol}%</td><td className="pr-3">Sharpe {v.sharpe}</td><td>maxDD {v.maxdd}%</td></tr>)}</tbody></table><div className="mt-2 text-[12px] text-mute">No committee beats equal-weight after costs. Tier B was selected using OOS results, so treat it as an upper bound.</div></Card>
    <Card title="Gap audit (sceptical buyer view)"><table className="w-full text-[12px]"><tbody>{J.gaps.map(g => <tr key={g.gap} className="border-t border-line"><td className="py-1 pr-3 text-ink">{g.gap}</td><td className="pr-3 text-mute">{g.why}</td><td className="pr-3">{g.source}</td><td>{g.status}</td></tr>)}</tbody></table></Card>
    <Card title="Recommended agents (not created)"><ul className="space-y-2 text-[12px]">{J.agents.map(x => <li key={x.name}><b>{x.name}.</b> {x.charter}</li>)}</ul></Card>
  </div>
}

// ---------------- Alpha Committee (AlphaAgents arXiv:2508.11152, adapted) ----------------
type CStat = { cagr: number; vol: number; sharpe: number; maxdd: number }
type CJ = { paper: string; chain_ok: boolean; n: number; roles: string[]; backtest: Record<string, { full: Record<string, CStat>; oos_2021: Record<string, CStat>; committee_calls: number; committee_beat_ew_pct: number }>;
  ledger: { kind: string; instrument: string; call: string; entry: number; entry_date: string; thesis: string; exit_rule: string; benchmark: string; hash: string; logged_at: string }[];
  licensing: { jur: string; url: string; grade: string; quote: string; meaning: string }[] }
type FJ = { asof: string; positioning: string; tiers: [string, string][]; partners: { region: string; firm: string; situation: string }[]; crowded: { name: string; country: string; short_pct: number; asof: string }[]; ledger: { n: number; ok: boolean }; kept: string[]; killed: string[]; pit: Record<string, any>; situations: { entity: string; country: string; date: string; basis: string }[] }
function Home() {
  const { data: J } = useApi<FJ>("/api/flagship")
  if (!J || !J.tiers) return <div className="p-6 text-mute">Loading…</div>
  return <div className="space-y-5 p-6">
    <PageHead kicker={`TRIAGE OS · Credit & Forced-Seller Intelligence · ${J.asof}`} title={J.positioning} sub="Worldwide restructuring calendar, control maps and forced sellers. The cross-asset radar is macro and forced-flow context, not an alpha claim. Public sources; not investment advice." />
    <Card title={`Restructuring calendar — next ${J.situations.length} dated catalysts`}><table className="w-full text-[12px]"><tbody>{J.situations.map((s, i) => <tr key={i} className="border-t border-line"><td className="num py-1 pr-3 text-amber">{s.date}</td><td className="pr-3">{s.entity}</td><td className="pr-3 text-mute">{s.country}</td><td className="text-mute">{s.basis}</td></tr>)}</tbody></table></Card>
    <div className="grid grid-cols-2 gap-5">
      <Card title="Crowded shorts — forced buy-in watch (AMF / AFM registers)"><table className="w-full text-[12px]"><tbody>{J.crowded.map(c => <tr key={c.name} className="border-t border-line"><td className="py-1">{c.name}</td><td className="text-mute">{c.country}</td><td className="num text-right">{c.short_pct.toFixed(2)}%</td><td className="num pl-3 text-mute">{c.asof}</td></tr>)}</tbody></table><div className="mt-2 text-[11px] text-dim">Risk flag only: the &gt;5% crossing signal was killed out of sample.</div></Card>
      <Card title="Credibility"><ul className="space-y-1.5 text-[12px]"><li>Forward ledger: <b>{J.ledger.n}</b> paper calls, hash chain {J.ledger.ok ? "verified" : "BROKEN"}, anchored daily (OpenTimestamps).</li><li>Kept signals: <b>{J.kept.join(", ") || "none"}</b></li><li>Killed (shown, not hidden): {J.killed.join(", ")}</li><li>Point-in-time: {J.pit?.summary ?? "pending"}</li></ul></Card>
      <Card title="Pricing (judgement)"><table className="w-full text-[12px]"><tbody>{J.tiers.map(t => <tr key={t[0]} className="border-t border-line"><td className="py-1">{t[0]}</td><td className="num text-right">{t[1]}</td></tr>)}</tbody></table></Card>
      <Card title="First 10 design-partner targets (firms only, nothing sent)"><table className="w-full text-[12px]"><tbody>{J.partners.map(p => <tr key={p.firm} className="border-t border-line"><td className="py-1 pr-2 text-mute">{p.region}</td><td className="pr-2">{p.firm}</td><td className="text-mute">{p.situation}</td></tr>)}</tbody></table></Card>
    </div>
  </div>
}
type BC = { t: string; name: string; choke: string; chain: string; fact: string; cat: [string, string]; risks: string; kill: string; mcap_usd: number; r12m: number | null; score: number; grade: string; contrarian: string; ev: string[] }
function Bottleneck() {
  const { data: J } = useApi<{ top: BC[]; base: { sub300: Record<string, number> }; ledger_ok: boolean }>("/api/bottleneck")
  if (!J || !J.top) return <div className="p-6 text-mute">Loading…</div>
  const b = J.base.sub300
  return <div className="space-y-5 p-6">
    <PageHead kicker="Bottleneck Hunt · research only · paper WATCH calls" title="Small companies inside supply chokepoints" sub="Asymmetric setups, not promises. Nothing here claims 100x. Every name is vetoed by Quant Validation as recommendation-grade." />
    <Card title="Base rate: chokepoint small caps, entry cap under $300m, 12-month window (survivorship-biased upward)"><div className="grid grid-cols-5 gap-4 text-[12px]"><Stat label="Touched 10x" value={`${b.touch_10x_pct}%`} /><Stat label="Still ≥10x at 12m" value={`${b.hold_10x_pct}%`} /><Stat label="Touched 2x" value={`${b.touch_2x_pct}%`} /><Stat label="Lost ≥50%" value={`${b.lose_50_pct}%`} /><Stat label="Median max drawdown" value={`${b.median_maxdd}%`} /></div></Card>
    <Card title={`Top 15 (ledger chain ${J.ledger_ok ? "verified" : "BROKEN"})`}><table className="w-full text-[12px]"><thead><tr className="text-mute"><td>#</td><td>Company</td><td>Chain</td><td className="text-right">Mcap $m</td><td className="text-right">12m</td><td className="text-right">Score</td><td>Grade</td><td>Catalyst</td><td>Kill if</td></tr></thead><tbody>{J.top.map((c, i) => <tr key={c.t} className="border-t border-line align-top"><td className="py-1 pr-2">{i + 1}</td><td className="pr-2"><b>{c.name}</b><div className="text-mute">{c.t}</div></td><td className="pr-2 text-mute">{c.chain}<div className="mt-1">{c.ev.map(u => <a key={u} className="mr-2 text-info" href={u} target="_blank">src</a>)}</div></td><td className="num text-right">{c.mcap_usd}</td><td className="num text-right">{c.r12m ?? "–"}%</td><td className="num text-right">{c.score}</td><td>{c.grade}</td><td className="pr-2"><span className="num text-amber">{c.cat[0]}</span> {c.cat[1]}</td><td className="text-mute">{c.kill}</td></tr>)}</tbody></table></Card>
  </div>
}
function EdgeLab() {
  const { data: J } = useApi<{ playbook: Record<string, string>[]; results: Record<string, any>; overlooked: Record<string, string>[]; live: Record<string, any>[] }>("/api/edge")
  if (!J || !J.playbook) return <div className="p-6 text-mute">Loading…</div>
  const tone = (s: string) => s.startsWith("KEPT") ? "text-up" : s.startsWith("KILLED") ? "text-down" : "text-amber"
  return <div className="space-y-5 p-6">
    <PageHead kicker="Edge Lab · research only · paper ledger" title="How the big funds find edge, and what survives our tests" sub="Filing-date point-in-time events from EDGAR, costs, out-of-sample from 2022, kill rule enforced. One mechanism survives; it is an avoid/risk signal because borrow is scarce." />
    <Card title="Backtests"><table className="w-full text-[12px]"><thead><tr className="text-mute"><td>Mechanism</td><td>Status</td><td className="text-right">OOS n</td><td className="text-right">OOS prec</td><td className="text-right">OOS mean</td><td className="text-right">OOS median</td><td className="text-right">IS mean</td></tr></thead><tbody>{Object.entries(J.results).map(([k, v]) => <tr key={k} className="border-t border-line"><td className="py-1 pr-2">{k}</td><td className={tone(v.status)}>{v.status}</td><td className="num text-right">{v.OOS?.n ?? "–"}</td><td className="num text-right">{v.OOS?.precision ?? "–"}%</td><td className="num text-right">{v.OOS?.mean ?? "–"}%</td><td className="num text-right">{v.OOS?.median ?? "–"}%</td><td className="num text-right">{v.IS?.mean ?? "–"}%</td></tr>)}</tbody></table></Card>
    <Card title="Big-funds playbook"><table className="w-full text-[12px]"><tbody>{J.playbook.map(p => <tr key={p.fund} className="border-t border-line align-top"><td className="py-1 pr-2 font-semibold">{p.fund}</td><td className="pr-2">{p.mechanism}</td><td className="pr-2 text-mute">{p.free}</td><td>{p.grade}</td></tr>)}</tbody></table></Card>
    <Card title="Overlooked audit"><ul className="space-y-1.5 text-[12px]">{J.overlooked.map(o => <li key={o.item}><b>{o.item}</b>: {o.why} <span className="text-amber">{o.status}</span></li>)}</ul></Card>
    <Card title="Live AVOID / paper SHORT-WATCH (M5 late filers)"><table className="w-full text-[12px]"><tbody>{J.live.map(r => <tr key={r.ticker} className="border-t border-line"><td className="py-1 pr-2">{r.ticker}</td><td className="pr-2">{r.company}</td><td className="num pr-2">{r.filed}</td><td className="pr-2 text-mute">{r.deadline_note}</td><td><a className="text-info" href={r.src} target="_blank">filing</a></td></tr>)}</tbody></table></Card>
  </div>
}
function Committee() {
  const { data: J } = useApi<CJ>("/api/committee")
  if (!J || !J.backtest) return <div className="p-6 text-mute">Loading…</div>
  const keys = ["committee", "equal_weight", ...J.roles]
  return <div className="space-y-5 p-6">
    <PageHead kicker="Alpha Committee · PAPER ONLY" title="Six agents debate, the ledger keeps score" sub="Protocol adapted from AlphaAgents (BlackRock, arXiv:2508.11152): independent analysis, round-robin debate (each agent speaks at least twice), consensus, risk profiles. Rule-based agents, so the backtest has no LLM look-ahead. No trades, not advice." right={<a href={J.paper} target="_blank" className="text-[12px] text-info">Paper</a>} />
    {Object.entries(J.backtest).map(([prof, b]) => <Card key={prof} title={`Backtest — ${prof} (committee picks beat EW ${b.committee_beat_ew_pct}% of the time)`}><table className="w-full text-[12px]"><thead><tr className="text-mute"><td>Portfolio</td><td>CAGR full</td><td>Sharpe full</td><td>MaxDD full</td><td>CAGR 2021+</td><td>Sharpe 2021+</td><td>MaxDD 2021+</td></tr></thead><tbody>{keys.map(k => <tr key={k} className={cn("border-t border-line", k === "committee" && "text-amber")}><td className="py-1">{k}</td><td>{b.full[k]?.cagr}%</td><td>{b.full[k]?.sharpe}</td><td>{b.full[k]?.maxdd}%</td><td>{b.oos_2021[k]?.cagr}%</td><td>{b.oos_2021[k]?.sharpe}</td><td>{b.oos_2021[k]?.maxdd}%</td></tr>)}</tbody></table></Card>)}
    <Card title={`Hash-chained paper ledger — ${J.n} calls, chain ${J.chain_ok ? "verified" : "BROKEN"}`}><table className="w-full text-[12px]"><tbody>{J.ledger.map(r => <tr key={r.hash} className="border-t border-line"><td className="py-1 pr-2">{r.entry_date}</td><td className="pr-2">{r.instrument}</td><td className="pr-2"><Tag>{r.call}</Tag></td><td className="pr-2">{r.entry.toPrecision(4)}</td><td className="pr-2 text-mute">{r.thesis.slice(0, 120)}</td><td className="font-mono text-[10px] text-mute">{r.hash.slice(0, 10)}</td></tr>)}</tbody></table></Card>
    <Card title="Licensing (high level, user to handle)"><ul className="space-y-2 text-[12px]">{J.licensing.map(l => <li key={l.url}><b>{l.jur}</b> — <a className="text-info" href={l.url} target="_blank">{l.grade}</a>: “{l.quote}” <span className="text-mute">{l.meaning}</span></li>)}</ul></Card>
  </div>
}

// ---------------- World ----------------
type WChk = { url: string; fetched: string; token: string; found: boolean; quote: string; grade: string }
type WPx = { instrument: string; value: number; unit: string; kind: string; date: string; source: string } | null
type WSit = { id: string; country: string; entity: string; stage: string; chokepoint: string; date: string; basis: string; url: string; status: string; note: string; checks: WChk[]; price: WPx; recovery: { value: number; basis: string } | null; gap: number | null }
type WJ = { asof: string; situations: WSit[]; killed: { name: string; why: string }[]; forced: { topic: string; fact: string; grade: string; check: WChk }[]; buyers: { firm: string; base: string; situation: string }[]; backers: { name: string; type: string; evidence: string; check: WChk }[]; passes: string[]; scenarios: { name: string; arr: number }[] }
function World() {
  const { data: J } = useApi<WJ>("/api/world")
  const [mkt, setMkt] = useState("All")
  const [open, setOpen] = useState<string | null>(null)
  if (!J) return <div className="text-mute text-[12px]">Loading…</div>
  const mkts = ["All", ...Array.from(new Set(J.situations.map(s => s.country)))]
  const rows = J.situations.filter(s => mkt === "All" || s.country === mkt)
  const dated = J.situations.filter(s => s.date !== "TBC").sort((a, b) => a.date.localeCompare(b.date))
  return <div>
    <PageHead kicker={`World desk · v2 · ${J.asof}`} title="25 live non-US situations: who decides, when, and the price" sub="Every fact was fetched again today from a primary source, and each one is logged with its URL, fetch time and exact quote. Secondary-only items are labelled. Gaps are computed only where a current price and a recovery figure both exist." right={<a href="/research/TRIAGE_World.pdf" target="_blank" className="text-[12px] text-info">Open PDF</a>} />
    <div className="mb-3 grid grid-cols-5 gap-3">
      <Stat label="Live situations" value={String(J.situations.length)} />
      <Stat label="Primary-verified" value={String(J.situations.filter(s => s.status === "VERIFIED-PRIMARY").length)} />
      <Stat label="With public price" value={String(J.situations.filter(s => s.price).length)} />
      <Stat label="Killed" value={String(J.killed.filter(k => !k.name.includes("NOT")).length)} />
      <Stat label="Base ARR (judgement)" value={`£${J.scenarios.find(x => x.name === "Base")?.arr}k`} />
    </div>
    <div className="grid grid-cols-2 gap-3">
      <Card title="Court calendar"><div className="flex flex-wrap gap-2 p-3">{dated.map(s => <a key={s.id} href={s.url} target="_blank" className="rounded-[3px] border border-line px-2 py-1 text-[11.5px] hover:text-ink"><b className="text-amber">{s.date}</b> {s.country} · {s.entity.split(" (")[0]}</a>)}</div></Card>
      <Card title="Forced sellers (weekly layer)"><div className="p-2 text-[11.5px]">{J.forced.map(f => <div key={f.topic} className="border-b border-line py-1"><b>{f.topic}</b>: {f.fact} <span className="text-mute">· {f.grade.split(".")[0]}</span></div>)}</div></Card>
    </div>
    <div className="my-3 flex gap-1">{mkts.map(m => <button key={m} onClick={() => setMkt(m)} className={cn("rounded-[3px] px-2 py-1 text-[11.5px]", mkt === m ? "bg-line text-ink" : "text-mute")}>{m}</button>)}</div>
    <Card title="Situations, chokepoints, prices (click a row for the sourcing quotes)"><table className="w-full text-[11.5px]"><thead><tr className="text-left text-mute"><th className="p-2">#</th><th>Mkt</th><th>Situation</th><th>Who decides</th><th>Catalyst</th><th>Price</th><th>Recovery</th><th>Gap</th><th>Check</th></tr></thead>
      <tbody>{rows.map(s => <>
        <tr key={s.id} onClick={() => setOpen(open === s.id ? null : s.id)} className="cursor-pointer border-t border-line align-top hover:bg-line/30"><td className="p-2 text-mute">{s.id}</td><td>{s.country}</td><td><a href={s.url} target="_blank" className="text-info">{s.entity}</a><div className="text-mute">{s.stage}</div></td><td>{s.chokepoint}</td><td><b>{s.date}</b><div className="text-mute">{s.basis}</div></td>
          <td>{s.price ? <><b>{s.price.value}</b> {s.price.unit}<div className="text-mute">{s.price.kind.split(" (")[0]} · {s.price.date}</div></> : <span className="text-mute">none</span>}</td>
          <td>{s.recovery ? <>{s.recovery.value}%<div className="text-mute">{s.recovery.basis.slice(0, 60)}</div></> : <span className="text-mute">—</span>}</td>
          <td>{s.gap !== null ? <b className={s.gap < 0 ? "text-down" : "text-up"}>{s.gap > 0 ? "+" : ""}{s.gap} pts</b> : <span className="text-mute">abstain</span>}</td>
          <td><Tag>{s.status}</Tag></td></tr>
        {open === s.id && <tr key={s.id + "q"}><td colSpan={9} className="bg-line/20 p-2 text-[11px]">{s.note && <div className="mb-1 text-amber">{s.note}</div>}{s.checks.map((c, i) => <div key={i} className="mb-1"><Tag>{c.grade}</Tag> <a href={c.url} target="_blank" className="text-info">{host(c.url)}</a> <span className="text-mute">fetched {c.fetched.slice(0, 16)}</span> — “…{c.quote.slice(80, 320)}…”</div>)}</td></tr>}
      </>)}</tbody></table></Card>
    <div className="mt-3 grid grid-cols-3 gap-3">
      <Card title="Killed or kept (changelog)"><div className="p-2 text-[11.5px]">{J.killed.map(k => <div key={k.name} className="border-b border-line py-1"><b>{k.name}</b><div className="text-mute">{k.why}</div></div>)}</div></Card>
      <Card title="Buyers fitted to situations (judgement)"><div className="max-h-[300px] overflow-auto p-2 text-[11.5px]">{J.buyers.map(b => <div key={b.firm} className="border-b border-line py-1"><b>{b.firm}</b> <span className="text-mute">{b.base}</span> → {b.situation}</div>)}</div></Card>
      <Card title="Backers (no raise until milestones)"><div className="max-h-[300px] overflow-auto p-2 text-[11.5px]">{J.backers.map(b => <div key={b.name} className="border-b border-line py-1"><a href={b.check.url} target="_blank" className="text-info">{b.name}</a> <Tag>{b.check.found ? "VERIFIED" : "NOT FOUND"}</Tag><div className="text-mute">{b.evidence}</div></div>)}<div className="mt-1 text-mute">Passes: {J.passes.join("; ")}</div></div></Card>
    </div>
  </div>
}

// ---------------- Systemic radar ----------------
type SysJ = any
function Gauge({ label, fill, unmet }: { label: string; fill: number | null; unmet: number | null }) {
  const f = Math.max(0, Math.min(100, fill ?? 0)); const a = Math.PI * (1 - f / 100); const x = 50 + 40 * Math.cos(a), y = 50 - 40 * Math.sin(a)
  return <div className="flex flex-col items-center"><svg viewBox="0 0 100 58" className="w-[120px]"><path d="M10 50 A40 40 0 0 1 90 50" fill="none" stroke="#2a323c" strokeWidth="9" />
    <path d={`M10 50 A40 40 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}`} fill="none" stroke={f < 50 ? "#e5484d" : f < 100 ? "#f5a524" : "#30a46c"} strokeWidth="9" />
    <text x="50" y="47" textAnchor="middle" fontSize="13" fill="#e6e9ec" fontFamily="JetBrains Mono">{f.toFixed(0)}%</text></svg>
    <div className="text-[11.5px] font-semibold text-ink">{label}</div><div className="num text-[10.5px] text-amber">{unmet ? `$${(unmet / 1000).toFixed(2)}bn unmet` : "queue cleared"}</div></div>
}
function Heat({ rows }: { rows: { st: string; n: number; hi: number; asset_hi: number; cre_hi: number }[] }) {
  const top = [...rows].sort((a, b) => b.asset_hi - a.asset_hi).slice(0, 24); const mx = { hi: Math.max(...top.map(r => r.hi), 1), asset_hi: Math.max(...top.map(r => r.asset_hi), 1), share: 1 }
  const cell = (v: number, m: number) => `rgba(245,165,36,${(0.08 + 0.9 * Math.min(1, v / m)).toFixed(2)})`
  return <div className="grid grid-cols-[repeat(12,minmax(0,1fr))] gap-1">{top.map(r => <div key={r.st} className="rounded-[2px] p-1.5 text-center" style={{ background: cell(r.asset_hi, mx.asset_hi) }} title={`${r.st}: ${r.hi} banks >300%, $${(r.asset_hi / 1000).toFixed(1)}bn assets`}>
    <div className="text-[11px] font-semibold text-ink">{r.st}</div><div className="num text-[10px] text-ink/80">{r.hi}/{r.n}</div><div className="num text-[9.5px] text-ink/70">${(r.asset_hi / 1000).toFixed(0)}bn</div></div>)}</div>
}
function Contagion({ edges }: { edges: { a: string; b: string; shared: number }[] }) {
  const sys = ["Non-traded BDCs", "Listed BDCs", "Insurers", "Banks (CRE>300%)", "CMBS / office", "Mutual funds"]
  const sysE: [string, string, string][] = [["Non-traded BDCs", "Listed BDCs", "shared borrowers / marks"], ["Non-traded BDCs", "Insurers", "~$32bn fund interests"], ["Banks (CRE>300%)", "CMBS / office", "office maturities"], ["Insurers", "CMBS / office", "CRE loans & CMBS"], ["Mutual funds", "CMBS / office", "$73bn CMBS-like ABS"], ["Banks (CRE>300%)", "Non-traded BDCs", "subscription / NAV lines"], ["Mutual funds", "Listed BDCs", "stressed-issuer overlap"]]
  const bdcs = [...new Set(edges.flatMap(e => [e.a, e.b]))].slice(0, 10)
  const pos: Record<string, [number, number]> = {}
  sys.forEach((s, i) => { const a = (i / sys.length) * 2 * Math.PI - Math.PI / 2; pos[s] = [300 + 170 * Math.cos(a), 170 + 120 * Math.sin(a)] })
  bdcs.forEach((s, i) => { const a = (i / bdcs.length) * 2 * Math.PI; pos[s] = [pos["Listed BDCs"][0] + 70 * Math.cos(a), pos["Listed BDCs"][1] + 45 * Math.sin(a)] })
  return <svg viewBox="0 0 600 340" className="w-full">
    {sysE.map(([a, b, l], i) => <g key={i}><line x1={pos[a][0]} y1={pos[a][1]} x2={pos[b][0]} y2={pos[b][1]} stroke="#f5a524" strokeOpacity="0.55" strokeWidth="2" /><text x={(pos[a][0] + pos[b][0]) / 2} y={(pos[a][1] + pos[b][1]) / 2 - 3} fontSize="8.5" fill="#8a96a3" textAnchor="middle">{l}</text></g>)}
    {edges.filter(e => pos[e.a] && pos[e.b]).map((e, i) => <line key={"b" + i} x1={pos[e.a][0]} y1={pos[e.a][1]} x2={pos[e.b][0]} y2={pos[e.b][1]} stroke="#4c8dff" strokeOpacity="0.6" strokeWidth={Math.min(4, e.shared / 2)} />)}
    {bdcs.map(b => <g key={b}><circle cx={pos[b][0]} cy={pos[b][1]} r="9" fill="#13202f" stroke="#4c8dff" /><text x={pos[b][0]} y={pos[b][1] + 3} fontSize="6.5" fill="#cfe0ff" textAnchor="middle">{b}</text></g>)}
    {sys.map(s => <g key={s}><circle cx={pos[s][0]} cy={pos[s][1]} r="22" fill="#1b1508" stroke="#f5a524" /><text x={pos[s][0]} y={pos[s][1] + 34} fontSize="10" fill="#e6e9ec" textAnchor="middle">{s}</text></g>)}
  </svg>
}
function Wall({ by }: { by: Record<string, Record<string, number>> }) {
  const types = Object.keys(by).sort((a, b) => Object.values(by[b]).reduce((x, y) => x + y, 0) - Object.values(by[a]).reduce((x, y) => x + y, 0))
  const yrs = ["2026", "2027", "2028"]; const tot = yrs.map(y => types.reduce((s, t) => s + (by[t][y] ?? 0), 0)); const mx = Math.max(...tot, 1)
  const col: Record<string, string> = { Office: "#e5484d", Retail: "#f5a524", Other: "#5b6570", Lodging: "#a78bfa", "Mixed use": "#4c8dff", Multifamily: "#30a46c", Industrial: "#8a96a3" }
  return <div><svg viewBox="0 0 420 220" className="w-full">{yrs.map((y, i) => { let acc = 0; return <g key={y}>{types.map(t => { const v = by[t][y] ?? 0; const h = (v / mx) * 170; acc += h; return <rect key={t} x={40 + i * 130} y={190 - acc} width="80" height={h} fill={col[t] ?? "#5b6570"}><title>{`${t} ${y}: $${v.toFixed(0)}m`}</title></rect> })}
    <text x={80 + i * 130} y="206" fontSize="11" fill="#e6e9ec" textAnchor="middle">{y}</text><text x={80 + i * 130} y={186 - acc} fontSize="10" fill="#f5a524" textAnchor="middle" fontFamily="JetBrains Mono">${(tot[i] / 1000).toFixed(1)}bn</text></g> })}</svg>
    <div className="flex flex-wrap gap-3 text-[10.5px] text-mute">{types.map(t => <span key={t} className="flex items-center gap-1"><span className="h-2 w-2" style={{ background: col[t] ?? "#5b6570" }} />{t}</span>)}</div></div>
}
function Systemic() {
  const { data: J } = useApi<SysJ>("/api/systemic")
  if (!J || !J.banks) return <div className="p-6 text-mute">Loading…</div>
  const B = J.banks
  return <div><PageHead kicker="Systemic radar · 23 Oct 2026" title="Where the next $10bn+ dislocation is" sub={`Every FDIC bank (${B.n.toLocaleString()}), every N-PORT fund series (${J.nport.series.toLocaleString()}), 40 BDCs' marks and non-traded BDC tender results. Probabilities are judgement.`} right={<a href="/research/Where_the_next_dislocation_is.pdf" target="_blank" className="text-[12px] text-info">Open PDF</a>} />
    <div className="grid grid-cols-5 gap-3 p-3">
      <Card title="Unmet BDC redemptions"><div className="num text-[22px] text-amber">${J.unmet_bn.toFixed(1)}bn</div><div className="text-[11px] text-dim">of ${J.requested_bn.toFixed(1)}bn requested, latest round, 6 funds</div></Card>
      <Card title="Banks CRE >300% capital"><div className="num text-[22px] text-ink">{B.hi}</div><div className="text-[11px] text-dim">${B.hi_asset_bn.toFixed(0)}bn assets · {B.hi_prev} a year ago</div></Card>
      <Card title="Unrealised securities losses"><div className="num text-[22px] text-ink">${(-(B.afs_ul + B.htm_ul)).toFixed(0)}bn</div><div className="text-[11px] text-dim">vs ${B.t1.toFixed(0)}bn tier 1, all banks</div></Card>
      <Card title="CMBS delinquency"><div className="num text-[22px] text-ink">8.02%</div><div className="text-[11px] text-dim">office 12.16% · Trepp Sep 2026</div></Card>
      <Card title="HY OAS"><div className="num text-[22px] text-ink">{J.fred.BAMLH0A0HYM2.value}%</div><div className="text-[11px] text-dim">counter-signal: spreads tight</div></Card>
    </div>
    <div className="grid grid-cols-[1.1fr_1fr] gap-3 px-3">
      <Card title="Redemption-queue gauges" right="fill = accepted ÷ requested, latest final tender"><div className="grid grid-cols-3 gap-y-3 py-2">{[...J.tender_latest].sort((a: any, b: any) => (b.unmet_usd_m ?? 0) - (a.unmet_usd_m ?? 0)).map((r: any) => <Gauge key={r.ticker} label={`${r.ticker} · ${r.expired}`} fill={r.fill} unmet={r.unmet_usd_m} />)}</div></Card>
      <Card title="Contagion network" right="amber = system channels · blue = BDC pairs sharing 3+ stressed borrowers"><Contagion edges={J.cascade.edges} /></Card>
    </div>
    <div className="grid grid-cols-[1.4fr_1fr] gap-3 p-3">
      <Card title="Heatmap: banks above 300% CRE/capital by state" right="shade = assets of high-CRE banks · n above / screened"><Heat rows={J.states} /></Card>
      <Card title="Maturity wall (ABS-EE sample)" right={`${J.maturity.trusts} trusts · ${J.maturity.loans.toLocaleString()} loans`}><Wall by={J.maturity.by_type} /></Card>
    </div>
    <div className="px-3 pb-3"><Card title="Ranked theses (judgement)" pad={false}><table className="w-full text-[12px]"><tbody>{J.theses.map((t: any) => <tr key={t.rank} className="border-b border-line align-top"><td className="num w-8 p-2 text-amber">{t.rank}</td><td className="p-2 text-ink"><div className="font-semibold">{t.name}</div><div className="text-[11px] text-mute">{t.evidence}</div></td><td className="w-[220px] p-2 text-ink">{t.size}</td><td className="w-[200px] p-2 text-amber">{t.prob}</td><td className="w-[260px] p-2 text-mute">{t.buyers}</td></tr>)}</tbody></table></Card></div>
  </div>
}

// ---------------- Control ----------------
type CClass = { cls: string; voting: number; block: number; cost: number | null; group: number; group_blocks: boolean; group_carries: boolean; outside: number; outside_can_block: boolean; insider_blocks: boolean }
type Holder = { trust: string; label: string; directing_holder: string; special_servicer: string; controlling_class: string; cc_balance: string; source_url: string; filed: string }
type CSit = { name: string; chokepoint: string; cost: string; date: string }
function Control() {
  const { data } = useApi<{ classes: CClass[]; holders: Holder[]; situations: CSit[]; prices: { secured: number; unsecured: number } }>("/api/control")
  const yn = (b: boolean) => <Tag tone={b ? "up" : "down"}>{b ? "yes" : "no"}</Tag>
  const ccols: Col<CClass>[] = [
    { key: "c", label: "Hughes class", render: r => <span className="text-ink">{r.cls}</span> },
    { key: "v", label: "Voting $m", align: "right", render: r => <span className="num">{fmtM(r.voting)}</span> },
    { key: "b", label: "Block >1/3", align: "right", render: r => <span className="num text-amber">{fmtM(r.block)}</span> },
    { key: "k", label: "Cost at FV", align: "right", render: r => <span className="num">{r.cost == null ? "n/a" : fmtM(r.cost)}</span> },
    { key: "g", label: "Group (min)", align: "right", render: r => <span className="num">{fmtM(r.group)}</span> },
    { key: "gb", label: "Group blocks", render: r => yn(r.group_blocks) },
    { key: "gc", label: "Group carries", render: r => yn(r.group_carries) },
    { key: "o", label: "Outside float", align: "right", render: r => <span className="num">{fmtM(r.outside)}</span> },
    { key: "ob", label: "Float can block", render: r => yn(r.outside_can_block) },
  ]
  const hs = (data?.holders ?? []).filter(h => h.directing_holder)
  const hcols: Col<Holder>[] = [
    { key: "t", label: "Trust", sort: r => r.trust, text: r => r.trust, render: r => <span className="text-ink">{r.trust}</span> },
    { key: "h", label: "Directing holder / CCR", sort: r => r.directing_holder, text: r => r.directing_holder, render: r => <span className="text-amber">{r.directing_holder}</span> },
    { key: "s", label: "Special servicer", sort: r => r.special_servicer, text: r => r.special_servicer, render: r => <span className="text-mute">{r.special_servicer}</span> },
    { key: "c", label: "Ctrl class", render: r => <Tag>{r.controlling_class || "–"}</Tag> },
    { key: "b", label: "Class bal $m", align: "right", sort: r => Number(r.cc_balance || 0), render: r => <span className="num">{r.cc_balance ? fmtM(Number(r.cc_balance) / 1e6) : "–"}</span> },
    { key: "u", label: "10-D", align: "right", render: r => <SourceLink s={{ title: `${r.trust}: ${r.label}`, url: r.source_url, status: "VERIFIED", checked: r.filed }} /> },
  ]
  return <div><PageHead kicker="Control analysis · 22 Oct 2026" title="Who decides, and what a seat costs" sub="§1126(c) voting math for Hughes 26-90739 at reported fair value, chokepoints in four other situations, and CMBS directing holders parsed from 10-D filings. Likelihoods in the PDF are judgement." right={<a href="/research/Control_Bottleneck.pdf" target="_blank" className="text-[12px] text-info">Open PDF</a>} />
    <div className="grid grid-cols-5 gap-3 p-3">{(data?.situations ?? []).map(s => <Card key={s.name} title={s.name}><div className="text-[12px] text-ink">{s.chokepoint}</div><div className="mt-2 text-[11.5px] text-amber">{s.cost}</div><div className="mt-1 text-[11px] text-dim">{s.date}</div></Card>)}</div>
    <div className="px-3"><Card title="Hughes voting math" right={`FV secured ${data?.prices.secured.toFixed(1) ?? ""} · unsecured ${data?.prices.unsecured.toFixed(1) ?? ""}`} pad={false}><DataTable rows={data?.classes ?? []} cols={ccols} maxHeight={260} /></Card></div>
    <div className="p-3"><Card title={`CMBS directing holders (${hs.length}/${data?.holders.length ?? 0} trusts named)`} pad={false}><DataTable rows={hs} cols={hcols} maxHeight={420} /></Card></div></div>
}

// ---------------- Situations ----------------
function Situations({ sits }: { sits: Sit[] | null }) {
  const cols: Col<Sit>[] = [
    { key: "t", label: "Situation", sort: r => r.title, text: r => r.title, render: r => <span className="font-medium text-ink">{r.title}</span> },
    { key: "n", label: "Next date", sort: r => r.timeline.find(t => t.date > "2026-10-22")?.date ?? "9999", render: r => { const n = r.timeline.filter(t => t.date > "2026-10-22").sort((a, b) => a.date.localeCompare(b.date))[0]; return n ? <span className="num text-amber">{n.date}</span> : <span className="text-dim">none scheduled</span> } },
    { key: "e", label: "Events", align: "right", sort: r => r.timeline.length, render: r => <span className="num">{r.timeline.length}</span> },
    { key: "f", label: "Verified facts", align: "right", sort: r => r.facts.length, render: r => <span className="num">{r.facts.filter(f => statusKey(f.status) === "VERIFIED").length}/{r.facts.length}</span> },
    { key: "go", label: "", align: "right", render: () => <ChevronRight size={14} className="text-dim" /> },
  ]
  return <div><PageHead kicker="Coverage" title="Situations" sub="Restructurings and court cases under coverage, with dated catalysts and the claims ledger for each." />
    <div className="p-3"><Card pad={false}><DataTable rows={sits ?? []} cols={cols} onRow={r => { location.hash = `/situation/${r.key}` }} initialSort={{ key: "n", dir: 1 }} /></Card></div></div>
}

function SituationView({ s }: { s: Sit }) {
  const kw = s.title.split(" ")[0]
  const { data: cap } = useApi<Tranche[]>(`/api/cap?situation=${encodeURIComponent(kw)}`)
  const { data: marks } = useApi<Record<string, any[]>>(MARK_KW[s.key] ? `/api/marks?borrower=${encodeURIComponent(MARK_KW[s.key])}` : null)
  const open = useSource()
  const tl = s.timeline.map(t => { const f = s.facts.find(f => f.claim === t.what); return f && statusKey(f.status) === "CORRECTED" && f.fix ? { ...t, what: f.fix, status: f.status } : t })
  const total = (cap ?? []).reduce((a, r) => a + (Number(r.amount_usd_m) || 0), 0)
  const meta = SIT_META[s.key]
  return <div>
    <PageHead kicker={meta ? `${meta.court} · ${meta.stage}` : "Situation"} title={s.title} sub={s.key === "hughes" ? "Debtor-in-possession on cash collateral; Noteholder Group seeks to terminate exclusivity and file a debt-for-equity plan with a litigation trust against the parent." : undefined}
      right={s.key === "hughes" ? <a href="/research/Hughes_Satellite_Note.pdf" target="_blank"><Button variant="solid"><FileText size={13} />Read the note</Button></a> : undefined} />
    <div className="grid grid-cols-5 border-b border-line bg-panel">
      <Stat label="Disclosed debt" value={fmtM(total, 0)} sub={`${cap?.length ?? 0} tranches`} />
      <Stat label="Next court date" value={tl.filter(t => t.date > "2026-10-22").sort((a, b) => a.date.localeCompare(b.date))[0]?.date ?? "—"} tone="amber" />
      <Stat label="Facts in ledger" value={fmtInt(s.facts.length)} sub={`${s.facts.filter(f => statusKey(f.status) === "VERIFIED").length} verified`} />
      <Stat label="Corrected" value={fmtInt(s.facts.filter(f => statusKey(f.status) === "CORRECTED").length)} tone="amber" sub="after primary re-read" />
      <Stat label="Timeline events" value={fmtInt(tl.length)} />
    </div>
    <div className="grid grid-cols-[minmax(0,1fr)_380px] gap-3 p-3">
      <div className="flex flex-col gap-3">
        <Card title="Capital structure waterfall" right="Face value, priority order" pad={false}><Waterfall rows={cap ?? []} /></Card>
        {MARK_KW[s.key] && <Card title="BDC mark history" right="Par-weighted, by lender"><MarkChart series={marks ?? {}} /></Card>}
        <Card title="Claims ledger" pad={false}>
          <DataTable rows={s.facts} maxHeight={360} cols={[
            { key: "id", label: "ID", width: 56, sort: r => r.claim_id, render: r => <span className="num text-mute">{r.claim_id}</span> },
            { key: "c", label: "Claim", sort: r => r.claim, text: r => r.claim + r.fix, render: r => <div className="py-1"><div className="text-ink">{r.claim}</div>{r.fix && <div className="text-[11px] text-amber/90">{r.fix}</div>}</div> },
            { key: "s", label: "Status", sort: r => r.status, render: r => <VBadge status={r.status} /> },
            { key: "u", label: "Source", align: "right", render: r => <SourceLink s={{ title: r.claim, url: r.primary_url, status: r.status, checked: r.checked, detail: r.fix || undefined }} /> },
          ]} dense={false} />
        </Card>
      </div>
      <div className="flex flex-col gap-3">
        <Card title="Case timeline"><Timeline items={tl} /></Card>
        <Card title="Primary documents">
          <div className="flex flex-col gap-1.5">{[...new Map(s.facts.map(f => [f.primary_url, f])).values()].map(f => <button key={f.primary_url} onClick={() => open({ title: f.claim, url: f.primary_url, status: f.status, checked: f.checked, detail: f.fix })} className="flex items-center justify-between gap-2 rounded-[3px] border border-line px-2 py-1.5 text-left hover:border-line2 hover:bg-line/40"><span className="truncate font-mono text-[10.5px] text-info">{host(f.primary_url)}{new URL(f.primary_url).pathname.split("/").pop()?.slice(0, 32)}</span><VBadge status={f.status} compact /></button>)}</div>
        </Card>
      </div>
    </div>
  </div>
}

// ---------------- Graph ----------------
function GraphView({ q }: { q: string }) {
  const { data: g0 } = useApi<{ nodes: GNode[]; edges: GEdge[] }>("/api/graph"); const [sel, setSel] = useState<GNode | null>(null)
  const { data: e2 } = useApi<Edge[]>("/api/edges")
  const data = useMemo(() => { if (!g0) return null
    const nodes = new Map(g0.nodes.map(n => [n.id, n])); const edges = [...g0.edges]
    for (const e of (e2 ?? []).filter(e => statusKey(e.status) !== "FALSE_POSITIVE")) {
      const s = `C:${e.src.toUpperCase()}`, t = `R:${e.type}:${e.dst.toUpperCase()}`
      if (!nodes.has(s)) nodes.set(s, { id: s, label: e.src, kind: "company", url: e.source_url, status: e.status })
      if (!nodes.has(t)) nodes.set(t, { id: t, label: e.dst, kind: e.type, url: e.source_url, status: e.status })
      edges.push({ s, t, label: e.type })
    }
    return { nodes: [...nodes.values()], edges } }, [g0, e2])
  const open = useSource()
  const counts = useMemo(() => { const c: Record<string, number> = {}; data?.nodes.forEach(n => c[n.kind] = (c[n.kind] ?? 0) + 1); return c }, [data])
  useEffect(() => { if (q && data) setSel(data.nodes.find(n => n.label.toLowerCase().includes(q.toLowerCase())) ?? null) }, [q, data])
  return <div><PageHead kicker="Network" title="Relationship graph" sub="Issuers, debt tranches, 13F holders and owners connected by verified filings. Force-directed layout; node size scales with degree. Click a node to isolate its neighbourhood." />
    <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-3 p-3">
      <Card pad={false} title="Graph" right={<span className="flex gap-3 whitespace-nowrap">{Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 7).map(([k, v]) => <span key={k} className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: GRAPH_COLORS[k] ?? "#7d8794" }} />{k.replace(/_/g, " ")} <span className="num">{v}</span></span>)}</span>}>
        {data && <Graph nodes={data.nodes} edges={data.edges} onSelect={setSel} height={700} />}
      </Card>
      <Card title="Selection">{sel ? <div className="flex flex-col gap-3"><div><Tag tone="amber">{sel.kind}</Tag><div className="mt-2 text-[14px] text-ink">{sel.label}</div></div>
        {sel.status && <VBadge status={sel.status} />}
        {sel.url ? <Button variant="outline" onClick={() => open({ title: sel.label, url: sel.url, status: sel.status })}>Open source drawer</Button> : <div className="text-[12px] text-dim">Structural node (no single source document).</div>}
        <div className="text-[11.5px] text-mute">Neighbours: {data?.edges.filter(e => e.s === sel.id || e.t === sel.id).length ?? 0}</div></div>
        : <div className="text-[12px] text-dim">Select a node to see its filing and verification status.</div>}</Card>
    </div></div>
}

// ---------------- Edges ----------------
function Edges() {
  const { data } = useApi<Edge[]>("/api/edges")
  const cols: Col<Edge>[] = [
    { key: "t", label: "Type", sort: r => r.type, text: r => r.type, render: r => <Tag tone="info">{r.type.replace(/_/g, " ")}</Tag> },
    { key: "s", label: "Company", sort: r => r.src, text: r => r.src, render: r => <span className="block max-w-[260px] truncate text-ink">{r.src}</span> },
    { key: "d", label: "Linked record", sort: r => r.dst, text: r => r.dst, render: r => <span className="block max-w-[220px] truncate text-mute">{r.dst}</span> },
    { key: "x", label: "Detail", text: r => r.detail, render: r => <span className="block max-w-[420px] truncate text-[11.5px] text-mute" title={r.detail}>{r.detail}</span> },
    { key: "m", label: "Match", sort: r => r.match, render: r => <span className="font-mono text-[10.5px] text-dim">{r.match}</span> },
    { key: "v", label: "Status", sort: r => r.status, render: r => <VBadge status={r.status} /> },
    { key: "u", label: "Source", align: "right", render: r => <SourceLink s={{ title: `${r.src} → ${r.dst}`, url: r.source_url, status: r.status, detail: r.detail, method: `match: ${r.match}` }} /> },
  ]
  return <div><PageHead kicker="Joins" title="Cross-dataset edges" sub="Links between distressed borrowers and federal contracts, EPA enforcement, sanctions lists, pension filings and UK PSC registers. Top 20 re-checked against the primary record." />
    <div className="p-3"><Card pad={false}><DataTable rows={data ?? []} cols={cols} initialSort={{ key: "t", dir: 1 }} maxHeight={720} /></Card></div></div>
}

// ---------------- Verify ----------------
function Verify() {
  const { data } = useApi<Ver[]>("/api/verification"); const [st, setSt] = useState("ALL")
  const rows = (data ?? []).filter(r => st === "ALL" || statusKey(r.status) === st)
  const cols: Col<Ver>[] = [
    { key: "id", label: "ID", width: 60, sort: r => r.claim_id, text: r => r.claim_id, render: r => <span className="num text-mute">{r.claim_id}</span> },
    { key: "a", label: "Artifact", sort: r => r.artifact, text: r => r.artifact, render: r => <Tag>{r.artifact}</Tag> },
    { key: "c", label: "Claim", sort: r => r.claim, text: r => `${r.claim} ${r.fix}`, render: r => <div className="py-1"><div className="text-ink">{r.claim}</div>{r.fix && <div className="text-[11px] text-amber/90">{r.fix}</div>}</div> },
    { key: "s", label: "Status", sort: r => r.status, render: r => <VBadge status={r.status} /> },
    { key: "d", label: "Checked", sort: r => r.checked, render: r => <span className="num text-mute">{r.checked}</span> },
    { key: "u", label: "Primary source", align: "right", render: r => <SourceLink s={{ title: r.claim, url: r.primary_url, status: r.status, checked: r.checked, detail: r.fix || undefined, method: r.method }} /> },
  ]
  return <div><PageHead kicker="Audit" title="Verification ledger" sub="Every published claim, re-fetched from its primary document and token-matched. Corrections are kept, not overwritten." right={<div className="flex gap-1">{["ALL", "VERIFIED", "CORRECTED", "UNVERIFIABLE", "FALSE_POSITIVE"].map(k => <Button key={k} variant={st === k ? "outline" : "ghost"} onClick={() => setSt(k)} className="text-[11px]">{k === "ALL" ? "All" : k.replace("_", " ").toLowerCase()}</Button>)}</div>} />
    <div className="p-3"><Card pad={false}><DataTable rows={rows} cols={cols} dense={false} maxHeight={740} /></Card></div></div>
}

// ---------------- Hit log ----------------
function HitLog() {
  const { data } = useApi<{ count: number; chain_ok: boolean; entries: Hit[] }>("/api/hitlog")
  const cols: Col<Hit>[] = [
    { key: "n", label: "#", sort: r => r.seq, render: r => <span className="num text-mute">{r.seq}</span> },
    { key: "t", label: "Logged (UTC)", sort: r => r.ts_utc, render: r => <span className="num text-mute">{r.ts_utc.slice(0, 16).replace("T", " ")}</span> },
    { key: "e", label: "Company", sort: r => r.entity, text: r => r.entity, render: r => <span className="block max-w-[320px] truncate text-ink">{r.entity}</span> },
    { key: "k", label: "Signal", sort: r => r.kind, text: r => r.kind, render: r => <Tag tone="violet">{r.kind.replace("signal:", "")}</Tag> },
    { key: "p", label: "Prediction", text: r => r.prediction, render: r => <span className="text-mute">{r.prediction}</span> },
    { key: "h", label: "Hash", render: r => <span className="font-mono text-[10.5px] text-dim">{r.hash.slice(0, 12)}…</span> },
    { key: "u", label: "Source", align: "right", render: r => <SourceLink s={{ title: `${r.entity}: ${r.kind}`, url: r.source_url, status: "VERIFIED", detail: `Prediction: ${r.prediction}. Entry #${r.seq}, sha256 ${r.hash}` }} /> },
  ]
  return <div><PageHead kicker="Track record" title="Signal hit log" sub="Append-only, sha256-chained record of every signal at the time it fired, so hit rates cannot be back-fitted." right={<Tag tone={data?.chain_ok ? "up" : "down"}>{data?.chain_ok ? "chain intact" : "chain broken"} · {fmtInt(data?.count)} entries</Tag>} />
    <div className="p-3"><Card pad={false}><DataTable rows={data?.entries ?? []} cols={cols} initialSort={{ key: "n", dir: -1 }} maxHeight={740} /></Card></div></div>
}

// ---------------- Research ----------------
function Research() {
  const docs = [
    { href: "/research/Where_the_next_dislocation_is.pdf", kicker: "Systemic radar · 23 Oct 2026", title: "Where the next dislocation is", desc: "Bank CRE concentration across all FDIC banks, non-traded BDC redemption queues, the CRE maturity wall, insurer exposure and fund-overlap cascades, ranked." },
    { href: "/research/Control_Bottleneck.pdf", kicker: "Control analysis · 22 Oct 2026", title: "Control bottleneck: who decides, and what a seat costs", desc: "Hughes voting math and blocking costs, eight paths to control, five capital playbooks; Fresno CMBS, Loparex, BayWa, Branicks; CMBS directing holders." },
    { href: "/research/Hughes_Satellite_Note.pdf", kicker: "Situation note · 22 Oct 2026", title: "Hughes Satellite Systems (Case 26-90739): the fight is over who owns the litigation", desc: "Capital structure and recovery scenarios, holder map, 1 Dec exclusivity hearing, plan-fight dynamics, catalysts, risks and a line-by-line verification appendix." },
    { href: "/research/TRIAGE_Master_Report.pdf", kicker: "Desk report · 22 Oct 2026", title: "TRIAGE master report: private-credit distress, court calendar and the verification ledger", desc: "BDC marks, top-15 capital structures, claims calendar, cross-dataset edges and the signal track record." },
  ]
  return <div><PageHead kicker="Publications" title="Research" sub="Long-form notes built on the same verified dataset as the terminal." />
    <div className="grid grid-cols-2 gap-3 p-3">{docs.map(d => <a key={d.href} href={d.href} target="_blank" className="group rounded-[3px] border border-line bg-panel p-5 hover:border-amber/50">
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-amber">{d.kicker}</div>
      <div className="mt-2 text-[17px] font-semibold leading-snug text-ink group-hover:underline">{d.title}</div>
      <p className="mt-2 text-[12.5px] leading-relaxed text-mute">{d.desc}</p>
      <div className="mt-4 flex items-center gap-1 text-[11.5px] text-info">Open PDF <ExternalLink size={11} /></div></a>)}</div></div>
}
