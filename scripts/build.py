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


CAT_COLORS = {
    "ai-tool": ("#f3e8ff", "#7c3aed"),
    "dev-tool": ("#dbeafe", "#1d4ed8"),
    "github": ("#e5e7eb", "#374151"),
    "web-app": ("#ccfbf1", "#0f766e"),
    "article": ("#fef3c7", "#b45309"),
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def xml_esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def make_og_image(total):
    """Generate og-image.png (1200x630 social card) with the current count."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), "#faf9f6")
    d = ImageDraw.Draw(img)
    try:
        serif = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 104)
        sans = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
        kick = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except OSError:
        serif = sans = kick = ImageFont.load_default()
    d.rectangle([0, 0, W, 14], fill="#4f46e5")
    d.text((80, 90), "CHEAPINFRA  ·  #SHARE-TECH", font=kick, fill="#78716c")
    d.text((76, 170), "The Resource", font=serif, fill="#1c1917")
    d.text((76, 290), "Library", font=serif, fill="#1c1917")
    d.text((80, 450), f"{total} curated developer resources", font=sans, fill="#57534e")
    d.text((80, 500), "AI tools, dev tools, repos & articles", font=sans, fill="#78716c")
    img.save(ROOT / "og-image.png")


def main():
    all_res = []
    for f in sorted(NOTES_DIR.glob("*.md")):
        all_res.extend(parse_notes(f))

    weeks = {}
    for r in all_res:
        weeks.setdefault(r["week"], []).append(r)
    week_info = {label: parse_week(label) for label in weeks}
    ordered = sorted(weeks, key=lambda l: week_info[l]["end"], reverse=True)

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
    sections, nav = [], []
    for wi, label in enumerate(ordered):
        info = week_info[label]
        res = weeks[label]
        latest = ' <span class="newdot">new</span>' if wi == 0 else ''
        nav.append(f'<a class="wnav" href="#{info["slug"]}">{esc(label)}{latest}<span>{len(res)}</span></a>')
        cards = []
        for r in res:
            chips = "".join(
                f'<span class="chip" style="--bg:{CAT_COLORS.get(c, ("#f0f0f0", "#555"))[0]};'
                f'--fg:{CAT_COLORS.get(c, ("#f0f0f0", "#555"))[1]}">{esc(c)}</span>'
                for c in r["categories"])
            blob = esc((r["title"] + " " + r["brief"] + " " + r["sharer"]).lower())
            cards.append(
                f'<article class="card" id="r-{r["id"]}" data-cats="{" ".join(r["categories"])}" data-search="{blob}">'
                f'<h3><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a></h3>'
                f'<div class="meta">{chips}</div>'
                f'<p>{esc(r["brief"])}</p>'
                f'<div class="attr"><span class="who">{esc(r["sharer"])}</span> · {esc(r["date"])}'
                f' · <a class="plink" href="#r-{r["id"]}" title="Permalink">⧉</a></div>'
                f'</article>')
        badge = ' <span class="latest">Latest</span>' if wi == 0 else ''
        sections.append(
            f'<section class="week" id="{info["slug"]}" data-week="{esc(label)}">'
            f'<div class="weekhead"><h2>Week of {esc(label)}</h2>{badge}'
            f'<span class="wcount">{len(res)} resources</span></div>'
            + "\n".join(cards) + '</section>')

    fchips = "".join(f'<button class="fchip" data-cat="{c}">{c} <b>{cat_counts[c]}</b></button>' for c in cats)
    wchips = "".join(f'<button class="fchip wfilter" data-week="{esc(l)}">{esc(l)}</button>' for l in ordered)
    catchips = "".join(f'<span class="catchip">{c} × {cat_counts[c]}</span>' for c in cats)
    desc = (f"A curated, browsable archive of {total} developer resources shared in the "
            f"CheapInfra Discord's #share-tech channel, newest first.")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resource Library — CheapInfra #share-tech</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="Resource Library — CheapInfra #share-tech">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:image" content="{SITE_URL}/og-image.png">
<link rel="alternate" type="application/rss+xml" title="Resource Library feed" href="feed.xml">
<style>
:root {{
  --paper: #faf9f6; --card: #ffffff; --ink: #1c1917; --muted: #78716c;
  --line: #e7e2da; --accent: #4f46e5; --accent-soft: #eef2ff;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --paper: #141210; --card: #1e1b18; --ink: #ece7df; --muted: #a8a29e;
    --line: #2e2a26; --accent: #a5b4fc; --accent-soft: #262544;
  }}
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--paper); color: var(--ink);
  margin: 0; line-height: 1.6;
}}
.wrap {{ max-width: 860px; margin: 0 auto; padding: 0 20px 80px; }}
.hero {{ padding: 56px 0 8px; }}
.hero .kicker {{
  font-size: 13px; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 12px;
}}
.hero h1 {{
  font-family: Georgia, "Times New Roman", serif; font-weight: 600;
  font-size: clamp(32px, 5vw, 46px); line-height: 1.15; margin: 0 0 12px;
  letter-spacing: -0.01em;
}}
.hero p {{ color: var(--muted); max-width: 62ch; margin: 0 0 24px; }}
.stats {{ display: flex; gap: 28px; flex-wrap: wrap; margin-bottom: 8px; }}
.stat b {{ display: block; font-size: 26px; font-weight: 650; }}
.stat span {{ font-size: 13px; color: var(--muted); }}
.catchips {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 14px 0 8px; }}
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
.toolbar {{
  position: sticky; top: 0; z-index: 10;
  background: color-mix(in srgb, var(--paper) 92%, transparent);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  padding: 14px 0; border-bottom: 1px solid var(--line);
  margin: 24px -20px 0; padding-left: 20px; padding-right: 20px;
}}
#search {{
  width: 100%; padding: 11px 14px; font-size: 15px; border: 1px solid var(--line);
  border-radius: 10px; background: var(--card); color: var(--ink); margin-bottom: 10px;
}}
#search:focus {{ outline: 2px solid var(--accent); border-color: transparent; }}
.frow {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
.frow + .frow {{ margin-top: 6px; }}
.flabel {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-right: 4px; }}
.fchip {{
  border: 1px solid var(--line); background: var(--card); color: var(--ink);
  border-radius: 999px; padding: 4px 13px; cursor: pointer; font-size: 13px;
  transition: all 0.15s ease;
}}
.fchip b {{ font-weight: 700; opacity: 0.55; }}
.fchip:hover {{ border-color: var(--accent); }}
.fchip.active {{ background: var(--ink); color: var(--paper); border-color: var(--ink); }}
.wnavs {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 28px 0 8px; }}
.wnav {{
  text-decoration: none; color: var(--ink); font-size: 13px;
  border: 1px solid var(--line); border-radius: 10px; padding: 8px 12px;
  background: var(--card); display: flex; gap: 8px; align-items: baseline;
}}
.wnav span {{ color: var(--muted); font-size: 12px; }}
.wnav:hover {{ border-color: var(--accent); }}
.week {{ margin-top: 40px; scroll-margin-top: 150px; }}
.weekhead {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 4px; }}
.weekhead h2 {{
  font-family: Georgia, "Times New Roman", serif; font-size: 24px; font-weight: 600; margin: 0;
}}
.wcount {{ font-size: 13px; color: var(--muted); }}
.card {{
  background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 18px 20px; margin: 12px 0; transition: box-shadow 0.18s ease, transform 0.18s ease;
  scroll-margin-top: 150px;
}}
.card:hover {{ box-shadow: 0 8px 28px rgba(0,0,0,0.08); transform: translateY(-1px); }}
.card:target {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.card h3 {{ margin: 0 0 8px; font-size: 17px; font-weight: 650; letter-spacing: -0.005em; }}
.card h3 a {{ text-decoration: none; color: inherit; }}
.card h3 a:hover {{ color: var(--accent); }}
.card p {{ margin: 10px 0 12px; color: var(--ink); }}
.meta {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.chip {{
  font-size: 11.5px; font-weight: 600; border-radius: 999px; padding: 3px 11px;
  background: var(--bg, #f0f0f0); color: var(--fg, #555);
}}
.attr {{ font-size: 13px; color: var(--muted); }}
.attr .who {{ font-weight: 600; color: var(--ink); }}
.plink {{ color: var(--muted); text-decoration: none; opacity: 0; transition: opacity 0.15s; }}
.card:hover .plink {{ opacity: 1; }}
.card.hidden, .week.hidden {{ display: none; }}
.empty {{ color: var(--muted); font-style: italic; text-align: center; margin: 48px 0; }}
footer {{
  margin-top: 64px; padding-top: 24px; border-top: 1px solid var(--line);
  font-size: 13px; color: var(--muted);
}}
footer a {{ color: var(--accent); }}
.top {{
  position: fixed; right: 20px; bottom: 20px; width: 42px; height: 42px; border-radius: 50%;
  border: 1px solid var(--line); background: var(--card); color: var(--ink);
  cursor: pointer; font-size: 18px; display: none; align-items: center; justify-content: center;
}}
.top.show {{ display: flex; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="kicker">CheapInfra · #share-tech</div>
    <h1>The Resource Library</h1>
    <p>Every genuinely useful link shared in the channel — AI tools, dev tools, websites, articles and repos — curated week by week, newest first. Collected read-only; each entry carries a two-sentence brief and its sharer.</p>
    <div class="stats">
      <div class="stat"><b>{total}</b><span>resources</span></div>
      <div class="stat"><b>{len(ordered)}</b><span>weeks covered</span></div>
      <div class="stat"><b>{len(cats)}</b><span>categories</span></div>
    </div>
    <div class="catchips">{catchips}</div>
  </header>
  <div class="toolbar">
    <input id="search" type="search" placeholder="Search {total} resources…" autocomplete="off">
    <div class="frow"><span class="flabel">Category</span>{fchips}</div>
    <div class="frow"><span class="flabel">Week</span>{wchips}</div>
  </div>
  <nav class="wnavs">{"".join(nav)}</nav>
  <main id="main">
{"".join(sections)}
  </main>
  <p class="empty" id="empty" style="display:none">Nothing matches — try a different search.</p>
  <footer>
    Built from read-only collection of CheapInfra's #share-tech channel. Briefs are editorial summaries (~2 sentences); claims originating from announcement posts are unverified unless independently checked. Data: <a href="data.json">data.json</a> · Weekly lists: <a href="weeks/">weeks/</a> · Raw logs: <a href="raw/">raw/</a> · <a href="CHANGELOG.md">Changelog</a>
  </footer>
</div>
<button class="top" id="top" aria-label="Back to top">↑</button>
<script>
const q = document.getElementById('search');
const cchips = [...document.querySelectorAll('.fchip[data-cat]')];
const wchips = [...document.querySelectorAll('.fchip[data-week]')];
const cards = [...document.querySelectorAll('.card')];
const weeks = [...document.querySelectorAll('.week')];
const empty = document.getElementById('empty');
const top = document.getElementById('top');
let activeCat = null, activeWeek = null;
function apply() {{
  const term = q.value.trim().toLowerCase();
  let visible = 0;
  for (const c of cards) {{
    const okCat = !activeCat || c.dataset.cats.split(' ').includes(activeCat);
    const okWeek = !activeWeek || c.closest('.week').dataset.week === activeWeek;
    const okQ = !term || c.dataset.search.includes(term);
    const show = okCat && okWeek && okQ;
    c.classList.toggle('hidden', !show);
    if (show) visible++;
  }}
  for (const w of weeks) {{
    const any = [...w.querySelectorAll('.card')].some(c => !c.classList.contains('hidden'));
    w.classList.toggle('hidden', !any);
  }}
  empty.style.display = visible ? 'none' : 'block';
}}
q.addEventListener('input', apply);
for (const ch of cchips) ch.addEventListener('click', () => {{
  activeCat = activeCat === ch.dataset.cat ? null : ch.dataset.cat;
  cchips.forEach(c => c.classList.toggle('active', c.dataset.cat === activeCat));
  apply();
}});
for (const ch of wchips) ch.addEventListener('click', () => {{
  activeWeek = activeWeek === ch.dataset.week ? null : ch.dataset.week;
  wchips.forEach(c => c.classList.toggle('active', c.dataset.week === activeWeek));
  apply();
}});
addEventListener('scroll', () => top.classList.toggle('show', scrollY > 600));
top.addEventListener('click', () => scrollTo({{top: 0, behavior: 'smooth'}}));
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
    for label in ordered:
        info = week_info[label]
        year = info["end"][0]
        for r in weeks[label]:
            m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})", r.get("date", ""))
            if m:
                mon = MONTHS.get(m.group(2)[:3].title(), info["end"][1])
                dt = datetime(year, mon, int(m.group(1)), 12, 0, tzinfo=timezone.utc)
            else:
                dt = datetime(*info["end"], 12, 0, tzinfo=timezone.utc)
            items.append(
                f"<item><title>{xml_esc(r['title'])}</title>"
                f"<link>{xml_esc(r['url'])}</link>"
                f"<guid isPermaLink=\"true\">{xml_esc(r['url'])}</guid>"
                f"<pubDate>{format_datetime(dt)}</pubDate>"
                f"<description>{xml_esc(r['brief'] + ' — shared by ' + r['sharer'] + ' in #share-tech.')}</description>"
                f"</item>")
    rss = (f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\">"
           f"<channel><title>The Resource Library — CheapInfra #share-tech</title>"
           f"<link>{SITE_URL}/</link>"
           f"<description>{xml_esc(desc)}</description>"
           + "\n".join(items) + "</channel></rss>")
    (ROOT / "feed.xml").write_text(rss)

    print(f"resources: {total}")
    for label in ordered:
        print(f"  {label}: {len(weeks[label])}")


if __name__ == "__main__":
    main()
