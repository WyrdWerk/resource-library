#!/usr/bin/env python3
"""Build the CheapInfra #share-tech resource library repo.

Reads curated research notes from notes/*.md and regenerates:
  index.html   — the browsable site (search + category + week filters)
  data.json    — the full dataset (title, url, sharer, date, categories, brief, warning, week, id)
  weeks/*.md   — per-week curated lists with briefs
  CHANGELOG.md — batch history derived from notes/

Hand-maintained (never overwritten by this script):
  notes/*.md, raw/*.md, README.md, AGENTS.md, scripts/build.py

Usage: python3 scripts/build.py   (run from anywhere; paths resolve to repo root)
"""
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = ROOT / "notes"
WEEKS_DIR = ROOT / "weeks"

# Canonical URL of the deployed site (custom domain on Cloudflare Pages).
SITE_URL = "https://cheapinfra-resources.wyrdwerk.com"

# Header social links; also used for the twitter:creator tag and share text.
REPO_URL = "https://github.com/WyrdWerk/resource-library"
LINKEDIN_URL = "https://www.linkedin.com/in/yash-jain-65295511b/"
X_HANDLE = "thelaggingway"

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


WARN_RE = re.compile(
    r"unverified|announcement only|expect rough edges|link-only share"
    r"|claims? (?:comes|come) from (?:the )?poster"
    r"|not independently (?:checked|verified)"
    r"|treat [^.]*experimental|use at your own risk"
    r"|no (?:benchmark|working link|repo) was", re.I)


def split_warning(brief):
    """Split a brief into (description, warning). Sentences that flag an
    unverified/experimental/announcement-only claim become the warning bar;
    the rest stays as the description. If every sentence is a caveat, the
    brief stays whole and no warning is shown."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", brief)
    warn = [p for p in parts if WARN_RE.search(p)]
    keep = [p for p in parts if not WARN_RE.search(p)]
    if warn and keep:
        return " ".join(keep), " ".join(warn)
    return brief, ""


def count_dropped(paths):
    """Count bullets under '## Dropped' sections across notes files."""
    n = 0
    for p in paths:
        in_drop = False
        for line in p.read_text().splitlines():
            s = line.strip()
            if s.startswith("## "):
                in_drop = s.startswith("## Dropped")
            elif in_drop and s.startswith("- "):
                n += 1
    return n


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
    W, row_h, pad_l, pad_r, pad_t = 560, 34, 170, 84, 10
    H = pad_t + len(items) * row_h + 10
    vmax = max([v for _, v, _, _ in items] + [1])
    bw = (W - pad_l - pad_r) / vmax
    parts = []
    for i, (label, v, cls, extra) in enumerate(items):
        y = pad_t + i * row_h
        lab = label if len(label) <= 18 else label[:17] + "…"
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
        r["_desc"], r["_warn"] = split_warning(r["brief"])
    # Permalink ids: dated-week entries claim slugs first so previously
    # published #r-<id> anchors keep pointing at the same card; the providers
    # section (added later) takes the -2 suffixed variants on collision.
    for r in all_res:
        if r["week"] != "providers":
            r["id"] = slugify(r["title"], seen)
    for r in all_res:
        if r["week"] == "providers":
            r["id"] = slugify(r["title"], seen)

    dropped = count_dropped(NOTES_DIR.glob("*.md"))
    total = len(all_res)
    cats = sorted({c for r in all_res for c in r["categories"]})
    cat_counts = {c: sum(1 for r in all_res if c in r["categories"]) for c in cats}

    data = [{k: v for k, v in r.items() if not k.startswith("_")} | {"warning": r["_warn"]}
            for r in all_res]
    (ROOT / "data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))

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
    sections, wrows = [], []
    wseq = 0  # sequential number for dated week sections only
    newest_week_badged = False  # "Latest"/"new" stay on the newest week, not providers
    for wi, label in enumerate(ordered):
        info = week_info[label]
        res = weeks[label]
        dlabel = info["label"]
        if label == "providers":
            wnum_html = ""
            is_newest_week = False
        else:
            wseq += 1
            wnum_html = f'<span class="weeknum">{wseq:02d}</span>'
            is_newest_week = not newest_week_badged
            newest_week_badged = True
        latest = ' <span class="newdot">new</span>' if is_newest_week else ''
        wrows.append(f'<button class="navrow" data-week="{esc(label)}"><span>{esc(dlabel)}{latest}</span><b>{len(res)}</b></button>')
        cards = []
        for ci, r in enumerate(res):
            chips = "".join(
                f'<button class="chip c-{c}" data-cat="{c}" title="Show all {esc(CAT_LABELS.get(c, c))}">{esc(CAT_LABELS.get(c, c))}</button>'
                for c in r["categories"])
            blob = esc((r["title"] + " " + r["brief"] + " " + r["sharer"]).lower())
            u = urlsplit(r["url"])
            dom = u.netloc.replace("www.", "") + u.path.rstrip("/")
            if len(dom) > 52:
                dom = dom[:51] + "…"
            warnbar = (f'<p class="warnbar"><span class="warnmark">⚠</span> {esc(r["_warn"])}</p>'
                       if r["_warn"] else "")
            cards.append(
                f'<article class="card" id="r-{r["id"]}" data-cats="{" ".join(r["categories"])}" data-search="{blob}">'
                f'<span class="cardnum">{ci + 1:02d}</span>'
                f'<div class="card-main">'
                f'<h3><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a></h3>'
                f'<p>{esc(r["_desc"])}</p>'
                f'{warnbar}'
                f'<a class="dlink" href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(dom)} ↗</a>'
                f'</div>'
                f'<div class="card-side">'
                f'<div class="meta">{chips}</div>'
                f'<div class="side-row">Shared by <button class="who" data-sharer="{esc(r["sharer"])}" title="Search for {esc(r["sharer"])}">{esc(r["sharer"])}</button></div>'
                f'<div class="side-row">{esc(r["date"])} · <a class="plink" href="#r-{r["id"]}" title="Copy a link to this resource">Copy link</a></div>'
                f'</div>'
                f'</article>')
        badge = ' <span class="latest">Latest</span>' if is_newest_week else ''
        heading = "Providers" if label == "providers" else esc(dlabel)
        if label == "providers":
            wcount = f"{len(res)} inference provider{'s' if len(res) != 1 else ''}"
        else:
            wcount = f"{len(res)} kept"
        sections.append(
            f'<section class="week" id="{info["slug"]}" data-week="{esc(label)}">'
            f'<div class="weekhead">{wnum_html}<h2>{heading}</h2>{badge}'
            f'<span class="wcount">{wcount}</span></div>'
            + "\n".join(cards) + '</section>')

    crows = (f'<button class="navrow active" data-cat="all"><span>All resources</span><b>{total}</b></button>' +
             "".join(f'<button class="navrow" data-cat="{c}"><span>{CAT_LABELS.get(c, c)}</span><b>{cat_counts[c]}</b></button>'
                     for c in cats))
    wrows = "".join(wrows)

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
        arows.append({"label": label,
                      "short": "Providers" if label == "providers" else short_label(label),
                      "total": len(weeks[label]), "counts": counts})
    frows = []
    # Fortnightly rows: pair dated weeks exactly as before (providers was not
    # there), then append the providers pseudo-section as its own clean row.
    warows = [r for r in arows if r["label"] != "providers"]
    parows = [r for r in arows if r["label"] == "providers"]
    for i in range(0, len(warows), 2):
        grp = warows[i:i + 2]
        counts = {c: sum(g["counts"].get(c, 0) for g in grp) for c in cats}
        fl = (grp[0]["label"].split("–")[0] + "–" + grp[1]["label"].split("–")[1]
              if len(grp) == 2 else grp[0]["label"])
        frows.append({"label": fl, "short": short_label(fl),
                      "total": sum(g["total"] for g in grp), "counts": counts})
    for p in parows:
        frows.append({"label": p["label"], "short": p["short"],
                      "total": p["total"], "counts": dict(p["counts"])})
    sharer_counts = Counter(r["sharer"] for r in all_res)
    top_sharers = sharer_counts.most_common(10)
    top_name, top_n = top_sharers[0]
    sp_counts = Counter(c for r in all_res if r["sharer"] == top_name for c in r["categories"])
    _week_rows = [r for r in arows if r["label"] != "providers"] or arows
    busiest = max(_week_rows, key=lambda r: r["total"])
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
    share_text = (f"Useful things worth opening: {total} hand-curated AI tools, dev tools, repos and inference providers "
                  f"from CheapInfra's #share-tech and #providers, via @{X_HANDLE}")
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
<link rel="canonical" href="{SITE_URL}/">
<meta property="og:site_name" content="CheapInfra #share-tech + #providers Resource Library">
<meta property="og:title" content="Resource Library — CheapInfra #share-tech + #providers">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}/">
<meta property="og:image" content="{SITE_URL}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Useful things worth opening — {total} curated developer resources">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:creator" content="@{X_HANDLE}">
<meta name="twitter:title" content="Resource Library — CheapInfra #share-tech + #providers">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{SITE_URL}/og-image.png">
<link rel="alternate" type="application/rss+xml" title="Resource Library feed" href="feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230a0c0b'/%3E%3Ctext x='16' y='23.5' font-family='Georgia,serif' font-size='21' text-anchor='middle' fill='%237ed7b6'%3E%23%3C/text%3E%3C/svg%3E">
<meta name="theme-color" content="#0a0c0b">
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
.serif {{ font-family: Georgia, "Times New Roman", serif; }}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 0 32px 90px; }}
@media (max-width: 640px) {{ .wrap {{ padding: 0 18px 72px; }} }}
.hero {{ padding: 48px 0 40px; border-bottom: 1px solid var(--line); }}
.kicker {{
  display: flex; align-items: center; gap: 12px;
  font-size: 10.5px; letter-spacing: 0.18em; text-transform: uppercase; font-weight: 700;
  color: var(--accent);
}}
.kicker::before {{ content: ""; width: 28px; height: 1px; background: var(--accent); }}
.hero-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 56px; align-items: end; margin-top: 22px; }}
@media (max-width: 800px) {{ .hero-grid {{ grid-template-columns: 1fr; gap: 32px; }} }}
.hero h1 {{
  font-family: Georgia, "Times New Roman", serif; font-weight: 400;
  font-size: clamp(42px, 6.6vw, 76px); line-height: 1.02; margin: 0 0 24px;
  letter-spacing: -0.03em;
}}
.hero h1 span {{ display: block; }}
.hero p.lede {{ color: var(--muted); max-width: 54ch; margin: 0; font-size: 16px; line-height: 1.7; }}
.review {{ border-left: 1px solid var(--line); padding: 4px 0 4px 24px; margin-bottom: 8px; }}
.eyebrow {{
  font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.16em;
  color: var(--muted); font-weight: 700;
}}
.review .eyebrow {{ display: block; margin-bottom: 10px; }}
.rrange {{ font-family: Georgia, "Times New Roman", serif; font-size: 21px; line-height: 1.3; display: block; margin-bottom: 18px; }}
.rstats {{ display: flex; gap: 56px; margin-bottom: 14px; }}
.rstat b {{ display: block; font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 30px; line-height: 1.05; }}
.rstat span {{ font-size: 12px; color: var(--muted); }}
.rsub {{ font-size: 11.5px; color: var(--muted); display: block; line-height: 1.5; }}
.latest {{
  font-size: 10px; font-weight: 700; background: var(--accent-soft); color: var(--accent);
  border-radius: 4px; padding: 2px 8px; text-transform: uppercase; letter-spacing: 0.1em;
  align-self: center;
}}
.newdot {{
  font-size: 10px; font-weight: 700; color: var(--accent); text-transform: uppercase;
  letter-spacing: 0.08em; margin-left: 6px;
}}
/* ---- two-column layout ---- */
.layout {{ display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 56px; padding-top: 36px; }}
.side {{
  position: sticky; top: 24px; align-self: start;
  max-height: calc(100vh - 48px); overflow-y: auto; padding: 0 6px 16px 0;
  scrollbar-width: thin; scrollbar-color: var(--line) transparent;
}}
@media (max-width: 860px) {{
  .layout {{ grid-template-columns: 1fr; gap: 28px; }}
  .side {{ position: static; max-height: none; overflow: visible; padding: 0; }}
  .navlist.weeks {{ max-height: 220px; overflow-y: auto; }}
}}
.sblock {{ margin-bottom: 28px; }}
.shead {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }}
.searchbox {{ position: relative; }}
.searchbox svg {{
  position: absolute; left: 11px; top: 50%; transform: translateY(-50%);
  width: 14px; height: 14px; color: var(--muted); pointer-events: none;
}}
#search {{
  width: 100%; padding: 9px 12px 9px 33px; font: inherit; font-size: 13.5px;
  border: 1px solid var(--line); border-radius: 6px; background: transparent; color: var(--ink);
}}
#search:focus {{ outline: none; border-color: var(--accent); }}
#search::placeholder {{ color: var(--muted); opacity: 0.8; }}
.clearbtn {{
  border: 0; background: none; padding: 0; cursor: pointer; color: var(--muted);
  font: inherit; font-size: 10.5px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
}}
.clearbtn:hover {{ color: var(--accent); }}
.navlist {{ display: flex; flex-direction: column; }}
.navrow {{
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
  width: 100%; text-align: left; cursor: pointer;
  background: none; border: 0; border-bottom: 1px solid var(--line);
  color: var(--ink); font: inherit; font-size: 13.5px; padding: 9px 2px;
  transition: color 0.15s ease;
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
}}
.navrow:hover {{ color: var(--accent); }}
.navrow b {{
  font-size: 10.5px; font-weight: 600; color: var(--muted); background: var(--line);
  border-radius: 4px; padding: 1px 7px; min-width: 26px; text-align: center; flex: none;
}}
.navrow.active {{ color: var(--accent); font-weight: 600; }}
.navrow.active b {{ background: var(--accent-soft); color: var(--accent); }}
.wdetails > summary {{ cursor: pointer; list-style: none; }}
.wdetails > summary::-webkit-details-marker {{ display: none; }}
.wdetails > summary .eyebrow::after {{ content: " ▾"; }}
.wdetails:not([open]) > summary .eyebrow::after {{ content: " ▸"; }}
.cut summary {{ cursor: pointer; font-size: 12.5px; font-weight: 600; list-style: none; }}
.cut summary::-webkit-details-marker {{ display: none; }}
.cut summary::before {{ content: "▸"; display: inline-block; margin-right: 6px; transition: transform 0.15s ease; }}
.cut[open] summary::before {{ transform: rotate(90deg); }}
.cut p {{ font-size: 12.5px; color: var(--muted); line-height: 1.55; margin: 10px 0 0; }}
.cut p b {{ color: var(--ink); }}
.mainhead {{
  display: flex; justify-content: space-between; align-items: baseline; gap: 16px;
  border-bottom: 1px solid var(--ink); padding-bottom: 14px;
}}
.shortlist-h {{
  font-family: Georgia, "Times New Roman", serif; font-size: 30px; font-weight: 400;
  margin: 0; letter-spacing: -0.015em; scroll-margin-top: 24px;
}}
.mcount {{ font-size: 12px; color: var(--muted); white-space: nowrap; }}
.shortlist-sub {{ color: var(--muted); font-size: 13.5px; margin: 12px 0 0; }}
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
.week {{ margin-top: 40px; scroll-margin-top: 24px; }}
.weekhead {{
  display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
  padding-bottom: 12px; border-bottom: 1px solid var(--line);
}}
.weeknum {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px;
  color: var(--accent); font-weight: 600; letter-spacing: 0.06em;
}}
.weekhead h2 {{
  font-family: Georgia, "Times New Roman", serif; font-size: 20px; font-weight: 400; margin: 0;
  letter-spacing: -0.01em;
}}
.wcount {{ margin-left: auto; font-size: 12px; color: var(--muted); }}
.card {{
  display: grid; grid-template-columns: 34px minmax(0, 1fr) 150px; gap: 0 20px;
  padding: 26px 0; border-bottom: 1px solid var(--line);
  scroll-margin-top: 24px; transition: background 0.2s ease;
}}
@media (max-width: 640px) {{
  .card {{ grid-template-columns: 26px minmax(0, 1fr); gap: 0 12px; padding: 22px 0; }}
  .card-side {{ grid-column: 2; margin-top: 12px; display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: center; }}
  .card-side .meta {{ margin-bottom: 0; }}
}}
.card:target {{ background: var(--accent-soft); box-shadow: -12px 0 0 var(--accent-soft), 12px 0 0 var(--accent-soft); }}
.cardnum {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px;
  color: var(--muted); padding-top: 9px;
}}
.card h3 {{
  margin: 0 0 10px; font-family: Georgia, "Times New Roman", serif;
  font-size: 23px; font-weight: 400; line-height: 1.25; letter-spacing: -0.012em;
}}
.card h3 a {{ text-decoration: none; color: inherit; transition: color 0.15s ease; }}
.card h3 a:hover {{ color: var(--accent); }}
.card-main p {{
  margin: 0 0 14px; font-size: 14.5px; line-height: 1.65; max-width: 64ch;
  color: color-mix(in srgb, var(--ink) 80%, var(--paper));
}}
.warnbar {{
  display: flex; gap: 8px; align-items: baseline; margin: 0 0 14px; max-width: 64ch;
  padding: 8px 12px; border: 1px solid rgba(217,120,90,.32); border-radius: 4px;
  background: rgba(150,62,42,.28); color: #eeb09a; font-size: 12.5px; line-height: 1.45;
}}
[data-theme="light"] .warnbar {{ background: rgba(155,72,42,.08); border-color: rgba(155,72,42,.25); color: var(--warm); }}
.warnbar .warnmark {{ flex: none; }}
.dlink {{
  display: inline-block; font-size: 12.5px; font-weight: 700; color: var(--accent);
  text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px;
  word-break: break-all; -webkit-tap-highlight-color: transparent;
}}
.dlink:hover {{ text-decoration-thickness: 2px; }}
.card-side {{ font-size: 11.5px; color: var(--muted); padding-top: 6px; line-height: 1.5; }}
.card-side .meta {{ margin-bottom: 12px; }}
.side-row .who {{
  font: inherit; font-weight: 600; color: var(--ink); background: none; border: 0; padding: 0;
  cursor: pointer; text-align: left;
}}
.side-row .who:hover {{ color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }}
.meta {{ display: flex; gap: 5px; flex-wrap: wrap; }}
.chip {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10.5px; border-radius: 3px; padding: 2px 7px;
  background: var(--line); color: var(--muted); white-space: nowrap;
  border: 0; cursor: pointer; line-height: 1.5; transition: filter 0.15s ease;
}}
.chip:hover {{ filter: brightness(1.25); }}
[data-theme="light"] .chip:hover {{ filter: brightness(0.92); }}
.plink {{ color: var(--muted); text-decoration: none; opacity: 0.6; transition: opacity 0.15s, color 0.15s; }}
.card:hover .plink {{ opacity: 1; }}
.plink:hover {{ color: var(--accent); }}
.sharebtn {{
  border: 0; background: none; padding: 0; cursor: pointer; font: inherit; color: var(--accent);
  text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px;
}}
a.navrow {{ text-decoration: none; }}
.topbar {{ gap: 16px; flex-wrap: wrap; }}
.topactions {{ display: flex; gap: 8px; }}
.topactions a.theme-toggle {{ color: var(--muted); }}
.topactions a.theme-toggle:hover {{ color: var(--ink); }}
.topactions svg {{ width: 16px; height: 16px; }}
.toast {{
  position: fixed; left: 50%; bottom: 24px; transform: translate(-50%, 12px);
  background: var(--ink); color: var(--paper); font-size: 13px; font-weight: 600;
  padding: 8px 16px; border-radius: 6px; opacity: 0; pointer-events: none;
  transition: opacity 0.2s ease, transform 0.2s ease; z-index: 50;
}}
.toast.show {{ opacity: 1; transform: translate(-50%, 0); }}
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
.topbar {{ display: flex; justify-content: space-between; align-items: center; }}
.theme-toggle {{
  background: transparent; border: 1px solid var(--line); border-radius: 50%;
  width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--ink); flex-shrink: 0; transition: border-color 0.15s ease;
}}
.theme-toggle:hover {{ border-color: var(--accent); }}
.theme-toggle svg {{ width: 18px; height: 18px; }}
.theme-toggle .icon-sun {{ display: block; }}
.theme-toggle .icon-moon {{ display: none; }}
[data-theme="light"] .theme-toggle .icon-sun {{ display: none; }}
[data-theme="light"] .theme-toggle .icon-moon {{ display: block; }}
/* ---- tabs ---- */
.tabs {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 3px; padding: 3px;
  border: 1px solid var(--line); border-radius: 8px;
}}
.tab {{
  border: 0; background: transparent; color: var(--muted); border-radius: 6px;
  padding: 7px 0; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
  -webkit-tap-highlight-color: transparent; touch-action: manipulation;
}}
.tab:hover {{ color: var(--ink); }}
.tab.active {{ background: var(--accent-soft); color: var(--accent); }}
.lib-hidden {{ display: none !important; }}
/* ---- category chips (theme-aware) ---- */
.chip.c-ai-tool {{ color: var(--cat-ai-tool); background: var(--cat-ai-tool-bg); }}
.chip.c-dev-tool {{ color: var(--cat-dev-tool); background: var(--cat-dev-tool-bg); }}
.chip.c-github {{ color: var(--cat-github); background: var(--cat-github-bg); }}
.chip.c-web-app {{ color: var(--cat-web-app); background: var(--cat-web-app-bg); }}
.chip.c-article {{ color: var(--cat-article); background: var(--cat-article-bg); }}
.chip.c-providers {{ color: var(--cat-providers); background: var(--cat-providers-bg); }}
/* ---- analytics ---- */
#analytics {{ scroll-margin-top: 24px; }}
.an-sub {{ color: var(--muted); font-size: 13.5px; margin: 12px 0 22px; }}
.an-stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
.an-stat {{
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 12px 18px; min-width: 140px;
}}
.an-stat b {{ display: block; font-size: 21px; font-weight: 600; font-family: Georgia, "Times New Roman", serif; letter-spacing: -0.01em; }}
.an-stat span {{ font-size: 12px; color: var(--muted); }}
.an-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
@media (max-width: 1000px) and (min-width: 861px), (max-width: 640px) {{ .an-grid {{ grid-template-columns: 1fr; }} }}
.an-card {{
  background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px;
}}
.an-card.wide {{ grid-column: 1 / -1; }}
.an-card h3 {{ margin: 0 0 4px; font-size: 16px; font-weight: 650; }}
.an-card .sub {{ color: var(--muted); font-size: 13px; margin: 0 0 14px; }}
.chart {{ width: 100%; height: auto; display: block; }}
.an-card.wide .chart {{ max-height: 380px; }}
.ax {{ fill: var(--muted); font-size: 11px; }}
.val {{ fill: var(--ink); font-size: 11px; font-weight: 700; }}
.an-card:not(.wide) .ax {{ font-size: 15px; }}
.an-card:not(.wide) .val {{ font-size: 15px; }}
.grid {{ stroke: var(--line); stroke-width: 1; }}
.bar {{ fill: var(--accent); }}
.seg-ai-tool {{ fill: var(--cat-ai-tool); background: var(--cat-ai-tool); }}
.seg-dev-tool {{ fill: var(--cat-dev-tool); background: var(--cat-dev-tool); }}
.seg-github {{ fill: var(--cat-github); background: var(--cat-github); }}
.seg-web-app {{ fill: var(--cat-web-app); background: var(--cat-web-app); }}
.seg-article {{ fill: var(--cat-article); background: var(--cat-article); }}
.seg-providers {{ fill: var(--cat-providers); background: var(--cat-providers); }}
.hbar-label {{ fill: var(--ink); font-size: 16px; }}
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
      <div class="topactions">
      <a class="theme-toggle" href="{REPO_URL}" target="_blank" rel="noopener" aria-label="Source on GitHub" title="Source on GitHub"><svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg></a>
      <a class="theme-toggle" href="{LINKEDIN_URL}" target="_blank" rel="noopener me" aria-label="LinkedIn" title="LinkedIn"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z"/></svg></a>
      <a class="theme-toggle" href="https://x.com/{X_HANDLE}" target="_blank" rel="noopener me" aria-label="X (Twitter)" title="@{X_HANDLE} on X"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
      <button id="themeToggle" class="theme-toggle" aria-label="Toggle light and dark mode">
        <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
        <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
      </button>
      </div>
    </div>
    <div class="hero-grid">
      <div>
        <h1><span>Useful things</span> <span>worth opening.</span></h1>
        <p class="lede">Every genuinely useful link shared in the channels — AI tools, dev tools, websites, articles, repos, plus a curated section of inference providers from #providers — newest first. Collected read-only; each entry carries a two-sentence brief and its sharer.</p>
      </div>
      <aside class="review" aria-label="Review summary">
        <span class="eyebrow">Review window</span>
        <span class="rrange">{range_str}</span>
        <div class="rstats">
          <div class="rstat"><b>{total}</b><span>kept</span></div>
          <div class="rstat"><b>{dropped}</b><span>cut</span></div>
        </div>
        <span class="rsub">Across {len(ordered)} sections, with boundary-day catch-ups folded in.</span>
      </aside>
    </div>
  </header>
  <div class="layout">
  <aside class="side" aria-label="Views and filters">
    <div class="sblock">
      <div class="shead"><span class="eyebrow">View</span></div>
      <div class="tabs" role="tablist" aria-label="Library or analytics">
        <button class="tab active" data-tab="library" role="tab" aria-selected="true">Library</button>
        <button class="tab" data-tab="analytics" role="tab" aria-selected="false">Analytics</button>
      </div>
    </div>
    <div class="sblock side-lib">
      <div class="shead"><label class="eyebrow" for="search">Search</label><button id="clearAll" class="clearbtn" type="button">Clear all</button></div>
      <div class="searchbox">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input id="search" type="search" placeholder="Name, topic, person…" autocomplete="off">
      </div>
    </div>
    <div class="sblock side-lib">
      <div class="shead"><span class="eyebrow">Category</span></div>
      <nav class="navlist">{crows}</nav>
    </div>
    <details class="sblock side-lib wdetails" id="weekBlock" open>
      <summary class="shead"><span class="eyebrow">Week</span></summary>
      <nav class="navlist weeks">{wrows}</nav>
    </details>
    <div class="sblock">
      <div class="shead"><span class="eyebrow">Share the dossier</span></div>
      <nav class="navlist">
        <a class="navrow" href="https://x.com/intent/post?text={quote(share_text)}&amp;url={quote(SITE_URL + '/', safe='')}" target="_blank" rel="noopener"><span>Share on X</span><b>↗</b></a>
        <a class="navrow" href="https://www.linkedin.com/sharing/share-offsite/?url={quote(SITE_URL + '/', safe='')}" target="_blank" rel="noopener"><span>Share on LinkedIn</span><b>↗</b></a>
        <a class="navrow" href="feed.xml"><span>RSS feed</span><b>↗</b></a>
      </nav>
    </div>
    <details class="cut">
      <summary>What made the cut?</summary>
      <p><b>Kept:</b> AI tools, dev tools, useful websites, articles and GitHub repos — things a developer would actually use.</p>
      <p><b>Cut ({dropped}):</b> hype-only posts, exact duplicates, redundant announcement tweets, and links with no usable resource.</p>
      <p>Entries flagged <span class="warnmark">⚠</span> carry a caveat, typically an unverified claim from an announcement post.</p>
    </details>
  </aside>
  <div class="content">
  <div class="mainhead">
    <h2 class="shortlist-h" id="results">The shortlist</h2>
    <span class="mcount"><span id="mcount">{total} resources</span> · <button class="sharebtn" id="copyView" title="Copy a link to this exact view, filters included">Copy link</button></span>
  </div>
  <p class="shortlist-sub">Every kept resource, newest week first. Search and the sidebar filters narrow it down.</p>
  <main id="main">
{"".join(sections)}
  </main>
  <p class="empty" id="empty" style="display:none">Nothing matches — try a different search.</p>
  <section id="analytics" hidden>
    <div class="mainhead"><h2 class="shortlist-h">Analytics</h2><span class="mcount">{total} resources · {len(ordered)} sections</span></div>
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
  </div>
  </div>
  <footer>
    <span class="fsrc">Source: CheapInfra Discord · #share-tech + #providers</span> · Last updated {today_str}<br>
    Briefs are editorial summaries (~2 sentences); entries flagged <span class="warnmark">⚠</span> carry a caveat — typically unverified claims from Discord posts — lifted from the brief at build time.<br>
    Data: <a href="data.json">data.json</a> · Weekly lists: <a href="weeks/">weeks/</a> · Raw logs: <a href="raw/">raw/</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="feed.xml">RSS</a>
  </footer>
</div>
<button class="top" id="top" aria-label="Back to top">↑</button>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>
// theme: black is the default; the toggle offers the light editorial theme, choice remembered
const tt = document.getElementById('themeToggle');
const themeMeta = document.querySelector('meta[name="theme-color"]');
function syncThemeColor() {{
  if (themeMeta) themeMeta.content = document.documentElement.dataset.theme === 'light' ? '#f4f6f1' : '#0a0c0b';
}}
syncThemeColor();
function setTheme(t) {{
  document.documentElement.dataset.theme = t;
  try {{ localStorage.setItem('rl-theme', t); }} catch(e) {{}}
  syncThemeColor();
}}
if (tt) tt.addEventListener('click', () => {{
  const cur = document.documentElement.dataset.theme || 'dark';
  setTheme(cur === 'dark' ? 'light' : 'dark');
}});
// library filtering
const q = document.getElementById('search');
const cchips = [...document.querySelectorAll('.navrow[data-cat]')];
const wchips = [...document.querySelectorAll('.navrow[data-week]')];
const mcount = document.getElementById('mcount');
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
  if (mcount) mcount.textContent = visible === cards.length
    ? `${{cards.length}} resources` : `${{visible}} of ${{cards.length}} resources`;
  syncUrl();
  return visible;
}}
// filter state lives in the hash as key=value pairs so filtered views can be shared;
// plain hashes (#r-<id> permalinks, week anchors) are left alone
function syncUrl() {{
  const p = new URLSearchParams();
  if (activeCat) p.set('cat', activeCat);
  if (activeWeek) p.set('week', activeWeek);
  if (q.value.trim()) p.set('q', q.value.trim());
  const anEl = document.getElementById('analytics');
  if (anEl && !anEl.hidden) p.set('view', 'analytics');
  const s = p.toString();
  if (s) history.replaceState(null, '', '#' + s);
  else if (location.hash.includes('=')) history.replaceState(null, '', location.pathname + location.search);
}}
// only scroll when the results heading is out of view (e.g. scrolled deep, or sidebar stacked on mobile)
function goResults() {{
  if (!resultsH) return;
  const top = resultsH.getBoundingClientRect().top;
  if (top < 0 || top > innerHeight * 0.6) resultsH.scrollIntoView({{behavior: 'smooth', block: 'start'}});
}}
if (q) {{
  q.addEventListener('input', apply);
  q.addEventListener('keydown', (e) => {{ if (e.key === 'Enter') {{ apply(); goResults(); }} }});
}}
function setFilters(cat, week, term) {{
  activeCat = cat; activeWeek = week;
  if (term !== undefined) q.value = term;
  cchips.forEach(c => c.classList.toggle('active',
    c.dataset.cat === 'all' ? activeCat === null : c.dataset.cat === activeCat));
  wchips.forEach(c => c.classList.toggle('active', c.dataset.week === activeWeek));
  apply();
}}
for (const ch of cchips) ch.addEventListener('click', () => {{
  const cat = ch.dataset.cat === 'all' ? null : ch.dataset.cat;
  setFilters(activeCat === cat ? null : cat, activeWeek);
  goResults();
}});
for (const ch of wchips) ch.addEventListener('click', () => {{
  setFilters(activeCat, activeWeek === ch.dataset.week ? null : ch.dataset.week);
  goResults();
}});
// clear all: reset search text, category and week filters
const clearBtn = document.getElementById('clearAll');
if (clearBtn) clearBtn.addEventListener('click', () => {{
  setFilters(null, null, '');
  goResults();
}});
// copy-to-clipboard with a fallback for browsers without the async clipboard API
const toast = document.getElementById('toast');
let toastTimer;
function showToast(msg) {{
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 1800);
}}
async function copyLink(url, msg) {{
  try {{
    await navigator.clipboard.writeText(url);
  }} catch (e) {{
    const ta = document.createElement('textarea');
    ta.value = url; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); ta.remove();
  }}
  showToast(msg);
}}
const pageUrl = () => location.origin + location.pathname;
const copyView = document.getElementById('copyView');
if (copyView) copyView.addEventListener('click', () => copyLink(location.href,
  location.hash.includes('=') ? 'Link to this filtered view copied' : 'Link copied'));
// category tags and sharer names inside cards act as shortcuts into the filters
const mainEl = document.getElementById('main');
if (mainEl) mainEl.addEventListener('click', (e) => {{
  const plink = e.target.closest('.plink');
  if (plink) {{
    e.preventDefault();
    copyLink(pageUrl() + plink.getAttribute('href'), 'Link to this resource copied');
    return;
  }}
  const chip = e.target.closest('.chip[data-cat]');
  const who = e.target.closest('.who[data-sharer]');
  if (chip) setFilters(chip.dataset.cat, null, '');
  else if (who) setFilters(null, null, who.dataset.sharer);
  else return;
  goResults();
}});
// keyboard: "/" focuses search, Esc clears it
addEventListener('keydown', (e) => {{
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
  if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) {{
    e.preventDefault();
    if (an && !an.hidden) showTab('library');
    q.focus();
  }} else if (e.key === 'Escape' && document.activeElement === q) {{
    setFilters(activeCat, activeWeek, '');
    q.blur();
  }}
}});
// tabs: library / analytics
const tabs = [...document.querySelectorAll('.tab')];
const an = document.getElementById('analytics');
const libEls = [...document.querySelectorAll('.side-lib, .content > .mainhead, .shortlist-sub, #main')];
function showTab(name) {{
  const showAn = name === 'analytics';
  tabs.forEach(x => {{
    const on = x.dataset.tab === name;
    x.classList.toggle('active', on);
    x.setAttribute('aria-selected', on ? 'true' : 'false');
  }});
  if (an) an.hidden = !showAn;
  libEls.forEach(e => e.classList.toggle('lib-hidden', showAn));
  if (empty) empty.classList.toggle('lib-hidden', showAn);
  const target = showAn ? an : resultsH;
  if (target && target.getBoundingClientRect().top < 0) target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
  syncUrl();
}}
for (const t of tabs) t.addEventListener('click', () => showTab(t.dataset.tab));
// restore shared filter state from the URL
if (location.hash.includes('=')) {{
  const p = new URLSearchParams(location.hash.slice(1));
  const cat = cchips.some(c => c.dataset.cat === p.get('cat')) ? p.get('cat') : null;
  const week = wchips.some(c => c.dataset.week === p.get('week')) ? p.get('week') : null;
  setFilters(cat, week, p.get('q') || '');
  if (p.get('view') === 'analytics') showTab('analytics');
}}
// on narrow screens the sidebar stacks above the list, so start with the week list collapsed
const weekBlock = document.getElementById('weekBlock');
if (weekBlock && matchMedia('(max-width: 860px)').matches) weekBlock.open = false;
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
