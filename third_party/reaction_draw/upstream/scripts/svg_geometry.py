#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Geometry of the backend's SVG for check_rules.py: numbers and lengths, path outlines, shapes and the signed
clearance between them (in points)."""
import math
import re
import xml.etree.ElementTree as ET

SVG_NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG_NS)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')

class CheckError(Exception):
    """An SVG that cannot be read."""


# ----------------------------------------------------------------------------------------------- small helpers
_NUM = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')


def nums(s):
    return [float(x) for x in _NUM.findall(s or '')]


def local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


# ----------------------------------------------------------------------------------------------- what the backend writes
def group_scale(transform):
    """The factor of a group's scale(s) transform, the only transform in the export (1.0 without one)."""
    if not transform:
        return 1.0
    m = re.fullmatch(r'\s*scale\(\s*(%s)\s*\)\s*' % _NUM.pattern, transform)
    if not m:
        raise CheckError('unsupported transform %r' % transform)
    return float(m.group(1))


def parse_path(d):
    """Path data of absolute M, L and Z commands, all that the export holds -> [(points, closed)]."""
    subs, pts = [], []
    for cmd, body in re.findall(r'([A-Za-z])([^A-Za-z]*)', d or ''):
        if cmd not in 'MLZ':
            raise CheckError('unsupported path command %r' % cmd)
        if cmd != 'L' and pts:
            subs.append((pts, cmd == 'Z'))
            pts = []
        v = nums(body)
        pts += [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]
    if pts:
        subs.append((pts, False))
    return subs


# ----------------------------------------------------------------------------------------------- geometry
def dist_pt_seg(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / l2
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def dist_seg_seg(p, q, r, s):
    d1, d2, d3, d4 = _orient(r, s, p), _orient(r, s, q), _orient(p, q, r), _orient(p, q, s)
    if ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4)):
        return 0.0
    return min(dist_pt_seg(p[0], p[1], r[0], r[1], s[0], s[1]), dist_pt_seg(q[0], q[1], r[0], r[1], s[0], s[1]),
               dist_pt_seg(r[0], r[1], p[0], p[1], q[0], q[1]), dist_pt_seg(s[0], s[1], p[0], p[1], q[0], q[1]))


def point_in_poly(x, y, pts):
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def poly_area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                     for i in range(len(pts)))


def bbox_gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def dist_pt_box(p, box):
    return math.hypot(max(box[0] - p[0], 0.0, p[0] - box[2]), max(box[1] - p[1], 0.0, p[1] - box[3]))


def _is_convex(pts):
    n, sign = len(pts), 0
    if n < 3:
        return False
    for i in range(n):
        a, b, c = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cr) < 1e-12:
            continue
        sg = 1 if cr > 0 else -1
        if sign == 0:
            sign = sg
        elif sg != sign:
            return False
    return sign != 0


class Shape(object):
    """A drawn primitive in root viewBox space.  cls: bond | mark | arrow | glyph."""
    __slots__ = ('cls', 'kind', 'pts', 'closed', 'fill', 'hw', 'desc', 'sid', 'owner', 'quad', 'bbox', 'segs',
                 '_ends', 'el_idx', 'convex')

    def __init__(self, cls, kind, pts, closed, fill, hw, desc, quad=False):
        self.cls, self.kind, self.pts, self.closed, self.fill, self.hw = cls, kind, pts, closed, fill, hw
        self.desc, self.quad, self.sid, self.owner, self._ends, self.el_idx = desc, quad, None, None, None, None
        n = len(pts)
        segs = [(pts[i], pts[i + 1]) for i in range(n - 1)]
        if closed and n > 2:
            segs.append((pts[-1], pts[0]))
        self.segs = segs or [(pts[0], pts[0])]
        self.convex = bool(closed and fill and _is_convex(pts))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.bbox = (min(xs) - hw, min(ys) - hw, max(xs) + hw, max(ys) + hw)

    def ends(self):
        """(end points, axis segment) of a bond-like shape; used for the 'attached' test."""
        if self._ends is None:
            pts = self.pts
            if self.kind in ('seg', 'line'):
                self._ends = ([pts[0], pts[-1]], (pts[0], pts[-1]))
            else:
                far = (0.0, pts[0], pts[0])
                for i in range(len(pts)):
                    for j in range(i + 1, len(pts)):
                        d = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                        if d > far[0]:
                            far = (d, pts[i], pts[j])
                length, p, q = far
                cx, cy = sum(v[0] for v in pts) / len(pts), sum(v[1] for v in pts) / len(pts)
                area = abs(poly_area(pts)) if len(pts) > 2 else 0.0
                if length > 0 and self.fill and area > 0 and length >= 2.5 * (area / length) and self.kind != 'ring':
                    u = ((q[0] - p[0]) / length, (q[1] - p[1]) / length)
                    ts = [(v[0] - cx) * u[0] + (v[1] - cy) * u[1] for v in pts]
                    e1 = (cx + u[0] * min(ts), cy + u[1] * min(ts))
                    e2 = (cx + u[0] * max(ts), cy + u[1] * max(ts))
                    self._ends = ([e1, e2], (e1, e2))
                else:
                    self._ends = ([(cx, cy)], ((cx, cy), (cx, cy)))
        return self._ends


def dist_shapes(a, b):
    """(geometric distance between two shapes, crossing).  Distance is 0 and crossing True when they intersect."""
    if a.fill and a.closed and point_in_poly(b.pts[0][0], b.pts[0][1], a.pts):
        return 0.0, True
    if b.fill and b.closed and point_in_poly(a.pts[0][0], a.pts[0][1], b.pts):
        return 0.0, True
    best = float('inf')
    for p, q in a.segs:
        for r, s in b.segs:
            d = dist_seg_seg(p, q, r, s)
            if d <= 0.0:
                return 0.0, True
            if d < best:
                best = d
    return best, False


def _inward_depth(pt, quad, sign):
    """Distance from pt to the boundary of a convex polygon if pt is inside, else None."""
    depth = float('inf')
    n = len(quad)
    for i in range(n):
        p, q = quad[i], quad[(i + 1) % n]
        ex, ey = q[0] - p[0], q[1] - p[1]
        length = math.hypot(ex, ey)
        if length == 0:
            continue
        d = ((pt[0] - p[0]) * (-ey * sign) + (pt[1] - p[1]) * (ex * sign)) / length
        if d < 0:
            return None
        depth = min(depth, d)
    return depth if depth != float('inf') else None


def max_depth_in_quad(shape, quad):
    """How deep the shape's outline reaches into a convex quad (sampled along its segments)."""
    sign = 1.0 if poly_area(quad) > 0 else -1.0
    xs, ys = [p[0] for p in quad], [p[1] for p in quad]
    step = max(min(max(xs) - min(xs), max(ys) - min(ys)) / 6.0, 1e-3)
    best = 0.0
    for (p, q) in shape.segs:
        n = max(1, int(math.ceil(math.hypot(q[0] - p[0], q[1] - p[1]) / step)))
        for k in range(n + 1):
            t = k / float(n)
            d = _inward_depth((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t), quad, sign)
            if d is not None and d > best:
                best = d
    return best


def clearance(a, b):
    """Signed clearance between two shapes (negative: overlapping, magnitude = depth where it can be told)."""
    if a.convex and b.convex:
        return quad_gap(a.pts, b.pts) - a.hw - b.hw
    d, crossing = dist_shapes(a, b)
    if not crossing:
        return d - a.hw - b.hw
    depth = 0.0
    if b.quad:
        depth = max_depth_in_quad(a, b.pts)
    elif a.quad:
        depth = max_depth_in_quad(b, a.pts)
    return -(a.hw + b.hw + depth)


def quad_gap(p, q):
    """Signed gap of two convex polygons: > 0 distance, < 0 penetration depth (separating-axis test)."""
    best_pen, separated = float('inf'), False
    for poly in (p, q):
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            nx, ny = b[1] - a[1], -(b[0] - a[0])
            length = math.hypot(nx, ny)
            if length == 0:
                continue
            nx, ny = nx / length, ny / length
            pp = [nx * v[0] + ny * v[1] for v in p]
            qq = [nx * v[0] + ny * v[1] for v in q]
            sep = max(min(qq) - max(pp), min(pp) - max(qq))
            if sep >= 0:
                separated = True
            else:
                best_pen = min(best_pen, -sep)
    if separated:
        best = float('inf')
        for i in range(len(p)):
            for j in range(len(q)):
                best = min(best, dist_seg_seg(p[i], p[(i + 1) % len(p)], q[j], q[(j + 1) % len(q)]))
        return best
    return -best_pen


# ----------------------------------------------------------------------------------------------- SVG -> scene
_UNIT_PT = {'pt': 1.0, 'px': 0.75, 'mm': 72.0 / 25.4, 'cm': 72.0 / 2.54, 'in': 72.0, 'pc': 12.0, '': 0.75}


def length_pt(v):
    m = re.match(r'^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([a-z%]*)\s*$', v or '')
    if not m or m.group(2) not in _UNIT_PT:
        return None
    return float(m.group(1)) * _UNIT_PT[m.group(2)]
