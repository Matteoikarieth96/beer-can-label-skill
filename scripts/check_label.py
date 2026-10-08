#!/usr/bin/env python3
"""QA for a built label: python3 scripts/check_label.py spec.json out/label.svg [--json]

Checks size and ratio against the template, required elements (style, ABV,
volume, producer, emphasised allergens, recycling, best-before box, distributor
placeholder on the Hopera preset), minimum text size in mm, WCAG contrast,
the back-seam safe zone and the top/bottom margins, the field of vision for
name + volume + ABV, em dashes, text overflow and open placeholders.

Exit code 1 when there is at least one error. This is a design aid, not legal
advice: confirm the mandatory particulars with your producer.
"""
import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labelkit.colors import contrast, is_hex  # noqa: E402
from labelkit.spec import SpecError, load_spec, placeholders  # noqa: E402
from labelkit.textfit import est_width  # noqa: E402

LEGAL_ROLES = {"producer", "ingredients", "contains", "abv", "volume", "style", "recycling",
               "recycling-code", "best-before-label", "lot-label"}
KEEP_SAFE_ROLES = {"best-before", "recycling-box", "distributor", "logo", "distributor-logo"}
ALLERGENS = ["barley", "wheat", "rye", "oats?", "spelt", "kamut", "gluten", "lactose", "milk", "sulph?ites",
             "sulfites", "orzo", "frumento", "grano", "segale", "avena", "farro", "glutine", "lattosio", "latte",
             "solfiti", "anidride solforosa"]
ALLERGEN_RE = re.compile(r"\b(" + "|".join(ALLERGENS) + r")\b", re.I)
MALT_RE = re.compile(r"\b(malt|malto)\b", re.I)
TRANSFORM_RE = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")
MAX_SVG_BYTES = 40 * 1024 * 1024


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2, a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def parse_transform(s):
    m = (1, 0, 0, 1, 0, 0)
    for name, args in TRANSFORM_RE.findall(s or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "matrix" and len(v) == 6:
            t = tuple(v)
        elif name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            t = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                t = mul(mul((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "skewX":
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            continue
        m = mul(m, t)
    return m


def apply(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def bbox(m, x0, y0, x1, y1):
    pts = [apply(m, x, y) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def num(value, default=0.0):
    if value is None:
        return default
    m = re.match(r"\s*(-?[0-9.]+)", str(value))
    return float(m.group(1)) if m else default


def is_bold(el):
    w = el.get("font-weight", "")
    return w in ("bold", "bolder") or (w.isdigit() and int(w) >= 600)


def split_emphasis(text_el):
    """Return (plain_text_without_emphasis, emphasised_segments, full_text)."""
    plain, emph = [text_el.text or ""], []
    for child in text_el:
        t = "".join(child.itertext())
        if local(child.tag) == "tspan" and (is_bold(child) or child.get("data-role") == "allergen"):
            emph.append(t)
            plain.append(" " * len(t))
        else:
            plain.append(t)
        plain.append(child.tail or "")
    full = "".join(text_el.itertext())
    return "".join(plain), emph, full


def collect(root, width_factors=None):
    """Walk the SVG with the current transform; return text entries and role boxes."""
    width_factors = width_factors or {}
    texts, boxes = [], []

    def walk(el, ctm, fs, anchor, weight):
        ctm = mul(ctm, parse_transform(el.get("transform")))
        fs = num(el.get("font-size"), fs) if el.get("font-size") else fs
        anchor = el.get("text-anchor", anchor)
        weight = el.get("font-weight", weight)
        tag = local(el.tag)
        if tag == "text":
            full = "".join(el.itertext())
            on_path = any(local(c.tag) == "textPath" for c in el)
            width = num(el.get("data-w"), -1)
            if width < 0:
                wf = width_factors.get(el.get("class", ""), 1.0)
                width = est_width(full, fs, weight in ("700", "bold"), num(el.get("letter-spacing")), wf)
            x, y = num((el.get("x") or "0").split()[0]), num((el.get("y") or "0").split()[0])
            off = {"middle": 0.5, "end": 1.0}.get(anchor, 0.0) * width
            scale = math.sqrt(abs(ctm[0] * ctm[3] - ctm[1] * ctm[2]))
            texts.append({
                "el": el, "role": el.get("data-role", ""), "legal": el.get("data-legal") == "1",
                "text": full, "fs": fs * scale, "bold": weight in ("700", "bold", "800", "900"),
                "bbox": None if on_path else bbox(ctm, x - off, y - 0.8 * fs, x - off + width, y + 0.25 * fs),
                "fill": el.get("fill", ""), "data_fill": el.get("data-fill", ""), "bg": el.get("data-bg", ""),
                "overflow": el.get("data-overflow") == "1",
            })
            parent = texts[-1]
            for sub in el.iter():
                sub_role = sub.get("data-role", "") if local(sub.tag) == "tspan" else ""
                if sub_role and sub_role != "allergen":
                    entry = dict(parent)
                    entry.update({"role": sub_role, "text": "".join(sub.itertext()), "legal": True,
                                  "fill": sub.get("fill", parent["fill"])})
                    texts.append(entry)
            return
        role = el.get("data-role", "")
        if tag in ("rect", "image") and role:
            x, y, w, h = (num(el.get(k)) for k in ("x", "y", "width", "height"))
            boxes.append({"role": role, "bbox": bbox(ctm, x, y, x + w, y + h), "w": w, "h": h, "el": el})
        for child in el:
            walk(child, ctm, fs, anchor, weight)

    walk(root, (1, 0, 0, 1, 0, 0), 16.0, "start", "400")
    return texts, boxes


def check(spec_path, svg_path):
    errors, warnings, info = [], [], []
    try:
        spec, tpl, spec_warn = load_spec(spec_path)
    except SpecError as exc:
        return {"errors": [f"spec: {p}" for p in exc.problems], "warnings": [], "info": []}
    warnings.extend(spec_warn)
    data = Path(svg_path).read_bytes()
    if len(data) > MAX_SVG_BYTES:
        return {"errors": ["SVG is larger than 40 MB"], "warnings": [], "info": []}
    if re.search(rb"<!DOCTYPE|<!ENTITY", data, re.I):
        return {"errors": ["SVG contains a DOCTYPE or ENTITY declaration; refused"], "warnings": [], "info": []}
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        return {"errors": [f"SVG is not well-formed: {exc}"], "warnings": [], "info": []}

    W, H = tpl["width_px"], tpl["height_px"]
    ppm = tpl["px_per_mm"]
    sw, sh = num(root.get("width")), num(root.get("height"))
    if (round(sw), round(sh)) != (W, H):
        errors.append(f"size is {sw:g} x {sh:g} px, the template expects {W} x {H} px")
    if sw < tpl["min_width_px"] or sh < tpl["min_height_px"]:
        errors.append(f"size is below the template minimum {tpl['min_width_px']} x {tpl['min_height_px']} px")
    if sh and abs(sw / sh - tpl["ideal_ratio"]) / tpl["ideal_ratio"] > 0.02:
        warnings.append(f"ratio {sw / sh:.3f} differs from the can wrap ratio {tpl['ideal_ratio']:.3f}")
    if root.get("data-fitted") != "1":
        info.append("text widths are estimated (built without the Chrome fit pass)")
    if root.get("data-fonts-missing"):
        warnings.append(f"web fonts did not load when rendering: {root.get('data-fonts-missing')}")

    fonts = spec["design"]["fonts"]
    texts, boxes = collect(root, {"display": fonts["display"]["width"], "body": fonts["body"]["width"]})
    roles = {t["role"] for t in texts if t["role"]} | {b["role"] for b in boxes}
    qa = spec["qa"]
    min_fs_mm = qa["min_x_height_mm"] / qa["x_height_ratio"]

    def show(t):
        s = t["text"].strip()
        return (s[:48] + "...") if len(s) > 48 else s

    # required elements
    for role, what in (("name", "beer name"), ("style", "beer style"), ("abv", "alcohol by volume"),
                       ("volume", "net volume"), ("producer", "producer name and address")):
        if role not in roles:
            errors.append(f"missing {what} (data-role={role})")
    if not roles & {"recycling", "recycling-code"}:
        errors.append("missing recycling information (for example Can / ALU 41)")
    else:
        code = " ".join(t["text"] for t in texts if t["role"] == "recycling-code")
        if code and not re.search(r"[A-Z]{2,5}\s?\d{1,3}", code):
            warnings.append(f"recycling code {code!r} does not look like a Decision 97/129/EC code (e.g. ALU 41)")
    bb = [b for b in boxes if b["role"] == "best-before"]
    if not bb:
        (errors if spec["best_before"]["show"] else warnings).append("missing best-before box (date and lot are printed into it later)")
    else:
        bw_mm, bh_mm = bb[0]["w"] / ppm, bb[0]["h"] / ppm
        if bw_mm < 20 or bh_mm < 8:
            errors.append(f"best-before box is {bw_mm:.0f} x {bh_mm:.0f} mm; leave at least 30 x 12 mm for date and lot")
        elif bw_mm < 30 or bh_mm < 12:
            warnings.append(f"best-before box is {bw_mm:.0f} x {bh_mm:.0f} mm; 30 x 12 mm or more is safer for inkjet coding")
    if tpl["preset"].startswith("hopera") and "distributor" not in roles:
        errors.append("Hopera preset: missing the 'Distributed by' placeholder box for the distributor's logo")

    # allergens
    allergen_texts = [t for t in texts if t["role"] in ("ingredients", "contains")]
    if not allergen_texts:
        errors.append("no ingredients list or 'Contains:' statement found (allergens must be declared)")
    emphasised = []
    for t in allergen_texts:
        plain, emph, _ = split_emphasis(t["el"])
        emphasised.extend(emph)
        for m in ALLERGEN_RE.finditer(plain):
            errors.append(f"allergen '{m.group(0)}' is not emphasised (bold) in: {show(t)}")
        for m in MALT_RE.finditer(plain):
            warnings.append(f"'{m.group(0)}' is not emphasised: name the cereal (barley malt, wheat malt) and emphasise it")
    if allergen_texts and not any(ALLERGEN_RE.search(e) for e in emphasised):
        if not any(ALLERGEN_RE.search(t["text"]) for t in allergen_texts):
            warnings.append("no allergen declared: beer brewed with barley, wheat, oats or rye must emphasise them; "
                            "confirm the recipe")

    # per-text checks
    margin = spec["layout"]["margin_mm"] * ppm
    seam = W * spec["layout"]["seam_safe_pct"] / 100.0
    pal = spec["design"]["palette"]
    default_bgs = [pal["bg"], pal["bg2"]]
    for t in texts:
        fs_mm = t["fs"] / ppm
        legal = t["legal"] or t["role"] in LEGAL_ROLES
        if t["overflow"]:
            errors.append(f"text does not fit its box even at the minimum size: {show(t)}")
        if legal and fs_mm < min_fs_mm - 0.01:
            errors.append(f"mandatory text is {fs_mm:.2f} mm (x-height about {fs_mm * qa['x_height_ratio']:.2f} mm, "
                          f"minimum {qa['min_x_height_mm']} mm): {show(t)}")
        elif not legal and t["role"] != "placeholder" and fs_mm < 1.8:
            warnings.append(f"text is {fs_mm:.2f} mm tall and hard to read: {show(t)}")
        if t["role"] == "volume" and fs_mm * 0.7 < 4.0:
            warnings.append(f"volume figures are about {fs_mm * 0.7:.1f} mm high; 4 mm is the usual minimum for "
                            "200 ml to 1 l (Directive 76/211/EEC)")
        if t["role"] == "abv" and not re.search(r"\d+(?:[.,]\d)?\s?%\s?vol", t["text"]):
            warnings.append(f"alcohol should read like '5.0% vol' with at most one decimal: {show(t)}")
        if "\u2014" in t["text"]:
            errors.append(f"em dash in text (use a comma, colon or parentheses): {show(t)}")
        if "\u2013" in t["text"]:
            warnings.append(f"en dash in text: {show(t)}")
        # contrast
        fill = t["fill"] if is_hex(t["fill"]) else (t["data_fill"] if is_hex(t["data_fill"]) else None)
        if fill:
            bgs = [t["bg"]] if is_hex(t["bg"]) else default_bgs
            ratio = min(contrast(fill, b) for b in bgs)
            large = fs_mm >= 6.35 or (fs_mm >= 4.94 and t["bold"])
            need = 3.0 if large else 4.5
            if ratio < need:
                msg = f"contrast {ratio:.1f}:1 is below {need}:1 for {'large' if large else 'small'} text: {show(t)}"
                (errors if legal and ratio < 3.0 else warnings).append(msg)
        # geometry
        if t["bbox"]:
            x0, y0, x1, y1 = t["bbox"]
            if x0 < seam or x1 > W - seam:
                errors.append(f"text inside the back-seam safe zone ({spec['layout']['seam_safe_pct']:g}% of the "
                              f"width at each edge): {show(t)}")
            if y0 < margin or y1 > H - margin:
                errors.append(f"text inside the top/bottom margin ({spec['layout']['margin_mm']:g} mm): {show(t)}")
            if t["role"] in ("name", "abv", "volume"):
                cxm = (x0 + x1) / 2
                if not W / 4 <= cxm <= 3 * W / 4:
                    errors.append(f"{t['role']} is outside the front field of vision (name, volume and ABV must be "
                                  f"seen together): {show(t)}")
    for b in boxes:
        if b["role"] in KEEP_SAFE_ROLES:
            x0, y0, x1, y1 = b["bbox"]
            if x0 < seam or x1 > W - seam or y0 < margin or y1 > H - margin:
                errors.append(f"{b['role']} box enters the seam safe zone or the top/bottom margin")

    for item in placeholders(spec):
        warnings.append(f"open placeholder: {item}")
    info.append(f"{len(texts)} text elements checked; minimum legal font size {min_fs_mm:.2f} mm "
                f"({min_fs_mm * ppm:.1f} px at {ppm:.2f} px/mm)")
    return {"errors": errors, "warnings": warnings, "info": info}


def main(argv=None):
    ap = argparse.ArgumentParser(description="QA a built can label against its spec and template.")
    ap.add_argument("spec")
    ap.add_argument("svg")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)
    report = check(args.spec, args.svg)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for key, label in (("errors", "ERROR"), ("warnings", "WARN"), ("info", "INFO")):
            for line in report[key]:
                print(f"{label}: {line}")
        print(f"\n{len(report['errors'])} error(s), {len(report['warnings'])} warning(s). "
              "Not legal advice: confirm mandatory text with your producer.")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
