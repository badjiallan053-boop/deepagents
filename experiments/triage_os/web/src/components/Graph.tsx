import { useEffect, useRef } from "react"
import cytoscape from "cytoscape"
export type GNode = { id: string; label: string; kind: string; url?: string | null; status?: string | null }
export type GEdge = { s: string; t: string; label?: string }
const COL: Record<string, string> = { company: "#f5a524", tranche: "#4ea1ff", holder: "#a78bfa", owner: "#2fbf71", gap: "#ef4d5a", gov_contractor: "#38bdf8", environmental_liability: "#84cc16", sanctions: "#ef4d5a", pension: "#f472b6", record: "#7d8794" }
export default function Graph({ nodes, edges, onSelect, height = 620 }: { nodes: GNode[]; edges: GEdge[]; onSelect?: (n: GNode) => void; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const ids = new Set(nodes.map(n => n.id))
    const cy = cytoscape({
      container: ref.current, wheelSensitivity: 0.25,
      elements: [...nodes.map(n => ({ data: { ...n, short: n.label.length > 34 ? n.label.slice(0, 32) + "…" : n.label } })), ...edges.filter(e => ids.has(e.s) && ids.has(e.t)).map((e, i) => ({ data: { id: `e${i}`, source: e.s, target: e.t, label: e.label ?? "" } }))],
      style: [
        { selector: "node", style: { "background-color": (e: cytoscape.NodeSingular) => COL[e.data("kind")] ?? "#7d8794", width: (e: cytoscape.NodeSingular) => 6 + Math.min(22, e.degree(false) * 2.2), height: (e: cytoscape.NodeSingular) => 6 + Math.min(22, e.degree(false) * 2.2), label: (e: cytoscape.NodeSingular) => (e.data("kind") === "company" || e.degree(false) >= 3 ? e.data("short") : ""), color: "#8b95a1", "font-size": 6, "font-family": "JetBrains Mono, Menlo, monospace", "text-valign": "bottom", "text-margin-y": 3, "border-width": 1, "border-color": "#07090c", "text-outline-color": "#07090c", "text-outline-width": 2 } as any },
        { selector: "node[kind='company']", style: { "font-size": 7, color: "#f5d9a6", "font-weight": "bold" } as any },
        { selector: "node:selected, node.hl", style: { label: "data(short)", "font-size": 8, color: "#ffffff" } as any },
        { selector: "edge", style: { width: 0.8, "line-color": "#2b3542", "curve-style": "haystack", opacity: 0.9 } as any },
        { selector: ".faded", style: { opacity: 0.12 } as any },
        { selector: "node:selected", style: { "border-color": "#ffffff", "border-width": 2 } as any },
      ],
      layout: { name: "cose", animate: false, nodeRepulsion: () => 6000, idealEdgeLength: () => 30, gravity: 0.6, numIter: 2000, componentSpacing: 30, nestingFactor: 1.2, padding: 20 } as any,
    })
    cy.on("tap", "node", ev => { const n = ev.target; cy.elements().addClass("faded"); n.closedNeighborhood().removeClass("faded"); cy.nodes().removeClass("hl"); n.closedNeighborhood().nodes().addClass("hl"); onSelect?.(n.data() as GNode) })
    cy.on("tap", ev => { if (ev.target === cy) cy.elements().removeClass("faded") })
    return () => cy.destroy()
  }, [nodes, edges])
  return <div ref={ref} style={{ height }} className="w-full bg-[radial-gradient(circle_at_center,#0f141b_0%,#07090c_75%)]" />
}
export const GRAPH_COLORS = COL
