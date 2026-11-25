#!/usr/bin/env python3
# Modified for Agent Scientist: portable runtime integration and UTF-8/BOM handling.
"""Browser step of the Octet backend (started by octet_draw.py; needs Playwright and Chrome or Chromium).

  python octet_run.py JOB.json

Reads the job that octet_draw.py wrote, starts one headless browser for the whole job, opens the adapter page,
draws the figure (adapter.ts drawFigure), writes figure.oct, figure.cdxml (Octet's CDXML writer alone, for ChemDraw)
and figure.svg, reads figure.cdxml in a fresh page with Octet's CDXML reader alone, renders figure.png (at the job's dpi, true size, on white) and
figure_small.png (small_dpi), and writes report.json and reload.json into the job's output directory.  Prints one JSON line with
the status and the time of each stage.  Uses only the standard library and Playwright, so it can run on another
machine that sees the same paths (octet_draw.py --browser-cmd).
"""
import json
import math
import os
import re
import sys
import tempfile
import time
from pathlib import Path


def launch(pw, browser='auto', timeout=30000):
    """System Chrome, else Playwright's Chromium, else the executable at `browser`."""
    # --disable-lcd-text: gray antialiasing; LCD (sub-pixel) text would put orange and blue fringes on black glyphs
    args = ['--no-sandbox', '--disable-dev-shm-usage', '--disable-lcd-text']
    if browser == 'auto':
        browser = os.environ.get('AGENT_BROWSER_EXECUTABLE_PATH') or browser
    errors = []
    if browser in ('auto', 'chrome'):
        try:
            return pw.chromium.launch(channel='chrome', headless=True, args=args, timeout=timeout)
        except Exception as e:      # no system Chrome
            errors.append('chrome: %s' % str(e).splitlines()[0])
    if browser in ('auto', 'chromium'):
        try:
            return pw.chromium.launch(headless=True, args=args, timeout=timeout)
        except Exception as e:
            errors.append('chromium: %s' % str(e).splitlines()[0])
    if browser not in ('auto', 'chrome', 'chromium'):
        return pw.chromium.launch(executable_path=browser, headless=True, args=args, timeout=timeout)
    raise RuntimeError('no browser could be started (%s); install Google Chrome or run "playwright install chromium"' % '; '.join(errors))


MAX_PX = 12000


def png(browser, svg, dpi, width=None):
    """The SVG on an opaque white page at `dpi` of its size in pt (or `width` px wide); long side at most MAX_PX."""
    m = re.search(r'viewBox="\s*([-\d.eE]+)[ ,]+([-\d.eE]+)[ ,]+([\d.eE]+)[ ,]+([\d.eE]+)\s*"', svg)
    vw, vh = float(m.group(3)), float(m.group(4))
    w = min(float(width) if width else vw * dpi / 72.0, MAX_PX, MAX_PX * vw / vh)
    h = vh * w / vw
    page = browser.new_page(viewport={'width': int(math.ceil(w)) + 2, 'height': int(math.ceil(h)) + 2}, device_scale_factor=1)
    try:
        sized = svg.replace('<svg ', '<svg style="width:%.2fpx;height:%.2fpx;display:block" ' % (w, h), 1)
        page.set_content('<!doctype html><meta charset="utf-8"><body style="margin:0;background:#fff">'
                         '<div style="width:%.2fpx;height:%.2fpx;background:#fff">%s</div>' % (w, h, sized))
        page.evaluate('document.fonts.ready')
        return page.screenshot(clip={'x': 0, 'y': 0, 'width': w, 'height': h}, omit_background=False)
    finally:
        page.close()


def check_environment(html):
    """One empty adapter page, the same browser launcher and font test as a real drawing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {'ok': False, 'problems': ['browser Python: install Playwright here: python -m pip install playwright; '
                                        'install its browser: python -m playwright install chromium']}
    with tempfile.TemporaryDirectory(prefix='octet-chrome-') as scratch:
        old = os.environ.get('XDG_CONFIG_HOME')
        os.environ['XDG_CONFIG_HOME'] = scratch
        try:
            with sync_playwright() as pw:
                try:
                    browser = launch(pw, timeout=30000)
                except Exception as exc:
                    return {'ok': False, 'problems': ['browser: install Google Chrome or run python -m playwright install chromium '
                                                    'in the browser Python environment (%s)' % (str(exc).strip().splitlines() or [type(exc).__name__])[0][:200]]}
                try:
                    page = browser.new_page(viewport={'width': 160, 'height': 100})
                    page.goto(Path(html).resolve().as_uri(), timeout=8000)
                    page.wait_for_function('typeof window.checkEnvironment === "function"', timeout=5000)
                    font = page.evaluate('checkEnvironment()')
                    good = font.get('ok', False)
                    return {'ok': bool(good), 'browser': browser.version, 'font_check': font,
                            'problems': [] if good else ['font widths: install Arial or Liberation Sans on the browser machine '
                                                        '(Debian/Ubuntu: apt-get install fonts-liberation)']}
                finally:
                    browser.close()
        finally:
            if old is None:
                os.environ.pop('XDG_CONFIG_HOME', None)
            else:
                os.environ['XDG_CONFIG_HOME'] = old


def run_job(job_path):
    t0 = time.perf_counter()
    job = json.loads(Path(job_path).read_text(encoding='utf-8-sig'))
    out = Path(job['out_dir'])
    html = Path(job['html'])
    T = {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError('Playwright is not installed here: "pip install playwright" (and Google Chrome, or "playwright install '
                           'chromium"), or run the browser step on a machine that has it with --browser-cmd "ssh HOST /path/to/python"')
    errors = []
    with tempfile.TemporaryDirectory(prefix='octet-chrome-') as scratch:
        os.environ['XDG_CONFIG_HOME'] = scratch
        with sync_playwright() as pw:
            t = time.perf_counter()
            browser = launch(pw, job.get('browser', 'auto'))
            T['browser_start'] = time.perf_counter() - t
            try:
                t = time.perf_counter()
                page = browser.new_page(viewport={'width': 1600, 'height': 900})
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('console', lambda m: errors.append('console: ' + m.text) if m.type == 'error' else None)
                page.goto(html.as_uri())
                page.wait_for_function('() => typeof window.drawFigure === "function"', timeout=60000)
                T['page_load'] = time.perf_counter() - t
                t = time.perf_counter()
                res = page.evaluate('async j => await drawFigure(j)', job['page'])
                T['draw'] = time.perf_counter() - t
                (out / 'figure.oct').write_text(res['oct'], encoding='utf-8')
                # the ChemDraw file: Octet's own CDXML writer (toCdxml), without Octet's JSON layer
                (out / 'figure.cdxml').write_text(res['cdxml'], encoding='utf-8')
                (out / 'figure.svg').write_text(res['svg'], encoding='utf-8')
                # the .cdxml file, read in a fresh page with Octet's CDXML reader alone, is what reload.json gives as "cdxml_only"
                t = time.perf_counter()
                fresh = browser.new_page(viewport={'width': 1600, 'height': 900})
                fresh_errors = []
                fresh.on('pageerror', lambda e: fresh_errors.append(str(e)))
                fresh.goto(html.as_uri())
                fresh.wait_for_function('() => typeof window.readCdxml === "function"', timeout=60000)
                meta = res.get('meta') or {}
                cdxml_file = fresh.evaluate('async q => await readCdxml(q.text, q.refs, q.numbers, q.ids, q.roles)',
                                            {'text': (out / 'figure.cdxml').read_text(encoding='utf-8-sig'), 'refs': meta.get('refs', []),
                                             'numbers': meta.get('numbers', []), 'ids': meta.get('curvedIds', []),
                                             'roles': meta.get('captionRoles', [])})
                fresh.close()
                T['read_cdxml'] = time.perf_counter() - t
                t = time.perf_counter()
                (out / 'figure.png').write_bytes(png(browser, res['svg'], job['dpi'], job.get('png_width')))
                T['png'] = time.perf_counter() - t
                if job.get('small_dpi'):
                    t = time.perf_counter()
                    (out / 'figure_small.png').write_bytes(png(browser, res['svg'], job['small_dpi']))
                    T['preview_png'] = time.perf_counter() - t
                version = browser.version
            finally:
                browser.close()
    report = res['report']
    report['reload']['cdxml_file_lost'] = cdxml_file.get('lost')
    res['reload']['cdxml_only'] = cdxml_file
    report['page_errors'] = errors + fresh_errors
    report['browser'] = version
    tm = {k: round(v, 3) for k, v in T.items()}
    tm.update({'page_' + k: round(v / 1000.0, 3) for k, v in report.pop('timings_ms', {}).items()})
    tm['runner_s'] = round(time.perf_counter() - t0, 3)
    report['timings_s'] = tm
    files = {'oct': 'figure.oct', 'cdxml': 'figure.cdxml', 'svg': 'figure.svg', 'png': 'figure.png'}
    if job.get('small_dpi'):
        files['preview'] = 'figure_small.png'
    report['files'] = files
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'reload.json').write_text(json.dumps(res['reload'], ensure_ascii=False, indent=1), encoding='utf-8')
    status = {'ok': True, 'problems': len(report.get('problems', [])), 'page_errors': len(report['page_errors']), 'runner_s': tm['runner_s'], 'timings_s': tm}
    return status


if __name__ == '__main__':
    try:
        st = check_environment(sys.argv[2]) if sys.argv[1] == '--check-env' else run_job(sys.argv[1])
    except Exception as e:          # the page's own error message arrives here
        print('octet_run.py: %s' % str(e).strip().splitlines()[0] if str(e).strip() else repr(e), file=sys.stderr)
        sys.exit(2)
    print(json.dumps(st))
