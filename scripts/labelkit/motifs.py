"""Parametric SVG motifs.

Every motif returns (defs, body) SVG fragments. Bands, waves and mountains are
built with a period that divides the label width exactly, so the pattern meets
itself at the back seam without a visible jump.

Roles: background (one), frame (one, around the front emblem), emblem (drawn
when there is no logo), band (top and bottom), scenery (bottom of the wrap).
"""
import math

from .colors import darken, is_hex, lighten, mix
from .safety import text_problem

PALETTE_ROLES = ("bg", "bg2", "primary", "secondary", "text", "muted", "panel")


def _p(kind, *args):
    return (kind,) + args


MOTIFS = {
    "sunburst": {"role": "background", "params": {
        "color": _p("color", "primary"), "rays": _p("int", 12, 120, 40),
        "opacity": _p("float", 0.02, 0.4, 0.08), "reach": _p("float", 0.3, 1.5, 0.8)}},
    "laurel": {"role": "frame", "params": {
        "color": _p("color", "primary"), "leaves": _p("int", 6, 18, 12), "berries": _p("bool", True)}},
    "roundel": {"role": "frame", "params": {
        "color": _p("color", "primary"), "ring_text": _p("text", 80, ""), "stars": _p("int", 0, 9, 3)}},
    "hop": {"role": "emblem", "params": {
        "color": _p("color", "secondary"), "leaf_color": _p("color", "primary")}},
    "greek-key": {"role": "band", "params": {
        "color": _p("color", "primary"), "height_mm": _p("float", 3.0, 10.0, 5.5)}},
    "zigzag": {"role": "band", "params": {
        "color": _p("color", "primary"), "height_mm": _p("float", 3.0, 10.0, 5.0), "lines": _p("int", 1, 3, 2)}},
    "waves": {"role": "scenery", "params": {
        "color": _p("color", "secondary"), "layers": _p("int", 1, 5, 3), "height_pct": _p("float", 5, 30, 14),
        "opacity": _p("float", 0.1, 1.0, 0.35), "amplitude_mm": _p("float", 0.5, 6, 2.2),
        "period_mm": _p("float", 8, 60, 26)}},
    "mountains": {"role": "scenery", "params": {
        "color": _p("color", "secondary"), "layers": _p("int", 1, 4, 3), "height_pct": _p("float", 8, 35, 18),
        "opacity": _p("float", 0.1, 1.0, 0.4), "peaks": _p("int", 3, 20, 9), "seed": _p("int", 1, 9999, 7),
        "snow": _p("bool", False)}},
}


def validate_motif(m, palette=None):
    if not isinstance(m, dict) or not isinstance(m.get("type"), str) or m.get("type") not in MOTIFS:
        raise ValueError(f"unknown motif {m.get('type') if isinstance(m, dict) else m!r} "
                         f"(choose from {', '.join(sorted(MOTIFS))})")
    spec = MOTIFS[m["type"]]["params"]
    extra = set(m) - {"type"} - set(spec)
    if extra:
        raise ValueError(f"{m['type']}: unknown parameter(s) {', '.join(sorted(extra))}")
    out = {}
    for name, rule in spec.items():
        kind = rule[0]
        val = m.get(name, rule[-1])
        if kind == "color":
            if not (val in PALETTE_ROLES or is_hex(val)):
                raise ValueError(f"{m['type']}.{name}: palette role ({', '.join(PALETTE_ROLES)}) or #rrggbb")
        elif kind == "int":
            if isinstance(val, bool) or not isinstance(val, int) or not rule[1] <= val <= rule[2]:
                raise ValueError(f"{m['type']}.{name}: integer between {rule[1]} and {rule[2]}")
        elif kind == "float":
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not rule[1] <= val <= rule[2]:
                raise ValueError(f"{m['type']}.{name}: number between {rule[1]} and {rule[2]}")
            val = float(val)
        elif kind == "bool":
            if not isinstance(val, bool):
                raise ValueError(f"{m['type']}.{name}: true or false")
        elif kind == "text":
            if not isinstance(val, str) or len(val) > rule[1] or text_problem(val):
                raise ValueError(f"{m['type']}.{name}: one line of text up to {rule[1]} characters "
                                 "(no line breaks, tabs or control characters)")
        out[name] = val
    return {"type": m["type"], "params": out}


def color_of(ctx, value):
    return ctx["palette"][value] if value in ctx["palette"] else value


def ink(ctx, value):
    """Fill for an accent: the metallic gradient when the colour is primary and metallic is on."""
    if value == "primary" and ctx.get("metallic"):
        return "url(#metal)"
    return color_of(ctx, value)


# --------------------------------------------------------------------------- background

def sunburst(ctx, p):
    cx, cy = ctx["cx"], ctx["hero_cy"]
    reach = p["reach"] * ctx["H"]
    rays = []
    n = p["rays"]
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + math.pi / n
        rays.append(f"M{cx:.1f},{cy:.1f} L{cx + reach * math.cos(a0):.1f},{cy + reach * math.sin(a0):.1f} "
                    f"L{cx + reach * math.cos(a1):.1f},{cy + reach * math.sin(a1):.1f}Z")
    defs = (f'<radialGradient id="sunfade"><stop offset="0" stop-color="#fff"/>'
            f'<stop offset=".85" stop-color="#fff" stop-opacity="0"/></radialGradient>'
            f'<mask id="sunmask"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{reach:.1f}" fill="url(#sunfade)"/></mask>')
    body = (f'<path d="{" ".join(rays)}" fill="{color_of(ctx, p["color"])}" opacity="{p["opacity"]:.3f}" '
            f'mask="url(#sunmask)"/>')
    return defs, body


# --------------------------------------------------------------------------- frames

def _leaf(x, y, ang, length, width, fill, stroke, sw):
    d = (f"M0,0 C{length * .3:.1f},{-width:.1f} {length * .75:.1f},{-width * .8:.1f} {length:.1f},0 "
         f"C{length * .75:.1f},{width * .8:.1f} {length * .3:.1f},{width:.1f} 0,0Z")
    return (f'<g transform="translate({x:.1f},{y:.1f}) rotate({math.degrees(ang):.1f})">'
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw:.1f}"/>'
            f'<path d="M{length * .05:.1f},0 L{length * .86:.1f},0" stroke="{stroke}" stroke-width="{sw * .8:.1f}" '
            f'opacity=".7"/></g>')


def laurel(ctx, p):
    cx, cy, r = ctx["cx"], ctx["hero_cy"], ctx["hero_r"]
    fill = ink(ctx, p["color"])
    base = color_of(ctx, p["color"]) if not fill.startswith("url") else ctx["palette"]["primary"]
    stroke = darken(base, 0.45)
    R = 0.80 * r
    n = p["leaves"]
    sw = max(1.0, r * 0.008)
    out = []
    for side in (1, -1):
        a0, a1 = math.radians(84), math.radians(-56)
        pts = []
        for i in range(n + 1):
            t = i / n
            a = a0 + (a1 - a0) * t
            pts.append((cx + side * R * math.cos(a), cy + R * math.sin(a), a, t))
        stem = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y, a, t) in enumerate(pts))
        out.append(f'<path d="{stem}" fill="none" stroke="{fill}" stroke-width="{r * .02:.1f}" stroke-linecap="round"/>')
        for i, (x, y, a, t) in enumerate(pts[:-1]):
            dx, dy = math.sin(a), -math.cos(a)
            nx, ny = math.cos(a), math.sin(a)
            if side < 0:
                dx, nx = -dx, -nx
            g = math.atan2(dy, dx)
            length = r * (0.36 - 0.15 * t)
            width = r * (0.098 - 0.035 * t)
            spread = math.radians(38)
            out.append(_leaf(x + nx * r * .016, y + ny * r * .016, g - side * spread, length, width, fill, stroke, sw))
            out.append(_leaf(x - nx * r * .016, y - ny * r * .016, g + side * spread, length * .88, width * .9,
                             fill, stroke, sw))
            if p["berries"] and i in (n // 5, n // 2, (4 * n) // 5):
                bx, by = x + nx * r * .12 + dx * r * .07, y + ny * r * .12 + dy * r * .07
                out.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r * .035:.1f}" fill="{fill}" '
                           f'stroke="{stroke}" stroke-width="{sw:.1f}"/>')
        x, y, a, t = pts[-1]
        dx, dy = math.sin(a), -math.cos(a)
        if side < 0:
            dx = -dx
        out.append(_leaf(x, y, math.atan2(dy, dx), r * .23, r * .067, fill, stroke, sw))
    return "", '<g data-motif="laurel">' + "".join(out) + "</g>"


def _star(x, y, rad, fill):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = rad if k % 2 == 0 else rad * 0.42
        pts.append(f"{x + rr * math.cos(a):.1f},{y + rr * math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'


def roundel(ctx, p):
    from .safety import esc
    cx, cy, r = ctx["cx"], ctx["hero_cy"], ctx["hero_r"]
    fill = ink(ctx, p["color"])
    out = [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * .97:.1f}" fill="none" stroke="{fill}" stroke-width="{r * .03:.1f}"/>',
           f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * .78:.1f}" fill="none" stroke="{fill}" stroke-width="{r * .014:.1f}"/>']
    defs = ""
    rr = r * 0.835
    if p["ring_text"]:
        defs = (f'<path id="ringpath" d="M{cx - rr:.1f},{cy:.1f} A{rr:.1f},{rr:.1f} 0 0 1 {cx + rr:.1f},{cy:.1f}" '
                f'fill="none"/>')
        fs = r * 0.095
        out.append(f'<text class="display" font-size="{fs:.1f}" font-weight="700" letter-spacing="{fs * .18:.1f}" '
                   f'fill="{fill}" data-fill="{ctx["palette"]["primary"] if fill.startswith("url") else fill}" '
                   f'data-role="ring-text" data-maxw="{math.pi * rr * .9:.1f}" data-minfs="{fs * .55:.1f}">'
                   f'<textPath href="#ringpath" xlink:href="#ringpath" startOffset="50%" text-anchor="middle">'
                   f'{esc(p["ring_text"])}</textPath></text>')
    n = p["stars"]
    for k in range(n):
        a = math.pi / 2 + (k - (n - 1) / 2) * 0.24
        out.append(_star(cx + rr * 1.04 * math.cos(a), cy + rr * 1.04 * math.sin(a), r * 0.045, fill))
    return defs, '<g data-motif="roundel">' + "".join(out) + "</g>"


# --------------------------------------------------------------------------- emblem

def hop(ctx, p, cx=None, cy=None, size=None):
    """Stylised hop cone: shingled, pointed bracts and two leaves on a curled stem."""
    cx = ctx["cx"] if cx is None else cx
    cy = ctx["hero_cy"] if cy is None else cy
    S = ctx["emblem_size"] if size is None else size
    body_fill = color_of(ctx, p["color"])
    leaf_fill = ink(ctx, p["leaf_color"])
    leaf_base = ctx["palette"]["primary"] if leaf_fill.startswith("url") else leaf_fill
    stroke = darken(body_fill, 0.5)
    leaf_stroke = darken(leaf_base, 0.45)
    sw = max(1.0, S * 0.008)
    cone_h, cone_w = S * 0.66, S * 0.56
    top = cy - cone_h * 0.36
    out = []
    # curled stem and two large leaves
    out.append(f'<path d="M{cx:.1f},{top + S * .03:.1f} C{cx - S * .01:.1f},{top - S * .08:.1f} '
               f'{cx + S * .06:.1f},{top - S * .15:.1f} {cx + S * .13:.1f},{top - S * .14:.1f} '
               f'C{cx + S * .19:.1f},{top - S * .13:.1f} {cx + S * .18:.1f},{top - S * .07:.1f} '
               f'{cx + S * .13:.1f},{top - S * .075:.1f}" fill="none" stroke="{leaf_stroke}" '
               f'stroke-width="{S * .016:.1f}" stroke-linecap="round"/>')
    out.append(_leaf(cx - S * .01, top - S * .05, math.radians(-158), S * .36, S * .12, leaf_fill, leaf_stroke, sw))
    out.append(_leaf(cx + S * .03, top - S * .09, math.radians(-38), S * .30, S * .105, leaf_fill, leaf_stroke, sw))
    rows = 5
    bracts = []
    for k in range(rows):
        t = (k + 0.5) / rows
        y = top + t * cone_h
        hw = (cone_w / 2) * math.sin(math.pi * (0.16 + 0.76 * t)) ** 0.7
        n = 2 if k % 2 == 0 else 3
        if k == rows - 1:
            n = 1
        a = (2 * hw / n) * 0.62
        c = cone_h / rows * 0.95
        for j in range(n):
            bx = cx + (j - (n - 1) / 2) * (2 * hw / n) * (0.95 if n > 1 else 1)
            bracts.append((k, bx, y, a, c))
    for k, bx, y, a, c in sorted(bracts, key=lambda b: -b[0]):
        shade = mix(body_fill, "#ffffff", 0.14 * (1 - k / rows))
        d = (f"M{bx - a:.1f},{y - c * .5:.1f} Q{bx:.1f},{y - c * 1.0:.1f} {bx + a:.1f},{y - c * .5:.1f} "
             f"C{bx + a * 1.05:.1f},{y + c * .15:.1f} {bx + a * .45:.1f},{y + c * .7:.1f} {bx:.1f},{y + c * 1.05:.1f} "
             f"C{bx - a * .45:.1f},{y + c * .7:.1f} {bx - a * 1.05:.1f},{y + c * .15:.1f} {bx - a:.1f},{y - c * .5:.1f}Z")
        out.append(f'<path d="{d}" fill="{shade}" stroke="{stroke}" stroke-width="{sw:.1f}" stroke-linejoin="round"/>')
        out.append(f'<path d="M{bx:.1f},{y - c * .45:.1f} L{bx:.1f},{y + c * .8:.1f}" stroke="{stroke}" '
                   f'stroke-width="{sw * .8:.1f}" opacity=".5"/>')
    return "", '<g data-motif="hop">' + "".join(out) + "</g>"


# --------------------------------------------------------------------------- bands

def _band_y(ctx, h, where):
    top = ctx["band_offset"]
    return top if where == "top" else ctx["H"] - top - h


def greek_key(ctx, p):
    W = ctx["W"]
    h = p["height_mm"] * ctx["ppm"]
    stroke = ink(ctx, p["color"])
    sw = h * 0.085
    n = max(4, round(W / (h * 1.15)))
    u = W / n
    out = []
    for where in ("top", "bottom"):
        y0 = _band_y(ctx, h, where)

        def Y(v):  # v in 0..56 key space, 0 = outer edge
            yy = y0 + v / 56 * h
            return yy if where == "top" else (y0 + h) - (yy - y0)
        parts = [f"M0,{Y((sw / 2) / h * 56):.1f} H{W:.1f}", f"M0,{Y(51.5):.1f} H{W:.1f}"]
        for i in range(n):
            x0 = i * u
            X = lambda v: x0 + v / 64 * u  # noqa: E731
            parts.append(f"M{X(8):.1f},{Y(51.5):.1f} V{Y(14):.1f} H{X(54):.1f} V{Y(42):.1f} H{X(22):.1f} "
                         f"V{Y(26):.1f} H{X(40):.1f}")
        out.append(f'<path d="{" ".join(parts)}" fill="none" stroke="{stroke}" stroke-width="{sw:.1f}" '
                   f'stroke-linejoin="miter" stroke-linecap="square" data-band="{where}"/>')
    return "", '<g data-motif="greek-key">' + "".join(out) + "</g>"


def zigzag(ctx, p):
    W = ctx["W"]
    h = p["height_mm"] * ctx["ppm"]
    stroke = ink(ctx, p["color"])
    sw = h * 0.09
    n = max(4, round(W / (h * 1.1)))
    u = W / n
    out = []
    for where in ("top", "bottom"):
        y0 = _band_y(ctx, h, where)
        parts = [f"M0,{y0 + sw / 2:.1f} H{W:.1f}", f"M0,{y0 + h - sw / 2:.1f} H{W:.1f}"]
        lines = p["lines"]
        inner_top, inner_h = y0 + h * 0.22, h * 0.56
        for L in range(lines):
            amp = inner_h / (lines + 0.6)
            yb = inner_top + L * amp * 0.6
            pts = []
            for i in range(n + 1):
                pts.append(f"{i * u:.1f},{yb + amp:.1f}")
                if i < n:
                    pts.append(f"{i * u + u / 2:.1f},{yb:.1f}")
            parts.append("M" + " L".join(pts))
        out.append(f'<path d="{" ".join(parts)}" fill="none" stroke="{stroke}" stroke-width="{sw:.1f}" '
                   f'stroke-linejoin="miter" data-band="{where}"/>')
    return "", '<g data-motif="zigzag">' + "".join(out) + "</g>"


# --------------------------------------------------------------------------- scenery

def waves(ctx, p):
    W, H, ppm = ctx["W"], ctx["H"], ctx["ppm"]
    color = color_of(ctx, p["color"])
    top = H * (1 - p["height_pct"] / 100)
    L = p["layers"]
    out = []
    step = max(4.0, W / 600)
    for i in range(L):
        base = top + (i / max(1, L)) * (H - top) * 0.62
        amp = p["amplitude_mm"] * ppm * (1 - 0.12 * i)
        k = max(1, round(W / (p["period_mm"] * ppm * (1 + 0.25 * (L - 1 - i)))))
        phase = i * 1.3
        pts = []
        x = 0.0
        while x < W:
            pts.append(f"{x:.1f},{base + amp * math.sin(2 * math.pi * k * x / W + phase):.1f}")
            x += step
        pts.append(f"{W:.1f},{base + amp * math.sin(2 * math.pi * k + phase):.1f}")
        op = p["opacity"] * (0.45 + 0.55 * (i + 1) / L)
        out.append(f'<path d="M0,{H} L{" L".join(pts)} L{W},{H}Z" fill="{color}" fill-opacity="{op:.3f}"/>')
    return "", '<g data-motif="waves">' + "".join(out) + "</g>"


def mountains(ctx, p):
    W, H = ctx["W"], ctx["H"]
    color = color_of(ctx, p["color"])
    top = H * (1 - p["height_pct"] / 100)
    L = p["layers"]
    out = []
    state = [p["seed"] * 7919 + 13]

    def rnd():
        state[0] = (state[0] * 1103515245 + 12345) % 2147483648
        return state[0] / 2147483648

    for i in range(L):
        n = p["peaks"] + 2 * i
        span = (H - top) * (1 - 0.18 * i)
        base = H
        heights = [span * (0.55 + 0.45 * rnd()) for _ in range(n)]
        heights.append(heights[0])  # same height at both edges, no jump at the back seam
        pts = []
        caps = []
        for j in range(n + 1):
            x = j * W / n
            pts.append((x, base - heights[j]))
            if j < n:
                pts.append((x + W / (2 * n), base - heights[j] * (0.25 + 0.3 * rnd()) - span * 0.05))
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        op = p["opacity"] * (0.45 + 0.55 * (i + 1) / L)
        shade = mix(color, ctx["palette"]["bg2"], 0.35 * (L - 1 - i) / max(1, L - 1))
        out.append(f'<polygon points="0,{H} {poly} {W},{H}" fill="{shade}" fill-opacity="{op:.3f}"/>')
        if p["snow"] and i == 0:
            for j in range(0, len(pts) - 1, 2):
                px, py = pts[j]
                lx, ly = pts[j - 1] if j > 0 else (pts[-2][0] - W, pts[-2][1])
                rx, ry = pts[j + 1]
                f = 0.22
                a = (px + (lx - px) * f, py + (ly - py) * f)
                b = (px + (rx - px) * f, py + (ry - py) * f)
                m = (px, py + (a[1] - py) * 0.9)
                caps.append(f'<polygon points="{px:.1f},{py:.1f} {b[0]:.1f},{b[1]:.1f} '
                            f'{(px + b[0]) / 2:.1f},{m[1]:.1f} {(px + a[0]) / 2:.1f},{m[1] * 1.0:.1f} '
                            f'{a[0]:.1f},{a[1]:.1f}" fill="{lighten(color, .75)}" fill-opacity="{op:.3f}"/>')
        out.extend(caps)
    return "", '<g data-motif="mountains">' + "".join(out) + "</g>"


DRAW = {"sunburst": sunburst, "laurel": laurel, "roundel": roundel, "hop": hop,
        "greek-key": greek_key, "zigzag": zigzag, "waves": waves, "mountains": mountains}
