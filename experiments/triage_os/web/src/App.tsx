import { useEffect, useMemo, useState } from "react"
import { Activity, ChevronRight, Command as Cmd, FileText, Gavel, LayoutDashboard, Network, ScrollText, ShieldCheck, TrendingDown, Waypoints, ExternalLink } from "lucide-react"
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
  { r: "overview", label: "Overview", icon: LayoutDashboard },
  { r: "situations", label: "Situations", icon: Gavel },
  { r: "marks", label: "Marks monitor", icon: TrendingDown },
  { r: "graph", label: "Relationship graph", icon: Waypoints },
  { r: "edges", label: "Cross-dataset edges", icon: Network },
  { r: "verify", label: "Verification ledger", icon: ShieldCheck },
  { r: "hitlog", label: "Signal hit log", icon: ScrollText },
  { r: "research", label: "Research", icon: FileText },
]
const MARK_KW: Record<string, string> = { medallia: "Medallia", omnis: "Omnis", truefood: "True Food" }
const SIT_META: Record<string, { court: string; stage: string }> = { hughes: { court: "Bankr. S.D. Tex.", stage: "Ch. 11 · exclusivity contested" } }

function useRoute(): [string, (r: string) => void] {
  const get = () => decodeURIComponent(location.hash.replace(/^#\/?/, "")) || "overview"
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
        <a href="#/overview"><Wordmark /></a>
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
          {top === "overview" && <Overview sits={sits} stats={stats} />}
          {top === "situations" && <Situations sits={sits} />}
          {top === "situation" && sits && <SituationView s={sits.find(s => s.key === base.split("/")[1]) ?? sits[0]} />}
          {top === "marks" && <Marks />}
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
