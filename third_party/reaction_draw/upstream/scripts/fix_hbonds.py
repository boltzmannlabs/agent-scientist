#!/usr/bin/env python3
# Modified for Agent Scientist: portable runtime integration and UTF-8/BOM handling.
# SPDX-License-Identifier: Apache-2.0
"""Opt-in repair: python scripts/fix_hbonds.py INPUT.json --out NEW_DIR.

Run only after judging that an hbonds dotted line overlaps. Normal drawing never
imports this module. Keep the input; save an improved spec beside it under a new
name. Real saved/reloaded drawings, not the search heuristic, decide acceptance.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import shutil
import tempfile
import sys
import time

sys.dont_write_bytecode = True               # an installed skill folder may be read-only

import check_rules as rules
import draw_figure
import layout
import layout_repair
import specutil


def findings(result):
    return [s for c in result['checks'].values() for s in c['findings'] if 'hbond ' in s]


def improves(before, after):
    return (len(findings(after)) < len(findings(before))
            and all(len(after['checks'][n]['findings']) <= len(c['findings'])
                    for n, c in before['checks'].items())
            and all(not after['checks'][n]['findings'] for n in
                    ('graph', 'stereochemistry', 'charges', 'hydrogens', 'cdxml')))


def _targets(lay, result, include_crossing=False):
    text = '\n'.join(findings(result))
    out = []
    for p in lay.panels:
        first = p['id'] + '.' + p['species'][0]
        for pair in p['hbonds']:
            refs = [specutil.ref_text(h['panel'], h['species'], h['atom']) for h in pair]
            # A different residue's label may cross this contact. Include that
            # residue's own contact too, so it can turn without moving substrate.
            if (any('hbond ' + '-'.join(order) in text for order in (refs, refs[::-1]))
                    or (include_crossing and any(end['sid'] != first and '(' + end['sid'] + ':' in text
                                                 for end in pair))):
                out.append((p['id'], pair))
    return out


def _endpoint_options(lay, end):
    """Only the same donor's explicit H and its bonded N/O/S; never another acceptor."""
    mol = lay.mol[end['sid']]
    m = end['atom']
    i = mol.idx[m]
    if mol.is_h[i]:
        return [mol.map[j] for j in mol.adj[i] if mol.atoms[j]['symbol'] in ('N', 'O', 'S')]
    if mol.atoms[i]['symbol'] in ('N', 'O', 'S'):
        return [mol.map[j] for j in mol.adj[i] if mol.is_h[j]]
    return []


def _cost(lay, pid):
    """Cheap continuous-line clearance estimate; the unchanged detectors judge the dots."""
    positions, labels, bonds = {}, [], []
    for key in lay.panels[lay.pidx[pid]]['species']:
        sid = pid + '.' + key
        mol = lay.mol[sid]
        xy = lay.expanded(sid, lay.xy[sid])
        for m, pt in xy.items():
            ref = sid + ':' + str(m)
            positions[ref] = pt
            if mol.labeled(mol.idx[m]):
                labels.append((ref, lay.label_box(sid, m, xy)))
        for e in mol.order:
            a, b = (mol.map[i] for i in e)
            bonds.append((sid, xy[a], xy[b]))
    hbond_cost, clutter, length = 0.0, 0.0, 0.0
    for pair in lay.panels[lay.pidx[pid]]['hbonds']:
        refs = [specutil.ref_text(h['panel'], h['species'], h['atom']) for h in pair]
        a, b = (positions[r] for r in refs)
        steps = max(10, math.ceil(layout.dist(a, b) / .1))
        bounds = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        for ref, box in labels:
            if ref in refs or rules.box_gap(bounds, box) > .12:
                continue
            for k in range(steps + 1):
                pt = layout.add(a, (b[0]-a[0], b[1]-a[1]), k / steps)
                hbond_cost += 10000 * max(0, .12 - rules.pt_box_gap(pt, box)) ** 2
        length += .0001 * layout.dist(a, b) ** 2
    for k, (ref, box) in enumerate(labels):
        for _, other in labels[k+1:]:
            clutter += 100 * max(0, .12 - rules.box_gap(box, other)) ** 2
        for sid, a, b in bonds:
            if ref.rsplit(':', 1)[0] == sid:
                continue  # rigid moves preserve internal bond/label geometry
            bounds = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
            if rules.box_gap(bounds, box) > .12:
                continue
            for t in (0, .2, .4, .6, .8, 1):
                pt = layout.add(a, (b[0]-a[0], b[1]-a[1]), t)
                clutter += 100 * max(0, .12 - rules.pt_box_gap(pt, box)) ** 2
    return hbond_cost, clutter, length


def _poses(lay, sid, end, other, base, hand, root_turns=True):
    xy = base[sid]
    # Turning around the contact changes label directions; turning around the
    # side-chain root also moves the contact without shifting the residue label.
    roots = [end['atom']] + (list(lay.sp[sid]['residue']) if root_turns else [])
    for root in dict.fromkeys(roots):
        axis = layout.ang(other[0]-xy[root][0], other[1]-xy[root][1])
        for mirror, deg in ((False, 0), (False, 15), (False, -15), (False, 30),
                            (False, -30), (True, 0), (True, 15), (True, -15)):
            turned = layout_repair._turn(xy, root, set(xy), deg, mirror, axis)
            for distance, direction in [(0, 0)] + [(d, a) for d in (.15, .3) for a in range(0, 360, 45)]:
                shift = layout.vec(direction)
                candidate = {m: layout.add(pt, shift, distance) for m, pt in turned.items()}
                if all(layout.dist(candidate[m], hand[sid][m]) <= layout_repair.HAND_LIMIT + 1e-8
                       for m in lay.sp[sid]['xy']):
                    yield candidate, '%s: %s, turn %+g deg around atom %s, offset %.2f at %g deg' % (
                        sid, 'flip along contact' if mirror else 'keep handedness', deg, root, distance, direction)


def candidates(lay, result, original_hand, root_turns=False):
    """Greedy bounded alternatives; the panel's first species (substrate) stays fixed."""
    base = copy.deepcopy(lay.xy)
    targets = _targets(lay, result, include_crossing=root_turns)
    changes = []
    def benefit(before, after):
        # A second search can turn at the residue root, but cannot trade a
        # predicted new text/bond collision for a clearer hydrogen bond.
        if root_turns and after[1] > before[1] + 1e-8:
            return None
        delta = after[0] - before[0]
        if not root_turns:
            delta += after[1] - before[1] + after[2] - before[2]
        return (delta, after[2]-before[2]) if delta < -1e-6 else None
    for _ in range(layout_repair.MAX_MOVES):
        best = None
        for pid, pair in targets:
            before = _cost(lay, pid)
            for end in pair:
                old = end['atom']
                for atom in _endpoint_options(lay, end):
                    end['atom'] = atom
                    after = _cost(lay, pid)
                    gain = benefit(before, after)
                    if gain is not None and (best is None or gain < best[0]):
                        best = (gain, 'end', end, atom, '%s: hbond endpoint %s -> %s (same donor)' % (
                            end['sid'], old, atom))
                end['atom'] = old
            first = pid + '.' + lay.panels[lay.pidx[pid]]['species'][0]
            movable = [end for end in pair if end['sid'] != first and
                       (lay.sp[end['sid']]['residue'] or lay.mol[end['sid']].n <= 3)]
            if not movable:
                continue
            end = min(movable, key=lambda e: lay.mol[e['sid']].n)
            sid = end['sid']
            other = next(e for e in pair if e is not end)
            current = lay.xy[sid]
            for xy, reason in _poses(lay, sid, end, lay.xy[other['sid']][other['atom']], base, original_hand, root_turns):
                lay.xy[sid] = xy
                after = _cost(lay, pid)
                gain = benefit(before, after)
                if gain is not None and (best is None or gain < best[0]):
                    best = (gain, 'pose', sid, xy, reason)
            lay.xy[sid] = current
        if best is None:
            break
        _, kind, target, value, reason = best
        if kind == 'end':
            target['atom'] = value
        else:
            lay.xy[target] = value
        changes.append(reason)
        # Finish cheap adjustments across panels before spending a browser draw.
        yield changes[:]


def _write_spec(raw, lay):
    data = copy.deepcopy(raw)
    for p in data['panels']:
        pid = p['id']
        p['hbonds'] = [[specutil.ref_text(e['panel'], e['species'], e['atom']) for e in pair]
                       for pair in lay.panels[lay.pidx[pid]]['hbonds']]
        for sp in p['species']:
            sid = pid + '.' + sp['id']
            # Pin all existing placements, preventing inheritance/contact re-layout
            # from moving the substrate when only a residue was adjusted.
            sp['xy'] = {str(m): list(pt) for m, pt in lay.xy[sid].items()}
    return data


def repair(spec_path, out, png_width=None, browser_cmd=None, log=print):
    started = time.monotonic()
    spec_path, out = Path(spec_path), Path(out)
    raw = json.loads(spec_path.read_text(encoding='utf-8-sig'))
    if out.exists() and any(out.iterdir()):
        raise ValueError('--out must be a new or empty directory')
    out.mkdir(parents=True, exist_ok=True)
    status, _ = draw_figure.run(spec_path, out, png_width=png_width, browser_cmd=browser_cmd, log=lambda s: None)
    if status == 2:
        raise ValueError((out / 'summary.txt').read_text(encoding='utf-8-sig'))
    fig = rules.load_figure(out)
    result = rules.run_checks(fig)
    current_pc = json.loads((out / 'checks.json').read_text(encoding='utf-8-sig'))['positive_control']
    initial = copy.deepcopy(result)
    log('HBONDS: before %d findings; %d failed checks' % (len(findings(result)), len(result['failed'])))
    chosen, accepted = None, []
    attempts = 0
    if findings(result):
        spec = specutil.load_spec(spec_path)
        lay = layout.Layout(spec)
        lay.run()
        hand = copy.deepcopy(lay.xy)
        # Start from the checked baseline's pre-backend layout, including any
        # ordinary bounded repairs; undo each panel's page translation.
        for p in fig.resolved['panels']:
            anchor = p['atoms'][0]
            anchor_sid, anchor_mp = anchor['ref'].rsplit(':', 1)
            ax, ay = lay.xy[anchor_sid][int(anchor_mp)]
            ox, oy = anchor['x']-ax, anchor['y']-ay
            for a in p['atoms']:
                sid, mp = a['ref'].rsplit(':', 1)
                lay.xy[sid][int(mp)] = (a['x']-ox, a['y']-oy)
        seed = copy.deepcopy(lay)
        def plans():
            # Try the simpler contact-centered plan first; root turns are a
            # fallback, sharing the same total MAX_DRAWS real-drawing budget.
            for root_turns in (False, True):
                trial = copy.deepcopy(seed)
                choices = [(_write_spec(raw, trial), changes)
                           for changes in candidates(trial, initial, hand, root_turns)]
                count = layout_repair.MAX_DRAWS - 1 if root_turns else 1
                yield from reversed(choices[-count:])
        for data, changes in plans():
            attempts += 1
            with tempfile.TemporaryDirectory(prefix='.hbond-', dir=str(out)) as temp:
                scratch = Path(temp)
                candidate_path = scratch / 'candidate.json'
                candidate_path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
                # No structural retries: only the explicit hbond plan may move atoms.
                code, _ = draw_figure.run(candidate_path, scratch / 'draw', png_width=png_width,
                                         browser_cmd=browser_cmd, draw=draw_figure._backend(), log=lambda s: None)
                if code == 2:
                    log('HBONDS: candidate %d could not draw; kept baseline' % attempts)
                    continue
                candidate_fig = rules.load_figure(scratch / 'draw')
                checked = rules.run_checks(candidate_fig)
                pc = json.loads((scratch / 'draw' / 'checks.json').read_text(encoding='utf-8-sig'))['positive_control']
                better = pc['ok'] and improves(result, checked)
                log('HBONDS: candidate %d %s; findings %d -> %d; failed checks %d -> %d; remaining: %s' % (
                    attempts, 'accepted' if better else 'rejected', len(findings(result)), len(findings(checked)),
                    len(result['failed']), len(checked['failed']), ', '.join(checked['failed']) or 'none'))
                if better:
                    for name in draw_figure.OUTPUTS:
                        if (scratch / 'draw' / name).is_file():
                            shutil.copyfile(scratch / 'draw' / name, out / name)
                    result, current_pc, chosen, accepted = checked, pc, data, changes
                    if result['ok']:
                        break
    saved = None
    if chosen is not None:
        # Exclusive creation: never overwrite the agent's spec or an earlier repair.
        for index in range(10000):
            suffix = '.hbonds' + ('' if index == 0 else '-%d' % index) + '.json'
            saved = spec_path.with_name(spec_path.stem + suffix)
            try:
                with saved.open('x', encoding='utf-8') as handle:
                    handle.write(json.dumps(chosen, ensure_ascii=False, indent=1) + '\n')
                break
            except FileExistsError:
                continue
        else:
            raise ValueError('no free repaired-input filename')
        for change in accepted:
            log('HBONDS: changed ' + change)
        log('HBONDS: chosen input ' + str(saved))
        if result['ok']:
            draw_figure._save_pass(out, saved.read_bytes())
    elapsed = time.monotonic() - started
    report = {'before': len(findings(initial)), 'after': len(findings(result)), 'attempts': attempts,
              'elapsed_s': round(elapsed, 3), 'changes': accepted, 'chosen_input': str(saved) if saved else None,
              'before_counts': {n: len(c['findings']) for n, c in initial['checks'].items()},
              'after_counts': {n: len(c['findings']) for n, c in result['checks'].items()}}
    (out / 'hbond_repair.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    message = 'HBONDS: %d -> %d findings, %d candidates, %.2f s; %s' % (
        report['before'], report['after'], attempts, elapsed,
        'saved ' + str(saved) if saved else 'no improving candidate; input unchanged')
    with (out / 'summary.txt').open('a', encoding='utf-8') as handle:
        handle.write(message + '\n')
    log(message)
    ok = result['ok'] and current_pc['ok']
    log('RESULT: ' + ('all checks pass' if ok else 'CHECKS FAILED; see summary and manual hbond guidance'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('spec', type=Path, metavar='INPUT.json')
    ap.add_argument('--out', type=Path, required=True, help='new/empty output directory')
    ap.add_argument('--png-width', type=int, help='figure.png width in px instead of the input\'s dpi')
    ap.add_argument('--browser-cmd')
    args = ap.parse_args()
    try:
        return repair(args.spec, args.out, args.png_width, args.browser_cmd,
                      log=lambda s: print(s, flush=True))
    except (OSError, ValueError, rules.InputError) as exc:
        print('HBONDS: error: ' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
