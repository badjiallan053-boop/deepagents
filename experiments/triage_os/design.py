"""TRIAGE print/web design system: one stylesheet + SVG chart helpers shared by the
research note, the master report and the landing page. No third-party code."""
import html, subprocess, os

WORDMARK = ('<span class="wm"><svg width="18" height="18" viewBox="0 0 32 32"><rect width="32" height="32" rx="5" fill="#f5a524"/>'
            '<path d="M8 9h16v3h-6.5v12h-3V12H8z" fill="#0b0f14"/></svg><b>TRIAGE</b></span>')

PRINT_CSS = r"""
@page { size: Letter; margin: 18mm 15mm 16mm 15mm;
  @top-left { content: "TRIAGE  |  Special Situations Research"; font: 600 7pt 'Inter'; letter-spacing: .14em; color: #8a929c; }
  @top-right { content: string(doctitle); font: 500 7pt 'Inter'; color: #8a929c; }
  @bottom-left { content: "Not investment advice. See disclaimer on the final page."; font: 400 6.5pt 'Inter'; color: #8a929c; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 500 7pt 'JetBrains Mono'; color: #8a929c; } }
@page :first { @top-left { content: none } @top-right { content: none } }
:root { --ink:#0d1218; --mute:#5b6570; --dim:#8a929c; --line:#d9dde2; --amber:#c97d06; --amberbg:#fff6e5; --navy:#0b0f14; --up:#1d8a52; --down:#c53340; --info:#1f6fd1; --violet:#6d4fd8; }
* { box-sizing: border-box; }
html { font-family: 'Inter', 'IBM Plex Sans', Arial, sans-serif; font-size: 9pt; color: var(--ink); line-height: 1.45; font-feature-settings: "tnum" 1; }
body { margin: 0; }
h1,h2,h3 { font-family: 'Inter Tight','Inter',sans-serif; letter-spacing: -.01em; margin: 0; }
.doctitle { string-set: doctitle content(); }
h2 { font-size: 13pt; margin: 14pt 0 5pt; padding-top: 6pt; border-top: 2px solid var(--navy); }
h2 .n { color: var(--amber); font-family: 'JetBrains Mono', monospace; font-size: 9pt; margin-right: 6pt; vertical-align: 1pt; }
h3 { font-size: 9.5pt; margin: 9pt 0 3pt; text-transform: uppercase; letter-spacing: .08em; color: var(--mute); }
p { margin: 0 0 5pt; text-align: left; }
.wm { display: inline-flex; align-items: center; gap: 6px; } .wm b { font: 700 11pt 'JetBrains Mono', monospace; letter-spacing: .32em; }
.cover { background: var(--navy); color: #e8ecf0; margin: 0 0 4pt; padding: 9mm 10mm 7mm; border-radius: 2px; } .cover .wm b { color: #fff; }
.cover .kick { color: #f5a524; font: 600 7.5pt 'Inter'; letter-spacing: .16em; text-transform: uppercase; margin-top: 7mm; }
.cover h1 { font-size: 22pt; line-height: 1.12; margin: 4pt 0 6pt; color: #fff; max-width: 165mm; }
.cover .sub { color: #aab3bd; font-size: 10pt; max-width: 160mm; }
.cover .meta { display: flex; gap: 18pt; margin-top: 10pt; padding-top: 8pt; border-top: 1px solid #26303b; font-size: 7.5pt; color: #8f99a4; }
.cover .meta b { display: block; color: #e8ecf0; font: 600 8.5pt 'JetBrains Mono', monospace; margin-top: 1pt; }
.view { border-left: 3px solid var(--amber); background: var(--amberbg); padding: 7pt 9pt; margin: 9pt 0; }
.view .lbl { font: 700 7pt 'Inter'; letter-spacing: .14em; color: var(--amber); text-transform: uppercase; }
.view p { font-size: 10pt; margin: 2pt 0 0; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12pt; } .cols3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10pt; }
.kpis { display: grid; grid-template-columns: repeat(5, 1fr); border: 1px solid var(--line); margin: 8pt 0; }
.kpi { padding: 5pt 7pt; border-right: 1px solid var(--line); } .kpi:last-child { border-right: 0; }
.kpi .l { font: 600 6.5pt 'Inter'; letter-spacing: .1em; text-transform: uppercase; color: var(--dim); }
.kpi .v { font: 600 13pt 'JetBrains Mono', monospace; margin-top: 2pt; } .kpi .s { font-size: 7pt; color: var(--mute); }
table { width: 100%; border-collapse: collapse; margin: 4pt 0 8pt; font-size: 8pt; page-break-inside: auto; }
thead th { font: 600 6.8pt 'Inter'; text-transform: uppercase; letter-spacing: .07em; color: var(--mute); text-align: left; border-bottom: 1.2px solid var(--navy); padding: 3pt 4pt; }
td { padding: 3pt 4pt; border-bottom: .5px solid var(--line); vertical-align: top; } tr { page-break-inside: avoid; }
td.r, th.r { text-align: right; } .num, td.r { font-family: 'JetBrains Mono', monospace; font-size: 7.6pt; }
tr.tot td { font-weight: 700; border-top: 1px solid var(--navy); border-bottom: 0; }
.fn { font-size: 6.8pt; color: var(--mute); } sup.f { font: 600 6pt 'JetBrains Mono'; color: var(--info); }
.badge { display: inline-block; font: 700 6pt 'Inter'; letter-spacing: .08em; padding: 1pt 3pt; border-radius: 2px; text-transform: uppercase; border: .6px solid; white-space: nowrap; }
.b-VERIFIED { color: var(--up); border-color: var(--up); } .b-CORRECTED { color: var(--amber); border-color: var(--amber); }
.b-ALLEGATION { color: var(--violet); border-color: var(--violet); } .b-ASSUMPTION { color: var(--info); border-color: var(--info); } .b-UNVERIFIABLE { color: var(--dim); border-color: var(--dim); }
.chart { margin: 4pt 0 2pt; page-break-inside: avoid; } h2, h3, .cap { page-break-after: avoid; } .chart svg { width: 100%; height: auto; display: block; }
.cap { font: 600 7pt 'Inter'; color: var(--mute); text-transform: uppercase; letter-spacing: .08em; margin-top: 6pt; }
.src { font-size: 6.6pt; color: var(--dim); margin-bottom: 6pt; }
.box { border: 1px solid var(--line); padding: 6pt 8pt; margin: 6pt 0; } .box h3 { margin-top: 0; }
ul { margin: 2pt 0 6pt; padding-left: 12pt; } li { margin: 1.5pt 0; }
.pb { page-break-before: always; } .avoid { page-break-inside: avoid; }
a { color: var(--info); text-decoration: none; word-break: break-all; }
.disc { font-size: 6.8pt; color: var(--mute); line-height: 1.4; } .disc h3 { color: var(--ink); }
.tl { position: relative; margin: 4pt 0 6pt 4pt; border-left: 1.2px solid var(--line); }
.tl .e { position: relative; padding: 0 0 4.5pt 10pt; } .tl .e:before { content: ""; position: absolute; left: -4px; top: 3pt; width: 7px; height: 7px; border-radius: 50%; background: var(--navy); }
.tl .e.f:before { background: #fff; border: 1.5px solid var(--amber); }
.tl .d { font: 600 7.5pt 'JetBrains Mono', monospace; color: var(--mute); } .tl .e.f .d { color: var(--amber); }
"""

def esc(s): return html.escape(str(s), quote=True)

def badge(status): 
    k = str(status).split()[0].upper().rstrip(";")
    return f'<span class="badge b-{esc(k)}">{esc(k.replace("_", " ").title())}</span>'

def render_pdf(html_path, pdf_path):
    subprocess.run(["google-chrome", "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=5000", f"--print-to-pdf={pdf_path}", f"file://{os.path.abspath(html_path)}"],
                   check=True, capture_output=True, timeout=240)
    out = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True).stdout
    return int([l for l in out.splitlines() if l.startswith("Pages:")][0].split()[-1])

# ---------- SVG chart helpers (vector, print-safe) ----------
FONT = "font-family='Inter, Arial' "
def hbars(rows, width=520, bar_h=13, gap=5, label_w=190, value_fmt=lambda v: f"${v:,.0f}m", colors=None, max_v=None):
    """rows: [(label, value, color_or_None, note)]"""
    max_v = max_v or max(r[1] for r in rows) or 1
    h = len(rows) * (bar_h + gap) + 4; plot = width - label_w - 70; out = []
    for i, r in enumerate(rows):
        lab, v, col = r[0], r[1], (r[2] if len(r) > 2 and r[2] else "#0b0f14")
        y = i * (bar_h + gap) + 2; w = max(1, v / max_v * plot)
        out.append(f"<text x='{label_w-6}' y='{y+bar_h-3}' text-anchor='end' {FONT}font-size='8' fill='#0d1218'>{esc(lab)}</text>"
                   f"<rect x='{label_w}' y='{y}' width='{w:.1f}' height='{bar_h}' fill='{col}'/>"
                   f"<text x='{label_w+w+4}' y='{y+bar_h-3}' font-family='JetBrains Mono' font-size='7.5' fill='#5b6570'>{esc(value_fmt(v))}</text>")
    return f"<svg viewBox='0 0 {width} {h}' xmlns='http://www.w3.org/2000/svg'>{''.join(out)}</svg>"

def stacked(segments, width=520, h=34, title=None):
    """segments: [(label, value, color)] -> one horizontal 100% bar with labels below."""
    tot = sum(s[1] for s in segments) or 1; x = 0; out = []
    for lab, v, col in segments:
        w = v / tot * width
        out.append(f"<rect x='{x:.1f}' y='0' width='{w:.1f}' height='16' fill='{col}'/>")
        if w > 40: out.append(f"<text x='{x+3:.1f}' y='11.5' font-family='JetBrains Mono' font-size='7.2' fill='#fff'>{v/tot*100:.1f}%</text>")
        out.append(f"<text x='{x+1:.1f}' y='27' {FONT}font-size='7' fill='#5b6570'>{esc(lab)}</text>" if w > 60 else "")
        x += w
    return f"<svg viewBox='0 0 {width} {h}' xmlns='http://www.w3.org/2000/svg'>{''.join(out)}</svg>"

def grouped_bars(cats, series, width=520, h=170, ymax=100, ref_lines=(), fmt=lambda v: f"{v:.0f}"):
    """cats: [str]; series: [(name, color, [values])]; ref_lines: [(value, label, color)]"""
    P = dict(l=30, r=8, t=10, b=34); pw = width - P["l"] - P["r"]; ph = h - P["t"] - P["b"]
    y = lambda v: P["t"] + ph * (1 - v / ymax); out = []
    for t in range(0, ymax + 1, 25):
        out.append(f"<line x1='{P['l']}' x2='{width-P['r']}' y1='{y(t):.1f}' y2='{y(t):.1f}' stroke='#e6e9ed'/><text x='{P['l']-4}' y='{y(t)+2.5:.1f}' text-anchor='end' font-family='JetBrains Mono' font-size='7' fill='#8a929c'>{t}</text>")
    gw = pw / len(cats); bw = min(18, gw * 0.8 / len(series))
    for i, c in enumerate(cats):
        x0 = P["l"] + i * gw + (gw - bw * len(series)) / 2
        for j, (nm, col, vals) in enumerate(series):
            v = vals[i]; bx = x0 + j * bw
            out.append(f"<rect x='{bx:.1f}' y='{y(v):.1f}' width='{bw-2:.1f}' height='{y(0)-y(v):.1f}' fill='{col}'/><text x='{bx+(bw-2)/2:.1f}' y='{y(v)-2:.1f}' text-anchor='middle' font-family='JetBrains Mono' font-size='6.5' fill='#0d1218'>{fmt(v)}</text>")
        out.append(f"<text x='{P['l']+i*gw+gw/2:.1f}' y='{h-P['b']+11}' text-anchor='middle' {FONT}font-size='7.3' fill='#0d1218'>{esc(c)}</text>")
    for v, lab, col in ref_lines:
        out.append(f"<line x1='{P['l']}' x2='{width-P['r']}' y1='{y(v):.1f}' y2='{y(v):.1f}' stroke='{col}' stroke-dasharray='4 3' stroke-width='1.1'/><text x='{width-P['r']-2}' y='{y(v)-3:.1f}' text-anchor='end' {FONT}font-size='7' font-weight='600' fill='{col}'>{esc(lab)}</text>")
    lx = P["l"]
    for nm, col, _ in series:
        out.append(f"<rect x='{lx}' y='{h-12}' width='8' height='8' fill='{col}'/><text x='{lx+11}' y='{h-5}' {FONT}font-size='7.3' fill='#0d1218'>{esc(nm)}</text>"); lx += 12 + len(nm) * 4.4 + 14
    return f"<svg viewBox='0 0 {width} {h}' xmlns='http://www.w3.org/2000/svg'>{''.join(out)}</svg>"

def timeline_svg(events, start, end, width=520, h=104):
    """events: [(iso_date, short_label, future_bool)] laid out on a date axis with alternating label rows."""
    import datetime as dt
    d = lambda s: dt.date.fromisoformat(s); s0, s1 = d(start), d(end); span = (s1 - s0).days or 1
    x = lambda s: 10 + (d(s) - s0).days / span * (width - 20); out = [f"<line x1='10' x2='{width-10}' y1='48' y2='48' stroke='#0b0f14' stroke-width='1.2'/>"]
    m = dt.date(s0.year, s0.month, 1)
    while m <= s1:
        if m >= s0: out.append(f"<line x1='{x(m.isoformat()):.1f}' x2='{x(m.isoformat()):.1f}' y1='45' y2='51' stroke='#8a929c'/><text x='{x(m.isoformat()):.1f}' y='60' text-anchor='middle' font-family='JetBrains Mono' font-size='6.5' fill='#8a929c'>{m.strftime('%b %y')}</text>")
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    for i, (ds, lab, fut) in enumerate(events):
        xx = x(ds); up = i % 2 == 0; ty = 10 + (i // 2 % 3) * 10 if up else 70 + (i // 2 % 3) * 10
        col = "#c97d06" if fut else "#0b0f14"
        out.append(f"<circle cx='{xx:.1f}' cy='48' r='3.2' fill='{'#fff' if fut else col}' stroke='{col}' stroke-width='1.4'/><line x1='{xx:.1f}' x2='{xx:.1f}' y1='{48-4 if up else 52}' y2='{ty+2 if up else ty-8}' stroke='{col}' stroke-width='.5'/>"
                   f"<text x='{xx:.1f}' y='{ty}' text-anchor='middle' {FONT}font-size='6.6' fill='{col}'>{esc(lab)}</text>")
    return f"<svg viewBox='0 0 {width} {h}' xmlns='http://www.w3.org/2000/svg'>{''.join(out)}</svg>"

def report_from_markdown(md_text, title, kicker, sub, meta, html_path, pdf_path):
    """Render a markdown report in the TRIAGE print design: cover block, numbered sections,
    status cells as badges, bare URLs shortened to host+path links."""
    import markdown, re
    body = markdown.markdown(md_text, extensions=["tables"])
    body = re.sub(r"^\s*<h1>.*?</h1>", "", body, count=1, flags=re.S)
    n = [0]
    def h2(m):
        n[0] += 1; t = re.sub(r"^\s*\d+\.\s*", "", m.group(1))
        return f'<h2><span class="n">{n[0]:02d}</span>{t}</h2>'
    body = re.sub(r"<h2>(.*?)</h2>", h2, body)
    def url(m):
        u = m.group(0); short = re.sub(r"^https?://(www\.)?", "", u); short = short if len(short) < 46 else short[:30] + "…" + short[-12:]
        return f'<a href="{u}">{html.escape(short)}</a>'
    body = re.sub(r'(?<![="\'>])https?://[^\s<|)"]+', url, body)
    body = re.sub(r"<td>(VERIFIED|CORRECTED|UNVERIFIABLE|FALSE_POSITIVE)([^<]*)</td>", lambda m: f"<td>{badge(m.group(1))}<span class='fn'>{m.group(2)}</span></td>", body)
    body = re.sub(r"<td>(-?[\d,]+\.?\d*%?|\$[\d,.]+[mbk]?)</td>", r"<td class='r'>\1</td>", body)
    metas = "".join(f"<div>{html.escape(k)}<b>{html.escape(str(v))}</b></div>" for k, v in meta)
    doc = (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{PRINT_CSS} table {{ font-size: 7pt; }} td {{ word-break: break-word; }} img {{ max-width: 100%; }}</style></head><body>"
           f"<div class='cover'>{WORDMARK}<div class='kick'>{html.escape(kicker)}</div><h1 class='doctitle'>{html.escape(title)}</h1><div class='sub'>{html.escape(sub)}</div><div class='meta'>{metas}</div></div>{body}"
           f"<div class='disc avoid'><h3>Disclaimer and publisher's exclusion</h3><p>Published by TRIAGE for general information. Impersonal; not investment advice, a recommendation, or an offer or solicitation to buy or sell any security. Not tailored to any reader; intended to fall within the publisher's exclusion of section 202(a)(11)(D) of the US Investment Advisers Act of 1940. Facts are drawn from public filings and registries linked in the text; statements by parties are allegations; scenario figures are labelled assumptions. Companies only; no personal data.</p></div></body></html>")
    open(html_path, "w").write(doc)
    return render_pdf(html_path, pdf_path)
