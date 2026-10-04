"""Website chronology must not change the legacy content/export contract."""
import json
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


class LibraryHTML(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.cards = []
        self.groups = []
        self.ids = []
        self.group = None
        self.options = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "section" and "week" in attrs.get("class", "").split():
            self.group = attrs["id"]
            self.groups.append(self.group)
        if tag == "article":
            self.cards.append({**attrs, "parent": self.group})
        if tag == "option":
            self.options.append(attrs.get("value"))


def entry(title, day, categories):
    return (f"### {title}\n- URL: https://example.com/{title.lower().replace(' ', '-')}\n"
            f"- Posted by: tester, {day} 12:00 IST\n- Category: {categories}\n"
            "- Brief: Resource description. Small and useful.\n\n")


@pytest.fixture(scope="module")
def built_library(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("library-sorting")
    (tmp / "scripts").mkdir()
    (tmp / "notes").mkdir()
    shutil.copy(ROOT / "scripts/build.py", tmp / "scripts/build.py")
    (tmp / "notes/week.md").write_text(
        "## Week: 24 Sep–1 Oct 2026\n\n"
        + entry("Zara Tool", "30 Sep", "dev-tool, github")
        + entry("Alpha Article", "1 Oct", "article")
        + entry("Boundary App", "1 Oct", "web-app")
        + "## Week: 1–8 Oct 2026\n\n"
        + entry("Beta Repo", "1 Oct", "github")
        + entry("Delta AI", "4 Oct", "ai-tool"))
    (tmp / "notes/providers.md").write_text(
        "# Providers — collected in 2026\n\n## Providers\n\n"
        + entry("Omega Provider", "29 Sep", "providers")
        + entry("Early Provider", "16 Sep", "providers")
        + entry("Gamma Provider", "3 Oct", "providers"))
    (tmp / "notes/details-fixture.md").write_text(
        "## Details\n\n### delta-ai\n- Details: An existing expanded breakdown.\n")
    proc = subprocess.run([sys.executable, "scripts/build.py"], cwd=tmp,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return tmp, LibraryHTML((tmp / "index.html").read_text())


def test_static_library_is_newest_first_across_categories(built_library):
    _, html = built_library
    assert [c["id"] for c in html.cards] == [
        "r-delta-ai", "r-gamma-provider", "r-alpha-article", "r-beta-repo",
        "r-boundary-app", "r-zara-tool", "r-omega-provider", "r-early-provider",
    ]
    assert len({c["id"] for c in html.cards}) == 8


def test_presentation_period_does_not_replace_source_week(built_library):
    _, html = built_library
    cards = {c["id"]: c for c in html.cards}
    for identifier in ("r-alpha-article", "r-beta-repo", "r-boundary-app", "r-gamma-provider"):
        assert cards[identifier]["parent"] == "2026-10-01_to_2026-10-08"
    assert cards["r-alpha-article"]["data-week"] == "24 Sep–1 Oct 2026"
    assert cards["r-gamma-provider"]["data-week"] == "providers"
    assert cards["r-gamma-provider"]["data-date"] == "2026-10-03"
    assert cards["r-zara-tool"]["data-cats"] == "dev-tool github"
    assert cards["r-early-provider"]["parent"] == "date-2026-09-16"


def test_existing_anchors_and_all_six_sort_choices_exist(built_library):
    _, html = built_library
    assert "providers" in html.ids
    assert "2026-09-24_to_2026-10-01" in html.ids
    assert html.options == ["newest", "oldest", "title", "title-desc", "category", "category-desc"]
    assert len(html.ids) == len(set(html.ids))


def test_dataset_order_and_fields_remain_source_order(built_library):
    tmp, _ = built_library
    rows = json.loads((tmp / "data.json").read_text())
    assert [r["id"] for r in rows] == [
        "omega-provider", "early-provider", "gamma-provider", "zara-tool",
        "alpha-article", "boundary-app", "beta-repo", "delta-ai",
    ]
    assert rows[4]["week"] == "24 Sep–1 Oct 2026"
    assert list(rows[0]) == ["title", "week", "url", "sharer", "date", "categories",
                            "brief", "id", "warning", "details"]


@pytest.mark.skipif(shutil.which("agent-browser") is None, reason="agent-browser is not installed")
def test_interactive_sorts_preserve_filters_details_and_url(built_library):
    tmp, _ = built_library
    browser = ["agent-browser", "--namespace", "library-sort-tests", "--session", "sorting", "--json"]

    def run(*args):
        proc = subprocess.run([*browser, *args], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        result = json.loads(proc.stdout)
        assert result["success"], result
        return result

    try:
        run("open", (tmp / "index.html").as_uri())
        run("set", "viewport", "1280", "720", "2")
        run("eval", """(() => {
          const check = (condition, message) => { if (!condition) throw new Error(message); };
          const ids = () => [...document.querySelectorAll('.card:not(.hidden)')]
            .map(c => c.id.slice(2));
          const equal = (actual, expected, message) => check(
            JSON.stringify(actual) === JSON.stringify(expected), message + ': ' + actual);
          const select = document.getElementById('sortOrder');
          const sort = mode => { select.value = mode; select.dispatchEvent(new Event('change')); };
          const expectations = {
            newest: ['delta-ai','gamma-provider','alpha-article','beta-repo','boundary-app','zara-tool','omega-provider','early-provider'],
            oldest: ['early-provider','omega-provider','zara-tool','alpha-article','beta-repo','boundary-app','gamma-provider','delta-ai'],
            title: ['alpha-article','beta-repo','boundary-app','delta-ai','early-provider','gamma-provider','omega-provider','zara-tool'],
            'title-desc': ['zara-tool','omega-provider','gamma-provider','early-provider','delta-ai','boundary-app','beta-repo','alpha-article'],
            category: ['delta-ai','alpha-article','zara-tool','beta-repo','gamma-provider','omega-provider','early-provider','boundary-app'],
            'category-desc': ['boundary-app','gamma-provider','omega-provider','early-provider','beta-repo','zara-tool','alpha-article','delta-ai']
          };
          document.querySelector('#r-delta-ai .detail-toggle').click();
          for (const [mode, expected] of Object.entries(expectations)) {
            sort(mode);
            equal(ids(), expected, mode);
            check(document.querySelectorAll('.card').length === 8, 'Cards lost or duplicated');
            check(document.getElementById('r-delta-ai').classList.contains('open'), 'Details collapsed');
            check(new URLSearchParams(location.hash.slice(1)).get('sort') ===
              (mode === 'newest' ? null : mode), 'Sort URL mismatch');
          }
          document.getElementById('clearAll').click();
          document.querySelector('.navrow[data-cat="github"]').click();
          for (const mode of Object.keys(expectations)) {
            sort(mode);
            equal(ids().slice().sort(), ['beta-repo','zara-tool'], 'Multi-category filter');
          }
          document.getElementById('clearAll').click();
          document.querySelector('.navrow[data-week="24 Sep–1 Oct 2026"]').click();
          sort('category-desc');
          equal(ids(), ['boundary-app','zara-tool','alpha-article'], 'Source week filter');
          document.getElementById('clearAll').click();
          const search = document.getElementById('search');
          search.value = 'provider'; search.dispatchEvent(new Event('input'));
          sort('oldest');
          equal(ids(), ['early-provider','omega-provider','gamma-provider'], 'Search preserved');
          search.value = 'no-such-resource'; search.dispatchEvent(new Event('input'));
          equal(ids(), [], 'Empty results');
          check(getComputedStyle(document.getElementById('empty')).display !== 'none', 'Empty message hidden');
          document.getElementById('clearAll').click();
          equal(ids(), expectations.newest, 'Clear all order');
          check(select.value === 'newest' && !location.hash && !search.value, 'Clear all state');
          document.querySelector('[data-tab="analytics"]').click();
          check(select.getClientRects().length === 0, 'Sort leaked into Analytics');
          document.querySelector('[data-tab="api"]').click();
          check(select.getClientRects().length === 0, 'Sort leaked into API');
          document.querySelector('[data-tab="library"]').click();
          check(select.getClientRects().length > 0, 'Sort missing from Library');
          return 'All six sorting modes and interaction checks passed';
        })()""")
        run("open", (tmp / "index.html").as_uri() + "#sort=title-desc&cat=github&q=tool")
        run("reload")
        run("eval", """(() => {
          const ids = [...document.querySelectorAll('.card:not(.hidden)')].map(c => c.id);
          if (document.getElementById('sortOrder').value !== 'title-desc' ||
              document.getElementById('search').value !== 'tool' ||
              JSON.stringify(ids) !== JSON.stringify(['r-zara-tool'])) throw new Error('URL restore failed');
          return 'Shared sorting/filter state restored';
        })()""")
        run("open", (tmp / "index.html").as_uri() + "#sort=unsupported")
        run("reload")
        run("eval", """(() => {
          if (document.getElementById('sortOrder').value !== 'newest' || location.hash)
            throw new Error('Invalid sort did not fall back');
          return 'Invalid sort falls back to newest';
        })()""")
    finally:
        subprocess.run([*browser, "close"], capture_output=True, timeout=30)
