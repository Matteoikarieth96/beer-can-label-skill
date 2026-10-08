"""Input safety: escaping, path containment, logo loading and SVG sanitizing.

Every logo is untrusted data. PNG and JPEG files are checked by magic bytes and
embedded as base64 data URIs. SVG logos are parsed, reduced to a whitelist of
drawing elements and attributes, and then embedded as an <image> data URI (never
inlined), so even a missed construct cannot run script or fetch anything.
"""
import base64
import html
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_LOGO_PIXELS = 12000  # per side, for PNG/JPEG headers

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ALLOWED_TAGS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "textPath", "defs", "linearGradient", "radialGradient", "stop",
    "clipPath", "mask", "pattern", "symbol", "use", "title", "desc", "style", "image",
    "filter", "feGaussianBlur", "feOffset", "feBlend", "feColorMatrix", "feComposite",
    "feFlood", "feMerge", "feMergeNode", "feMorphology", "feDropShadow",
}
# Dropped with their children: script, foreignObject, iframe, animation elements
# (which can rewrite href at runtime), feImage (fetches URLs), a, metadata, etc.
EXTERNAL_URL_RE = re.compile(r"url\(\s*['\"]?\s*(?!#)", re.I)
BAD_VALUE_RE = re.compile(r"(javascript|vbscript|livescript)\s*:|expression\s*\(|@import", re.I)
DATA_IMAGE_RE = re.compile(r"^data:image/(png|jpeg);base64,[A-Za-z0-9+/=\s]+$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class UnsafeInput(ValueError):
    """Raised when an input file or value is refused."""


def esc(value):
    """Escape text for SVG/HTML text nodes and attribute values."""
    return html.escape(str(value), quote=True)


def resolve_inside(base_dir, rel_path, what="file"):
    """Resolve rel_path against base_dir and refuse anything that escapes it."""
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise UnsafeInput(f"{what}: empty path")
    if "\x00" in rel_path or CONTROL_RE.search(rel_path):
        raise UnsafeInput(f"{what}: control characters in path")
    base = Path(base_dir).resolve()
    candidate = (base / rel_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise UnsafeInput(f"{what}: path {rel_path!r} points outside {base}") from None
    return candidate


def ensure_output_dir(out_dir, allowed_roots):
    """Resolve out_dir and require it to sit inside one of allowed_roots."""
    out = Path(out_dir).expanduser().resolve()
    for root in allowed_roots:
        try:
            out.relative_to(Path(root).resolve())
            break
        except ValueError:
            continue
    else:
        roots = ", ".join(str(Path(r).resolve()) for r in allowed_roots)
        raise UnsafeInput(f"output folder {out} must be inside one of: {roots}")
    if out.exists() and not out.is_dir():
        raise UnsafeInput(f"output path {out} exists and is not a folder")
    out.mkdir(parents=True, exist_ok=True)
    return out


# ---------------------------------------------------------------- raster logos

def _png_size(data):
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise UnsafeInput("PNG header is malformed")
    return struct.unpack(">II", data[16:24])


def _jpeg_size(data):
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + seg_len
    raise UnsafeInput("JPEG has no size header")


# ---------------------------------------------------------------- SVG logos

def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _ns(tag):
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def sanitize_svg(data):
    """Return (clean_svg_bytes, report). Raises UnsafeInput on refusal.

    Refused outright: DOCTYPE or ENTITY declarations (entity expansion and
    external entities), non-SVG roots, unparsable XML. Stripped and reported:
    script, foreignObject, animation and other non-whitelisted elements, on*
    event attributes, external href/xlink:href, external url(...) references,
    javascript:/vbscript:/expression() values, <style> blocks with @import or
    external url().
    """
    if len(data) > MAX_LOGO_BYTES:
        raise UnsafeInput("SVG logo is larger than 5 MB")
    try:
        # UTF-8 only: another encoding (UTF-16 with a BOM, for instance) could hide a DOCTYPE from the text scan below
        head = data.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsafeInput("SVG logo is not UTF-8 encoded; re-export it as UTF-8") from None
    if re.search(r"<!DOCTYPE|<!ENTITY|encoding\s*=\s*[\"'](?!utf-?8)", head, re.I):
        raise UnsafeInput("SVG logo contains a DOCTYPE or ENTITY declaration; refused")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise UnsafeInput(f"SVG logo is not well-formed XML: {exc}") from None
    if _local(root.tag) != "svg" or _ns(root.tag) not in ("", SVG_NS):
        raise UnsafeInput("logo root element is not <svg>")

    report = []

    def clean(el):
        for child in list(el):
            if not isinstance(child.tag, str):
                el.remove(child)  # comments, processing instructions
                continue
            name = _local(child.tag)
            if _ns(child.tag) not in ("", SVG_NS) or name not in ALLOWED_TAGS:
                report.append(f"removed <{name}>")
                el.remove(child)
                continue
            if name == "style":
                css = child.text or ""
                if EXTERNAL_URL_RE.search(css) or BAD_VALUE_RE.search(css):
                    report.append("removed <style> with @import, external url() or script")
                    el.remove(child)
                    continue
            clean_attrs(child)
            clean(child)

    def clean_attrs(el):
        name = _local(el.tag)
        for attr in list(el.attrib):
            value = el.attrib[attr]
            local = _local(attr)
            ns = _ns(attr)
            if local.lower().startswith("on"):
                report.append(f"removed {local} handler on <{name}>")
                del el.attrib[attr]
                continue
            if ns not in ("", XLINK_NS, XML_NS):
                del el.attrib[attr]  # editor metadata (inkscape:, sodipodi:, ...)
                continue
            if local == "href":
                ok = value.startswith("#") or (name == "image" and DATA_IMAGE_RE.match(value))
                if not ok:
                    report.append(f"removed external href on <{name}>")
                    del el.attrib[attr]
                continue
            if BAD_VALUE_RE.search(value) or EXTERNAL_URL_RE.search(value) or "data:" in value.lower():
                report.append(f"removed unsafe {local} on <{name}>")
                del el.attrib[attr]

    clean_attrs(root)
    clean(root)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    out = ET.tostring(root, encoding="utf-8")
    return out, report


def svg_aspect(svg_bytes):
    root = ET.fromstring(svg_bytes)
    vb = root.attrib.get("viewBox", "").replace(",", " ").split()
    try:
        if len(vb) == 4:
            w, h = float(vb[2]), float(vb[3])
        else:
            w = float(re.sub(r"[^0-9.]", "", root.attrib.get("width", "")))
            h = float(re.sub(r"[^0-9.]", "", root.attrib.get("height", "")))
        if w > 0 and h > 0:
            return w, h
    except ValueError:
        pass
    return 1.0, 1.0


def load_logo(base_dir, rel_path, what="logo"):
    """Load a user-supplied logo file and return a dict ready for embedding.

    Returns {"data_uri", "width", "height", "kind", "report"}.
    """
    path = resolve_inside(base_dir, rel_path, what)
    if not path.is_file():
        raise UnsafeInput(f"{what}: {rel_path!r} is not a file")
    size = path.stat().st_size
    if size > MAX_LOGO_BYTES:
        raise UnsafeInput(f"{what}: {rel_path!r} is larger than 5 MB")
    data = path.read_bytes()
    ext = path.suffix.lower()
    if ext == ".png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise UnsafeInput(f"{what}: {rel_path!r} is not a PNG file")
        w, h = _png_size(data)
        mime, report = "image/png", []
    elif ext in (".jpg", ".jpeg"):
        if not data.startswith(b"\xff\xd8\xff"):
            raise UnsafeInput(f"{what}: {rel_path!r} is not a JPEG file")
        w, h = _jpeg_size(data)
        mime, report = "image/jpeg", []
    elif ext == ".svg":
        data, report = sanitize_svg(data)
        w, h = svg_aspect(data)
        mime = "image/svg+xml"
    else:
        raise UnsafeInput(f"{what}: only .svg, .png, .jpg or .jpeg files are accepted")
    if mime != "image/svg+xml" and (w <= 0 or h <= 0 or w > MAX_LOGO_PIXELS or h > MAX_LOGO_PIXELS):
        raise UnsafeInput(f"{what}: image size {w}x{h} is out of range")
    uri = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    return {"data_uri": uri, "width": float(w), "height": float(h), "kind": mime, "report": report}
