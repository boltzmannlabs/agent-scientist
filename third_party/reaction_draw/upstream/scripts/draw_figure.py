#!/usr/bin/env python3
# Modified for Agent Scientist: portable runtime integration and UTF-8/BOM handling.
# SPDX-License-Identifier: Apache-2.0
"""Draw a figure from an input file in one command: layout, Octet Draw, save and reload, SVG and PNG, every check.

  python draw_figure.py INPUT.json --out DIR [--dpi 600 | --png-width N] [--browser-cmd "ssh HOST PYTHON"]
                        [--no-positive-control] [--quiet] [--octet PATH --node-modules PATH]
  python draw_figure.py --check-env [--browser-cmd "ssh HOST PYTHON"]

Exit status: 0 when every check passes (and the positive control finds every planted error), 1 when a check fails,
2 when the input file is wrong or a stage cannot run. Stages, outputs and options: the repository's docs/backend.md.
"""
import argparse
import output_lock
import json
import signal
import sys
import time
import platform
import re
import shutil
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True               # an installed skill folder may be read-only
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'octet'))
import specutil  # noqa: E402
import check_rules  # noqa: E402
import stereochemistry as stereo  # noqa: E402

SMALL_DPI = 150
ACS_COLUMNS_PT = ((234, 'single column (3.25 in)'), (504, 'double column (7 in)'))
START = time.time()
SPEC_NEXT = 'NEXT: fix each input error in the input file and rerun the same command; do not stop.'
# what a run writes into DIR; the files of an earlier run are removed first, so that a failed run leaves no stale figure
# or verdict behind (summary.txt then says why it failed)
OUTPUTS = ('resolved.json', 'figure.oct', 'figure.cdxml', 'figure.svg', 'figure.png', 'figure_small.png', 'report.json', 'reload.json', 'checks.json', 'summary.txt')
PASS_FILES = ('figure.oct', 'figure.cdxml', 'figure.svg', 'figure.png', 'figure_small.png',
              'summary.txt', 'resolved.json')


def _progress(message):
    """One line on stderr per drawing: a run takes minutes, and a log that stays empty looks like a hang."""
    print('progress (%3.0f s): %s' % (time.time() - START, message), file=sys.stderr, flush=True)


def _passing(out):
    summary = out / 'summary.txt'
    return summary.is_file() and 'RESULT: all checks pass' in summary.read_text(encoding='utf-8-sig').splitlines()


def _save_pass(out, spec_bytes=None):
    """Copy only managed passing files; never remove other files in either directory."""
    saved = out / 'last_pass'
    saved.mkdir(exist_ok=True)
    for name in PASS_FILES:
        if (out / name).is_file():
            shutil.copyfile(out / name, saved / name)
    if spec_bytes is not None:
        (saved / 'input.json').write_bytes(spec_bytes)


def run(spec_path, out_dir, png_width=None, octet_dir=None, node_modules=None, browser_cmd=None, positive_control=True,
        draw=None, log=print, dpi=None):
    """Retain the last checked figure through failed checks and early-stage failures."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / '.draw.lock').open('a+b') as lock:
        try:
            output_lock.acquire(lock)
        except OSError:
            message = 'input error: another draw_figure.py is writing %s; wait for it to finish or use another --out' % out
            log(message)
            return 2, {'error': message}
        # Read before the pipeline replaces its outputs (the input may be in DIR).
        try:
            spec_bytes = Path(spec_path).read_bytes()
        except OSError:
            spec_bytes = None
        if _passing(out):
            _save_pass(out)
        status, result = _run(spec_path, out_dir, png_width, octet_dir, node_modules, browser_cmd, positive_control, draw, log, dpi)
        if status == 0:
            _save_pass(out, spec_bytes)
        elif _passing(out / 'last_pass'):
            message = ('the last passing figure is in %s/last_pass/; hand it over unless this change fixes a chemistry error' % out)
            with (out / 'summary.txt').open('a', encoding='utf-8') as summary:
                summary.write(message + '\n')
            log(message)
        return status, result


def _failed(out, what, message, notes, times, log, stereo_lines=()):
    """A run that stopped before its checks: summary.txt says where and why; returns its lines."""
    if what == 'input error':
        lines = list(stereo_lines) + ['input error: ' + problem for problem in message]
    else:
        lines = ['%s: %s' % (what, message)] + ['note: %s' % n for n in notes]
        lines.extend(stereo_lines)
    if times:
        lines.append('stages (s): ' + ', '.join('%s %.1f' % (k, v) for k, v in times.items()))
    lines.append('RESULT: FAILED (%s)' % what)
    if what == 'input error':
        lines.append(SPEC_NEXT)
    (out / 'summary.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for line in lines:
        log(line)
    return lines


def _backend():
    try:
        import octet_draw
    except ImportError as e:
        raise RuntimeError('cannot load the Octet backend (octet/octet_draw.py): %s' % e)
    if not hasattr(octet_draw, 'draw'):
        raise RuntimeError('octet/octet_draw.py has no draw(resolved, out_dir, ...) function')
    return octet_draw.draw


def size_line(out):
    """True size of figure.svg, the ACS column it fits (a note only) and the PNG sizes."""
    m = re.search(r'<svg[^>]*?\bwidth="([\d.]+)pt"[^>]*?\bheight="([\d.]+)pt"', (out / 'figure.svg').read_text(encoding='utf-8-sig'))
    if not m:
        return 'size: figure.svg has no width and height in pt'
    w, h = float(m.group(1)), float(m.group(2))
    fit = next(('fits the ACS ' + name for limit, name in ACS_COLUMNS_PT if w <= limit),
               'wider than the ACS double column (7 in), so it will be reduced')
    pngs = []
    for name in ('figure.png', 'figure_small.png'):
        if (out / name).exists():
            pw, ph = specutil.png_size((out / name).read_bytes())
            pngs.append('%s %d x %d px (%.0f dpi)' % (name, pw, ph, pw / w * 72))
    return 'size: %.0f x %.0f pt (%.2f x %.2f in), %s; %s' % (w, h, w / 72, h / 72, fit, ', '.join(pngs))


def _counts(checked):
    return {n: len(c['findings']) for n, c in checked['checks'].items()}


def _gaps(checked):
    """{pair of species: pt} from the species_gap warnings (two species closer than half a bond)."""
    out = {}
    for w in checked['checks'].get('species_gap', {}).get('warnings', []):
        m = re.match(r'^(\S+):\d+ and (\S+):\d+ are (-?[\d.]+) pt apart', w)
        if m:
            key = frozenset(m.group(1, 2))
            out[key] = min(out.get(key, 1e9), float(m.group(3)))
    return out


def _closer(result, checked):
    """True when a candidate brings two species closer than half a bond where they were not, or closer still."""
    before, after = _gaps(result), _gaps(checked)
    return any(k not in before or g < before[k] - 0.05 for k, g in after.items())


def _tighter(result, checked):
    """True when a candidate has more curved arrows close to other ink (arrows_clear warnings) than the checked figure."""
    def count(r):
        return len(r['checks'].get('arrows_clear', {}).get('warnings', []))
    return count(checked) > count(result)


def _no_gain(result):
    """Accept a candidate when no detector gains a finding, the total falls, and no two species come closer than half a
    bond where they were not."""
    before = _counts(result)
    def accept(checked):
        after = _counts(checked)
        return (all(after[n] <= before[n] for n in before) and sum(after.values()) < sum(before.values())
                and not _closer(result, checked) and not _tighter(result, checked))
    return accept


def _fixed_curved(saved, keep):
    """Saved routes of the curved arrows whose id passes keep(id), to be drawn again unchanged."""
    return {c['id']: {'from': [c['from'][0], -c['from'][1]], 'to': [c['to'][0], -c['to'][1]], 'bend': c.get('bend', 0),
                      'start': c.get('start'), 'end': c.get('end')}
            for c in saved.get('curved', []) if keep(c.get('id'))}


def _keep_saved_marks(atoms, saved, skip_prefix):
    """Keep the saved label alignment and charge angle of atoms outside the panel being changed."""
    for kept in saved.get('atoms', []):
        if not kept['ref'].startswith(skip_prefix):
            atoms[kept['ref']]['native_align'] = kept.get('align')
            if kept.get('charge_angle') is not None:
                atoms[kept['ref']]['charge_angle'] = kept['charge_angle']


def _more_crossings(resolved, fig):
    """True when the moved coordinates themselves hold more crossing bonds or too-close atoms than the checked figure's:
    bond_crossing would gain a finding, so the candidate is not drawn."""
    def count(res):
        return len(check_rules.det_bond_crossing(check_rules.Figure(res, {}, {}, None)))
    return count(resolved) > count(fig.resolved)


def _names(aid, text):
    """True when text names the arrow id as a whole word (A1, not the A1 of A10)."""
    return re.search(r'(?<![\w-])' + re.escape(aid) + r'(?![\w-])', text) is not None


def _candidate(resolved, out, fig, draw, draw_args, options, accept, keep_resolved=False):
    """Draw one retry candidate in a scratch folder and check it; copy its files into out when accept(checks).
    Returns (figure, checks, accepted, error); error names why nothing could be drawn or checked."""
    _progress('extra drawing (%s)' % ', '.join(sorted(k for k, v in options.items() if v is True)))
    with tempfile.TemporaryDirectory(prefix='.retry-', dir=str(out)) as scratch:
        dest = Path(scratch)
        (dest / 'resolved.json').write_text(json.dumps(resolved, ensure_ascii=False, indent=1), encoding='utf-8')
        try:
            draw(resolved, dest, options=options, **draw_args)
            candidate = check_rules.load_figure(dest)
            candidate.name = fig.name
            checked = check_rules.run_checks(candidate)
        except Exception as exc:
            return None, None, False, '%s: %s' % (type(exc).__name__, exc)
        accepted = accept(checked)
        if accepted:
            for name in OUTPUTS:
                if (dest / name).is_file() and not (keep_resolved and name == 'resolved.json'):
                    shutil.copyfile(dest / name, out / name)
        return candidate, checked, accepted, None


def retry_placements(resolved, out, fig, result, draw, draw_args):
    """Try extra backend candidates only after an exact rule fails; keep checks and passing figures unchanged."""
    import copy
    notes, accepted = [], {}
    for targets, flag in ((('charge_own_atom', 'overlap_charge', 'charge_open'), 'repairCharges'),
                          (('arrows_ends', 'arrows_shape', 'overlap_arrow_text', 'overlap_arrow_bond', 'overlap_arrow_arrow'), 'repairArrows'),
                          (('number_place', 'number_clear'), 'repairNumbers')):
        failed = [name for name in targets if name in result['failed']]
        if not failed:
            continue
        options = dict(accepted, **{flag: True})
        findings = ' '.join(x for name in failed for x in result['checks'][name]['findings'])
        if flag == 'repairNumbers':
            # Leave 0.5 pt for the glyph-box change on save/reload. Check thresholds
            # stay unchanged; only the failed drawing's placement search is wider.
            options['ownMarginPx'] = 8.5
        if flag == 'repairArrows':
            if 'overlap_arrow_arrow' in failed:
                options['reverseCurved'] = True
            options['repairArrowIds'] = [c['id'] for p in resolved['panels'] for c in p['curved']
                                         if _names(c['id'], findings)]
            if not options['repairArrowIds']:
                options.pop('repairArrowIds')
        saved = json.loads((out / 'reload.json').read_text(encoding='utf-8-sig'))
        retry_resolved = copy.deepcopy(fig.resolved)
        atoms = {a['ref']: a for p in retry_resolved['panels'] for a in p['atoms']}
        for kept in saved.get('atoms', []):
            a = atoms[kept['ref']]
            a['native_align'] = kept.get('align')
            if flag == 'repairCharges' and kept['ref'] in findings:
                a.pop('charge_angle', None)
            elif kept.get('charge_angle') is not None:
                a['charge_angle'] = kept['charge_angle']
        repair_ids = set(options.get('repairArrowIds', [])) if flag == 'repairArrows' else set()
        options['fixedCurved'] = _fixed_curved(saved, lambda i: i not in repair_ids)
        options['fixedNumbers'] = {n['ref']: n for n in saved.get('numbers', [])
                                   if flag != 'repairNumbers' or n['ref'] not in findings}
        before = _counts(result)
        def better(checked):
            after = _counts(checked)
            return all(after[n] <= before[n] for n in before) and any(after[n] < before[n] for n in failed)
        candidate, checked, ok, error = _candidate(retry_resolved, out, fig, draw, draw_args, options, better, keep_resolved=True)
        if error:
            notes.append('extra placement candidates (%s): %s; kept the original drawing' % (', '.join(failed), error))
            continue
        notes.append('extra placement candidates (%s): %s; findings %d -> %d' % (
            ', '.join(failed), 'kept the first improved drawing (no detector gained findings)' if ok else 'kept the original drawing',
            sum(before[n] for n in failed), sum(_counts(checked if ok else result)[n] for n in failed)))
        if ok:
            fig, result, accepted = candidate, checked, options
    return fig, result, notes


def retry_iupac_pairs(out, fig, result, draw, draw_args):
    """A free axial pair may need a small rigid turn of its molecule for a clear arrow.

    Keep connectivity, bond lengths, internal angles and stereo. Every candidate is
    checked on saved ink; keep it only if no detector gains a finding.
    """
    import copy
    import math
    notes = []
    targets = {'arrows_ends', 'arrows_shape', 'overlap_arrow_bond', 'overlap_arrow_text', 'overlap_arrow_arrow', 'overlap_text_text', 'overlap_text_bond'}
    for _ in range(3):
        if not targets.intersection(result['failed']):
            break
        findings = ' '.join(x for n in targets for x in result['checks'][n]['findings'])
        sources = [(c['from']['refs'][0], c['id']) for p in fig.resolved['panels'] for c in p['curved']
                   if c['from']['kind'] == 'atom' and c['electrons'] == 2
                   and (_names(c['id'], findings)
                        or c['from']['refs'][0] in findings)]
        accepted = False
        for ref, aid in dict.fromkeys(sources):
            # Retain checked routes in other panels while this panel is adjusted.
            panel_id = next(p['id'] for p in fig.resolved['panels'] if any(c['id'] == aid for c in p['curved']))
            all_findings = ' '.join(x for check in result['checks'].values() for x in check['findings'])
            untouched = {c['id'] for p in fig.resolved['panels'] if p['id'] != panel_id for c in p['curved']
                         if not _names(c['id'], all_findings)}
            saved = json.loads((out / 'reload.json').read_text(encoding='utf-8-sig'))
            fixed = _fixed_curved(saved, lambda i: i in untouched)
            fixed_numbers = {n['ref']: n for n in saved.get('numbers', [])
                             if not n['ref'].startswith(panel_id + '.') and n['ref'] not in all_findings}
            motions = ([(-90, 0, .7), (90, 0, .7), (0, 0, .1), (0, 0, -.1)]
                       if {'overlap_text_text', 'overlap_text_bond'}.intersection(result['failed']) else [])
            motions += [(d, 0, 0) for d in (-5, 5, -10, 10)]
            motions += [(0, distance * math.cos(math.radians(d)), -distance * math.sin(math.radians(d)))
                        for distance in (.1, .2) for d in range(0, 360, 45)]
            # A neighboring label can block every short axial route. A quarter
            # turn and at most one bond of separation keep the molecule intact.
            motions += [(d, sx, sy) for d in (-90, 90) for sx, sy in
                        ((0, .7), (.7, 0), (0, -.7), (-.7, 0), (1, 0), (-1, 0), (0, 1), (0, -1))]
            trials = [(d, sx, sy, repair) for d, sx, sy in motions
                      for repair in ((False, True) if abs(d) in (5, 10) else (True,))]
            for degree, sx, sy, repair in trials:
                resolved = copy.deepcopy(fig.resolved)
                atoms = {a['ref']: a for p in resolved['panels'] for a in p['atoms']}
                _keep_saved_marks(atoms, saved, panel_id + '.')
                root, sid = atoms[ref], atoms[ref]['species']
                x0, y0 = root['x'], root['y']
                co, si = math.cos(math.radians(degree)), math.sin(math.radians(degree))
                for a in atoms.values():
                    if a['species'] == sid:
                        a.pop('native_align', None)
                        dx, dy = a['x'] - x0, a['y'] - y0
                        a['x'], a['y'] = x0 + dx * co + dy * si + sx, y0 - dx * si + dy * co + sy
                if _more_crossings(resolved, fig):
                    continue
                options = {'repairArrows': True, 'repairCharges': repair, 'repairNumbers': repair, 'ownMarginPx': 8.5,
                           'reverseCurved': 'overlap_arrow_arrow' in result['failed'], 'fixedCurved': fixed, 'fixedNumbers': fixed_numbers}
                candidate, checked, ok, error = _candidate(resolved, out, fig, draw, draw_args, options, _no_gain(result))
                if error:
                    notes.append('axial-pair candidate %s %+g deg: %s' % (sid, degree, error))
                    continue
                if ok:
                    notes.append('axial lone pair for %s: rigid move of %s (%+g deg, offset %.3f/%.3f bonds); findings %d -> %d' %
                                 (aid, sid, degree, sx, sy, sum(_counts(result).values()), sum(_counts(checked).values())))
                    fig, result, accepted = candidate, checked, True
                if accepted:
                    break
            if accepted:
                break
        if not accepted or result['ok']:
            break
    return fig, result, notes


def retry_forming_branch(out, fig, result, draw, draw_args):
    """Open a blocked intramolecular forming-bond corridor by rigid bridge rotation.

    Keep every bond length and branch configuration; accept only a saved drawing
    that removes a finding without adding one to any detector.
    """
    import collections
    notes = []
    if 'overlap_arrow_bond' not in result['failed']:
        return fig, result, notes
    findings = ' '.join(result['checks']['overlap_arrow_bond']['findings'])
    saved = json.loads((out / 'reload.json').read_text(encoding='utf-8-sig'))
    for panel in fig.resolved['panels']:
        graph = collections.defaultdict(set)
        for b in panel['bonds']:
            graph[b['a']].add(b['b'])
            graph[b['b']].add(b['a'])
        for arrow in panel['curved']:
            if not _names(arrow['id'], findings) or arrow['to']['kind'] != 'gap':
                continue
            left, right = arrow['to']['refs']
            if left not in graph or right not in graph:
                continue
            # A bridge on the shortest path to the receiving atom defines a rigid branch.
            queue, previous = collections.deque([left]), {left: None}
            while queue and right not in previous:
                here = queue.popleft()
                for neighbor in sorted(graph[here]):
                    if neighbor not in previous:
                        previous[neighbor] = here
                        queue.append(neighbor)
            if right not in previous:
                continue
            path = [right]
            while previous[path[-1]] is not None:
                path.append(previous[path[-1]])
            path.reverse()
            # (pivot, root, other end): the bridge next to the receiving atom first, then the giving side's bridges
            # from the giving atom on (a chorismate side chain turned about its ring atom)
            turns = [(path[-2], path[-1], left)] if len(path) > 2 else []
            turns += [(path[k + 1], path[k], right) for k in range(1, len(path) - 1)]
            for pivot, root, other in turns:
                branch, queue = {root}, collections.deque([root])
                while queue:
                    here = queue.popleft()
                    for neighbor in graph[here] - {pivot} - branch:
                        branch.add(neighbor)
                        queue.append(neighbor)
                if other in branch or any(n != root and n in graph[pivot] for n in branch):
                    continue  # a ring is never cut or deformed
                found = _turn_branch(out, fig, result, draw, draw_args, saved, panel, graph, arrow, pivot, branch, notes)
                if found:
                    return found
    return fig, result, notes


def _turn_branch(out, fig, result, draw, draw_args, saved, panel, graph, arrow, pivot, branch, notes):
    """Draw the branch turned rigidly about pivot by 120, -120, 60, -60 and 180 degrees (and with the terminal arms of an
    S, P or N exchanged); (fig, result, notes) of the first drawing that removes a finding without adding one, else None."""
    import copy
    import math
    untouched = {c['id'] for p in fig.resolved['panels'] if p['id'] != panel['id'] for c in p['curved']}
    fixed = _fixed_curved(saved, lambda i: i in untouched)
    fixed_numbers = {n['ref']: n for n in saved.get('numbers', []) if not n['ref'].startswith(panel['id'] + '.')}
    for degree, swap_ends in ((d, swap) for d in (120, -120, 60, -60, 180) for swap in (False, True)):
        resolved = copy.deepcopy(fig.resolved)
        atoms = {a['ref']: a for p in resolved['panels'] for a in p['atoms']}
        x0, y0 = atoms[pivot]['x'], atoms[pivot]['y']
        _keep_saved_marks(atoms, saved, panel['id'] + '.')
        co, si = math.cos(math.radians(degree)), math.sin(math.radians(degree))
        for ref in branch:
            a = atoms[ref]
            dx, dy = a['x'] - x0, a['y'] - y0
            a['x'], a['y'] = x0 + co * dx + si * dy, y0 - si * dx + co * dy
        for ref in graph:
            atoms[ref].pop('charge_angle', None)
            atoms[ref].pop('native_align', None)
        if swap_ends:
            swapped = False
            for ref in sorted(branch):
                leaves = sorted(n for n in graph[ref] if len(graph[n]) == 1 and n in branch)
                if len(leaves) != 2 or atoms[ref]['el'] not in ('S', 'P', 'N'):
                    continue
                a, b = (atoms[n] for n in leaves)
                center = atoms[ref]
                da, db = math.hypot(a['x'] - center['x'], a['y'] - center['y']), math.hypot(b['x'] - center['x'], b['y'] - center['y'])
                if min(da, db) <= 0:
                    continue
                ax, ay, bx, by = a['x'], a['y'], b['x'], b['y']
                a['x'], a['y'] = center['x'] + (bx - center['x']) * da / db, center['y'] + (by - center['y']) * da / db
                b['x'], b['y'] = center['x'] + (ax - center['x']) * db / da, center['y'] + (ay - center['y']) * db / da
                swapped = True
            if not swapped:
                continue
        if _more_crossings(resolved, fig):
            continue
        options = {'fixedCurved': fixed, 'fixedNumbers': fixed_numbers, 'repairArrows': True,
                   'repairArrowIds': [c['id'] for c in panel['curved']], 'ownMarginPx': 8.5}
        candidate, checked, ok, error = _candidate(resolved, out, fig, draw, draw_args, options, _no_gain(result))
        if error:
            notes.append('forming-bond corridor %s %+d deg: %s' % (arrow['id'], degree, error))
        elif ok:
            return candidate, checked, notes + ['forming-bond corridor %s: rigid branch about %s rotated %+d degrees%s; all bond lengths and checked configurations retained' % (arrow['id'], pivot, degree, ', terminal-arm directions exchanged' if swap_ends else '')]
    return None


def retry_layout(spec, out, fig, result, draw, draw_args):
    """Try bounded structural alternatives on failure, accepting only independently checked drawings."""
    import layout_repair
    notes = []
    protected = ('graph', 'stereochemistry', 'charges', 'hydrogens', 'labels_drawn', 'arrows_count',
                 'arrows_head', 'arrows_color', 'colors', 'cdxml', 'frame', 'bond_crossing')
    def rank(checked):
        return len(checked['failed']), sum(len(c['findings']) for c in checked['checks'].values())
    alternatives = iter(layout_repair.candidates(spec, result, fig))
    rejected = 0
    for attempt in range(1, layout_repair.MAX_DRAWS + 1):
        try:
            resolved = next(alternatives)
        except StopIteration:
            break
        except Exception as exc:
            notes.append('automatic layout search: %s; kept the checked drawing' % exc)
            break
        options = {'repairCharges': True, 'repairNumbers': True, 'repairArrows': True}
        if not set(result['failed']).intersection({'arrows_ends', 'arrows_shape'}):
            options['ownMarginPx'] = 8.5
        def better(checked, result=result):
            safe = not checked['checks']['stereochemistry']['findings'] and all(
                set(checked['checks'][n]['findings']) <= set(result['checks'][n]['findings']) for n in protected)
            return safe and rank(checked) < rank(result) and not _closer(result, checked)
        candidate, checked, ok, error = _candidate(resolved, out, fig, draw, draw_args, options, better)
        if error:
            notes.append('automatic layout candidate %d: %s; kept the checked drawing' % (attempt, error))
            continue
        notes.append('automatic layout candidate %d: %s; failed checks %d -> %d, findings %d -> %d; remaining: %s' % (
            attempt, 'accepted' if ok else 'rejected', len(result['failed']), len(checked['failed']),
            rank(result)[1], rank(checked)[1], ', '.join(checked['failed']) or 'none'))
        if ok:
            notes.extend(n for n in resolved.get('notes', []) if n not in fig.resolved.get('notes', []))
            fig, result = candidate, checked
        rejected = 0 if ok else rejected + 1
        if result['ok'] or not layout_repair.relevant(result) or rejected >= layout_repair.MAX_DRAWS:
            break
    return fig, result, notes


def _run(spec_path, out_dir, png_width=None, octet_dir=None, node_modules=None, browser_cmd=None, positive_control=True,
        draw=None, log=print, dpi=None):
    """The whole pipeline; returns (exit status, summary dict).  draw: the backend function (default octet_draw.draw)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name in OUTPUTS:                        # the files of an earlier run in DIR
        if (out / name).is_file():
            (out / name).unlink()
    times = {}
    stereo_lines = []
    t0 = time.time()
    try:
        spec = specutil.load_spec(spec_path)
        data, _ = specutil._read_json(spec_path)
        resolved = specutil.resolve(spec)
        if 'stereo' in check_rules.figure_features(resolved):
            stereo_lines = stereo.report(specutil.stereo_sources(spec), data)
    except specutil.SpecError as e:
        from spec_validation import inspect_spec
        try:
            data, _ = specutil._read_json(spec_path)
            _, sources = inspect_spec(data)
            stereo_lines = stereo.report(sources, data)
        except specutil.SpecError:
            pass
        _failed(out, 'input error', e.problems, [], times, log, stereo_lines)
        return 2, {'error': str(e)}
    except Exception as e:                      # layout errors (e.g. RDKit missing) are reported, not raised
        _failed(out, 'layout error', '%s: %s' % (type(e).__name__, e), [], times, log, stereo_lines)
        return 2, {'error': str(e)}
    (out / 'resolved.json').write_text(json.dumps(resolved, ensure_ascii=False, indent=1), encoding='utf-8')
    times['resolve'] = time.time() - t0
    notes = list(resolved.get('notes', []))     # printed and kept in summary.txt with the result
    t1 = time.time()
    native_backend = draw is None
    _progress('first drawing')
    try:
        draw = draw or _backend()
        draw(resolved, out, png_width=png_width, octet_dir=octet_dir, node_modules=node_modules, browser_cmd=browser_cmd, dpi=dpi)
    except Exception as e:
        _failed(out, 'drawing failed', '%s: %s' % (type(e).__name__, e), notes, times, log, stereo_lines)
        return 2, {'error': str(e), 'times_s': times}
    times['draw'] = time.time() - t1
    t2 = time.time()
    try:
        fig = check_rules.load_figure(out)
        result = check_rules.run_checks(fig)
        if native_backend and result['failed']:
            _progress('failed: %s; trying alternatives, one line per drawing' % ', '.join(result['failed']))
            retry_started = time.time()
            retry_args = {'png_width': png_width, 'dpi': dpi, 'octet_dir': octet_dir,
                          'node_modules': node_modules, 'browser_cmd': browser_cmd}
            numbers_only = set(result['failed']) <= {'number_place', 'number_clear'}
            try:
                # Resolve saved arrow/number placement before trying molecular motions.
                fig, result, retried = retry_placements(resolved, out, fig, result, draw, retry_args)
                notes.extend(retried)
                placed = fig
                fig, result, retried = retry_forming_branch(out, fig, result, draw, retry_args)
                notes.extend(retried)
                fig, result, retried = retry_layout(spec, out, fig, result, draw, retry_args)
                notes.extend(retried)
                fig, result, retried = retry_iupac_pairs(out, fig, result, draw, retry_args)
                notes.extend(retried)
                if not numbers_only or fig is not placed:
                    fig, result, retried = retry_placements(fig.resolved, out, fig, result, draw, retry_args)
                    notes.extend(retried)
            except Exception as exc:     # a fault in a retry keeps the last accepted figure and its findings
                notes.append('automatic retry stopped: %s: %s' % (type(exc).__name__, exc))
            resolved = fig.resolved
            times['placement_retry'] = time.time() - retry_started
        pc = check_rules.positive_control(fig, checked=result['checks']) if positive_control else None
    except check_rules.InputError as e:
        _failed(out, 'checks could not run', str(e), notes, times, log, stereo_lines)
        return 2, {'error': str(e), 'times_s': times}
    times['check'] = time.time() - t2 - times.get('placement_retry', 0)
    times['total'] = time.time() - t0
    backend_times = fig.report.get('timings_s') or {}
    ok = result['ok'] and (pc is None or pc['ok'])
    lines = check_rules.summary_lines(result, pc)
    lines.extend(stereo_lines)
    lines.append('stages (s): ' + ', '.join('%s %.1f' % (k, v) for k, v in times.items()))
    if backend_times:
        lines.append('backend (s): ' + ', '.join('%s %.1f' % (k, float(v)) for k, v in backend_times.items()
                                                 if isinstance(v, (int, float)) and not isinstance(v, bool)))
    raw = {}
    try:
        raw = json.loads((out / 'report.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        pass
    for p in raw.get('problems') or []:
        lines.append('backend problem: %s' % p)
    for n in raw.get('notes') or []:
        lines.append('backend note: %s' % n)
    for n in notes:
        lines.append('note: %s' % n)
    if (out / 'figure.svg').exists():
        lines.append(size_line(out))
    files = sorted({p.name for p in out.iterdir() if p.is_file() and not p.name.startswith('.')} | {'checks.json', 'summary.txt'})
    lines.append('files: ' + ', '.join(files))
    lines.append('RESULT: %s' % ('all checks pass' if ok else 'CHECKS FAILED'))
    (out / 'checks.json').write_text(json.dumps({'result': result, 'positive_control': pc, 'times_s': times,
                                                 'backend_times_s': backend_times, 'files': files}, ensure_ascii=False, indent=1), encoding='utf-8')
    audit = check_rules.audit_lines(fig.features)
    (out / 'summary.txt').write_text('\n'.join(lines + audit) + '\n', encoding='utf-8')
    for line in lines + (audit if ok else []):       # on a pass the audit items are the agent's next step
        log(line)
    return (0 if ok else 1), {'ok': ok, 'times_s': times, 'failed': result['failed'],
                              'positive_control': None if pc is None else '%d/%d' % (pc['detected'], pc['planted'])}


def check_environment(browser_cmd=None, octet_dir=None, node_modules=None, log=print):
    problems = []
    log('Python: ' + platform.python_version())
    if sys.version_info < (3, 9):
        problems.append('Python: install Python 3.9 or newer and run this script with it')
    try:
        import rdkit
        from rdkit.Chem import rdCIPLabeler  # noqa: F401
        log('RDKit: ' + rdkit.__version__)
    except ImportError:
        problems.append('RDKit: install in this Python: python -m pip install rdkit')
    try:
        import octet_draw
        result = octet_draw.check_environment(browser_cmd, octet_dir, node_modules)
        if result.get('browser'):
            log('Browser: ' + result['browser'] + ' (tiny page OK)')
        font = result.get('font_check')
        if font:
            log('Font widths: %s ratio %.4f (%s)' % (font['font'], font['ratio'], 'OK' if font.get('ok') else 'FAILED'))
        problems.extend(result.get('problems', []))
        if not result.get('ok') and not result.get('problems'):
            problems.append('browser: probe failed; install Playwright, Chromium and Arial or Liberation Sans in the browser environment')
    except Exception as exc:
        problems.append('drawing backend: %s' % exc)
    for problem in problems:
        log('MISSING: ' + problem)
    log('ENVIRONMENT OK' if not problems else 'ENVIRONMENT FAILED')
    return 2 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n\n')[0])
    ap.add_argument('spec', type=Path, nargs='?', metavar='INPUT.json')
    ap.add_argument('--out', type=Path, help='output directory (full run only)')
    ap.add_argument('--check-env', action='store_true', help='probe Python, RDKit, browser and font widths; no input file needed')
    ap.add_argument('--dpi', type=float, help='figure.png resolution at the true size (default: the input\'s drawing.dpi, else 600)')
    ap.add_argument('--png-width', type=int, help='figure.png width in px instead of --dpi')
    ap.add_argument('--octet', help='build the drawing page from this Octet Draw checkout (needs Node.js and esbuild; '
                                    'default: the prebuilt page in octet/dist)')
    ap.add_argument('--node-modules', help='node_modules holding esbuild, with --octet')
    ap.add_argument('--browser-cmd', help='command that runs the browser part elsewhere, e.g. "ssh HOST /path/to/python"')
    ap.add_argument('--no-positive-control', action='store_true', help='skip the checker\'s positive control')
    ap.add_argument('--quiet', action='store_true', help='print the result, stereo notes and last passing figure location')
    args = ap.parse_args(argv)

    def interrupted(signum, frame):
        print('progress: stopped by a signal; DIR has no summary.txt, so its figure files are not checked', file=sys.stderr, flush=True)
        sys.exit(143)                              # unwinds the scratch folders and the browser job
    signal.signal(signal.SIGTERM, interrupted)
    if args.check_env:
        return check_environment(args.browser_cmd, args.octet, args.node_modules)
    if args.spec is None:
        ap.error('INPUT.json is required unless --check-env is used')
    if args.out is None:
        ap.error('--out DIR is required for a full run')

    def log(line):
        if (line.lstrip().startswith(('RESULT', 'FIX ', 'STEREO', 'AUDIT', '- [ ]', 'POSITIVE CONTROL', 'NEXT:', 'checks:', 'WARNING:', 'note:',
                                     'the last passing figure', 'input error', 'layout error',
                                     'drawing failed', 'checks could not', 'MISSED planted'))
                and (not args.quiet or not line.lstrip().startswith(('FIX ', 'POSITIVE CONTROL')))):
            print(line, flush=True)
    status, _ = run(args.spec, args.out, args.png_width, args.octet, args.node_modules, args.browser_cmd,
                    positive_control=not args.no_positive_control, log=log, dpi=args.dpi)
    return status


if __name__ == '__main__':
    sys.exit(main())
