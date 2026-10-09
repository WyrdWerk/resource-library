#!/usr/bin/env python3
"""Build the CheapInfra #share-tech resource library repo.

Reads curated research notes from notes/*.md and regenerates:
  index.html   — the browsable site (search + category + week filters)
  data.json    — the full dataset (title, url, sharer, date, categories, brief, warning, week, id, details)
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


def parse_details(path):
    """Parse a details sidecar file (notes/details-*.md).

    Sections: '## Details' with '### <record-id>' entries carrying a
    '- Details:' bullet (multi-line continuations joined like briefs).
    Returns {record_id: details_text}. Ignored by parse_notes: no '## Week:'.
    """
    out = {}
    in_details = False
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("## Details"):
            in_details = True
        elif s.startswith("## ") and in_details:
            in_details = False
        elif line.startswith("### ") and in_details:
            rid = line[4:].strip()
            i += 1
            field, parts = None, []
            while i < len(lines) and not lines[i].startswith("#"):
                l = lines[i].rstrip()
                if l.startswith("- Details:"):
                    parts = [l[len("- Details:"):].strip()]; field = "details"
                elif field == "details" and l.strip():
                    parts.append(l.strip())
                elif not l.strip():
                    field = None
                i += 1
            text = " ".join(parts).strip()
            if text:
                out[rid] = text
            continue
        i += 1
    return out


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


def hbar_chart(items):
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
        # Preserve Providers-first source/export grouping. The website builds
        # its own chronological presentation below, without changing batches.
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

    # Details sidecars: notes/details-*.md merge a long-form breakdown into
    # the record by id ("" when a record has none yet). Sidecars keep existing
    # notes files byte-identical; parse_notes ignores them (no '## Week:').
    details_map = {}
    for f in sorted(NOTES_DIR.glob("details-*.md")):
        details_map.update(parse_details(f))
    for r in all_res:
        r["details"] = details_map.get(r["id"], "")

    dropped = count_dropped(NOTES_DIR.glob("*.md"))
    total = len(all_res)
    cats = sorted({c for r in all_res for c in r["categories"]})
    cat_counts = {c: sum(1 for r in all_res if c in r["categories"]) for c in cats}

    data = []
    for r in all_res:
        row = {k: v for k, v in r.items() if not k.startswith("_") and k != "details"}
        row["warning"] = r["_warn"]
        row["details"] = r.get("details", "")
        data.append(row)
    (ROOT / "data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ---- weeks/*.md ----
    WEEKS_DIR.mkdir(exist_ok=True)
    for old in WEEKS_DIR.glob("*.md"):
        old.unlink()
    for label in ordered:
        info = week_info[label]
        res = weeks[label]
        if label == "providers":
            md = ["# Inference providers — curated from CheapInfra #providers", "",
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
    # Keep source batches and exports unchanged; chronology is website-only.
    from datetime import date
    batch_years = {}
    for r in all_res:
        if r["week"] == "providers" and r["_batch"] not in batch_years:
            header = (NOTES_DIR / r["_batch"]).read_text().splitlines()[0]
            year = re.search(r"\b(20\d{2})\b", r["_batch"] + " " + header)
            batch_years[r["_batch"]] = int(year.group(1)) if year else _smax[0]
    library = []
    display_info = dict(week_info)
    for r in all_res:
        year = (batch_years[r["_batch"]] if r["week"] == "providers"
                else week_info[r["week"]]["start"][0])
        day, month = r["date"].split()
        shared = date(year, MONTHS[norm_mon(month)], int(day))
        period = next((label for label in _wk
                       if week_info[label]["start"] <= (year, shared.month, shared.day)
                       <= week_info[label]["end"]), None)
        if period is None:
            period = f"{shared.day} {MON_NAME[shared.month]} {year}"
            display_info[period] = {"label": period, "slug": "date-" + shared.isoformat()}
        library.append({**r, "_shared_on": shared, "_period": period})
    library.sort(key=lambda r: (-r["_shared_on"].toordinal(), r["title"].lower(), r["id"]))
    display_weeks = {}
    for r in library:
        display_weeks.setdefault(r["_period"], []).append(r)

    wrows = []
    for label in _wk:
        info = week_info[label]
        latest = ' <span class="newdot">new</span>' if label == _wk[0] else ''
        wrows.append(f'<button class="navrow" data-week="{esc(label)}"><span>{esc(info["label"])}{latest}</span><b>{len(weeks[label])}</b></button>')

    sections = []
    anchored = {display_info[label]["slug"] for label in display_weeks}
    for wi, (label, res) in enumerate(display_weeks.items()):
        info = display_info[label]
        wnum_html = f'<span class="weeknum">{wi + 1:02d}</span>'
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
            det = ""
            card_cls = "card"
            if r.get("details"):
                card_cls = "card has-details"
                det = (f'<button class="detail-toggle" aria-expanded="false" title="Show the detailed breakdown">'
                       f'Detailed breakdown <span class="dt-arrow">↓</span></button>'
                       f'<div class="detail-body"><p class="detail-kicker">In detail</p><p>{esc(r["details"])}</p></div>')
            source_slug = week_info[r["week"]]["slug"]
            anchor = ""
            if source_slug not in anchored:
                anchor = f'<span id="{source_slug}" aria-hidden="true"></span>'
                anchored.add(source_slug)
            cards.append(
                f'<article class="{card_cls}" id="r-{r["id"]}" data-cats="{" ".join(r["categories"])}" data-search="{blob}" '
                f'data-week="{esc(r["week"])}" data-date="{r["_shared_on"].isoformat()}" '
                f'data-title="{esc(r["title"].lower())}" data-period="{info["slug"]}">'
                f'<span class="cardnum">{ci + 1:02d}</span>'
                f'<div class="card-main">{anchor}'
                f'<h3><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a></h3>'
                f'<p>{esc(r["_desc"])}</p>'
                f'{warnbar}'
                f'<a class="dlink" href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(dom)} ↗</a>'
                f'{det}'
                f'</div>'
                f'<div class="card-side">'
                f'<div class="meta">{chips}</div>'
                f'<div class="side-row">Shared by <button class="who" data-sharer="{esc(r["sharer"])}" title="Search for {esc(r["sharer"])}">{esc(r["sharer"])}</button></div>'
                f'<div class="side-row">{esc(r["date"])} · <a class="plink" href="#r-{r["id"]}" title="Copy a link to this resource">Copy link</a></div>'
                f'</div>'
                f'</article>')
        badge = ' <span class="latest">Latest</span>' if wi == 0 else ''
        sections.append(
            f'<section class="week" id="{info["slug"]}">'
            f'<div class="weekhead">{wnum_html}<h2>{esc(info["label"])}</h2>{badge}'
            f'<span class="wcount">{len(res)} kept</span></div>'
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
.library-head {{ flex-wrap: wrap; }}
.headtools {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
#sortOrder {{
  font: inherit; font-size: 12px; color: var(--ink); background: var(--paper);
  border: 1px solid var(--line); border-radius: 6px; padding: 7px 9px;
  cursor: pointer;
}}
#sortOrder:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
#randomFive {{ font-size: 12px; padding: 7px 11px; border-radius: 6px; }}
.share-dialog {{
  width: min(720px, calc(100% - 32px)); max-height: calc(100svh - 40px);
  padding: 24px; border: 1px solid var(--line); border-radius: 12px;
  background: var(--paper); color: var(--ink); overflow: auto;
}}
.share-dialog::backdrop {{ background: rgba(0,0,0,.6); }}
.share-dialog .shortlist-h {{ font-size: 26px; }}
.share-actions {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 16px 0; }}
#pickAgain {{ margin-left: auto; font-size: 12px; }}
.random-picks {{ display: flex; flex-wrap: wrap; gap: 4px 22px; padding-left: 18px; margin: 14px 0; font-size: 12px; }}
.random-picks a {{ color: var(--accent); overflow-wrap: anywhere; }}
.draft-field {{ margin-top: 18px; }}
.draft-field label {{ display: block; font-size: 12px; font-weight: 600; margin-bottom: 8px; }}
.draft-field textarea {{
  display: block; width: 100%; padding: 12px; resize: vertical;
  border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--ink);
  font: inherit; font-size: 13px; line-height: 1.6;
}}
.draft-field textarea:focus-visible, .share-dialog button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.draft-field textarea[aria-invalid="true"] {{ border-color: var(--warm); }}
.draft-footer {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 8px; }}
.draft-count, #shareStatus, .share-hint {{ font-size: 12px; color: var(--muted); }}
#shareStatus {{ min-height: 1.6em; margin: 12px 0 0; }}
.share-dialog button:disabled, #randomFive:disabled {{ opacity: .45; cursor: default; }}
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
.card.has-details {{ cursor: pointer; }}
.detail-toggle {{
  display: block; margin: 10px 0 0; padding: 0; border: 0; background: none;
  font-size: 12.5px; font-weight: 700; color: var(--muted); cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}}
.detail-toggle:hover {{ color: var(--accent); }}
.detail-toggle .dt-arrow {{ display: inline-block; transition: transform 0.15s ease; }}
.card.open .detail-toggle .dt-arrow {{ transform: rotate(180deg); }}
.detail-body {{ display: none; margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--line); }}
.card.open .detail-body {{ display: block; }}
.detail-body .detail-kicker {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 10.5px;
  text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 0 0 8px;
}}
.detail-body p:last-child {{ margin-bottom: 0; }}
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
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 3px; padding: 3px;
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
/* ---- api docs ---- */
.codeblock {{
  margin: 0; padding: 13px 15px; background: var(--card); border: 1px solid var(--line);
  border-radius: 10px; overflow-x: auto; white-space: pre-wrap; overflow-wrap: anywhere;
  font: 500 12px/1.75 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: var(--ink);
}}
.codeblock .cmt {{ color: var(--muted); }}
.codeblock + .codeblock {{ margin-top: 10px; }}
.apitb {{ width: 100%; border-collapse: collapse; margin-top: 4px; font-size: 13px; }}
.apitb th {{
  text-align: left; font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase;
  color: var(--muted); font-weight: 700; padding: 6px 14px 6px 0; border-bottom: 1px solid var(--line);
}}
.apitb td {{ padding: 9px 14px 9px 0; border-bottom: 1px solid var(--line); vertical-align: top; }}
.apitb td:first-child {{
  font: 500 12px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  white-space: normal; overflow-wrap: break-word;
}}
.apitb code {{
  color: var(--accent); background: var(--accent-soft); padding: 1px 5px; border-radius: 4px;
  overflow-wrap: anywhere;
  font: 500 12px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}}
.apilinks {{ display: grid; gap: 12px; margin-top: 4px; }}
.apilinks a {{ color: var(--accent); text-decoration: none; font-weight: 650; font-size: 13.5px; }}
.apilinks a:hover {{ text-decoration: underline; }}
.apilinks span {{ display: block; color: var(--muted); font-weight: 400; font-size: 12.5px; }}
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
      <div class="tabs" role="tablist" aria-label="Library, analytics, or API">
        <button class="tab active" data-tab="library" role="tab" aria-selected="true">Library</button>
        <button class="tab" data-tab="analytics" role="tab" aria-selected="false">Analytics</button>
        <button class="tab" data-tab="api" role="tab" aria-selected="false">API</button>
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
    <div class="sblock">
      <div class="shead"><span class="eyebrow">For agents</span></div>
      <nav class="navlist">
        <a class="navrow" href="#view=api"><span>API documentation</span><b>→</b></a>
        <a class="navrow" href="llms.txt" target="_blank" rel="noopener"><span>llms.txt</span><b>↗</b></a>
        <a class="navrow" href="api/openapi.yaml" target="_blank" rel="noopener"><span>OpenAPI contract</span><b>↗</b></a>
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
  <div class="mainhead library-head">
    <h2 class="shortlist-h" id="results">The shortlist</h2>
    <div class="headtools">
      <select id="sortOrder" aria-label="Sort resources" title="Sort resources. Category sorting uses the first listed category.">
        <option value="newest">Newest first</option>
        <option value="oldest">Oldest first</option>
        <option value="title">Name A–Z</option>
        <option value="title-desc">Name Z–A</option>
        <option value="category">Category A–Z</option>
        <option value="category-desc">Category Z–A</option>
      </select>
      <button class="fchip" id="randomFive" title="Pick up to five matching resources and prepare a copy-only draft" aria-haspopup="dialog">Random 5</button>
      <span class="mcount"><span id="mcount">{total} resources</span> · <button class="sharebtn" id="copyView" title="Copy a link to this exact view, filters and sorting included">Copy link</button></span>
    </div>
  </div>
  <p class="shortlist-sub">Every kept resource. Sort the list, or narrow it with search and the sidebar filters.</p>
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
  <section id="apidocs" hidden>
    <div class="mainhead"><h2 class="shortlist-h">API</h2><span class="mcount">v1 · read-only · no auth</span></div>
    <p class="an-sub">The same curated catalog this site renders, served as plain JSON over plain GETs — built for scripts and agents, documented for humans. No keys, no accounts; responses carry ETags and per-endpoint cache headers, and cross-origin reads are allowed from anywhere.</p>
    <div class="an-grid">
      <div class="an-card wide">
        <h3>Quick start</h3>
        <p class="sub">Search ranks by a fixed lexical score over titles, briefs, taxonomy labels and curated aliases — deterministic, no embeddings. A query (<code>q</code>) is what selects results; facet filters narrow it, as comma-separated lists: OR within a family, AND across families. To browse without a query, page through <code>/resources</code>.</p>
        <pre class="codeblock"><span class="cmt"># search — 20 per page by default, cursor-paginated</span>
curl "{SITE_URL}/api/v1/search?q=vector+database"

<span class="cmt"># CSV facet filters (OR within a family)</span>
curl "{SITE_URL}/api/v1/search?q=react+components&amp;topic=frontend,design"

<span class="cmt"># providers only, newest first, trimmed to four fields</span>
curl "{SITE_URL}/api/v1/search?q=gpu&amp;channel=providers&amp;sort=newest&amp;fields=id,title,canonical_url,shared_on"

<span class="cmt"># date-bounded (inclusive), title-sorted</span>
curl "{SITE_URL}/api/v1/search?q=agent&amp;from=2026-09-01&amp;to=2026-09-30&amp;sort=title"

<span class="cmt"># one record by id; the whole catalog, 100 per page</span>
curl "{SITE_URL}/api/v1/resources/openrouter"
curl "{SITE_URL}/api/v1/resources?limit=100"</pre>
      </div>
      <div class="an-card wide">
        <h3>Endpoints</h3>
        <p class="sub">Base path <code>/api/v1/</code>. Undocumented paths under it fall back to this site's HTML, so use only the documented ones. Full contract: <a href="api/openapi.yaml">api/openapi.yaml</a>.</p>
        <table class="apitb">
          <tr><th>Endpoint</th><th>Returns</th><th>Cache</th></tr>
          <tr><td>GET /search</td><td>Lexical search with facet filters, date bounds, sort and cursor pagination — the workhorse. Response: <code>results</code> + <code>next_cursor</code> (+ echoed <code>query</code>, <code>filters</code>, <code>sort</code>, <code>limit</code>).</td><td>60 s</td></tr>
          <tr><td>GET /resources</td><td>Canonical records in stable order, paginated via <code>limit</code>/<code>cursor</code>. Response: <code>records</code> + <code>next_cursor</code> + <code>total</code>.</td><td>300 s</td></tr>
          <tr><td>GET /resources/{{id}}</td><td>One canonical record by id, e.g. <code>/api/v1/resources/openrouter</code>.</td><td>1 h</td></tr>
          <tr><td>GET /resources.json</td><td>Static snapshot: the full raw array of all records in one request, no envelope, no params.</td><td>asset</td></tr>
          <tr><td>GET /facets.json</td><td>Every valid filter value with its count, grouped by filter family.</td><td>asset</td></tr>
          <tr><td>GET /taxonomy.json</td><td>The controlled vocabularies behind the facets: label, definition and aliases per value, plus the query synonym map.</td><td>asset</td></tr>
          <tr><td>GET /index.json</td><td>Manifest: API version, build time, record count, channels, <code>resources_sha256</code> (compare it to detect updates), endpoint registry.</td><td>asset</td></tr>
        </table>
      </div>
      <div class="an-card wide">
        <h3>Parameters</h3>
        <p class="sub">Filters combine with AND logic. Search-only params are marked; <code>/resources</code> takes only <code>fields</code>, <code>limit</code> and <code>cursor</code>. Unknown params are ignored.</p>
        <table class="apitb">
          <tr><th>Param</th><th>Meaning</th></tr>
          <tr><td>q</td><td>Free-text search query <span style="color:var(--muted)">(search only)</span>. Needed for results — a request with filters but no <code>q</code> returns an empty list. Exact id or URL queries rank first.</td></tr>
          <tr><td>resource_type</td><td>Facet filter, CSV allowed — values OR-ed. Alias: <code>type</code>. <span style="color:var(--muted)">(search only)</span></td></tr>
          <tr><td>topic · use_case · interface · technology</td><td>Facet filters, CSV allowed — values OR-ed within each family. Every value must exist in <a href="api/v1/facets.json">facets.json</a>, or the request is a 400 <code>bad_filter</code>. <span style="color:var(--muted)">(search only)</span></td></tr>
          <tr><td>channel</td><td><code>share-tech</code> or <code>providers</code> — which Discord channel the resource came from. <span style="color:var(--muted)">(search only)</span></td></tr>
          <tr><td>open_source</td><td><code>true</code> keeps resources whose brief says open source; <code>false</code> keeps everything else, including unknown licenses — it means “not known to be open source”. <span style="color:var(--muted)">(search only)</span></td></tr>
          <tr><td>from · to</td><td>Inclusive <code>YYYY-MM-DD</code> bounds on the shared date <span style="color:var(--muted)">(search only)</span>; <code>from ≤ to</code> required.</td></tr>
          <tr><td>sort</td><td><code>relevance</code> (default) · <code>newest</code> · <code>oldest</code> · <code>title</code> <span style="color:var(--muted)">(search only)</span>.</td></tr>
          <tr><td>limit</td><td>Page size, 1–100, default 20.</td></tr>
          <tr><td>cursor</td><td>Opaque pagination cursor — pass back the <code>next_cursor</code> from the previous page.</td></tr>
          <tr><td>fields</td><td>CSV projection of a record's top-level fields, e.g. <code>fields=id,title,canonical_url</code>. Any field below except <code>details</code>; unknown names are a 400 <code>bad_fields</code>.</td></tr>
        </table>
      </div>
      <div class="an-card wide">
        <h3>Record shape</h3>
        <p class="sub">One canonical record per resource, validated against a JSON Schema at build time. Unknown facts stay <code>null</code> — nothing is inferred.</p>
        <table class="apitb">
          <tr><th>Field</th><th>Meaning</th></tr>
          <tr><td>id</td><td>Immutable slug, e.g. <code>openrouter</code>. Never regenerated.</td></tr>
          <tr><td>title · canonical_url</td><td>Display name and HTTPS destination (unique across the catalog).</td></tr>
          <tr><td>brief · caveat</td><td>The ~2-sentence editorial summary, and any warning lifted from it (typically an unverified claim), else <code>null</code>.</td></tr>
          <tr><td>details</td><td>Researched long-form breakdown written from the live page, or <code>null</code> until enriched — the “In detail” text on library cards.</td></tr>
          <tr><td>resource_type · topics · use_cases · interfaces · technologies</td><td>Taxonomy facets — the same slugs the filters take.</td></tr>
          <tr><td>source · shared_on</td><td><code>{{"channel", "sharer"}}</code> (Discord channel and username) and the <code>YYYY-MM-DD</code> date it was shared.</td></tr>
          <tr><td>open_source · license</td><td><code>true</code> only when the brief says so, else <code>null</code>; license is <code>null</code> unless verified.</td></tr>
          <tr><td>display_period · legacy_categories</td><td>The site's week label (or <code>providers</code>) and its six display categories.</td></tr>
          <tr><td>verification · schema_version</td><td>Link-check status (<code>unchecked</code> for now) and the record schema version (<code>1.0</code>).</td></tr>
        </table>
      </div>
      <div class="an-card">
        <h3>Conventions &amp; errors</h3>
        <p class="sub">Predictable by design — the whole surface is byte-reproducible and covered by a parity gate against production.</p>
        <table class="apitb">
          <tr><th>Thing</th><th>Behavior</th></tr>
          <tr><td>Methods</td><td>GET, HEAD, OPTIONS only — anything else is a 405.</td></tr>
          <tr><td>CORS</td><td><code>Access-Control-Allow-Origin: *</code> on every response.</td></tr>
          <tr><td>Caching</td><td>ETag on every response; send <code>If-None-Match</code> to get a 304. <code>Last-Modified</code> is the catalog build time.</td></tr>
          <tr><td>Pagination</td><td>Pass <code>next_cursor</code> back unchanged with the same params; <code>null</code> means the last page. Search responses carry no total.</td></tr>
          <tr><td>Errors</td><td><code>{{"error": {{"code", "message"}}}}</code> — 400: <code>bad_fields</code>, <code>bad_limit</code>, <code>bad_cursor</code>, <code>bad_filter</code>, <code>bad_sort</code>; 404: <code>not_found</code>; 405: <code>method_not_allowed</code>; 500: <code>internal</code>; 503: <code>catalog_unavailable</code>.</td></tr>
          <tr><td>Versioning</td><td>Within v1, changes are additive only — fields and endpoints are never renamed or removed.</td></tr>
        </table>
      </div>
      <div class="an-card">
        <h3>Machine-readable docs</h3>
        <p class="sub">Everything an agent needs, linked for direct fetching.</p>
        <div class="apilinks">
          <a href="llms.txt" target="_blank" rel="noopener">llms.txt<span>A compact, agent-oriented index of this site and its API, with usage examples.</span></a>
          <a href="api/openapi.yaml" target="_blank" rel="noopener">api/openapi.yaml<span>The OpenAPI 3.1 contract for every endpoint.</span></a>
          <a href="api/v1/facets.json" target="_blank" rel="noopener">api/v1/facets.json<span>Every valid filter value, with counts.</span></a>
          <a href="docs/runbook.md" target="_blank" rel="noopener">docs/runbook.md<span>How the API is built, tested, audited and deployed.</span></a>
          <a href="docs/api-spec.md" target="_blank" rel="noopener">docs/api-spec.md<span>The original design spec — the OpenAPI contract wins where they differ.</span></a>
          <a href="{REPO_URL}" target="_blank" rel="noopener">GitHub repository<span>Source, catalog records, and the full history.</span></a>
        </div>
      </div>
    </div>
  </section>
  </div>
  </div>
  <footer>
    <span class="fsrc">Source: CheapInfra Discord · #share-tech + #providers</span> · Last updated {today_str}<br>
    Briefs are editorial summaries (~2 sentences); entries flagged <span class="warnmark">⚠</span> carry a caveat — typically unverified claims from Discord posts — lifted from the brief at build time.<br>
    Data: <a href="data.json">data.json</a> · Weekly lists: <a href="weeks/">weeks/</a> · Raw logs: <a href="raw/">raw/</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="feed.xml">RSS</a> · <a href="#view=api">API</a>
  </footer>
</div>
<button class="top" id="top" aria-label="Back to top">↑</button>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<dialog class="share-dialog" id="randomShare" aria-labelledby="randomTitle" aria-describedby="randomScope">
  <div class="mainhead">
    <h2 class="shortlist-h" id="randomTitle">Random picks</h2>
    <button class="fchip" id="closeRandom" autofocus>Close</button>
  </div>
  <p class="shortlist-sub" id="randomScope"></p>
  <ol class="random-picks" id="randomPicks"></ol>
  <div class="share-actions">
    <button class="fchip active" data-share-format="linkedin" aria-pressed="true">LinkedIn</button>
    <button class="fchip" data-share-format="x" aria-pressed="false">X post</button>
    <button class="sharebtn" id="pickAgain" title="Pick new resources and replace the drafts, including your edits">Pick again</button>
  </div>
  <div id="linkedinDraft"></div>
  <div id="xDraft" hidden>
    <p class="share-hint">One post. Up to three complete descriptions, fewer when needed. X counts are conservative estimates.</p>
  </div>
  <p id="shareStatus" role="status" aria-live="polite"></p>
</dialog>
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
const sortOrder = document.getElementById('sortOrder');
const randomFive = document.getElementById('randomFive');
const mainEl = document.getElementById('main');
const catLabels = {json.dumps(CAT_LABELS)};
const dateSections = [...mainEl.querySelectorAll('.week')];
const categorySections = new Map();
const nameSection = document.createElement('section');
nameSection.className = 'week';
const cmp = (a, b) => a < b ? -1 : a > b ? 1 : 0;
function compareCards(a, b) {{
  const mode = sortOrder.value;
  const title = cmp(a.dataset.title, b.dataset.title);
  const date = cmp(a.dataset.date, b.dataset.date);
  if (mode === 'title' || mode === 'title-desc') {{
    return (mode === 'title-desc' ? -title : title) || cmp(a.id, b.id);
  }}
  if (mode === 'category' || mode === 'category-desc') {{
    const category = cmp(catLabels[a.dataset.cats.split(' ')[0]], catLabels[b.dataset.cats.split(' ')[0]]);
    return (mode === 'category-desc' ? -category : category) || -date || title || cmp(a.id, b.id);
  }}
  return (mode === 'oldest' ? date : -date) || title || cmp(a.id, b.id);
}}
function renderOrder() {{
  const mode = sortOrder.value;
  let sections, groupFor;
  if (mode.startsWith('category')) {{
    const cats = Object.keys(catLabels).sort((a, b) =>
      cmp(catLabels[a], catLabels[b]) * (mode === 'category-desc' ? -1 : 1));
    sections = cats.map(cat => {{
      if (!categorySections.has(cat)) {{
        const section = document.createElement('section');
        section.className = 'week';
        const header = document.createElement('div');
        header.className = 'weekhead';
        const title = document.createElement('h2');
        title.textContent = catLabels[cat];
        const count = document.createElement('span');
        count.className = 'wcount';
        header.append(title, count);
        section.append(header);
        categorySections.set(cat, section);
      }}
      return categorySections.get(cat);
    }});
    groupFor = c => categorySections.get(c.dataset.cats.split(' ')[0]);
  }} else if (mode.startsWith('title')) {{
    sections = [nameSection];
    groupFor = () => nameSection;
  }} else {{
    sections = mode === 'oldest' ? [...dateSections].reverse() : dateSections;
    const byPeriod = new Map(dateSections.map(s => [s.id, s]));
    groupFor = c => byPeriod.get(c.dataset.period);
  }}
  for (const section of sections) {{
    const header = section.querySelector('.weekhead');
    section.replaceChildren(...(header ? [header] : []));
  }}
  for (const card of [...cards].sort(compareCards)) groupFor(card).append(card);
  let number = 0;
  for (const section of sections) {{
    const visible = [...section.querySelectorAll('.card:not(.hidden)')];
    section.classList.toggle('hidden', !visible.length);
    visible.forEach((card, i) => {{ card.querySelector('.cardnum').textContent = String(i + 1).padStart(2, '0'); }});
    const count = section.querySelector('.wcount');
    if (count) count.textContent = `${{visible.length}} kept`;
    const ordinal = section.querySelector('.weeknum');
    if (ordinal && visible.length) ordinal.textContent = String(++number).padStart(2, '0');
  }}
  mainEl.replaceChildren(...sections);
}}
// expandable detail breakdowns: clicking anywhere on a card toggles its
// detail section, except on links and buttons which keep native behavior
for (const c of document.querySelectorAll('.card.has-details')) {{
  const btn = c.querySelector('.detail-toggle');
  const toggle = () => {{
    const open = !c.classList.contains('open');
    c.classList.toggle('open', open);
    if (btn) btn.setAttribute('aria-expanded', String(open));
  }};
  if (btn) btn.addEventListener('click', (e) => {{ e.stopPropagation(); toggle(); }});
  c.addEventListener('click', (e) => {{
    if (e.target.closest('a, button')) return;
    toggle();
  }});
}}
const empty = document.getElementById('empty');
const resultsH = document.getElementById('results');
let activeCat = null, activeWeek = null;
function apply() {{
  const term = q.value.trim().toLowerCase();
  let visible = 0;
  for (const c of cards) {{
    const okCat = !activeCat || c.dataset.cats.split(' ').includes(activeCat);
    const okWeek = !activeWeek || c.dataset.week === activeWeek;
    const okQ = !term || c.dataset.search.includes(term);
    const show = okCat && okWeek && okQ;
    c.classList.toggle('hidden', !show);
    if (show) visible++;
  }}
  renderOrder();
  if (empty) empty.style.display = visible ? 'none' : 'block';
  if (mcount) mcount.textContent = visible === cards.length
    ? `${{cards.length}} resources` : `${{visible}} of ${{cards.length}} resources`;
  randomFive.disabled = !visible;
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
  if (sortOrder.value !== 'newest') p.set('sort', sortOrder.value);
  const anEl = document.getElementById('analytics');
  if (anEl && !anEl.hidden) p.set('view', 'analytics');
  const apiEl = document.getElementById('apidocs');
  if (apiEl && !apiEl.hidden) p.set('view', 'api');
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
sortOrder.addEventListener('change', () => {{ apply(); goResults(); }});
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
  sortOrder.value = 'newest';
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
  const modal = document.querySelector('dialog[open]');
  try {{
    await navigator.clipboard.writeText(url);
  }} catch (e) {{
    const ta = document.createElement('textarea');
    const focus = document.activeElement;
    ta.value = url; ta.style.position = 'fixed'; ta.style.left = '-9999px';
    (modal || document.body).appendChild(ta);
    ta.select();
    let copied = false;
    try {{ copied = document.execCommand('copy'); }} catch (e) {{}}
    ta.remove(); focus.focus({{preventScroll: true}});
    if (!copied) {{
      if (!modal) showToast('Copy failed — select and copy the text manually');
      return false;
    }}
  }}
  if (!modal) showToast(msg);
  return true;
}}
const pageUrl = () => location.origin + location.pathname;
const copyView = document.getElementById('copyView');
if (copyView) copyView.addEventListener('click', () => copyLink(location.href,
  location.hash.includes('=') ? 'Link to this filtered view copied' : 'Link copied'));
// Random discovery is a snapshot of matching cards, not another library filter.
const shareDialog = document.getElementById('randomShare');
const shareStatus = document.getElementById('shareStatus');
const shareFormats = [...document.querySelectorAll('[data-share-format]')];
const linkedinDraft = document.getElementById('linkedinDraft');
const xDraft = document.getElementById('xDraft');
let selectedCards = [], xCards = [], matchingCount = 0;
const textWeight = text => [...text].reduce((n, c) => n + (c.codePointAt(0) > 127 ? 2 : 1), 0);
const xLength = text => textWeight(text.replace(/https?:\\/\\/\\S+/g, ' '.repeat(23)));
function shareIntro(count, format) {{
  const heading = `${{count === 1 ? 'A useful resource' : 'Some useful resources'}} from ${{format === 'x' ? 'CheapInfra' : 'the CheapInfra Resource Library'}}.`;
  const source = {json.dumps(SITE_URL + '/')};
  return heading + '\\n' + (format === 'x' ? source : 'Curated from developer resources shared in CheapInfra Discord: ' + source);
}}
function shortLine(text, limit) {{
  const clean = text.replace(/\\s+/g, ' ').trim();
  if (textWeight(clean) <= limit) return clean;
  let excerpt = '';
  for (const c of clean) {{
    if (textWeight(excerpt + c + '…') > limit) break;
    excerpt += c;
  }}
  const space = excerpt.lastIndexOf(' ');
  if (space > excerpt.length * .65) excerpt = excerpt.slice(0, space);
  return excerpt.trimEnd() + '…';
}}
function shareEntry(card, limit) {{
  const url = card.querySelector('h3 a').getAttribute('href');
  const description = card.querySelector('.card-main > p').textContent.split(/(?<=[.!?])\\s+(?=[A-Z"'])/)[0];
  const warning = card.querySelector('.warnbar');
  const caveat = warning ? ' Caveat: ' + shortLine(warning.textContent.replace(/^⚠\\s*/, ''), Math.min(70, Math.floor(limit / 2))) : '';
  return url + '\\n' + shortLine(description, limit - textWeight(caveat)) + caveat;
}}
function xShareEntry(card) {{
  const url = card.querySelector('h3 a').getAttribute('href');
  const sentence = card.querySelector('.card-main > p').textContent
    .replace(/\\s+/g, ' ').trim().split(/(?<=[.!?])\\s+(?=[A-Z"'])/)[0];
  // Keep a descriptive lead before optional detail lists, never a character-cut fragment.
  const lead = sentence.split(/\\s+[—–]\\s+|:\\s+|;\\s+/)[0].trim();
  let description = lead.split(' ').length >= 4 && !/\\b(a|an|the|and|or|for|with|of|to|is|are)$/i.test(lead) ? lead : sentence;
  if (!/[.!?。！？]["'”’)]?$/.test(description)) description += '.';
  const warning = card.querySelector('.warnbar');
  const caveat = warning ? ' Caveat: ' + warning.textContent.replace(/^⚠\\s*/, '').replace(/\\s+/g, ' ').trim() : '';
  return url + '\\n' + description + caveat;
}}
function addDraft(container, text, label, format) {{
  const field = document.createElement('div');
  field.className = 'draft-field';
  const title = document.createElement('label');
  const ta = document.createElement('textarea');
  ta.id = `${{format}}-draft-${{container.querySelectorAll('textarea').length}}`;
  title.htmlFor = ta.id; title.textContent = label;
  ta.rows = format === 'x' ? xCards.length * 3 + 3 : 24; ta.value = text;
  const footer = document.createElement('div'); footer.className = 'draft-footer';
  const count = document.createElement('span'); count.className = 'draft-count';
  const copy = document.createElement('button'); copy.className = 'fchip';
  copy.dataset.copyDraft = ''; copy.textContent = format === 'x' ? 'Copy post' : 'Copy draft';
  const update = () => {{
    const length = format === 'x' ? xLength(ta.value) : ta.value.length;
    const limit = format === 'x' ? 280 : 3000;
    count.textContent = `${{length}} / ${{limit}}${{length > limit ? ' · Shorten before copying' : ''}}`;
    ta.setAttribute('aria-invalid', String(length > limit));
    copy.disabled = !ta.value.trim() || length > limit;
    shareStatus.textContent = '';
  }};
  ta.addEventListener('input', update);
  copy.addEventListener('click', async () => {{
    const ok = await copyLink(ta.value, 'Draft copied');
    shareStatus.textContent = ok ? 'Draft copied. Paste it when you’re ready.' : 'Copy failed. Select and copy the draft manually.';
    if (!ok) {{ ta.focus(); ta.select(); }}
  }});
  footer.append(count, copy); field.append(title, ta, footer); container.append(field);
  update();
}}
function showShareFormat(format) {{
  const showX = format === 'x';
  linkedinDraft.hidden = showX; xDraft.hidden = !showX;
  shareFormats.forEach(button => {{
    const active = button.dataset.shareFormat === format;
    button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active));
  }});
  const included = showX ? xCards : selectedCards;
  const picks = document.getElementById('randomPicks'); picks.replaceChildren();
  included.forEach(card => {{
    const link = card.querySelector('h3 a');
    const item = document.createElement('li'); const a = document.createElement('a');
    a.textContent = link.textContent; a.href = link.href; a.target = '_blank'; a.rel = 'noopener';
    item.append(a); picks.append(item);
  }});
  document.getElementById('randomTitle').textContent = showX && !included.length
    ? 'No complete X post fits these picks' : `${{included.length}} random pick${{included.length === 1 ? '' : 's'}}`;
  const picked = included.length === selectedCards.length ? String(included.length) : `${{included.length}} of ${{selectedCards.length}}`;
  document.getElementById('randomScope').textContent = `${{picked}} picks from ${{matchingCount}} matching resources. Copy only — nothing is posted.`;
  shareStatus.textContent = '';
}}
function pickRandom() {{
  const pool = [...mainEl.querySelectorAll('.card:not(.hidden)')];
  const size = Math.min(5, pool.length);
  if (!size) return;
  for (let i = 0; i < size; i++) {{
    const j = i + Math.floor(Math.random() * (pool.length - i));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }}
  matchingCount = pool.length; selectedCards = pool.slice(0, size);
  const entries = selectedCards.map(card => shareEntry(card, 160));
  const xEntries = [];
  xCards = [];
  for (const card of selectedCards) {{
    const entry = xShareEntry(card);
    const candidate = shareIntro(xCards.length + 1, 'x') + '\\n\\n' + [...xEntries, entry].join('\\n\\n');
    if (xLength(candidate) > 280) continue;
    xCards.push(card); xEntries.push(entry);
    if (xCards.length === 3) break;
  }}
  linkedinDraft.replaceChildren();
  xDraft.querySelectorAll('.draft-field').forEach(el => el.remove());
  xDraft.querySelector('.share-hint').textContent = xCards.length
    ? 'One post. Up to three complete descriptions, fewer when needed. X counts are conservative estimates.'
    : 'These descriptions need more room than one X post. Pick again or use LinkedIn; no descriptions were cut.';
  addDraft(linkedinDraft, shareIntro(selectedCards.length, 'linkedin') + '\\n\\n' + entries.join('\\n\\n'), 'Ready-to-paste LinkedIn post', 'linkedin');
  const xText = xCards.length ? shareIntro(xCards.length, 'x') + '\\n\\n' + xEntries.join('\\n\\n') : '';
  addDraft(xDraft, xText, `${{xCards.length}} resource${{xCards.length === 1 ? '' : 's'}} in one post`, 'x');
  showShareFormat(xDraft.hidden ? 'linkedin' : 'x');
}}
randomFive.addEventListener('click', () => {{ pickRandom(); shareDialog.showModal(); }});
document.getElementById('pickAgain').addEventListener('click', pickRandom);
document.getElementById('closeRandom').addEventListener('click', () => shareDialog.close());
shareFormats.forEach(button => button.addEventListener('click', () => showShareFormat(button.dataset.shareFormat)));
// category tags and sharer names inside cards act as shortcuts into the filters
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
    if ((an && !an.hidden) || (apid && !apid.hidden)) showTab('library');
    q.focus();
  }} else if (e.key === 'Escape' && document.activeElement === q) {{
    setFilters(activeCat, activeWeek, '');
    q.blur();
  }}
}});
// tabs: library / analytics / api
const tabs = [...document.querySelectorAll('.tab')];
const an = document.getElementById('analytics');
const apid = document.getElementById('apidocs');
const libEls = [...document.querySelectorAll('.side-lib, .content > .mainhead, .shortlist-sub, #main')];
function showTab(name) {{
  const showAn = name === 'analytics';
  const showApi = name === 'api';
  const hideLib = showAn || showApi;
  tabs.forEach(x => {{
    const on = x.dataset.tab === name;
    x.classList.toggle('active', on);
    x.setAttribute('aria-selected', on ? 'true' : 'false');
  }});
  if (an) an.hidden = !showAn;
  if (apid) apid.hidden = !showApi;
  libEls.forEach(e => e.classList.toggle('lib-hidden', hideLib));
  if (empty) empty.classList.toggle('lib-hidden', hideLib);
  const target = showAn ? an : (showApi ? apid : resultsH);
  if (target && target.getBoundingClientRect().top < 0) target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
  syncUrl();
}}
for (const t of tabs) t.addEventListener('click', () => showTab(t.dataset.tab));
// sidebar/footer links with href="#view=api" open the API tab in place (and stay shareable)
for (const a of document.querySelectorAll('a[href="#view=api"]')) a.addEventListener('click', (e) => {{
  e.preventDefault();
  showTab('api');
}});
// restore shared filter state from the URL
if (location.hash.includes('=')) {{
  const p = new URLSearchParams(location.hash.slice(1));
  const cat = cchips.some(c => c.dataset.cat === p.get('cat')) ? p.get('cat') : null;
  const week = wchips.some(c => c.dataset.week === p.get('week')) ? p.get('week') : null;
  sortOrder.value = [...sortOrder.options].some(o => o.value === p.get('sort')) ? p.get('sort') : 'newest';
  setFilters(cat, week, p.get('q') || '');
  if (p.get('view') === 'analytics') showTab('analytics');
  else if (p.get('view') === 'api') showTab('api');
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

    # ---- robots.txt / sitemap.xml / llms.txt ----
    (ROOT / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n")

    # lastmod from the newest collection window, not the build clock, so a
    # rebuild with unchanged notes produces a byte-identical sitemap and
    # crawlers only see a new lastmod when content actually changed
    _lm = max(info["end"] for l, info in week_info.items() if info["end"])
    lastmod = f"{_lm[0]:04d}-{_lm[1]:02d}-{_lm[2]:02d}"
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'<url><loc>{SITE_URL}/</loc><lastmod>{lastmod}</lastmod>'
        '<changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
        '</urlset>\n')
    (ROOT / "sitemap.xml").write_text(sitemap)

    n_details = sum(1 for r in all_res if r.get("details"))
    llms = f"""# Resource Library — CheapInfra #share-tech + #providers
> {total} curated developer resources shared in the CheapInfra Discord's #share-tech and #providers channels: AI tools, dev tools, websites, articles, GitHub repos, and inference providers. Every entry carries a ~2-sentence editorial brief, its sharer, its share date, and controlled taxonomy facets; {n_details} also carry a researched long-form `details` breakdown. The site is a single HTML page ({SITE_URL}/); the same catalog is served by a read-only JSON API v1 — GET only, no auth, CORS-open, ETag-cached, deterministic.

Base URL: {SITE_URL}/api/v1 — collected read-only from Discord, refreshed by a daily run; content is CC-BY-4.0.

## API

- [Search]({SITE_URL}/api/v1/search?q=vector+database): deterministic lexical search over title, brief, taxonomy labels, and curated aliases; exact id or URL queries rank first. `q` is required to get results — filters narrow a query, they do not browse on their own. Params: q, resource_type (alias type), topic, use_case, interface, technology, channel, open_source, from/to (inclusive YYYY-MM-DD on shared_on), sort=relevance|newest|oldest|title, limit (1-100, default 20), cursor, fields. Facet params accept CSV lists — OR within a family, AND across families; every value must exist in facets.json. Response: query, filters, sort, limit, results, next_cursor.
- [All records]({SITE_URL}/api/v1/resources?limit=100): every canonical record in stable order, paginated (fields, limit, cursor). Response: records, next_cursor, total. Use this (or resources.json) to browse or filter without a query.
- [One record]({SITE_URL}/api/v1/resources/openrouter): canonical record by immutable id
- [Static snapshot]({SITE_URL}/api/v1/resources.json): full raw array of all records in one request (no envelope, no params)
- [Facets]({SITE_URL}/api/v1/facets.json): every valid filter value with its record count, keyed by filter param name
- [Taxonomy]({SITE_URL}/api/v1/taxonomy.json): label, definition, and aliases for every facet value, plus the query synonym map
- [Manifest]({SITE_URL}/api/v1/index.json): api_version, generated_at, record_count, channels, resources_sha256 — compare the hash to detect catalog updates

Examples:
- {SITE_URL}/api/v1/search?q=react+components&topic=frontend,design
- {SITE_URL}/api/v1/search?q=gpu&channel=providers&sort=newest&fields=id,title,canonical_url,shared_on
- {SITE_URL}/api/v1/search?q=agent&from=2026-09-01&to=2026-09-30&sort=title&limit=50
- {SITE_URL}/api/v1/search?q=mcp&interface=mcp&open_source=true

## Record fields

id, title, canonical_url, brief, caveat (warning lifted from the brief, or null), details (long-form breakdown, or null), resource_type, topics, use_cases, interfaces, technologies, license (null unless verified), open_source (true / null — never inferred), display_period (site week label or "providers"), legacy_categories (ai-tool, dev-tool, github, web-app, article, providers), source {{channel, sharer}}, shared_on (YYYY-MM-DD), verification {{status, checked_at, final_url}}, schema_version. `fields` can select any of these except details.

## Docs

- [OpenAPI 3.1 contract]({SITE_URL}/api/openapi.yaml): every endpoint, param, header, error, and response schema
- [Runbook]({SITE_URL}/docs/runbook.md): build, test, audit, and deploy commands
- [API spec]({SITE_URL}/docs/api-spec.md): the original design spec (the OpenAPI contract wins where they differ)

## Site

- [Home]({SITE_URL}/): the browsable library — Library, Analytics, and API tabs; filters shareable via URL hash
- [data.json]({SITE_URL}/data.json): full site dataset (legacy row shape)
- [RSS]({SITE_URL}/feed.xml): all resources, newest first
- [Sitemap]({SITE_URL}/sitemap.xml)

## Notes

- Errors are JSON: {{"error": {{"code", "message"}}}}. Codes: bad_fields, bad_limit, bad_cursor, bad_filter, bad_sort (400), not_found (404), method_not_allowed (405), internal (500), catalog_unavailable (503).
- Methods: GET, HEAD, OPTIONS only (405 otherwise). CORS: Access-Control-Allow-Origin: * on every response. ETag/If-None-Match honored (304); Last-Modified is the catalog build time.
- Unknown paths under /api/v1/ return the site's HTML, not JSON — use only the documented paths.
- Cache-Control: search 60s, resources 300s, single record 3600s; static *.json assets use asset caching.
- open_source=false matches every record not known to be open source (license unknown included), not "closed source".
- Pagination: pass next_cursor back unchanged with the same params. On /search an unknown cursor restarts at page one; on /resources it is a 400 bad_cursor. Search responses have no total.
- Versioning: within v1, changes are additive only — fields and endpoints are never renamed or removed.
"""
    (ROOT / "llms.txt").write_text(llms)

    print(f"resources: {total}")
    for label in ordered:
        print(f"  {label}: {len(weeks[label])}")


if __name__ == "__main__":
    main()
