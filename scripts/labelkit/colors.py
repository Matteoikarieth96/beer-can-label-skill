"""Colour helpers: hex parsing, mixing and WCAG contrast."""
import re

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")  # always used with fullmatch


def is_hex(value):
    return isinstance(value, str) and bool(HEX_RE.fullmatch(value))


def to_rgb(hex_color):
    if not is_hex(hex_color):
        raise ValueError(f"not a #rrggbb colour: {hex_color!r}")
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def mix(a, b, t):
    """Blend colour a towards b by t (0 = a, 1 = b)."""
    ra, rb = to_rgb(a), to_rgb(b)
    return to_hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def lighten(c, t):
    return mix(c, "#ffffff", t)


def darken(c, t):
    return mix(c, "#000000", t)


def luminance(hex_color):
    def channel(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in to_rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
