import * as React from "react"
import * as Dialog from "@radix-ui/react-dialog"
import { ArrowDown, ArrowUp, ChevronsUpDown, ExternalLink, ShieldCheck, ShieldAlert, ShieldX, ShieldQuestion, X, Search } from "lucide-react"
import { cn, host, type Source } from "../lib"

export function Card({ className, title, right, children, pad = true }: { className?: string; title?: React.ReactNode; right?: React.ReactNode; children: React.ReactNode; pad?: boolean }) {
  return <section className={cn("rounded-[3px] border border-line bg-panel", className)}>
    {title && <header className="flex h-8 items-center justify-between border-b border-line px-3"><h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-mute">{title}</h3><div className="text-xxs text-dim">{right}</div></header>}
    <div className={cn(pad && "p-3")}>{children}</div>
  </section>
}

export function Wordmark({ size = 15 }: { size?: number }) {
  return <div className="flex items-center gap-2 select-none">
    <svg width={size + 5} height={size + 5} viewBox="0 0 32 32"><rect width="32" height="32" rx="5" fill="#f5a524" /><path d="M8 9h16v3h-6.5v12h-3V12H8z" fill="#07090c" /></svg>
    <span style={{ fontSize: size, letterSpacing: "0.32em" }} className="font-mono font-bold text-ink">TRIAGE</span>
  </div>
}

const STATUS: Record<string, { cls: string; icon: React.ElementType; label: string }> = {
  VERIFIED: { cls: "text-up border-up/40 bg-up/10", icon: ShieldCheck, label: "Verified" },
  CORRECTED: { cls: "text-amber border-amber/40 bg-amber/10", icon: ShieldAlert, label: "Corrected" },
  FALSE_POSITIVE: { cls: "text-down border-down/40 bg-down/10", icon: ShieldX, label: "False positive" },
  UNVERIFIABLE: { cls: "text-mute border-line2 bg-line/40", icon: ShieldQuestion, label: "Unverifiable" },
  ALLEGATION: { cls: "text-violet border-violet/40 bg-violet/10", icon: ShieldAlert, label: "Allegation" },
}
export function statusKey(s?: string | null) { const u = (s || "").toUpperCase(); return Object.keys(STATUS).find(k => u.startsWith(k)) || (u.includes("VERIFIED") ? "VERIFIED" : "UNVERIFIABLE") }
export function VBadge({ status, compact }: { status?: string | null; compact?: boolean }) {
  const k = statusKey(status); const s = STATUS[k]; const I = s.icon
  return <span title={status || ""} className={cn("inline-flex h-[18px] items-center gap-1 whitespace-nowrap rounded-[2px] border px-1.5 text-[10px] font-medium uppercase tracking-wide", s.cls)}><I size={11} />{!compact && s.label}</span>
}
export function Tag({ children, tone = "mute", className }: { children: React.ReactNode; tone?: "mute" | "amber" | "info" | "down" | "up" | "violet"; className?: string }) {
  const t = { mute: "text-mute border-line2", amber: "text-amber border-amber/40", info: "text-info border-info/40", down: "text-down border-down/40", up: "text-up border-up/40", violet: "text-violet border-violet/40" }[tone]
  return <span className={cn("inline-flex h-[18px] items-center rounded-[2px] border px-1.5 font-mono text-[10px] uppercase tracking-wide", t, className)}>{children}</span>
}
export function Button({ className, variant = "ghost", ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "ghost" | "solid" | "outline" }) {
  const v = { ghost: "hover:bg-line text-mute hover:text-ink", solid: "bg-amber text-bg hover:bg-amber/90 font-semibold", outline: "border border-line2 text-ink hover:bg-line" }[variant]
  return <button className={cn("inline-flex h-7 items-center gap-1.5 rounded-[3px] px-2.5 text-[12px] transition-colors", v, className)} {...p} />
}
export function Input(p: React.InputHTMLAttributes<HTMLInputElement>) {
  return <div className="relative"><Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-dim" /><input {...p} className={cn("h-7 w-56 rounded-[3px] border border-line2 bg-bg pl-7 pr-2 text-[12px] text-ink placeholder:text-dim focus:border-amber/60 focus:outline-none", p.className)} /></div>
}
export function Stat({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "up" | "down" | "amber" }) {
  return <div className="flex flex-col gap-1 border-r border-line px-4 py-3 last:border-r-0">
    <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-dim">{label}</div>
    <div className={cn("num text-[20px] font-semibold leading-none", tone === "up" && "text-up", tone === "down" && "text-down", tone === "amber" && "text-amber")}>{value}</div>
    {sub && <div className="text-[11px] text-mute">{sub}</div>}
  </div>
}

// ---------- Source drawer ----------
const SourceCtx = React.createContext<(s: Source) => void>(() => {})
export const useSource = () => React.useContext(SourceCtx)
export function SourceProvider({ children }: { children: React.ReactNode }) {
  const [src, setSrc] = React.useState<Source | null>(null)
  return <SourceCtx.Provider value={setSrc}>{children}
    <Dialog.Root open={!!src} onOpenChange={o => !o && setSrc(null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content className="fixed right-0 top-0 z-50 flex h-full w-[460px] flex-col border-l border-line2 bg-panel shadow-2xl">
          <div className="flex h-11 items-center justify-between border-b border-line px-4">
            <Dialog.Title className="text-[11px] font-semibold uppercase tracking-[0.1em] text-mute">Source & verification</Dialog.Title>
            <Dialog.Close className="text-mute hover:text-ink"><X size={16} /></Dialog.Close>
          </div>
          {src && <div className="flex flex-col gap-4 overflow-auto p-4">
            <div className="text-[14px] leading-snug text-ink">{src.title}</div>
            <div className="flex items-center gap-2"><VBadge status={src.status} />{src.checked && <span className="num text-[11px] text-mute">checked {src.checked}</span>}</div>
            {src.detail && <div className="rounded-[3px] border border-line bg-bg p-3 text-[12px] leading-relaxed text-ink/90">{src.detail}</div>}
            {src.method && <Field k="Method">{src.method}</Field>}
            <Field k="Primary source">
              {src.url ? <a href={src.url} target="_blank" rel="noreferrer" className="group flex items-start gap-1.5 break-all font-mono text-[11px] text-info hover:underline"><ExternalLink size={12} className="mt-0.5 shrink-0" />{src.url}</a> : <span className="text-down">No primary URL — not citable</span>}
            </Field>
            {src.url && <Field k="Publisher">{host(src.url)}</Field>}
            <Dialog.Description className="border-t border-line pt-3 text-[11px] leading-relaxed text-dim">Every figure in TRIAGE links to the filing or registry it was read from. Statuses come from the verification ledger (live re-fetch and token match against the primary document).</Dialog.Description>
          </div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </SourceCtx.Provider>
}
function Field({ k, children }: { k: string; children: React.ReactNode }) {
  return <div><div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-dim">{k}</div><div className="text-[12px] text-ink/90">{children}</div></div>
}
export function SourceLink({ s, children }: { s: Source; children?: React.ReactNode }) {
  const open = useSource()
  return <button onClick={e => { e.stopPropagation(); open(s) }} className="inline-flex items-center gap-1 whitespace-nowrap font-mono text-[10.5px] text-info hover:underline">{children ?? host(s.url) ?? "source"}<ExternalLink size={10} /></button>
}

// ---------- DataTable (sortable / filterable) ----------
export type Col<T> = { key: string; label: string; align?: "left" | "right" | "center"; width?: number | string; sort?: (r: T) => number | string | null; render: (r: T) => React.ReactNode; text?: (r: T) => string }
export function DataTable<T>({ rows, cols, initialSort, filterPlaceholder = "Filter", toolbar, maxHeight = 640, onRow, dense = true }: { rows: T[]; cols: Col<T>[]; initialSort?: { key: string; dir: 1 | -1 }; filterPlaceholder?: string; toolbar?: React.ReactNode; maxHeight?: number | string; onRow?: (r: T) => void; dense?: boolean }) {
  const [sort, setSort] = React.useState(initialSort)
  const [f, setF] = React.useState("")
  const view = React.useMemo(() => {
    const ql = f.toLowerCase().trim()
    let out = ql ? rows.filter(r => cols.some(c => (c.text ? c.text(r) : String(c.sort?.(r) ?? "")).toLowerCase().includes(ql))) : rows.slice()
    if (sort) { const c = cols.find(c => c.key === sort.key); if (c?.sort) out = out.sort((a, b) => { const x = c.sort!(a), y = c.sort!(b); if (x == null) return 1; if (y == null) return -1; return (x < y ? -1 : x > y ? 1 : 0) * sort.dir }) }
    return out
  }, [rows, cols, sort, f])
  return <div className="flex flex-col">
    <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
      <div className="flex items-center gap-2"><Input placeholder={filterPlaceholder} value={f} onChange={e => setF(e.target.value)} />{toolbar}</div>
      <div className="num text-[11px] text-dim">{view.length.toLocaleString()} / {rows.length.toLocaleString()} rows</div>
    </div>
    <div className="overflow-auto" style={{ maxHeight }}>
      <table className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 z-10 bg-panel2">
          <tr>{cols.map(c => <th key={c.key} style={{ width: c.width }} onClick={() => c.sort && setSort(s => s?.key === c.key ? { key: c.key, dir: (s.dir * -1) as 1 | -1 } : { key: c.key, dir: -1 })}
            className={cn("h-7 select-none border-b border-line2 px-2.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-dim", c.sort && "cursor-pointer hover:text-ink", c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left")}>
            <span className="inline-flex items-center gap-1">{c.label}{c.sort && (sort?.key === c.key ? (sort.dir === 1 ? <ArrowUp size={10} className="text-amber" /> : <ArrowDown size={10} className="text-amber" />) : <ChevronsUpDown size={10} className="opacity-40" />)}</span></th>)}</tr>
        </thead>
        <tbody>{view.slice(0, 600).map((r, i) => <tr key={i} onClick={() => onRow?.(r)} className={cn("border-b border-line/70 hover:bg-line/50", onRow && "cursor-pointer", i % 2 && "bg-white/[0.012]")}>
          {cols.map(c => <td key={c.key} className={cn("px-2.5 align-middle", dense ? "h-7" : "py-2", c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left")}>{c.render(r)}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
  </div>
}
