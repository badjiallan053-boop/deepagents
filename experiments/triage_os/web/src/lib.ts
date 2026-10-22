import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { useEffect, useState } from "react"
export const cn = (...a: ClassValue[]) => twMerge(clsx(a))

const cache = new Map<string, unknown>()
export function useApi<T>(path: string | null): { data: T | null; err: string | null } {
  const [data, setData] = useState<T | null>(path ? (cache.get(path) as T) ?? null : null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    if (!path) return
    if (cache.has(path)) { setData(cache.get(path) as T); return }
    let live = true
    fetch(path).then(r => r.ok ? r.json() : Promise.reject(r.statusText)).then(j => { cache.set(path, j); if (live) setData(j) }).catch(e => live && setErr(String(e)))
    return () => { live = false }
  }, [path])
  return { data, err }
}

// number formats: $m, bp, x, pts
export const fmtM = (v: number | null | undefined, d = 1) => v == null || isNaN(v) ? "—" : `$${v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}m`
export const fmtBn = (v: number | null | undefined, d = 2) => v == null || isNaN(v) ? "—" : `$${v.toFixed(d)}bn`
export const fmtPx = (v: number | null | undefined, d = 1) => v == null || isNaN(v) ? "—" : v.toFixed(d)
export const fmtChg = (v: number | null | undefined) => v == null || isNaN(v) ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)}`
export const fmtBp = (v: number | null | undefined) => v == null || isNaN(v) ? "—" : `${Math.round(v).toLocaleString()} bp`
export const fmtX = (v: number | null | undefined) => v == null || isNaN(v) ? "—" : `${v.toFixed(1)}x`
export const fmtPct = (v: number | null | undefined, d = 1) => v == null || isNaN(v) ? "—" : `${(v * 100).toFixed(d)}%`
export const fmtInt = (v: number | null | undefined) => v == null || isNaN(v) ? "—" : v.toLocaleString("en-US")
export const host = (u?: string | null) => { try { return u ? new URL(u).hostname.replace(/^www\./, "") : "" } catch { return "" } }

export type Source = { title: string; url?: string | null; status?: string | null; checked?: string | null; detail?: string | null; method?: string | null }
