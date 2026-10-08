"""Input safety: escaping, text checks, path containment, safe writes, logo loading and SVG sanitizing.

Every logo is untrusted data. PNG and JPEG files are checked by magic bytes and
header dimensions and embedded as base64 data URIs. SVG logos are parsed with a
guarded parser (UTF-8 only, no DOCTYPE or entities, nesting depth capped),
reduced to a whitelist of drawing elements and attributes, and then embedded as
an <image> data URI (never inlined), so even a missed construct cannot run
script or fetch anything.

Every output file goes through atomic_write: it refuses to write through a
symbolic link and replaces the target with os.replace from a fresh temp file.
"""
import base64
import html
import os
import re
import struct
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.parsers import expat

MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_LOGO_PIXELS = 12000  # per side, for PNG/JPEG headers
MAX_XML_DEPTH = 64

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"

# <style> and <image> are not allowed in logos: CSS has too many ways to fetch
# (escapes, @import, image-set), and a nested raster would bypass the size cap.
ALLOWED_TAGS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "textPath", "defs", "linearGradient", "radialGradient", "stop",
    "clipPath", "mask", "pattern", "symbol", "use", "title", "desc",
    "filter", "feGaussianBlur", "feOffset", "feBlend", "feColorMatrix", "feComposite",
    "feFlood", "feMerge", "feMergeNode", "feMorphology", "feDropShadow",
}
ALLOWED_XML_ATTRS = {"space", "lang"}
# Dropped with their children: script, style, image, foreignObject, iframe,
# animation elements (which can rewrite href at runtime), feImage (fetches URLs),
# a, metadata, etc.
EXTERNAL_URL_RE = re.compile(r"url\(\s*['\"]?\s*(?!#)", re.I)
BAD_VALUE_RE = re.compile(
    r"\\|(javascript|vbscript|livescript)\s*:|expression|@import|image-set|image\s*\(|src\s*\(|"
    r"-moz-binding|behavior|data:", re.I)
BAD_STYLE_RE = re.compile(r"[\\@]|url\s*\(|image-set|image\s*\(|src\s*\(|expression|-moz-binding|behavior", re.I)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Allowed in single-line label text: XML 1.0 characters minus tab/CR/LF, minus DEL and C1 controls.
TEXT_ALLOWED_RE = re.compile("[\u0020-\u007e\u00a0-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]*")


class UnsafeInput(ValueError):
    """Raised when an input file or value is refused."""


def esc(value):
    """Escape text for SVG/HTML text nodes and attribute values."""
    return html.escape(str(value), quote=True)


def text_problem(value):
    """Why a single-line text value is refused, or None when it is fine.

    Refuses line breaks, tabs and other control characters, unpaired surrogates
    and characters that XML 1.0 does not allow (U+FFFE, U+FFFF, ...).
    """
    if not TEXT_ALLOWED_RE.fullmatch(value):
        return "contains line breaks, tabs, control characters or characters not allowed in XML"
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return "contains an unpaired surrogate"
    return None


# ---------------------------------------------------------------- paths and writes

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


def refuse_symlinks(folder, names):
    """Refuse to start when any output we are about to write is a symlink (dangling ones included)."""
    for name in names:
        p = Path(folder) / name
        if p.is_symlink():
            raise UnsafeInput(f"{p} is a symbolic link; remove it before building (outputs never follow links)")
        if os.path.lexists(p) and not p.is_file():
            raise UnsafeInput(f"{p} exists and is not a regular file")


def atomic_write(path, data):
    """Write bytes or text to path without ever following a symlink.

    The data goes to a new temp file in the same folder (created with O_EXCL,
    mode 0600), then os.replace swaps it in. os.replace replaces a directory
    entry and never writes through a link, so a link planted after the check
    is replaced, not followed.
    """
    path = Path(path)
    if isinstance(data, str):
        data = data.encode("utf-8")
    if path.is_symlink():
        raise UnsafeInput(f"refusing to write through the symbolic link {path}")
    if os.path.lexists(path) and not path.is_file():
        raise UnsafeInput(f"refusing to replace {path}: not a regular file")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


# ---------------------------------------------------------------- guarded XML parsing

def parse_xml(data, what="SVG", max_depth=MAX_XML_DEPTH):
    """Parse untrusted XML bytes and return the root element.

    UTF-8 only (NUL bytes refused, so BOM-less UTF-16 cannot slip through), no
    DOCTYPE or ENTITY declarations (checked in the text and again by expat
    handlers), nesting depth capped. Raises UnsafeInput.
    """
    if b"\x00" in data:
        raise UnsafeInput(f"{what} contains NUL bytes (UTF-16 or binary data); re-export it as UTF-8")
    try:
        # UTF-8 only: another encoding (UTF-16 with a BOM, for instance) could hide a DOCTYPE from the text scan below
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsafeInput(f"{what} is not UTF-8 encoded; re-export it as UTF-8") from None
    if re.search(r"<!DOCTYPE|<!ENTITY", text, re.I) or \
            re.match(r"\s*\ufeff?<\?xml[^>]*encoding\s*=\s*[\"'](?!utf-?8)", text, re.I):
        raise UnsafeInput(f"{what} contains a DOCTYPE or ENTITY declaration or a non-UTF-8 encoding; refused")

    p = expat.ParserCreate(encoding="UTF-8")
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    depth = [0]

    def start(name, attrs):
        depth[0] += 1
        if depth[0] > max_depth:
            raise UnsafeInput(f"{what} nests elements deeper than {max_depth} levels; refused")

    def end(name):
        depth[0] -= 1

    def refuse(*_args):
        raise UnsafeInput(f"{what} contains a DOCTYPE or ENTITY declaration; refused")

    p.StartElementHandler = start
    p.EndElementHandler = end
    p.StartDoctypeDeclHandler = refuse
    p.EntityDeclHandler = refuse
    p.UnparsedEntityDeclHandler = refuse
    p.ExternalEntityRefHandler = refuse
    try:
        p.Parse(data, True)
    except expat.ExpatError as exc:
        raise UnsafeInput(f"{what} is not well-formed XML: {exc}") from None
    parser = ET.XMLParser(encoding="utf-8")
    try:
        parser.feed(data)
        return parser.close()
    except ET.ParseError as exc:
        raise UnsafeInput(f"{what} is not well-formed XML: {exc}") from None


# ---------------------------------------------------------------- raster logos

def _png_size(data):
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise UnsafeInput("PNG header is malformed")
    return struct.unpack(">II", data[16:24])


SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
STANDALONE_MARKERS = {0x01, 0xD8} | set(range(0xD0, 0xD8))


def _jpeg_size(data):
    """Walk the JPEG markers the way libjpeg does and return the first SOF size.

    0xFF fill bytes before a marker are skipped; standalone markers (SOI, RST,
    TEM) have no length; entropy-coded data after SOS is skipped up to the next
    real marker. Every SOF must be inside the size cap, not only the first.
    """
    n = len(data)
    if n < 4 or data[0] != 0xFF or data[1] != 0xD8:
        raise UnsafeInput("JPEG does not start with SOI")
    i, sizes = 2, []
    while i < n:
        if data[i] != 0xFF:
            raise UnsafeInput("JPEG marker structure is malformed")
        while i < n and data[i] == 0xFF:  # fill bytes
            i += 1
        if i >= n:
            break
        marker = data[i]
        i += 1
        if marker == 0x00:
            raise UnsafeInput("JPEG marker structure is malformed")
        if marker == 0xD9:  # EOI
            break
        if marker in STANDALONE_MARKERS:
            continue
        if i + 2 > n:
            raise UnsafeInput("JPEG segment is truncated")
        seg_len = struct.unpack(">H", data[i:i + 2])[0]
        if seg_len < 2 or i + seg_len > n:
            raise UnsafeInput("JPEG segment length is invalid")
        if marker in SOF_MARKERS:
            if seg_len < 7:
                raise UnsafeInput("JPEG frame header is truncated")
            h, w = struct.unpack(">HH", data[i + 3:i + 7])
            if not (0 < w <= MAX_LOGO_PIXELS and 0 < h <= MAX_LOGO_PIXELS):
                raise UnsafeInput(f"JPEG frame size {w}x{h} is out of range")
            sizes.append((w, h))
        i += seg_len
        if marker == 0xDA:  # SOS: skip entropy-coded data to the next real marker
            while i + 1 < n and not (data[i] == 0xFF and data[i + 1] not in (0x00, 0xFF)
                                     and not 0xD0 <= data[i + 1] <= 0xD7):
                i += 1
    if not sizes:
        raise UnsafeInput("JPEG has no frame header")
    return sizes[0]


# ---------------------------------------------------------------- SVG logos

def _local(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _ns(tag):
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def sanitize_svg(data):
    """Return (clean_svg_bytes, report). Raises UnsafeInput on refusal.

    Refused outright: NUL bytes or non-UTF-8 data, DOCTYPE or ENTITY
    declarations, nesting deeper than 64 levels, non-SVG roots, unparsable XML.
    Stripped and reported: script, style, image, foreignObject, animation and
    other non-whitelisted elements; on* event attributes; xml:base and other
    xml: attributes except xml:space and xml:lang; href/xlink:href that are not
    #internal; any value with a backslash (CSS escapes), url(...) to anything
    but #id, @import, image-set(), image(), src(), expression, -moz-binding,
    behavior, data: or script URLs; style attributes containing @, url(, a
    backslash or the functions above.
    """
    if len(data) > MAX_LOGO_BYTES:
        raise UnsafeInput("SVG logo is larger than 5 MB")
    root = parse_xml(data, "SVG logo")
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
            if ns == XML_NS:
                if local not in ALLOWED_XML_ATTRS:
                    report.append(f"removed xml:{local} on <{name}>")
                    del el.attrib[attr]
                continue
            if ns not in ("", XLINK_NS):
                del el.attrib[attr]  # editor metadata (inkscape:, sodipodi:, ...)
                continue
            if local == "href":
                if not value.startswith("#") or BAD_VALUE_RE.search(value):
                    report.append(f"removed external href on <{name}>")
                    del el.attrib[attr]
                continue
            if local == "style" and BAD_STYLE_RE.search(value):
                report.append(f"removed style attribute with url(), @, escapes or fetching functions on <{name}>")
                del el.attrib[attr]
                continue
            if BAD_VALUE_RE.search(value) or EXTERNAL_URL_RE.search(value):
                report.append(f"removed unsafe {local} on <{name}>")
                del el.attrib[attr]

    clean_attrs(root)
    clean(root)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    out = ET.tostring(root, encoding="utf-8")
    return out, report


def svg_aspect(svg_bytes):
    root = parse_xml(svg_bytes, "SVG logo")
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
