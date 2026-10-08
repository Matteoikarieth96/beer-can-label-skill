"""Spec loading, validation, defaults, templates, palettes and label strings."""
import copy
import json
import math
import re
from pathlib import Path

from .colors import is_hex
from .motifs import MOTIFS, validate_motif

FONT_RE = re.compile(r"^[A-Za-z0-9 ]{1,40}$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_SPEC_BYTES = 256 * 1024

# --------------------------------------------------------------------------- templates

PRESETS = {
    "hopera-sleek-330": {
        "title": "Hopera, 330 ml sleek can",
        "base_width_px": 1039,
        "base_height_px": 684,
        "min_width_px": 1039,
        "min_height_px": 684,
        "can_diameter_mm": 58.0,
        "can_height_mm": 146.0,
        "label_height_mm": 120.0,
        "distributor_box": True,
    },
}

# --------------------------------------------------------------------------- palettes
# Roles: bg (centre of the radial background), bg2 (edges), primary (metallic or
# accent ink), secondary (second accent), text (main text), muted (secondary
# text), panel (boxes and side-panel backdrops).
PALETTES = {
    "midnight-brass": {"bg": "#1b2b44", "bg2": "#0a1424", "primary": "#d9a441", "secondary": "#6fb7b0",
                       "text": "#f4ecd8", "muted": "#b8c4cc", "panel": "#132038"},
    "forest-cream": {"bg": "#24432f", "bg2": "#0f2117", "primary": "#e3c67b", "secondary": "#a7c957",
                     "text": "#f5efdc", "muted": "#cbd5bb", "panel": "#183020"},
    "hazy-gold": {"bg": "#f6d27a", "bg2": "#e9a945", "primary": "#2d1e2f", "secondary": "#8a3b12",
                  "text": "#2a1a1f", "muted": "#4f3a35", "panel": "#fff1cf"},
    "arctic-ink": {"bg": "#f1f5f8", "bg2": "#d3e0e8", "primary": "#1d3557", "secondary": "#c8102e",
                   "text": "#0f1d2c", "muted": "#3f5366", "panel": "#ffffff"},
    "coral-sunset": {"bg": "#f7e6d3", "bg2": "#efc9a4", "primary": "#8f2f1d", "secondary": "#2f6690",
                     "text": "#2a1d18", "muted": "#5c4438", "panel": "#fff7ee"},
    "stout-copper": {"bg": "#2a1c16", "bg2": "#0e0907", "primary": "#c8834a", "secondary": "#e8d5b5",
                     "text": "#f3e6d3", "muted": "#cdb9a2", "panel": "#1d130f"},
}
PALETTE_ROLES = ("bg", "bg2", "primary", "secondary", "text", "muted", "panel")

# --------------------------------------------------------------------------- strings
STRINGS = {
    "en": {
        "produced_by": "Produced and bottled by:",
        "ingredients": "Ingredients:",
        "contains": "Contains:",
        "distributed_by": "Distributed by",
        "distributor_placeholder": "DISTRIBUTOR LOGO",
        "distributor_hint": "supplied by the distributor",
        "best_before": "Best before:",
        "lot": "Lot:",
        "recycling_item": "Can",
        "recycling_code": "ALU 41",
        "recycling_material": "Aluminium, metal collection",
        "recycling_note": "Check your local collection rules.",
        "denomination": "",
        "alc_prefix": "alc.",
        "decimal": ".",
    },
    "it": {
        "produced_by": "Prodotta e confezionata da:",
        "ingredients": "Ingredienti:",
        "contains": "Contiene:",
        "distributed_by": "Distribuita da",
        "distributor_placeholder": "LOGO DISTRIBUTORE",
        "distributor_hint": "fornito dal distributore",
        "best_before": "Da consumarsi preferibilmente entro:",
        "lot": "Lotto:",
        "recycling_item": "Lattina",
        "recycling_code": "ALU 41",
        "recycling_material": "Alluminio, raccolta metalli",
        "recycling_note": "Verifica le disposizioni del tuo Comune.",
        "denomination": "Birra",
        "alc_prefix": "alc.",
        "decimal": ",",
    },
}

# --------------------------------------------------------------------------- defaults
DEFAULTS = {
    "spec_version": 1,
    "template": {"preset": "hopera-sleek-330", "scale": 2},
    "language": "en",
    "strings": {},
    "beer": {
        "name": "",
        "name_lines": [],
        "tagline": "",
        "style": "",
        "denomination": None,
        "abv": None,
        "volume_ml": 330,
        "volume_unit": "ml",
        "e_mark": False,
    },
    "producer": {"name": "", "address": "", "website": ""},
    "ingredients": [],
    "allergen_statement": "",
    "story": [],
    "claims": [],
    "notes": [],
    "distributor": {"show": None, "logo": ""},
    "recycling": {"item": None, "code": None, "material": None, "note": None},
    "best_before": {"show": True},
    "design": {
        "palette": "midnight-brass",
        "fonts": {
            "display": {"family": "Oswald", "weights": [400, 700], "width": 0.85},
            "body": {"family": "Inter", "weights": [400, 700], "width": 1.0},
        },
        "motifs": [{"type": "sunburst"}, {"type": "laurel"}, {"type": "greek-key"}],
        "logo": {"path": "", "size_mm": 0},
        "metallic": True,
        "panel_backdrop": None,
        "grain": False,
        "name_case": "upper",
    },
    "layout": {
        "producer_strip": "left",
        "seam_safe_pct": 3.0,
        "margin_mm": 4.0,
        "legal_font_mm": 2.5,
        "body_font_mm": 2.8,
    },
    "qa": {"min_x_height_mm": 1.2, "x_height_ratio": 0.5},
}

TOP_KEYS = set(DEFAULTS)


class SpecError(ValueError):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def _merge(base, extra):
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


class _V:
    """Collects validation problems instead of failing on the first one."""

    def __init__(self):
        self.problems = []

    def text(self, value, where, maxlen, required=False):
        if value is None:
            value = ""
        if not isinstance(value, str):
            self.problems.append(f"{where}: must be text")
            return ""
        if CONTROL_RE.search(value):
            self.problems.append(f"{where}: contains control characters")
            return ""
        value = value.strip()
        if len(value) > maxlen:
            self.problems.append(f"{where}: longer than {maxlen} characters")
        if required and not value:
            self.problems.append(f"{where}: is required")
        return value

    def number(self, value, where, lo, hi, required=False):
        if value is None or value == "":
            if required:
                self.problems.append(f"{where}: is required")
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            self.problems.append(f"{where}: must be a number")
            return None
        if not lo <= value <= hi:
            self.problems.append(f"{where}: must be between {lo} and {hi}")
            return None
        return float(value)

    def unknown(self, obj, allowed, where):
        if not isinstance(obj, dict):
            self.problems.append(f"{where}: must be an object")
            return
        for key in obj:
            if key not in allowed:
                self.problems.append(f"{where}: unknown key {key!r}")


def validate_font(font, where, v):
    if isinstance(font, str):
        font = {"family": font}
    if not isinstance(font, dict):
        v.problems.append(f"{where}: must be a family name or an object")
        return None
    v.unknown(font, {"family", "weights", "width"}, where)
    family = font.get("family", "")
    if not isinstance(family, str) or not FONT_RE.match(family):
        v.problems.append(f"{where}.family: {family!r} is not a valid Google Fonts family name "
                          "(letters, digits and spaces, 1 to 40 characters)")
        return None
    weights = font.get("weights", [400, 700])
    if (not isinstance(weights, list) or not 1 <= len(weights) <= 6
            or any(isinstance(w, bool) or not isinstance(w, int) or w % 100 or not 100 <= w <= 900 for w in weights)):
        v.problems.append(f"{where}.weights: use a list such as [400, 700] (multiples of 100)")
        weights = [400]
    width = v.number(font.get("width", 1.0), f"{where}.width", 0.5, 1.5) or 1.0
    return {"family": family, "weights": sorted(set(weights)), "width": width}


def resolve_template(tpl, v):
    v.unknown(tpl, {"preset", "scale", "width_px", "height_px", "can_diameter_mm", "can_height_mm",
                    "label_height_mm", "distributor_box", "title"}, "template")
    preset = tpl.get("preset", "hopera-sleek-330")
    if preset in PRESETS:
        p = PRESETS[preset]
        scale = tpl.get("scale", 2)
        if scale not in (1, 2, 3):
            v.problems.append("template.scale: must be 1, 2 or 3")
            scale = 2
        out = dict(p)
        out.update({"preset": preset, "width_px": p["base_width_px"] * scale,
                    "height_px": p["base_height_px"] * scale, "scale": scale})
    elif preset == "custom":
        w = v.number(tpl.get("width_px"), "template.width_px", 300, 9000, required=True) or 2000
        h = v.number(tpl.get("height_px"), "template.height_px", 200, 9000, required=True) or 1300
        d = v.number(tpl.get("can_diameter_mm"), "template.can_diameter_mm", 30, 120, required=True) or 66
        lh = v.number(tpl.get("label_height_mm"), "template.label_height_mm", 30, 250, required=True) or 100
        ch = v.number(tpl.get("can_height_mm", lh + 26), "template.can_height_mm", lh + 10, 300) or lh + 26
        out = {"preset": "custom", "title": v.text(tpl.get("title", "Custom can"), "template.title", 60),
               "width_px": int(round(w)), "height_px": int(round(h)), "min_width_px": int(round(w)),
               "min_height_px": int(round(h)), "can_diameter_mm": d, "can_height_mm": ch,
               "label_height_mm": lh, "distributor_box": bool(tpl.get("distributor_box", False)), "scale": 1}
    else:
        v.problems.append(f"template.preset: unknown preset {preset!r} (use hopera-sleek-330 or custom)")
        return resolve_template({"preset": "hopera-sleek-330"}, _V())
    out["px_per_mm"] = out["height_px"] / out["label_height_mm"]
    out["ideal_ratio"] = math.pi * out["can_diameter_mm"] / out["label_height_mm"]
    return out


def load_spec(path):
    """Read, merge with defaults and validate. Returns (spec, template, warnings)."""
    path = Path(path)
    if path.stat().st_size > MAX_SPEC_BYTES:
        raise SpecError(["spec file is larger than 256 KB"])
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SpecError([f"spec is not valid JSON: {exc}"]) from None
    return validate_spec(raw)


def validate_spec(raw):
    v = _V()
    warnings = []
    if not isinstance(raw, dict):
        raise SpecError(["spec must be a JSON object"])
    v.unknown(raw, TOP_KEYS | {"_comment", "$schema"}, "spec")
    raw = {k: val for k, val in raw.items() if k in TOP_KEYS}
    s = _merge(DEFAULTS, raw)

    tpl = resolve_template(s["template"] if isinstance(s["template"], dict) else {}, v)

    lang = s.get("language")
    if lang not in STRINGS:
        v.problems.append(f"language: {lang!r} has no built-in strings (use en or it, then override text in 'strings')")
        lang = "en"
    s["language"] = lang
    strings = dict(STRINGS[lang])
    v.unknown(s["strings"], set(STRINGS["en"]), "strings")
    for key, val in (s["strings"] or {}).items():
        if key in strings:
            strings[key] = v.text(val, f"strings.{key}", 120)
    s["strings"] = strings

    b = s["beer"]
    v.unknown(b, set(DEFAULTS["beer"]), "beer")
    b["name"] = v.text(b.get("name"), "beer.name", 60, required=True)
    lines = b.get("name_lines") or []
    if not isinstance(lines, list) or len(lines) > 3:
        v.problems.append("beer.name_lines: list of at most 3 lines")
        lines = []
    b["name_lines"] = [v.text(x, "beer.name_lines[]", 40) for x in lines]
    b["tagline"] = v.text(b.get("tagline"), "beer.tagline", 80)
    b["style"] = v.text(b.get("style"), "beer.style", 50, required=True)
    if b.get("denomination") is None:
        b["denomination"] = strings["denomination"]
    b["denomination"] = v.text(b.get("denomination"), "beer.denomination", 30)
    b["abv"] = v.number(b.get("abv"), "beer.abv", 0, 20, required=True)
    b["volume_ml"] = v.number(b.get("volume_ml"), "beer.volume_ml", 50, 2000, required=True)
    if b.get("volume_unit") not in ("ml", "cl"):
        v.problems.append("beer.volume_unit: ml or cl")
    b["e_mark"] = bool(b.get("e_mark"))

    p = s["producer"]
    v.unknown(p, set(DEFAULTS["producer"]), "producer")
    p["name"] = v.text(p.get("name"), "producer.name", 80, required=True)
    p["address"] = v.text(p.get("address"), "producer.address", 140, required=True)
    p["website"] = v.text(p.get("website"), "producer.website", 80)

    ings = s["ingredients"]
    if not isinstance(ings, list) or len(ings) > 30:
        v.problems.append("ingredients: list of at most 30 items")
        ings = []
    clean = []
    for i, item in enumerate(ings):
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            v.problems.append(f"ingredients[{i}]: text or {{'text', 'allergen'}}")
            continue
        v.unknown(item, {"text", "allergen"}, f"ingredients[{i}]")
        clean.append({"text": v.text(item.get("text"), f"ingredients[{i}].text", 80, required=True),
                      "allergen": bool(item.get("allergen"))})
    s["ingredients"] = clean
    s["allergen_statement"] = v.text(s.get("allergen_statement"), "allergen_statement", 160)
    if not clean and not s["allergen_statement"]:
        v.problems.append("ingredients or allergen_statement: at least one is required (allergens must be declared)")

    for key, maxn, maxlen in (("story", 6, 600), ("claims", 8, 80), ("notes", 6, 120)):
        val = s.get(key) or []
        if isinstance(val, str):
            val = [val]
        if not isinstance(val, list) or len(val) > maxn:
            v.problems.append(f"{key}: list of at most {maxn} entries")
            val = []
        s[key] = [v.text(x, f"{key}[]", maxlen) for x in val if x]

    d = s["distributor"]
    v.unknown(d, set(DEFAULTS["distributor"]), "distributor")
    if d.get("show") is None:
        d["show"] = bool(tpl.get("distributor_box"))
    d["show"] = bool(d["show"])
    d["logo"] = v.text(d.get("logo"), "distributor.logo", 200)

    r = s["recycling"]
    v.unknown(r, set(DEFAULTS["recycling"]), "recycling")
    for key, skey in (("item", "recycling_item"), ("code", "recycling_code"),
                      ("material", "recycling_material"), ("note", "recycling_note")):
        r[key] = v.text(r.get(key) if r.get(key) is not None else strings[skey], f"recycling.{key}", 80)
    if not r["code"]:
        v.problems.append("recycling.code: required (for example ALU 41 for an aluminium can)")

    bb = s["best_before"]
    v.unknown(bb, {"show"}, "best_before")
    bb["show"] = bool(bb.get("show", True))
    if not bb["show"]:
        warnings.append("best_before.show is false: a date of minimum durability is required for beer under 10% vol in the EU")

    dz = s["design"]
    v.unknown(dz, set(DEFAULTS["design"]), "design")
    pal = dz.get("palette")
    if isinstance(pal, str):
        if pal not in PALETTES:
            v.problems.append(f"design.palette: unknown preset {pal!r} ({', '.join(PALETTES)})")
            pal = "midnight-brass"
        pal = dict(PALETTES[pal])
    elif isinstance(pal, dict):
        base = dict(PALETTES.get(pal.get("base", "midnight-brass"), PALETTES["midnight-brass"]))
        v.unknown(pal, set(PALETTE_ROLES) | {"base"}, "design.palette")
        for role in PALETTE_ROLES:
            if role in pal:
                if not is_hex(pal[role]):
                    v.problems.append(f"design.palette.{role}: use #rrggbb")
                else:
                    base[role] = pal[role]
        pal = base
    else:
        v.problems.append("design.palette: preset name or object")
        pal = dict(PALETTES["midnight-brass"])
    dz["palette"] = pal

    fonts = dz.get("fonts") or {}
    v.unknown(fonts, {"display", "body"}, "design.fonts")
    merged_fonts = {}
    for role in ("display", "body"):
        f = fonts.get(role, DEFAULTS["design"]["fonts"][role])
        merged_fonts[role] = validate_font(f, f"design.fonts.{role}", v) or DEFAULTS["design"]["fonts"][role]
    dz["fonts"] = merged_fonts

    motifs = dz.get("motifs") or []
    if not isinstance(motifs, list) or len(motifs) > 6:
        v.problems.append("design.motifs: list of at most 6 motifs")
        motifs = []
    seen_roles = {}
    clean_motifs = []
    for i, m in enumerate(motifs):
        if isinstance(m, str):
            m = {"type": m}
        try:
            cm = validate_motif(m, pal)
        except ValueError as exc:
            v.problems.append(f"design.motifs[{i}]: {exc}")
            continue
        role = MOTIFS[cm["type"]]["role"]
        if role in seen_roles:
            v.problems.append(f"design.motifs[{i}]: only one {role} motif allowed ({seen_roles[role]} already set)")
            continue
        seen_roles[role] = cm["type"]
        clean_motifs.append(cm)
    dz["motifs"] = clean_motifs

    logo = dz.get("logo") or {}
    if isinstance(logo, str):
        logo = {"path": logo}
    v.unknown(logo, {"path", "size_mm"}, "design.logo")
    dz["logo"] = {"path": v.text(logo.get("path"), "design.logo.path", 200),
                  "size_mm": v.number(logo.get("size_mm", 0), "design.logo.size_mm", 0, 60) or 0}
    dz["metallic"] = bool(dz.get("metallic"))
    if dz.get("panel_backdrop") is None:
        dz["panel_backdrop"] = any(MOTIFS[m["type"]]["role"] == "scenery" for m in clean_motifs)
    dz["panel_backdrop"] = bool(dz["panel_backdrop"])
    dz["grain"] = bool(dz.get("grain"))
    if dz.get("name_case") not in ("upper", "as-is"):
        v.problems.append("design.name_case: upper or as-is")
        dz["name_case"] = "upper"

    lay = s["layout"]
    v.unknown(lay, set(DEFAULTS["layout"]), "layout")
    if lay.get("producer_strip") not in ("left", "right"):
        v.problems.append("layout.producer_strip: left or right")
        lay["producer_strip"] = "left"
    lay["seam_safe_pct"] = v.number(lay.get("seam_safe_pct"), "layout.seam_safe_pct", 1, 10) or 3.0
    lay["margin_mm"] = v.number(lay.get("margin_mm"), "layout.margin_mm", 1, 15) or 4.0
    lay["legal_font_mm"] = v.number(lay.get("legal_font_mm"), "layout.legal_font_mm", 1.5, 6) or 2.5
    lay["body_font_mm"] = v.number(lay.get("body_font_mm"), "layout.body_font_mm", 1.5, 6) or 2.8

    qa = s["qa"]
    v.unknown(qa, set(DEFAULTS["qa"]), "qa")
    qa["min_x_height_mm"] = v.number(qa.get("min_x_height_mm"), "qa.min_x_height_mm", 0.5, 3) or 1.2
    qa["x_height_ratio"] = v.number(qa.get("x_height_ratio"), "qa.x_height_ratio", 0.3, 0.8) or 0.5

    if abs(tpl["width_px"] / tpl["height_px"] - tpl["ideal_ratio"]) / tpl["ideal_ratio"] > 0.02:
        warnings.append(f"template ratio {tpl['width_px'] / tpl['height_px']:.3f} differs from the can "
                        f"circumference / label height ratio {tpl['ideal_ratio']:.3f} by more than 2%")

    if v.problems:
        raise SpecError(v.problems)
    return s, tpl, warnings


def placeholders(spec):
    """Values that still look like placeholders (TBC, XXX, ...)."""
    found = []
    pattern = re.compile(r"\bTBC\b|\bTBD\b|XXX|\?\?|\bTO CONFIRM\b|\bDA CONFERMARE\b", re.I)

    def walk(obj, where):
        if isinstance(obj, dict):
            for k, val in obj.items():
                walk(val, f"{where}.{k}" if where else k)
        elif isinstance(obj, list):
            for i, val in enumerate(obj):
                walk(val, f"{where}[{i}]")
        elif isinstance(obj, str) and pattern.search(obj):
            found.append(f"{where} = {obj!r}")
    walk({k: spec[k] for k in ("beer", "producer", "ingredients", "allergen_statement", "claims", "notes")}, "")
    return found
