"""Copy-only sharing samples the current library view without changing it."""
import json
import shutil
import subprocess

import pytest

from tests.test_library_sorting import built_library


@pytest.mark.skipif(shutil.which("agent-browser") is None, reason="agent-browser is not installed")
def test_random_drafts_preserve_filters_content_edits_and_copy(built_library):
    tmp, _ = built_library
    browser = ["agent-browser", "--namespace", "random-share-tests", "--session", "draft", "--json"]

    def run(*args):
        proc = subprocess.run([*browser, *args], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        result = json.loads(proc.stdout)
        assert result["success"], result
        return result

    try:
        run("open", (tmp / "index.html").as_uri())
        run("set", "viewport", "1280", "720", "2")
        run("eval", r"""(async () => {
          const check = (ok, msg) => { if (!ok) throw new Error(msg); };
          const equal = (a, b, msg) => check(JSON.stringify(a) === JSON.stringify(b), msg);
          const button = document.getElementById('randomFive');
          check(button, 'Random 5 control missing');
          const dialog = document.getElementById('randomShare');
          const picks = () => [...document.querySelectorAll('#randomPicks a')].map(a => a.textContent);
          const format = name => document.querySelector('[data-share-format="'+name+'"]').click();
          const original = document.getElementById('main').innerHTML;
          const hash = location.hash;
          const draws = [0, .99, .25, .8, .6];
          Math.random = () => draws.shift() ?? 0;
          button.focus(); button.click();
          check(dialog.open, 'Draft dialog did not open');
          equal(picks(), ['Delta AI','Early Provider','Beta Repo','Gamma Provider','Omega Provider'], 'Wrong random sample');
          check(document.getElementById('main').innerHTML === original && location.hash === hash, 'Library view changed');
          check(document.activeElement.closest('dialog') === dialog, 'Focus escaped dialog');
          const draft = document.querySelector('#linkedinDraft textarea');
          const source = 'https://cheapinfra-resources.wyrdwerk.com/';
          const linkedinIntro = 'Some useful resources from the CheapInfra Resource Library.\n'
            + 'Curated from developer resources shared in CheapInfra Discord: ' + source;
          const entries = ['Delta AI','Early Provider','Beta Repo','Gamma Provider','Omega Provider'].map(title =>
            `https://example.com/${title.toLowerCase().replaceAll(' ','-')}\nResource description.`
          );
          const expected = linkedinIntro + '\n\n' + entries.join('\n\n');
          check(draft.value === expected, 'LinkedIn draft must include the library, source and five concise resources');
          check(draft.scrollHeight <= draft.clientHeight + 2, 'Five short entries are clipped in the desktop draft');
          draft.value += '\nMy own note.'; draft.dispatchEvent(new Event('input'));
          format('x');
          check(document.querySelectorAll('#xDraft textarea').length === 1, 'X must be a single post');
          const xPost = document.querySelector('#xDraft textarea');
          const xExpected = 'Some useful resources from CheapInfra.\n' + source
            + '\n\n' + entries.slice(0,3).join('\n\n');
          check(xPost.value === xExpected, 'X must introduce useful resources and include only the three entries that fit');
          xPost.value = 'https://example.com/a\n' + 'a'.repeat(256); xPost.dispatchEvent(new Event('input'));
          check(!document.querySelector('#xDraft [data-copy-draft]').disabled, '280-character X boundary rejected');
          xPost.value += 'a'; xPost.dispatchEvent(new Event('input'));
          check(document.querySelector('#xDraft [data-copy-draft]').disabled, 'Oversized X post advertised as ready');
          format('linkedin');
          check(draft.value.endsWith('My own note.'), 'Format switch lost edits');
          let copied = null;
          Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async text => { copied=text; }}});
          document.querySelector('#linkedinDraft [data-copy-draft]').click();
          await new Promise(r => setTimeout(r, 50));
          check(copied === draft.value, 'Clipboard did not receive reviewed draft');
          check(document.getElementById('shareStatus').textContent.includes('copied'), 'Copy confirmation missing');
          check(!document.getElementById('toast').classList.contains('show'), 'Duplicate copy toast leaked behind the dialog');
          draft.value = 'a'.repeat(3000); draft.dispatchEvent(new Event('input'));
          check(!document.querySelector('#linkedinDraft [data-copy-draft]').disabled, '3000 boundary rejected');
          draft.value += 'a'; draft.dispatchEvent(new Event('input'));
          check(document.querySelector('#linkedinDraft [data-copy-draft]').disabled, 'Oversized draft advertised as ready');
          Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async () => { throw new Error('Denied'); }}});
          let fallbackInDialog = false;
          document.execCommand = () => { fallbackInDialog = document.activeElement.closest('dialog') === dialog; return true; };
          draft.value = expected; draft.dispatchEvent(new Event('input'));
          document.querySelector('#linkedinDraft [data-copy-draft]').click();
          await new Promise(r => setTimeout(r, 50));
          check(fallbackInDialog, 'Clipboard fallback focused an inert background element');
          document.execCommand = () => false;
          document.querySelector('#linkedinDraft [data-copy-draft]').click();
          await new Promise(r => setTimeout(r, 50));
          check(document.getElementById('shareStatus').textContent.includes('manually'), 'Copy failure claimed success');
          document.getElementById('closeRandom').click();
          check(!dialog.open && document.activeElement === button, 'Close did not restore focus');
          document.querySelector('.navrow[data-cat="github"]').click();
          Math.random = () => 0;
          button.click();
          equal(picks(), ['Beta Repo','Zara Tool'], 'Did not use filtered results or duplicated small pool');
          check(document.getElementById('randomScope').textContent.includes('2'), 'Small-pool explanation missing');
          check(document.querySelector('#linkedinDraft textarea').value.startsWith(
            'Some useful resources from the CheapInfra Resource Library.\n'), 'Small pool must introduce useful resources');
          document.getElementById('closeRandom').click();
          const search = document.getElementById('search');
          search.value = 'no-match'; search.dispatchEvent(new Event('input'));
          check(button.disabled, 'Random action enabled with no matches');
          document.getElementById('clearAll').click();
          check(!button.disabled, 'Random action stayed disabled after reset');
          document.querySelector('.navrow[data-week="24 Sep–1 Oct 2026"]').click();
          search.value = 'article'; search.dispatchEvent(new Event('input'));
          button.click(); equal(picks(), ['Alpha Article'], 'Week/search intersection ignored');
          check(document.querySelector('#linkedinDraft textarea').value.startsWith(
            'A useful resource from the CheapInfra Resource Library.\n'), 'Single-pick introduction must be singular');
          format('x');
          check(document.querySelector('#xDraft textarea').value ===
            'A useful resource from CheapInfra.\n' + source
            + '\n\nhttps://example.com/alpha-article\nResource description.', 'Single-pick X draft must be ready to paste');
          document.getElementById('closeRandom').click();
          document.getElementById('clearAll').click();
          document.querySelector('[data-tab="analytics"]').click();
          check(button.getClientRects().length === 0, 'Random action leaked into Analytics');
          return 'Sampling, filtered pools, reviewed drafts, limits and clipboard outcomes passed';
        })()""")
        run("eval", r"""(() => {
          document.querySelector('[data-tab="library"]').click();
          const briefs = [...document.querySelectorAll('.card-main > p')];
          const descriptions = briefs.map(p => p.textContent);
          Math.random = () => 0;
          briefs.forEach(p => { p.textContent = 'a'.repeat(159) + '.'; });
          document.getElementById('randomFive').click();
          document.querySelector('[data-share-format="linkedin"]').click();
          const longDraft = document.querySelector('#linkedinDraft textarea');
          if (longDraft.scrollHeight > longDraft.clientHeight + 2)
            throw new Error('Introduction and five descriptions must fit the desktop LinkedIn editor');
          document.getElementById('closeRandom').click();
          briefs.forEach(p => { p.textContent = 'Tool.'; });
          document.getElementById('randomFive').click();
          document.querySelector('[data-share-format="x"]').click();
          const threeExpected = 'Some useful resources from CheapInfra.\n'
            + 'https://cheapinfra-resources.wyrdwerk.com/\n\n'
            + ['delta-ai','gamma-provider','alpha-article'].map(id =>
              'https://example.com/' + id + '\nTool.').join('\n\n');
          if (document.querySelector('#xDraft textarea').value !== threeExpected)
            throw new Error('X must use up to three complete descriptions with a compact introduction');
          if (document.querySelectorAll('#randomPicks a').length !== 3) throw new Error('X preview must match its three entries');
          const shortPost = document.querySelector('#xDraft textarea');
          if (shortPost.scrollHeight > shortPost.clientHeight + 2) throw new Error('Three-pick X post is clipped in its editor');
          document.getElementById('closeRandom').click();
          briefs.forEach((p,i) => { p.textContent = descriptions[i]; });
          const card = document.getElementById('r-delta-ai');
          card.querySelector('h3 a').textContent = '<img src=x onerror=alert(1)> & Delta';
          card.querySelector('.card-main > p').textContent = '界'.repeat(160) + ' ' + 'z'.repeat(500) + ' Full source description.';
          const warning = document.createElement('p'); warning.className = 'warnbar';
          warning.textContent = '⚠ Unverified claim. Use at your own risk.';
          card.querySelector('.card-main').append(warning);
          Math.random = () => 0;
          document.getElementById('randomFive').click();
          document.querySelector('[data-share-format="linkedin"]').click();
          const linkedin = document.querySelector('#linkedinDraft textarea').value;
          if (!linkedin.includes('Caveat: Unverified claim. Use at your own risk.')) throw new Error('Warning lost');
          if (document.querySelector('#randomPicks img')) throw new Error('Title interpreted as markup');
          document.querySelector('[data-share-format="x"]').click();
          const posts = [...document.querySelectorAll('#xDraft textarea')].map(el => el.value);
          if (posts.length !== 1) throw new Error('X must remain a single post');
          const [introduction, ...entries] = posts[0].split('\n\n');
          const heading = 'Some useful resources from CheapInfra.';
          if (introduction !== heading + '\nhttps://cheapinfra-resources.wyrdwerk.com/')
            throw new Error('Reduced X draft must introduce useful resources with its source');
          // Independent expectation: heading, source URL, three resource URLs, newlines and weighted descriptions.
          const length = heading.length + 26 + 76 + entries.reduce((n,entry) => n + [...entry.split('\n')[1]].reduce(
            (m,c) => m + (c.codePointAt(0)>127 ? 2 : 1), 0), 0);
          if (length > 280) throw new Error('X post over its limit');
          if (entries.length !== 3 || entries.some(entry => entry.split('\n').length !== 2))
            throw new Error('X must use three complete entries when other selected resources fit');
          if (entries.some(entry => entry.startsWith('https://example.com/delta-ai\n')))
            throw new Error('An oversized description must be omitted rather than cut to a fragment');
          if (entries.some(entry => entry.split('\n')[1] !== 'Resource description.'))
            throw new Error('X must preserve complete source descriptions');
          if (document.querySelectorAll('#randomPicks a').length !== 3) throw new Error('X preview shows excluded resources');
          const reducedPost = document.querySelector('#xDraft textarea');
          if (reducedPost.scrollHeight > reducedPost.clientHeight + 2) throw new Error('Three-pick X post is clipped in its editor');
          document.querySelector('[data-share-format="linkedin"]').click();
          if (document.querySelectorAll('#randomPicks a').length !== 5) throw new Error('LinkedIn lost two picks');
          document.querySelector('[data-share-format="x"]').click();
          document.getElementById('pickAgain').click();
          if (document.querySelector('#xDraft').hidden) throw new Error('Reroll changed platform');
          if (document.querySelectorAll('#randomPicks a').length !== 3) throw new Error('Reroll changed reduced X sample size');
          return 'Concise Unicode descriptions, caveats, safe rendering and URLs preserved';
        })()""")
        run("press", "Escape")
        run("eval", "if(document.getElementById('randomShare').open) throw new Error('Escape did not close dialog')")
    finally:
        subprocess.run([*browser, "close"], capture_output=True, timeout=30)


@pytest.mark.skipif(shutil.which("agent-browser") is None, reason="agent-browser is not installed")
def test_x_preserves_meaning_and_caveats_instead_of_forcing_entry_count(built_library):
    tmp, _ = built_library
    browser = ["agent-browser", "--namespace", "random-share-tests", "--session", "meaning", "--json"]

    def run(*args):
        proc = subprocess.run([*browser, *args], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        result = json.loads(proc.stdout)
        assert result["success"], result
        return result

    try:
        run("open", (tmp / "index.html").as_uri())
        run("set", "viewport", "1280", "900", "2")
        run("eval", r"""(async () => {
          const check = (ok, msg) => { if (!ok) throw new Error(msg); };
          const cards = [...document.querySelectorAll('#main .card')].slice(0,5);
          const descriptions = [
            'Interactive React components and micro-interactions.',
            'Production-ready shadcn/Tailwind UI blocks.',
            'React and Next.js interaction effects.'
          ];
          cards.forEach((card,i) => {
            card.querySelector('.card-main > p').textContent = i < 3
              ? descriptions[i].slice(0,-1) + ' — optional examples and installation details that are not needed in this post.'
              : 'x'.repeat(400) + '.';
          });
          Math.random = () => 0;
          const open = () => { document.getElementById('randomFive').click(); document.querySelector('[data-share-format="x"]').click(); };
          const post = () => document.querySelector('#xDraft textarea');
          const entries = () => post().value.split('\n\n').slice(1);
          const close = () => document.getElementById('closeRandom').click();
          const intro = 'Some useful resources from CheapInfra.\nhttps://cheapinfra-resources.wyrdwerk.com/';
          open();
          const expected = intro + '\n\n' + [
            'https://example.com/delta-ai\n' + descriptions[0],
            'https://example.com/gamma-provider\n' + descriptions[1],
            'https://example.com/alpha-article\n' + descriptions[2]
          ].join('\n\n');
          check(post().value === expected, 'X must preserve what each resource does, not character-cut its description');
          check(document.querySelectorAll('#randomPicks a').length === 3, 'Three-entry preview mismatch');
          check(!post().value.includes('…'), 'X generated an unfinished fragment');
          let copied = null;
          Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async text => {copied=text;}}});
          document.querySelector('#xDraft [data-copy-draft]').click();
          await new Promise(r => setTimeout(r, 50));
          check(copied === expected, 'Copy must include the complete meaningful post');
          close();
          // Adding a full warning must reduce the count, never remove the warning.
          const warning = document.createElement('p'); warning.className='warnbar';
          warning.textContent='⚠ Performance claims are vendor-reported; not independently verified.';
          cards[0].querySelector('.card-main').append(warning);
          open();
          check(entries().length === 2, 'Full caveat should reduce X to two complete entries');
          check(entries()[0] === 'https://example.com/delta-ai\n' + descriptions[0]
            + ' Caveat: Performance claims are vendor-reported; not independently verified.', 'X caveat was shortened or lost');
          check(entries()[1] === 'https://example.com/alpha-article\n' + descriptions[2], 'A later complete entry should fit without changing the first');
          check(document.querySelectorAll('#randomPicks a').length === 2, 'Two-entry preview mismatch');
          check(document.querySelector('#xDraft .draft-count').textContent === '280 / 280', 'Complete entries at the limit must remain copyable');
          document.querySelector('[data-share-format="linkedin"]').click();
          check(document.querySelectorAll('#randomPicks a').length === 5, 'LinkedIn must retain five selected resources');
          close();
          // A Unicode description with its entire warning can fit alone, not with another entry.
          const unicode = '按需推理服务，支持开放模型和实时监控。';
          cards[0].querySelector('.card-main > p').textContent=unicode;
          cards[1].querySelector('.card-main > p').textContent='m'.repeat(90)+'.';
          cards[2].querySelector('.card-main > p').textContent='n'.repeat(90)+'.';
          open();
          check(entries().length === 1, 'Prefer one intact entry over several fragments');
          const one = 'A useful resource from CheapInfra.\nhttps://cheapinfra-resources.wyrdwerk.com/\n\n'
            + 'https://example.com/delta-ai\n' + unicode
            + ' Caveat: Performance claims are vendor-reported; not independently verified.';
          check(post().value === one, 'Single-entry post must preserve Unicode and its full caveat');
          const independentlyCounted = 34 + 26 + 24 + [...unicode].length * 2
            + ' Caveat: Performance claims are vendor-reported; not independently verified.'.length;
          check(independentlyCounted <= 280, 'Single-entry example does not fit');
          check(!document.querySelector('#xDraft [data-copy-draft]').disabled, 'Valid single-entry post cannot be copied');
          check(document.querySelectorAll('#randomPicks a').length === 1, 'One-entry preview mismatch');
          close();
          // No source clause fits: explain the limitation instead of inventing or truncating text.
          cards.forEach(card => {card.querySelector('.card-main > p').textContent='z'.repeat(400)+'.';});
          open();
          check(!post().value && document.querySelector('#xDraft [data-copy-draft]').disabled, 'Unusable drafts must not be presented as ready');
          check(document.querySelector('#xDraft .share-hint').textContent.includes('Pick again'), 'No-fit recovery guidance missing');
          check(document.querySelectorAll('#randomPicks a').length === 0, 'No-fit preview claims included resources');
          return 'Meaningful clauses, three/two/one entries, complete warnings, Unicode and honest no-fit handling passed';
        })()""")
    finally:
        subprocess.run([*browser, "close"], capture_output=True, timeout=30)
