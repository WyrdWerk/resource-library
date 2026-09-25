#!/usr/bin/env python3
"""Build the CheapInfra #share-tech resource library repo.

Reads curated research notes from notes/*.md and regenerates:
  index.html   — the browsable site (search + category + week filters)
  data.json    — the full dataset (title, url, sharer, date, categories, brief, week, id)
  weeks/*.md   — per-week curated lists with briefs
  CHANGELOG.md — batch history derived from notes/

Hand-maintained (never overwritten by this script):
  notes/*.md, raw/*.md, README.md, AGENTS.md, scripts/build.py

Usage: python3 scripts/build.py   (run from anywhere; paths resolve to repo root)
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "notes"
WEEKS_DIR = ROOT / "weeks"

# TODO: update to the real deployed URL once Cloudflare Pages is configured.
SITE_URL = "https://resource-library.pages.dev"

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def norm_mon(s):
    return s.strip()[:3].title().replace("Sep", "Sep")


def parse_week(label):
    """'27 Aug–3 Sep 2026' -> dict with start/end dates and slug."""
    m = re.match(r"(\d{1,2})(?:\s+([A-Za-z]+))?\s*[–-]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
                 label.strip())
    if not m:
        raise ValueError(f"unparseable week label: {label!r}")
    sd, sm, ed, em, y = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    sm = norm_mon(sm) if sm else norm_mon(em)
    em = norm_mon(em)
    y = int(y)
    return {
        "label": label.strip(),
        "start": (y, MONTHS[sm], int(sd)),
        "end": (y, MONTHS[em], int(ed)),
        "slug": f"{y}-{MONTHS[sm]:02d}-{int(sd):02d}_to_{y}-{MONTHS[em]:02d}-{int(ed):02d}",
    }


def slugify(title, seen):
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "resource"
    s, n = base, 2
    while s in seen:
        s, n = f"{base}-{n}", n + 1
    seen.add(s)
    return s


def parse_notes(path):
    """Parse one notes file. Sections: '## Week: <label>' or '## Fold into week: <label>'."""
    resources = []
    current_week = None
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("## Fold into week:"):
            current_week = s[len("## Fold into week:"):].strip()
        elif s.startswith("## Week:"):
            current_week = s[len("## Week:"):].strip()
        elif s.startswith("## Providers"):
            # Special top-level section (not a week): curated #providers channel.
            current_week = "providers"
        elif line.startswith("### ") and current_week:
            title = re.sub(r"^\d+\.\s*", "", line[4:]).strip()
            entry = {"title": title, "week": current_week}
            i += 1
            field, brief_parts = None, []
            while i < len(lines) and not lines[i].startswith("#"):
                l = lines[i].rstrip()
                if l.startswith("- URL:"):
                    entry["url"] = l[len("- URL:"):].strip(); field = None
                elif l.startswith("- Posted by:"):
                    posted = l[len("- Posted by:"):].strip()
                    entry["sharer"] = posted.split(",")[0].strip()
                    m = re.search(r"(\d{1,2}\s+[A-Za-z]{3,4})\b", posted)
                    entry["date"] = m.group(1) if m else ""
                    field = None
                elif l.startswith("- Category:"):
                    entry["categories"] = [c.strip() for c in l[len("- Category:"):].split(",")]
                    field = None
                elif l.startswith("- Brief:"):
                    brief_parts = [l[len("- Brief:"):].strip()]; field = "brief"
                elif field == "brief" and l.strip():
                    brief_parts.append(l.strip())
                elif not l.strip():
                    field = None
                i += 1
            entry["brief"] = " ".join(brief_parts).strip()
            entry["_batch"] = path.name
            if entry.get("url"):
                resources.append(entry)
            continue
        i += 1
    return resources


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def xml_esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def make_og_image(total):
    """Generate og-image.png (1200x630 social card) with the current count."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), "#0a0c0b")
    d = ImageDraw.Draw(img)
    try:
        serif = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 104)
        sans = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
        kick = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except OSError:
        serif = sans = kick = ImageFont.load_default()
    d.rectangle([0, 0, W, 14], fill="#7ed7b6")
    d.text((80, 90), "CURATED FROM CHEAPINFRA  ·  #SHARE-TECH + #PROVIDERS", font=kick, fill="#9aa39b")
    d.text((76, 170), "Useful things", font=serif, fill="#ece9e0")
    d.text((76, 290), "worth opening.", font=serif, fill="#ece9e0")
    d.text((80, 450), f"{total} curated developer resources", font=sans, fill="#ece9e0")
    d.text((80, 500), "AI tools, dev tools, repos & articles", font=sans, fill="#9aa39b")
    img.save(ROOT / "og-image.png")


def _svg(w, h, inner):
    return f'<svg viewBox="0 0 {w} {h}" class="chart" role="img">\n{inner}\n</svg>'


def _ax(short):
    """Axis label for a period: end date only, e.g. '24 Sep'."""
    return re.split(r"[–-]", short)[-1].strip()


def vol_chart(rows):
    """Vertical bars: total resources per period, oldest -> newest."""
    W, H, pad_l, pad_b, pad_t = 560, 300, 34, 72, 28
    n = len(rows)
    cw = (W - pad_l - 14) / max(n, 1)
    bw = min(cw * 0.62, 64)
    vmax = max([r["total"] for r in rows] + [1])
    ph = (H - pad_t - pad_b) / vmax
    parts = [f'<line x1="{pad_l}" y1="{H - pad_b}" x2="{W - 10}" y2="{H - pad_b}" class="grid"/>']
    for i, r in enumerate(rows):
        x = pad_l + i * cw + (cw - bw) / 2
        bh = max(r["total"] * ph, 2)
        y = H - pad_b - bh
        cx = x + bw / 2
        ly = H - pad_b + 18
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="5" class="bar"/>')
        parts.append(f'<text x="{cx:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="val">{r["total"]}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="end" transform="rotate(-38 {cx:.1f} {ly:.1f})" class="ax">{esc(_ax(r["short"]))}</text>')
    return _svg(W, H, "\n".join(parts))


def stacked_chart(periods, cats):
    """Stacked vertical bars: category mix per period, oldest -> newest."""
    W, H, pad_l, pad_b, pad_t = 560, 320, 34, 72, 28
    n = len(periods)
    cw = (W - pad_l - 14) / max(n, 1)
    bw = min(cw * 0.62, 72)
    vmax = max([p["total"] for p in periods] + [1])
    ph = (H - pad_t - pad_b) / vmax
    parts = [f'<line x1="{pad_l}" y1="{H - pad_b}" x2="{W - 10}" y2="{H - pad_b}" class="grid"/>']
    for i, p in enumerate(periods):
        x = pad_l + i * cw + (cw - bw) / 2
        y = H - pad_b
        for c in cats:
            v = p["counts"].get(c, 0)
            if not v:
                continue
            sh = v * ph
            y -= sh
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{sh:.1f}" class="seg-{c}"><title>{esc(c)}: {v}</title></rect>')
        cx = x + bw / 2
        ly = H - pad_b + 18
        parts.append(f'<text x="{cx:.1f}" y="{H - pad_b - p["total"] * ph - 8:.1f}" text-anchor="middle" class="val">{p["total"]}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="end" transform="rotate(-38 {cx:.1f} {ly:.1f})" class="ax">{esc(_ax(p["short"]))}</text>')
    return _svg(W, H, "\n".join(parts))


def hbar_chart(items, suffix=""):
    """Horizontal bars. items: list of (label, value, css_class, extra_label)."""
    W, row_h, pad_l, pad_r, pad_t = 560, 34, 148, 52, 10
    H = pad_t + len(items) * row_h + 10
    vmax = max([v for _, v, _, _ in items] + [1])
    bw = (W - pad_l - pad_r) / vmax
    parts = []
    for i, (label, v, cls, extra) in enumerate(items):
        y = pad_t + i * row_h
        lab = label if len(label) <= 20 else label[:19] + "…"
        parts.append(f'<text x="{pad_l - 10}" y="{y + 20}" text-anchor="end" class="hbar-label">{esc(lab)}</text>')
        parts.append(f'<rect x="{pad_l}" y="{y + 6}" width="{max(v * bw, 3):.1f}" height="18" rx="5" class="{cls}"/>')
        parts.append(f'<text x="{pad_l + v * bw + 8:.1f}" y="{y + 20}" class="val">{v}{extra}</text>')
    return _svg(W, H, "\n".join(parts))


def main():
    all_res = []
    for f in sorted(NOTES_DIR.glob("*.md")):
        all_res.extend(parse_notes(f))

    weeks = {}
    for r in all_res:
        weeks.setdefault(r["week"], []).append(r)
    week_info = {label: parse_week(label) for label in weeks if label != "providers"}
    ordered = sorted([l for l in weeks if l != "providers"],
                     key=lambda l: week_info[l]["end"], reverse=True)
    if "providers" in weeks:
        # The providers section is a curated cross-channel collection, not a
        # week: it always leads, newest-first, with a stable "providers" slug.
        ordered.insert(0, "providers")
        week_info["providers"] = {"label": "Providers", "start": None,
                                  "end": None, "slug": "providers"}

    MON_NAME = {v: k for k, v in MONTHS.items()}
    _wk = [l for l in ordered if l != "providers"]
    _smin = min(week_info[l]["start"] for l in _wk)
    _smax = max(week_info[l]["end"] for l in _wk)
    range_str = f"{_smin[2]} {MON_NAME[_smin[1]]} – {_smax[2]} {MON_NAME[_smax[1]]} {_smax[0]}"

    seen = set()
    for r in all_res:
        r["id"] = slugify(r["title"], seen)

    total = len(all_res)
    cats = sorted({c for r in all_res for c in r["categories"]})
    cat_counts = {c: sum(1 for r in all_res if c in r["categories"]) for c in cats}

    (ROOT / "data.json").write_text(json.dumps(all_res, indent=2, ensure_ascii=False))

    # ---- weeks/*.md ----
    WEEKS_DIR.mkdir(exist_ok=True)
    for old in WEEKS_DIR.glob("*.md"):
        old.unlink()
    for label in ordered:
        info = week_info[label]
        res = weeks[label]
        if label == "providers":
            md = [f"# Inference providers — curated from CheapInfra #providers", "",
                  f"{len(res)} curated providers, with briefs.", ""]
        else:
            md = [f"# #share-tech resources — week of {label}", "",
                  f"{len(res)} curated resources, newest first.", ""]
        for r in res:
            md += [f"## {r['title']}",
                   f"- URL: {r['url']}",
                   f"- Shared by: {r['sharer']} ({r['date']})",
                   f"- Categories: {', '.join(r['categories'])}",
                   f"- Brief: {r['brief']}", ""]
        (WEEKS_DIR / f"{info['slug']}.md").write_text("\n".join(md))

    # ---- CHANGELOG.md ----
    batches = {}
    for r in all_res:
        batches.setdefault(r["_batch"], []).append(r)
    clog = ["# Changelog", "",
            "One entry per collection batch (a `notes/*.md` file).",
            "Counts are curated resources kept after filtering.", ""]
    for b in sorted(batches, reverse=True):
        rs = batches[b]
        wl = sorted({r["week"] for r in rs})
        clog.append(f"## {b}")
        clog.append(f"- {len(rs)} resources → {', '.join(wl)}")
        clog.append("")
    (ROOT / "CHANGELOG.md").write_text("\n".join(clog))

    # ---- index.html ----
    CAT_LABELS = {"ai-tool": "AI tools", "dev-tool": "Dev tools", "github": "GitHub repos",
                  "web-app": "Web apps", "article": "Articles", "providers": "Providers"}
    sections, nav = [], []
    for wi, label in enumerate(ordered):
        info = week_info[label]
        res = weeks[label]
        dlabel = info["label"]
        wnum = f"{wi + 1:02d}" if label != "providers" else "◆"
        latest = ' <span class="newdot">new</span>' if wi == 0 else ''
        nav.append(f'<a class="wnav" href="#{info["slug"]}">{esc(dlabel)}{latest}<span>{len(res)}</span></a>')
        cards = []
        for ci, r in enumerate(res):
            chips = "".join(
                f'<span class="chip c-{c}">{esc(CAT_LABELS.get(c, c))}</span>'
                for c in r["categories"])
            blob = esc((r["title"] + " " + r["brief"] + " " + r["sharer"]).lower())
            dom = urlsplit(r["url"]).netloc.replace("www.", "")
            cards.append(
                f'<article class="card" id="r-{r["id"]}" data-cats="{" ".join(r["categories"])}" data-search="{blob}">'
                f'<div class="card-main">'
                f'<div class="cardtop"><span class="cardnum">{ci + 1:02d}</span>'
                f'<h3><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a></h3></div>'
                f'<p>{esc(r["brief"])}</p>'
                f'<a class="dlink" href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(dom)} ↗</a>'
                f'</div>'
                f'<div class="card-side">'
                f'<div class="meta">{chips}</div>'
                f'<div class="side-row">Shared by <span class="who">{esc(r["sharer"])}</span></div>'
                f'<div class="side-row">{esc(r["date"])} · <a class="plink" href="#r-{r["id"]}" title="Permalink">⧉</a></div>'
                f'</div>'
                f'</article>')
        badge = ' <span class="latest">Latest</span>' if wi == 0 else ''
        heading = "Providers" if label == "providers" else f"Week of {esc(dlabel)}"
        wsub = "inference providers" if label == "providers" else "resources"
        sections.append(
            f'<section class="week" id="{info["slug"]}" data-week="{esc(dlabel)}">'
            f'<div class="weekhead"><span class="weeknum">{wnum}</span><h2>{heading}</h2>{badge}'
            f'<span class="wcount">{len(res)} {wsub}</span></div>'
            + "\n".join(cards) + '</section>')

    fchips = (f'<button class="fchip active" data-cat="all">All <b>{total}</b></button>' +
              "".join(f'<button class="fchip" data-cat="{c}">{CAT_LABELS.get(c, c)} <b>{cat_counts[c]}</b></button>'
                      for c in cats))
    wchips = "".join(f'<button class="fchip wfilter" data-week="{esc(week_info[l]["label"])}">{esc(week_info[l]["label"])}</button>' for l in ordered)
    catchips = "".join(f'<span class="catchip">{CAT_LABELS.get(c, c)} × {cat_counts[c]}</span>' for c in cats)

    # ---- analytics data ----
    from collections import Counter
    chrono = list(reversed(ordered))

    def short_label(label):
        return re.sub(r"\s+\d{4}$", "", label)

    arows = []
    for label in chrono:
        counts = {c: 0 for c in cats}
        for r in weeks[label]:
            for c in r["categories"]:
                counts[c] = counts.get(c, 0) + 1
        arows.append({"label": label, "short": short_label(label),
                      "total": len(weeks[label]), "counts": counts})
    frows = []
    for i in range(0, len(arows), 2):
        grp = arows[i:i + 2]
        counts = {c: sum(g["counts"].get(c, 0) for g in grp) for c in cats}
        if len(grp) == 2 and "–" in grp[0]["label"] and "–" in grp[1]["label"]:
            fl = grp[0]["label"].split("–")[0] + "–" + grp[1]["label"].split("–")[1]
        else:
            # Odd group, or the non-week "providers" section: join plainly.
            fl = " + ".join(g["label"] for g in grp)
        frows.append({"label": fl, "short": short_label(fl),
                      "total": sum(g["total"] for g in grp), "counts": counts})
    sharer_counts = Counter(r["sharer"] for r in all_res)
    top_sharers = sharer_counts.most_common(10)
    top_name, top_n = top_sharers[0]
    sp_counts = Counter(c for r in all_res if r["sharer"] == top_name for c in r["categories"])
    busiest = max(arows, key=lambda r: r["total"])
    top_cat = max(cats, key=lambda c: cat_counts[c])

    vol_svg = vol_chart(arows)
    trend_week_svg = stacked_chart(arows, cats)
    trend_fort_svg = stacked_chart(frows, cats)
    sharer_svg = hbar_chart([(s, n, "bar", "") for s, n in top_sharers])
    mix_svg = hbar_chart([(CAT_LABELS.get(c, c), cat_counts[c], f"seg-{c}", f" · {cat_counts[c] / total:.0%}")
                          for c in cats])
    legend = "".join(f'<span class="leg"><span class="seg-sw seg-{c}"></span>{CAT_LABELS.get(c, c)}</span>'
                     for c in cats)
    an_stats = (
        f'<div class="an-stat"><b>{total}</b><span>resources tracked</span></div>'
        f'<div class="an-stat"><b>{esc(busiest["short"])}</b><span>busiest week · {busiest["total"]} resources</span></div>'
        f'<div class="an-stat"><b>{esc(CAT_LABELS.get(top_cat, top_cat))}</b><span>top category · {cat_counts[top_cat]}</span></div>'
        f'<div class="an-stat"><b>{esc(top_name)}</b><span>top sharer · {top_n} shared</span></div>'
    )
    spotlight = (
        f'<p class="spot-name">{esc(top_name)} <span>· {top_n} resources shared</span></p>'
        + hbar_chart([(CAT_LABELS.get(c, c), sp_counts[c], f"seg-{c}", "") for c in cats if sp_counts[c]])
    )
    desc = (f"A curated, browsable archive of {total} developer resources shared in the "
            f"CheapInfra Discord's #share-tech and #providers channels, newest first.")
    from datetime import datetime
    today_str = datetime.now().strftime("%-d %B %Y")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resource Library — CheapInfra #share-tech + #providers</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="Resource Library — CheapInfra #share-tech + #providers">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:image" content="{SITE_URL}/og-image.png">
<link rel="alternate" type="application/rss+xml" title="Resource Library feed" href="feed.xml">
<script>try{{var t=localStorage.getItem('rl-theme');if(t!=='light'&&t!=='dark'){{t='dark';}}document.documentElement.dataset.theme=t;}}catch(e){{document.documentElement.dataset.theme='dark';}}</script>
<style>
:root {{
  color-scheme: dark;
  --paper: #0a0c0b; --card: #121514; --ink: #ece9e0; --muted: #9aa39b;
  --line: #232926; --accent: #7ed7b6; --accent-soft: rgba(126,215,182,.12); --warm: #d99a6c;
  --cat-ai-tool: #6ad5ba; --cat-ai-tool-bg: rgba(106,215,186,.14);
  --cat-dev-tool: #7ccf8a; --cat-dev-tool-bg: rgba(124,207,138,.13);
  --cat-github: #b3a1e8; --cat-github-bg: rgba(179,161,232,.14);
  --cat-web-app: #ef8fb8; --cat-web-app-bg: rgba(239,143,184,.13);
  --cat-article: #e3b341; --cat-article-bg: rgba(227,179,65,.14);
  --cat-providers: #6fb7e8; --cat-providers-bg: rgba(111,183,232,.14);
}}
[data-theme="light"] {{
  color-scheme: light;
  --paper: #f4f6f1; --card: #fbfcf8; --ink: #16231f; --muted: #52615c;
  --line: #dde3d9; --accent: #006a55; --accent-soft: #dcebe3; --warm: #9b482a;
  --cat-ai-tool: #0b6e4f; --cat-ai-tool-bg: #dcebe3;
  --cat-dev-tool: #2f7a3d; --cat-dev-tool-bg: #e2ecdc;
  --cat-github: #5b4a9e; --cat-github-bg: #e7e3f4;
  --cat-web-app: #a23168; --cat-web-app-bg: #f4dfea;
  --cat-article: #8a5a00; --cat-article-bg: #f3e9cd;
  --cat-providers: #1668a8; --cat-providers-bg: #dcebf7;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--paper); color: var(--ink);
  margin: 0; line-height: 1.6;
}}
.wrap {{ max-width: 920px; margin: 0 auto; padding: 0 22px 90px; }}
.hero {{ padding: 56px 0 6px; }}
.hero .kicker {{
  font-size: 12.5px; letter-spacing: 0.16em; text-transform: uppercase; font-weight: 600;
  color: var(--muted); margin-bottom: 14px;
}}
.hero-grid {{ display: grid; grid-template-columns: 1fr 260px; gap: 28px; align-items: start; }}
@media (max-width: 700px) {{ .hero-grid {{ grid-template-columns: 1fr; }} }}
.hero h1 {{
  font-family: Georgia, "Times New Roman", serif; font-weight: 600;
  font-size: clamp(34px, 5.4vw, 52px); line-height: 1.1; margin: 0 0 14px;
  letter-spacing: -0.01em;
}}
.hero p.lede {{ color: var(--muted); max-width: 60ch; margin: 0 0 6px; font-size: 16.5px; }}
.review {{
  border: 1px solid var(--line); border-radius: 12px; background: var(--card);
  padding: 16px 20px;
}}
.review .rlab {{
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em;
  color: var(--muted); font-weight: 700; display: block; margin-bottom: 10px;
}}
.ritem {{ margin-bottom: 12px; }}
.ritem:last-child {{ margin-bottom: 0; }}
.review .rval {{
  font-family: Georgia, "Times New Roman", serif; font-size: 23px; font-weight: 600;
  display: block; line-height: 1.2;
}}
.review .rval small {{ font-size: 13px; color: var(--muted); font-family: ui-sans-serif, system-ui, sans-serif; font-weight: 400; }}
.rsub {{ font-size: 12.5px; color: var(--muted); display: block; margin-top: 2px; }}
.catchips {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0 8px; }}
.catchip {{
  font-size: 12.5px; color: var(--muted); border: 1px solid var(--line);
  border-radius: 999px; padding: 3px 12px; background: var(--card);
}}
.latest {{
  font-size: 12px; font-weight: 700; background: var(--accent-soft); color: var(--accent);
  border-radius: 999px; padding: 3px 12px; text-transform: uppercase; letter-spacing: 0.06em;
}}
.newdot {{
  font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase;
  letter-spacing: 0.06em;
}}
.shortlist-h {{
  font-family: Georgia, "Times New Roman", serif; font-size: 30px; font-weight: 600;
  margin: 40px 0 4px; letter-spacing: -0.01em; scroll-margin-top: 230px;
}}
.shortlist-sub {{ color: var(--muted); font-size: 14.5px; margin: 0 0 8px; }}
.toolbar {{
  position: sticky; top: 0; z-index: 10;
  background: color-mix(in srgb, var(--paper) 94%, transparent);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  padding: 14px 0 12px; border-bottom: 1px solid var(--line);
  margin: 26px -22px 0; padding-left: 22px; padding-right: 22px;
}}
.searchlabel {{
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em;
  color: var(--muted); font-weight: 700; display: block; margin-bottom: 6px;
}}
#search {{
  flex: 1 1 auto; min-width: 0; padding: 11px 16px; font-size: 15px; border: 1px solid var(--line);
  border-radius: 10px; background: var(--card); color: var(--ink);
}}
#search:focus {{ outline: 2px solid var(--accent); border-color: transparent; }}
#search::placeholder {{ color: var(--muted); opacity: 0.8; }}
.searchrow {{ display: flex; gap: 10px; align-items: stretch; margin-bottom: 10px; }}
.clearbtn {{
  flex: 0 0 auto; white-space: nowrap; cursor: pointer;
  border: 1px solid var(--line); background: transparent; color: var(--muted);
  border-radius: 10px; padding: 0 18px; font: inherit; font-size: 13px; font-weight: 600;
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
  transition: border-color 0.15s ease, color 0.15s ease;
}}
.clearbtn:hover {{ border-color: var(--accent); color: var(--ink); }}
.clearbtn:active {{ transform: scale(0.97); }}
.frow {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
.frow + .frow {{ margin-top: 6px; }}
.flabel {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; margin-right: 6px; font-weight: 700; }}
.fchip {{
  border: 1px solid var(--line); background: var(--card); color: var(--ink);
  border-radius: 999px; padding: 5px 14px; cursor: pointer; font-size: 13px;
  transition: border-color 0.15s ease, background 0.15s ease;
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
}}
.fchip b {{ font-weight: 700; opacity: 0.55; }}
.fchip:hover {{ border-color: var(--accent); }}
.fchip.active {{ background: var(--accent); color: #0a0c0b; border-color: var(--accent); font-weight: 600; }}
[data-theme="light"] .fchip.active {{ color: #fff; }}
.wnavs {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 24px 0 8px; }}
.wnav {{
  text-decoration: none; color: var(--ink); font-size: 13px;
  border: 1px solid var(--line); border-radius: 10px; padding: 8px 12px;
  background: var(--card); display: flex; gap: 8px; align-items: baseline;
  -webkit-tap-highlight-color: transparent;
}}
.wnav span {{ color: var(--muted); font-size: 12px; }}
.wnav:hover {{ border-color: var(--accent); }}
.week {{ margin-top: 40px; scroll-margin-top: 230px; }}
.weekhead {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px; flex-wrap: wrap; }}
.weeknum {{
  font-family: Georgia, "Times New Roman", serif; font-size: 15px; color: var(--accent);
  font-weight: 600; letter-spacing: 0.04em;
}}
.weekhead h2 {{
  font-family: Georgia, "Times New Roman", serif; font-size: 25px; font-weight: 600; margin: 0;
  letter-spacing: -0.01em;
}}
.wcount {{ font-size: 13px; color: var(--muted); }}
.card {{
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 18px 22px; margin: 10px 0;
  display: grid; grid-template-columns: 1fr 172px; gap: 20px;
  transition: border-color 0.16s ease;
  scroll-margin-top: 230px;
}}
@media (max-width: 640px) {{
  .card {{ grid-template-columns: 1fr; gap: 12px; }}
  .card-side {{ border-top: 1px solid var(--line); padding-top: 10px; }}
}}
.card:hover {{ border-color: var(--accent); }}
.card:target {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.cardtop {{ display: flex; gap: 14px; align-items: baseline; }}
.cardnum {{
  font-family: Georgia, "Times New Roman", serif; font-size: 14px; color: var(--muted);
  font-weight: 600; min-width: 26px; text-align: right; flex-shrink: 0;
}}
.card h3 {{
  margin: 0 0 8px; font-family: Georgia, "Times New Roman", serif;
  font-size: 19px; font-weight: 600; letter-spacing: -0.005em; flex: 1;
}}
.card h3 a {{ text-decoration: none; color: inherit; }}
.card h3 a:hover {{ color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; }}
.card-main p {{ margin: 10px 0 12px; color: var(--ink); font-size: 15px; }}
.dlink {{
  display: inline-block; font-size: 13px; color: var(--accent); text-decoration: none;
  border: 1px solid var(--line); border-radius: 8px; padding: 4px 12px;
  margin: 2px 0 4px; word-break: break-all; -webkit-tap-highlight-color: transparent;
}}
.dlink:hover {{ border-color: var(--accent); }}
.card-side {{ font-size: 12.5px; color: var(--muted); }}
.card-side .meta {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }}
.side-row {{ margin-bottom: 4px; }}
.side-row .who {{ font-weight: 600; color: var(--ink); }}
.meta {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.chip {{
  font-size: 11.5px; font-weight: 600; border-radius: 999px; padding: 3px 11px;
  background: var(--line); color: var(--muted); white-space: nowrap;
}}
.plink {{ color: var(--muted); text-decoration: none; opacity: 0.45; transition: opacity 0.15s; }}
.card:hover .plink {{ opacity: 1; }}
.card.hidden, .week.hidden {{ display: none; }}
.empty {{ color: var(--muted); font-style: italic; text-align: center; margin: 48px 0; }}
footer {{
  margin-top: 72px; padding-top: 24px; border-top: 1px solid var(--line);
  font-size: 13px; color: var(--muted);
}}
footer .fsrc {{ font-weight: 600; color: var(--ink); }}
footer a {{ color: var(--accent); }}
.top {{
  position: fixed; right: 20px; bottom: 20px; width: 42px; height: 42px; border-radius: 50%;
  border: 1px solid var(--line); background: var(--card); color: var(--ink);
  cursor: pointer; font-size: 18px; display: none; align-items: center; justify-content: center;
}}
.top.show {{ display: flex; }}
/* ---- theme toggle ---- */
.topbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
.topbar .kicker {{ margin-bottom: 0; }}
.theme-toggle {{
  background: var(--card); border: 1px solid var(--line); border-radius: 50%;
  width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--ink); flex-shrink: 0; transition: border-color 0.15s ease;
}}
.theme-toggle:hover {{ border-color: var(--accent); }}
.theme-toggle svg {{ width: 18px; height: 18px; }}
.theme-toggle .icon-sun {{ display: block; }}
.theme-toggle .icon-moon {{ display: none; }}
[data-theme="light"] .theme-toggle .icon-sun {{ display: none; }}
[data-theme="light"] .theme-toggle .icon-moon {{ display: block; }}
/* ---- tabs ---- */
.tabs {{ display: flex; gap: 6px; margin: 26px 0 4px; }}
.tab {{
  border: 1px solid var(--line); background: var(--card); color: var(--muted);
  border-radius: 999px; padding: 8px 24px; font-size: 14px; cursor: pointer; font-weight: 600;
  transition: border-color 0.15s ease, background 0.15s ease;
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
}}
.tab:hover {{ border-color: var(--accent); color: var(--ink); }}
.tab.active {{ background: var(--accent); color: #0a0c0b; border-color: var(--accent); }}
[data-theme="light"] .tab.active {{ color: #fff; }}
.lib-hidden {{ display: none !important; }}
/* ---- category chips (theme-aware) ---- */
.chip.c-ai-tool {{ color: var(--cat-ai-tool); background: var(--cat-ai-tool-bg); }}
.chip.c-dev-tool {{ color: var(--cat-dev-tool); background: var(--cat-dev-tool-bg); }}
.chip.c-github {{ color: var(--cat-github); background: var(--cat-github-bg); }}
.chip.c-web-app {{ color: var(--cat-web-app); background: var(--cat-web-app-bg); }}
.chip.c-article {{ color: var(--cat-article); background: var(--cat-article-bg); }}
.chip.c-providers {{ color: var(--cat-providers); background: var(--cat-providers-bg); }}
/* ---- analytics ---- */
#analytics {{ margin-top: 8px; scroll-margin-top: 24px; }}
.an-h {{
  font-family: Georgia, "Times New Roman", serif; font-size: 26px; font-weight: 600;
  margin: 28px 0 4px;
}}
.an-sub {{ color: var(--muted); font-size: 14px; margin: 0 0 20px; }}
.an-stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
.an-stat {{
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 12px 18px; min-width: 140px;
}}
.an-stat b {{ display: block; font-size: 21px; font-weight: 600; font-family: Georgia, "Times New Roman", serif; letter-spacing: -0.01em; }}
.ritem {{ display: flex; flex-direction: column; gap: 2px; }}
.an-stat span {{ font-size: 12px; color: var(--muted); }}
.an-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
@media (max-width: 640px) {{ .an-grid {{ grid-template-columns: 1fr; }} }}
.an-card {{
  background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px;
}}
.an-card.wide {{ grid-column: 1 / -1; }}
.an-card h3 {{ margin: 0 0 4px; font-size: 16px; font-weight: 650; }}
.an-card .sub {{ color: var(--muted); font-size: 13px; margin: 0 0 14px; }}
.chart {{ width: 100%; height: auto; display: block; }}
.ax {{ fill: var(--muted); font-size: 11px; }}
.val {{ fill: var(--ink); font-size: 11px; font-weight: 700; }}
.grid {{ stroke: var(--line); stroke-width: 1; }}
.bar {{ fill: var(--accent); }}
.seg-ai-tool {{ fill: var(--cat-ai-tool); background: var(--cat-ai-tool); }}
.seg-dev-tool {{ fill: var(--cat-dev-tool); background: var(--cat-dev-tool); }}
.seg-github {{ fill: var(--cat-github); background: var(--cat-github); }}
.seg-web-app {{ fill: var(--cat-web-app); background: var(--cat-web-app); }}
.seg-article {{ fill: var(--cat-article); background: var(--cat-article); }}
.seg-providers {{ fill: var(--cat-providers); background: var(--cat-providers); }}
.hbar-label {{ fill: var(--ink); font-size: 12px; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 12px; }}
.leg {{ font-size: 12.5px; color: var(--muted); }}
.seg-sw {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; margin-right: 6px; }}
.segrow {{ display: flex; gap: 6px; margin-bottom: 14px; }}
.spot-name {{ font-size: 14px; font-weight: 650; margin: 0 0 10px; }}
.spot-name span {{ color: var(--muted); font-weight: 400; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="topbar">
      <div class="kicker">Curated from CheapInfra · #share-tech + #providers</div>
      <button id="themeToggle" class="theme-toggle" aria-label="Toggle light and dark mode">
        <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
        <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
      </button>
    </div>
    <div class="hero-grid">
      <div>
        <h1>Useful things worth opening.</h1>
        <p class="lede">Every genuinely useful link shared in the channels — AI tools, dev tools, websites, articles, repos, plus a curated section of inference providers from #providers — newest first. Collected read-only; each entry carries a two-sentence brief and its sharer.</p>
      </div>
      <aside class="review" aria-label="Review summary">
        <span class="rlab">Review window</span>
        <div class="ritem"><span class="rval">{range_str}</span></div>
        <div class="ritem"><span class="rval">{total} <small>resources kept</small></span><span class="rsub">across {len(ordered)} sections</span></div>
      </aside>
    </div>
    <div class="catchips">{catchips}</div>
  </header>
  <div class="toolbar">
    <label class="searchlabel" for="search">Search the library</label>
    <div class="searchrow">
      <input id="search" type="search" placeholder="Search {total} resources…" autocomplete="off">
      <button id="clearAll" class="clearbtn" type="button">Clear all</button>
    </div>
    <div class="frow"><span class="flabel">Category</span>{fchips}</div>
    <div class="frow"><span class="flabel">Week</span>{wchips}</div>
  </div>
  <div class="tabs" role="tablist" aria-label="Library or analytics">
    <button class="tab active" data-tab="library" role="tab" aria-selected="true">Library</button>
    <button class="tab" data-tab="analytics" role="tab" aria-selected="false">Analytics</button>
  </div>
  <nav class="wnavs">{"".join(nav)}</nav>
  <h2 class="shortlist-h" id="results">The shortlist</h2>
  <p class="shortlist-sub">Every kept resource, newest week first. Search and the filters above narrow it down.</p>
  <main id="main">
{"".join(sections)}
  </main>
  <section id="analytics" hidden>
    <h2 class="an-h">Analytics</h2>
    <p class="an-sub">What the channels have been sharing: volume, category mix and the most active sharers across {len(ordered)} sections.</p>
    <div class="an-stats">{an_stats}</div>
    <div class="an-grid">
      <div class="an-card">
        <h3>Resources per week</h3>
        <p class="sub">Curated resources added each week, oldest to newest.</p>
        {vol_svg}
      </div>
      <div class="an-card">
        <h3>Top sharers</h3>
        <p class="sub">Most prolific link-sharers in the channel.</p>
        {sharer_svg}
      </div>
      <div class="an-card wide">
        <h3>Category mix over time</h3>
        <p class="sub">How the category mix shifted across weeks.</p>
        <div class="legend">{legend}</div>
        <div class="segrow">
          <button class="fchip fswitch active" data-range="week">Weekly</button>
          <button class="fchip fswitch" data-range="fort">Fortnightly</button>
        </div>
        <div id="trendWeek">{trend_week_svg}</div>
        <div id="trendFort" hidden>{trend_fort_svg}</div>
      </div>
      <div class="an-card">
        <h3>All-time category mix</h3>
        <p class="sub">Share of each category across all {total} resources.</p>
        {mix_svg}
      </div>
      <div class="an-card">
        <h3>Sharer spotlight</h3>
        <p class="sub">What the top sharer shares most.</p>
        {spotlight}
      </div>
    </div>
  </section>
  <p class="empty" id="empty" style="display:none">Nothing matches — try a different search.</p>
  <footer>
    <span class="fsrc">Source: CheapInfra Discord · #share-tech + #providers</span> · Last updated {today_str}<br>
    Briefs are editorial summaries (~2 sentences); claims originating from Discord messages are unverified unless independently checked.<br>
    Data: <a href="data.json">data.json</a> · Weekly lists: <a href="weeks/">weeks/</a> · Raw logs: <a href="raw/">raw/</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="feed.xml">RSS</a>
  </footer>
</div>
<button class="top" id="top" aria-label="Back to top">↑</button>
<script>
// theme: black is the default; the toggle offers the light editorial theme, choice remembered
const tt = document.getElementById('themeToggle');
function setTheme(t) {{
  document.documentElement.dataset.theme = t;
  try {{ localStorage.setItem('rl-theme', t); }} catch(e) {{}}
}}
if (tt) tt.addEventListener('click', () => {{
  const cur = document.documentElement.dataset.theme || 'dark';
  setTheme(cur === 'dark' ? 'light' : 'dark');
}});
// library filtering
const q = document.getElementById('search');
const cchips = [...document.querySelectorAll('.fchip[data-cat]')];
const wchips = [...document.querySelectorAll('.fchip[data-week]')];
const cards = [...document.querySelectorAll('.card')];
const weeks = [...document.querySelectorAll('.week')];
const empty = document.getElementById('empty');
const resultsH = document.getElementById('results');
let activeCat = null, activeWeek = null;
function apply() {{
  const term = q.value.trim().toLowerCase();
  let visible = 0;
  for (const c of cards) {{
    const okCat = !activeCat || c.dataset.cats.split(' ').includes(activeCat);
    const wsec = c.closest('.week');
    const okWeek = !activeWeek || (wsec && wsec.dataset.week === activeWeek);
    const okQ = !term || c.dataset.search.includes(term);
    const show = okCat && okWeek && okQ;
    c.classList.toggle('hidden', !show);
    if (show) visible++;
  }}
  for (const w of weeks) {{
    const any = [...w.querySelectorAll('.card')].some(c => !c.classList.contains('hidden'));
    w.classList.toggle('hidden', !any);
  }}
  if (empty) empty.style.display = visible ? 'none' : 'block';
  return visible;
}}
function goResults() {{
  if (resultsH) resultsH.scrollIntoView({{behavior: 'smooth', block: 'start'}});
}}
if (q) {{
  q.addEventListener('input', apply);
  q.addEventListener('keydown', (e) => {{ if (e.key === 'Enter') {{ apply(); goResults(); }} }});
}}
for (const ch of cchips) ch.addEventListener('click', () => {{
  const cat = ch.dataset.cat === 'all' ? null : ch.dataset.cat;
  activeCat = activeCat === cat ? null : cat;
  cchips.forEach(c => c.classList.toggle('active',
    c.dataset.cat === 'all' ? activeCat === null : c.dataset.cat === activeCat));
  apply();
  goResults();
}});
for (const ch of wchips) ch.addEventListener('click', () => {{
  activeWeek = activeWeek === ch.dataset.week ? null : ch.dataset.week;
  wchips.forEach(c => c.classList.toggle('active', c.dataset.week === activeWeek));
  apply();
  goResults();
}});
// clear all: reset search text, category and week filters
const clearBtn = document.getElementById('clearAll');
if (clearBtn) clearBtn.addEventListener('click', () => {{
  activeCat = null; activeWeek = null;
  if (q) q.value = '';
  cchips.forEach(c => c.classList.toggle('active', c.dataset.cat === 'all'));
  wchips.forEach(c => c.classList.remove('active'));
  apply();
  goResults();
}});
// week-nav anchor links: clear filters first so the target section is visible,
// otherwise a link to a filtered-out week would have no scroll target
const wnavs = [...document.querySelectorAll('.wnav')];
for (const a of wnavs) a.addEventListener('click', () => {{
  if (activeCat || activeWeek || (q && q.value)) {{
    activeCat = null; activeWeek = null;
    if (q) q.value = '';
    cchips.forEach(c => c.classList.toggle('active', c.dataset.cat === 'all'));
    wchips.forEach(c => c.classList.remove('active'));
    apply();
  }}
}});
// tabs: library / analytics
const tabs = [...document.querySelectorAll('.tab')];
const an = document.getElementById('analytics');
const libSels = ['.toolbar', '.wnavs', '#main', '#empty', '.shortlist-h', '.shortlist-sub'];
function showTab(name) {{
  const showAn = name === 'analytics';
  tabs.forEach(x => {{
    const on = x.dataset.tab === name;
    x.classList.toggle('active', on);
    x.setAttribute('aria-selected', on ? 'true' : 'false');
  }});
  if (an) an.hidden = !showAn;
  libSels.forEach(s => {{
    const e = document.querySelector(s);
    if (e) e.classList.toggle('lib-hidden', showAn);
  }});
  const target = showAn ? an : resultsH;
  if (target) target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
  else scrollTo({{top: 0, behavior: 'smooth'}});
}}
for (const t of tabs) t.addEventListener('click', () => showTab(t.dataset.tab));
// back to top
const topBtn = document.getElementById('top');
if (topBtn) {{
  addEventListener('scroll', () => topBtn.classList.toggle('show', scrollY > 600), {{passive: true}});
  topBtn.addEventListener('click', () => scrollTo({{top: 0, behavior: 'smooth'}}));
}}
// analytics: weekly / fortnightly trend
const fsw = [...document.querySelectorAll('.fswitch')];
for (const b of fsw) b.addEventListener('click', () => {{
  fsw.forEach(x => x.classList.toggle('active', x === b));
  const fort = b.dataset.range === 'fort';
  const tw = document.getElementById('trendWeek'), tf = document.getElementById('trendFort');
  if (tw) tw.hidden = fort;
  if (tf) tf.hidden = !fort;
}});
</script>
</body>
</html>
"""
    (ROOT / "index.html").write_text(html)
    make_og_image(total)

    # ---- feed.xml (RSS 2.0, newest first) ----
    from datetime import datetime, timezone
    from email.utils import format_datetime
    items = []
    _fallback_end = max(week_info[l]["end"] for l in ordered if l != "providers")
    for label in ordered:
        info = week_info[label]
        end = info["end"] or _fallback_end
        year = end[0]
        for r in weeks[label]:
            m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})", r.get("date", ""))
            if m:
                mon = MONTHS.get(m.group(2)[:3].title(), end[1])
                dt = datetime(year, mon, int(m.group(1)), 12, 0, tzinfo=timezone.utc)
            else:
                dt = datetime(*end, 12, 0, tzinfo=timezone.utc)
            chan = "#providers" if label == "providers" else "#share-tech"
            items.append(
                f"<item><title>{xml_esc(r['title'])}</title>"
                f"<link>{xml_esc(r['url'])}</link>"
                f"<guid isPermaLink=\"true\">{xml_esc(r['url'])}</guid>"
                f"<pubDate>{format_datetime(dt)}</pubDate>"
                f"<description>{xml_esc(r['brief'] + ' — shared by ' + r['sharer'] + ' in ' + chan + '.')}</description>"
                f"</item>")
    rss = (f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\">"
           f"<channel><title>The Resource Library — CheapInfra #share-tech + #providers</title>"
           f"<link>{SITE_URL}/</link>"
           f"<description>{xml_esc(desc)}</description>"
           + "\n".join(items) + "</channel></rss>")
    (ROOT / "feed.xml").write_text(rss)

    print(f"resources: {total}")
    for label in ordered:
        print(f"  {label}: {len(weeks[label])}")


if __name__ == "__main__":
    main()
