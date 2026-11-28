import { Command } from "cmdk"
import * as Dialog from "@radix-ui/react-dialog"
import { useEffect, useState } from "react"
import { Building2, FileText, Gavel, LayoutDashboard, Network, Search, ShieldCheck, TrendingDown, Landmark, ScrollText } from "lucide-react"
type Hit = { name: string; kind: string; reason: string }
export default function Palette({ open, setOpen, go, situations }: { open: boolean; setOpen: (b: boolean) => void; go: (route: string) => void; situations: { key: string; title: string }[] }) {
  const [q, setQ] = useState(""); const [hits, setHits] = useState<Hit[]>([])
  useEffect(() => { const h = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(!open) } }; window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h) }, [open])
  useEffect(() => { if (q.length < 2) { setHits([]); return } const t = setTimeout(() => fetch(`/api/search?q=${encodeURIComponent(q)}`).then(r => r.json()).then(setHits).catch(() => {}), 120); return () => clearTimeout(t) }, [q])
  const pick = (r: string) => { setOpen(false); setQ(""); go(r) }
  const Item = ({ v, onSelect, icon: I, children, hint }: any) => <Command.Item value={v} onSelect={onSelect} className="flex h-8 cursor-pointer items-center gap-2.5 rounded-[3px] px-2.5 text-[12.5px] text-ink/90"><I size={14} className="text-mute" /><span className="flex-1 truncate">{children}</span>{hint && <span className="font-mono text-[10px] uppercase text-dim">{hint}</span>}</Command.Item>
  return <Dialog.Root open={open} onOpenChange={setOpen}><Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
    <Dialog.Content className="fixed left-1/2 top-[14%] z-50 w-[620px] -translate-x-1/2 overflow-hidden rounded-[4px] border border-line2 bg-panel shadow-2xl">
      <Dialog.Title className="sr-only">Command palette</Dialog.Title><Dialog.Description className="sr-only">Search issuers, holders, situations and views</Dialog.Description>
      <Command shouldFilter={false} className="flex flex-col">
        <div className="flex items-center gap-2 border-b border-line px-3"><Search size={15} className="text-amber" /><Command.Input value={q} onValueChange={setQ} placeholder="Search issuers, holders, situations, views…" className="h-11 flex-1 bg-transparent text-[13px] text-ink placeholder:text-dim focus:outline-none" /><kbd className="rounded border border-line2 px-1.5 font-mono text-[10px] text-dim">ESC</kbd></div>
        <Command.List className="max-h-[380px] overflow-auto p-1.5">
          <Command.Empty className="p-4 text-center text-[12px] text-dim">No matches in watchlist, cap tables or 13F holders.</Command.Empty>
          {hits.length > 0 && <Command.Group heading="Entities" className="text-[10px] uppercase tracking-wider text-dim [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5">
            {hits.slice(0, 12).map((h, i) => <Item key={i} v={`h${i}`} icon={h.kind === "holder" ? Landmark : Building2} hint={h.kind} onSelect={() => pick(`graph?q=${encodeURIComponent(h.name)}`)}>{h.name} <span className="text-dim">· {h.reason}</span></Item>)}
          </Command.Group>}
          <Command.Group heading="Situations" className="text-[10px] uppercase tracking-wider text-dim [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5">
            {situations.filter(s => !q || s.title.toLowerCase().includes(q.toLowerCase())).slice(0, 8).map(s => <Item key={s.key} v={s.key} icon={Gavel} onSelect={() => pick(`situation/${s.key}`)}>{s.title}</Item>)}
          </Command.Group>
          <Command.Group heading="Views" className="text-[10px] uppercase tracking-wider text-dim [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5">
            {[["overview", "Overview", LayoutDashboard], ["marks", "Distressed marks monitor", TrendingDown], ["graph", "Relationship graph", Network], ["edges", "Cross-dataset edges", Network], ["verify", "Verification ledger", ShieldCheck], ["hitlog", "Signal hit log", ScrollText], ["research", "Research library", FileText]].filter(v => !q || (v[1] as string).toLowerCase().includes(q.toLowerCase())).map(([r, l, I]: any) => <Item key={r} v={`v-${r}`} icon={I} onSelect={() => pick(r)}>{l}</Item>)}
          </Command.Group>
        </Command.List>
      </Command>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
}
