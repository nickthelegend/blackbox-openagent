"""Camera frames for simulated runs: a fixed pinhole camera over the bench, drawn with Pillow.

Not photoreal, but a real projection of the simulator state, so what the frame shows
(where the bottle is, whether it is in the fingers) agrees with the telemetry.
"""

from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import kinematics as K

W, H = 320, 240
CAM = np.array([0.34, 0.50, 0.44])
LOOK = np.array([0.10, -0.06, 0.05])
FOCAL = 330.0


def _basis():
    f = LOOK - CAM
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return f, r, u


F, R, U = _basis()


def project(p) -> tuple[float, float, float]:
    d = np.asarray(p, float) - CAM
    z = float(d @ F)
    x = float(d @ R)
    y = float(d @ U)
    z = max(z, 1e-3)
    return W / 2 + FOCAL * x / z, H / 2 - FOCAL * y / z, z


def _hex(c: str, k: float = 1.0) -> tuple[int, int, int]:
    c = c.lstrip("#")
    rgb = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    return tuple(int(max(0, min(255, v * k))) for v in rgb)


def _box(o, draw_list):
    w, d, h = o.size
    cx, cy, cz = o.pos
    xs, ys, zs = (cx - w / 2, cx + w / 2), (cy - d / 2, cy + d / 2), (cz - h / 2, cz + h / 2)
    fy = ys[1] if CAM[1] > cy else ys[0]  # the side faces the camera can see
    fx = xs[1] if CAM[0] > cx else xs[0]
    faces = [
        ([(xs[0], ys[0], zs[1]), (xs[1], ys[0], zs[1]), (xs[1], ys[1], zs[1]), (xs[0], ys[1], zs[1])], 1.08),  # top
        ([(xs[0], fy, zs[0]), (xs[1], fy, zs[0]), (xs[1], fy, zs[1]), (xs[0], fy, zs[1])], 0.82),
        ([(fx, ys[0], zs[0]), (fx, ys[1], zs[0]), (fx, ys[1], zs[1]), (fx, ys[0], zs[1])], 0.66),
    ]
    for pts, shade in faces:
        pp = [project(p) for p in pts]
        depth = sum(p[2] for p in pp) / 4
        draw_list.append((depth, "poly", [(p[0], p[1]) for p in pp], _hex(o.color, shade)))


def _cylinder(o, draw_list):
    w, _, h = o.size
    r = w / 2
    cx, cy, cz = o.pos
    n = 18
    top = [(cx + r * math.cos(a), cy + r * math.sin(a), cz + h / 2) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    bot = [(x, y, cz - h / 2) for x, y, _ in top]
    pt, pb = [project(p) for p in top], [project(p) for p in bot]
    # silhouette: left- and right-most projected points
    xs = [p[0] for p in pt + pb]
    lo, hi = int(np.argmin(xs)) % n, int(np.argmax(xs)) % n
    depth = project(o.pos)[2]
    body = [(pb[i][0], pb[i][1]) for i in range(n)]
    draw_list.append((depth + 0.002, "poly", body, _hex(o.color, 0.78)))
    side = [(pt[lo][0], pt[lo][1]), (pt[hi][0], pt[hi][1]), (pb[hi][0], pb[hi][1]), (pb[lo][0], pb[lo][1])]
    draw_list.append((depth + 0.001, "poly", side, _hex(o.color, 0.86)))
    draw_list.append((depth, "poly", [(p[0], p[1]) for p in pt], _hex(o.color, 1.06)))
    if "bottle" in o.label:  # cap
        cap_c = {"pill_bottle": "#c64b2b", "vitamin_bottle": "#c9572f", "water_bottle": "#2f4f7a"}[o.label]
        cr = r * 0.62
        cap = [(cx + cr * math.cos(a), cy + cr * math.sin(a), cz + h / 2 + 0.008) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        draw_list.append((depth - 0.001, "poly", [project(p)[:2] for p in cap], _hex(cap_c)))
        if o.label == "vitamin_bottle":  # the one visual difference: a pale stripe on the cap
            draw_list.append((depth - 0.002, "poly", [project(p)[:2] for p in cap[:5]] + [project((cx, cy, cz + h / 2 + 0.008))[:2]], _hex("#f1d9a8")))


def render_frame(sim, tcp) -> bytes:
    img = Image.new("RGB", (W, H), (58, 62, 66))
    dr = ImageDraw.Draw(img)
    # wall and bench
    for i in range(H):
        k = i / H
        dr.line([(0, i), (W, i)], fill=(int(70 - 22 * k), int(74 - 22 * k), int(78 - 20 * k)))
    bench = [(-0.12, -0.34, 0), (0.40, -0.34, 0), (0.40, 0.34, 0), (-0.12, 0.34, 0)]
    dr.polygon([project(p)[:2] for p in bench], fill=(156, 138, 112))
    # bench grain
    for k in np.linspace(-0.3, 0.3, 14):
        a, b = project((-0.12, k, 0)), project((0.40, k, 0))
        dr.line([a[:2], b[:2]], fill=(146, 128, 103), width=1)
    # zones
    for name, z in sim.setup.zones.items():
        (cx, cy), (w, d) = z["center"], z["size"]
        rim = [(cx - w / 2, cy - d / 2, 0.001), (cx + w / 2, cy - d / 2, 0.001), (cx + w / 2, cy + d / 2, 0.001), (cx - w / 2, cy + d / 2, 0.001)]
        dr.polygon([project(p)[:2] for p in rim], fill=(70, 76, 84), outline=(30, 33, 36))
    items = []
    # shadows
    for o in sim.objs.values():
        sx, sy = o.pos[0] + 0.006, o.pos[1] + 0.006
        r = max(o.size[0], o.size[1]) * 0.6
        sh = [(sx + r * math.cos(a), sy + r * math.sin(a), 0.0005) for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
        dr.polygon([project(p)[:2] for p in sh], fill=(124, 110, 90))
    for o in sim.objs.values():
        (_cylinder if o.shape == "cylinder" else _box)(o, items)
    # arm
    c = K.chain(sim.q)
    pts = [c["base"], c["shoulder"], c["elbow"], c["wrist"], c["tip"]]
    widths = [14, 11, 9, 6]
    for i in range(4):
        a, b = project(pts[i]), project(pts[i + 1])
        items.append(((a[2] + b[2]) / 2, "line", [a[:2], b[:2]], (34, 37, 41) if i < 3 else (52, 56, 61), widths[i]))
    for i, p in enumerate(pts[1:4]):
        a = project(p)
        rr = [6, 5, 4][i]
        items.append((a[2] - 0.001, "dot", (a[0], a[1], rr), (232, 120, 40)))
    # fingers
    gw = K.opening_to_width(sim.g) / 2 + 0.004
    b = math.radians(sim.q[0])
    perp = np.array([-math.sin(b), math.cos(b), 0])
    palm = c["wrist"] + (c["tip"] - c["wrist"]) * 0.55
    pa, pb = project(palm + perp * gw), project(palm - perp * gw)
    items.append((min(pa[2], pb[2]) - 0.002, "line", [pa[:2], pb[:2]], (52, 56, 61), 4))
    for sgn in (-1, 1):
        top = palm + perp * sgn * gw
        tip = c["tip"] + perp * sgn * gw + np.array([0, 0, -0.01])
        a, bb = project(top), project(tip)
        items.append((min(a[2], bb[2]) - 0.003, "line", [a[:2], bb[:2]], (210, 212, 214), 3))
    items.sort(key=lambda it: -it[0])
    for it in items:
        kind = it[1]
        if kind == "poly":
            dr.polygon(it[2], fill=it[3])
        elif kind == "line":
            dr.line(it[2], fill=it[3], width=it[4])
        else:
            x, y, rr = it[2]
            dr.ellipse([x - rr, y - rr, x + rr, y + rr], fill=it[3])
    img = img.filter(ImageFilter.GaussianBlur(0.45))
    # sensor noise and vignette, so it reads as a camera and not a diagram
    arr = np.asarray(img, dtype=np.float32)
    arr += sim.rng.normal(0, 3.2, arr.shape)
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - 0.28 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    arr *= vig[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(img)
    stamp = f"CAM0  {sim.t:05.2f}s"
    dr.text((8, H - 16), stamp, fill=(236, 236, 228))
    dr.text((W - 52, 6), "SIM", fill=(236, 236, 228))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=74, optimize=True)
    return buf.getvalue()
