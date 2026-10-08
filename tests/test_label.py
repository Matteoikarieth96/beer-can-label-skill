"""Tests for beer-can-label: spec validation, escaping, SVG sanitizing, paths, QA.

Run: python3 -m unittest discover -s tests -v
No network and no Chrome needed (builds use --no-render).
"""
import base64
import contextlib
import copy
import io
import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_label  # noqa: E402
import check_label  # noqa: E402
from labelkit.compose import compose  # noqa: E402
from labelkit.motifs import waves  # noqa: E402
from labelkit.preview import THREE_SRI, THREE_URL, build_preview  # noqa: E402
from labelkit.safety import UnsafeInput, ensure_output_dir, load_logo, resolve_inside, sanitize_svg  # noqa: E402
from labelkit.spec import SpecError, validate_spec  # noqa: E402
from labelkit.textfit import wrap_runs  # noqa: E402

TEMPLATE = json.loads((ROOT / "templates" / "spec.template.json").read_text(encoding="utf-8"))
SVG_NS = "{http://www.w3.org/2000/svg}"
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def spec_with(**changes):
    s = copy.deepcopy(TEMPLATE)
    for dotted, value in changes.items():
        keys = dotted.split("__")
        cur = s
        for k in keys[:-1]:
            cur = cur.setdefault(k, {})
        cur[keys[-1]] = value
    return s


def quiet(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue(), err.getvalue()


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def write_spec(self, spec, name="spec.json"):
        p = self.dir / name
        p.write_text(json.dumps(spec), encoding="utf-8")
        return p

    def build(self, spec):
        p = self.write_spec(spec)
        code, out, err = quiet(build_label.main, [str(p), "-o", str(self.dir / "out"), "--no-render"])
        return code, p, self.dir / "out" / "label.svg", out + err


# --------------------------------------------------------------------------- spec validation
class SpecValidation(unittest.TestCase):
    def test_template_is_valid_and_sized_for_hopera(self):
        spec, tpl, warnings = validate_spec(copy.deepcopy(TEMPLATE))
        self.assertEqual((tpl["width_px"], tpl["height_px"]), (2078, 1368))
        self.assertAlmostEqual(tpl["px_per_mm"], 11.4, places=2)
        self.assertEqual(warnings, [])

    def test_missing_required_fields(self):
        s = spec_with(beer__name="", producer__address="")
        with self.assertRaises(SpecError) as cm:
            validate_spec(s)
        text = " ".join(cm.exception.problems)
        self.assertIn("beer.name", text)
        self.assertIn("producer.address", text)

    def test_unknown_key_and_ranges(self):
        s = spec_with(beer__abv=45, design__palette={"bg": "red"})
        s["ingredient"] = []
        with self.assertRaises(SpecError) as cm:
            validate_spec(s)
        text = " ".join(cm.exception.problems)
        self.assertIn("unknown key 'ingredient'", text)
        self.assertIn("beer.abv", text)
        self.assertIn("design.palette.bg", text)

    def test_motif_validation(self):
        with self.assertRaises(SpecError):
            validate_spec(spec_with(design__motifs=[{"type": "flames"}]))
        with self.assertRaises(SpecError):
            validate_spec(spec_with(design__motifs=[{"type": "greek-key"}, {"type": "zigzag"}]))
        with self.assertRaises(SpecError):
            validate_spec(spec_with(design__motifs=[{"type": "waves", "layers": 99}]))

    def test_custom_template_ratio_warning(self):
        s = spec_with(template={"preset": "custom", "width_px": 1000, "height_px": 1000, "can_diameter_mm": 66,
                                "label_height_mm": 100})
        _, tpl, warnings = validate_spec(s)
        self.assertEqual(tpl["width_px"], 1000)
        self.assertTrue(any("ratio" in w for w in warnings))

    def test_bad_font_names_rejected(self):
        for bad in ["Inter;}</style><script>alert(1)</script>", "Roboto:wght@400", "Open+Sans", "x" * 41, ""]:
            with self.subTest(bad=bad):
                with self.assertRaises(SpecError):
                    validate_spec(spec_with(design__fonts={"display": {"family": bad}}))
        spec, _, _ = validate_spec(spec_with(design__fonts={"display": "IBM Plex Sans Condensed"}))
        self.assertEqual(spec["design"]["fonts"]["display"]["family"], "IBM Plex Sans Condensed")

    def test_control_characters_rejected(self):
        with self.assertRaises(SpecError):
            validate_spec(spec_with(beer__name="Bad\x00Name"))

    def test_italian_strings(self):
        spec, tpl, _ = validate_spec(spec_with(language="it", beer__abv=5.2))
        self.assertEqual(spec["strings"]["best_before"], "Da consumarsi preferibilmente entro:")
        svg, _ = compose(spec, tpl)
        self.assertIn("alc. 5,2% vol", svg)
        self.assertIn("BIRRA", svg)


# --------------------------------------------------------------------------- escaping
class Escaping(Workspace):
    PAYLOADS = ['</text><script>alert(1)</script>', 'Fish & "Chips" <b>', "it's <![CDATA[x]]>"]

    def test_text_injection_is_escaped(self):
        s = spec_with(beer__name=self.PAYLOADS[0], beer__tagline=self.PAYLOADS[1],
                      story=[self.PAYLOADS[2]], producer__name='"><svg onload=alert(1)>')
        s["ingredients"].append({"text": "</tspan><script>x</script>", "allergen": True})
        code, spec_path, svg_path, log = self.build(s)
        self.assertEqual(code, 0, log)
        raw = svg_path.read_text(encoding="utf-8")
        root = ET.fromstring(raw)  # well-formed despite the payloads
        tags = {el.tag.replace(SVG_NS, "") for el in root.iter()}
        self.assertNotIn("script", tags)
        self.assertNotIn("<script", raw)
        texts = ["".join(t.itertext()) for t in root.iter(SVG_NS + "text")]
        self.assertIn(self.PAYLOADS[1], texts)  # round-trips as plain text
        self.assertTrue(any(self.PAYLOADS[2] in t for t in texts))
        for el in root.iter():
            for attr in el.attrib:
                self.assertFalse(attr.lower().startswith("on"), attr)

    def test_preview_page_escapes_title_and_config(self):
        s = spec_with(beer__name="</script><script>alert(1)</script>")
        code, spec_path, svg_path, log = self.build(s)
        self.assertEqual(code, 0, log)
        html = (self.dir / "out" / "can_preview.html").read_text(encoding="utf-8")
        self.assertEqual(html.count("<script"), 3)  # config JSON, three.js, viewer
        cfg = re.search(r'<script type="application/json" id="cfg">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn("<", cfg)
        self.assertTrue(json.loads(cfg)["title"].startswith("</script>"))
        self.assertIn(THREE_URL, html)
        self.assertIn(f'integrity="{THREE_SRI}"', html)
        self.assertIn('id="fallback"', html)


# --------------------------------------------------------------------------- SVG logos
class SvgSanitizer(Workspace):
    def sanitize(self, svg):
        return sanitize_svg(svg.encode("utf-8"))

    def test_script_onload_foreignobject_and_external_refs_are_removed(self):
        evil = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                'viewBox="0 0 10 10" onload="alert(1)">'
                '<script>alert(2)</script>'
                '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">x</div></foreignObject>'
                '<a href="javascript:alert(3)"><rect width="5" height="5"/></a>'
                '<use xlink:href="https://evil.example/x.svg#a"/>'
                '<use href="#ok"/>'
                '<image href="https://evil.example/track.png" width="1" height="1"/>'
                '<rect id="ok" width="1" height="1" fill="url(https://evil.example/p.svg#g)" onclick="x()"/>'
                '<style>@import url(https://evil.example/a.css);</style>'
                '<set attributeName="href" to="javascript:alert(4)"/>'
                '<circle r="2" style="fill:red"/></svg>')
        clean, report = self.sanitize(evil)
        text = clean.decode("utf-8")
        for bad in ("script", "foreignObject", "onload", "onclick", "javascript", "evil.example", "@import",
                    "<set", "<a "):
            self.assertNotIn(bad, text, bad)
        self.assertIn('href="#ok"', text)  # internal references survive
        self.assertIn("circle", text)
        self.assertTrue(report)

    def test_entities_and_doctype_are_refused(self):
        billion = ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
                   '<svg xmlns="http://www.w3.org/2000/svg"><text>&b;</text></svg>')
        xxe = ('<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
               '<svg xmlns="http://www.w3.org/2000/svg"><text>&x;</text></svg>')
        for payload in (billion, xxe):
            with self.assertRaises(UnsafeInput):
                self.sanitize(payload)

    def test_non_utf8_and_declared_encodings_refused(self):
        bomb = '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>'
        with self.assertRaises(UnsafeInput):
            sanitize_svg(bomb.encode("utf-16"))
        with self.assertRaises(UnsafeInput):
            sanitize_svg(b'<?xml version="1.0" encoding="ISO-8859-1"?><svg xmlns="http://www.w3.org/2000/svg"/>')
        clean, _ = sanitize_svg(b'<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>')
        self.assertIn(b"<rect", clean)

    def test_non_svg_root_refused(self):
        with self.assertRaises(UnsafeInput):
            self.sanitize('<html xmlns="http://www.w3.org/1999/xhtml"><script/></html>')

    def test_logo_is_embedded_as_image_not_inlined(self):
        (self.dir / "logo.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" onload="alert(1)">'
            '<script>alert(1)</script><circle r="4" cx="5" cy="5"/></svg>', encoding="utf-8")
        code, _, svg_path, log = self.build(spec_with(design__logo={"path": "logo.svg"}))
        self.assertEqual(code, 0, log)
        self.assertIn("sanitizer", log)
        root = ET.parse(svg_path).getroot()
        imgs = [el for el in root.iter(SVG_NS + "image") if el.get("data-role") == "logo"]
        self.assertEqual(len(imgs), 1)
        href = imgs[0].get("{http://www.w3.org/1999/xlink}href")
        self.assertTrue(href.startswith("data:image/svg+xml;base64,"))
        inner = base64.b64decode(href.split(",", 1)[1]).decode("utf-8")
        self.assertNotIn("script", inner)
        self.assertNotIn("onload", inner)
        self.assertNotIn('r="4" cx="5"', svg_path.read_text(encoding="utf-8"))  # logo markup not inlined

    def test_raster_logo_checks(self):
        (self.dir / "ok.png").write_bytes(PNG_1PX)
        self.assertTrue(load_logo(self.dir, "ok.png")["data_uri"].startswith("data:image/png;base64,"))
        (self.dir / "fake.png").write_bytes(b"<svg onload=alert(1)>")
        with self.assertRaises(UnsafeInput):
            load_logo(self.dir, "fake.png")
        (self.dir / "big.png").write_bytes(PNG_1PX + b"\0" * (5 * 1024 * 1024 + 1))
        with self.assertRaises(UnsafeInput):
            load_logo(self.dir, "big.png")
        (self.dir / "logo.gif").write_bytes(b"GIF89a")
        with self.assertRaises(UnsafeInput):
            load_logo(self.dir, "logo.gif")


# --------------------------------------------------------------------------- paths
class Paths(Workspace):
    def test_logo_path_traversal_rejected(self):
        for bad in ["../../etc/passwd", "/etc/passwd", "sub/../../outside.svg", "..\\..\\x.svg/../../.."]:
            with self.subTest(bad=bad):
                with self.assertRaises(UnsafeInput):
                    resolve_inside(self.dir, bad)
        code, _, _, log = self.build(spec_with(design__logo={"path": "../../etc/passwd"}))
        self.assertEqual(code, 2)
        self.assertIn("outside", log)

    def test_symlink_escape_rejected(self):
        outside = tempfile.NamedTemporaryFile(suffix=".svg", delete=False)
        outside.write(b'<svg xmlns="http://www.w3.org/2000/svg"/>')
        outside.close()
        try:
            os.symlink(outside.name, self.dir / "link.svg")
            with self.assertRaises(UnsafeInput):
                load_logo(self.dir, "link.svg")
        finally:
            os.unlink(outside.name)

    def test_output_folder_must_stay_inside(self):
        with self.assertRaises(UnsafeInput):
            ensure_output_dir("/tmp/../etc/beer-label-out", [self.dir])
        p = self.write_spec(copy.deepcopy(TEMPLATE))
        elsewhere = tempfile.mkdtemp()
        try:
            cwd = os.getcwd()
            os.chdir(self.dir)
            try:
                code, _, err = quiet(build_label.main, [str(p), "-o", elsewhere, "--no-render"])
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 2)
            self.assertIn("must be inside", err)
        finally:
            os.rmdir(elsewhere)


# --------------------------------------------------------------------------- QA script
class Checker(Workspace):
    def check(self, spec_path, svg_path):
        return check_label.check(spec_path, svg_path)

    def test_template_label_passes(self):
        code, spec_path, svg_path, log = self.build(copy.deepcopy(TEMPLATE))
        self.assertEqual(code, 0, log)
        report = self.check(spec_path, svg_path)
        self.assertEqual(report["errors"], [])
        self.assertTrue(any("open placeholder" in w for w in report["warnings"]))

    def test_missing_allergen_emphasis_is_caught(self):
        s = copy.deepcopy(TEMPLATE)
        s["ingredients"] = [{"text": "water"}, {"text": "barley malt"}, {"text": "hops"}]
        code, spec_path, svg_path, log = self.build(s)
        self.assertEqual(code, 0, log)
        report = self.check(spec_path, svg_path)
        self.assertTrue(any("barley" in e and "not emphasised" in e for e in report["errors"]), report)

    def test_content_in_seam_zone_is_caught(self):
        code, spec_path, svg_path, log = self.build(copy.deepcopy(TEMPLATE))
        raw = svg_path.read_text(encoding="utf-8")
        raw = raw.replace("</svg>", '<text x="8" y="600" font-size="30" fill="#ffffff">LOT 42</text></svg>')
        svg_path.write_text(raw, encoding="utf-8")
        report = self.check(spec_path, svg_path)
        self.assertTrue(any("seam" in e for e in report["errors"]), report)

    def test_rotated_text_near_the_seam_is_caught(self):
        code, spec_path, svg_path, log = self.build(copy.deepcopy(TEMPLATE))
        raw = svg_path.read_text(encoding="utf-8").replace(
            "</svg>", '<text transform="translate(2050,1200) rotate(-90)" x="0" y="0" font-size="30" '
                      'fill="#ffffff">ROTATED NOTE</text></svg>')
        svg_path.write_text(raw, encoding="utf-8")
        self.assertTrue(any("seam" in e for e in self.check(spec_path, svg_path)["errors"]))

    def test_small_mandatory_text_and_dashes_are_caught(self):
        s = copy.deepcopy(TEMPLATE)
        s["story"] = ["Brewed slowly \u2014 then canned."]
        code, spec_path, svg_path, log = self.build(s)
        raw = svg_path.read_text(encoding="utf-8").replace(
            "</svg>", '<text x="900" y="700" font-size="15" data-role="producer" fill="#ffffff">tiny</text></svg>')
        svg_path.write_text(raw, encoding="utf-8")
        errors = self.check(spec_path, svg_path)["errors"]
        self.assertTrue(any("mandatory text" in e for e in errors), errors)
        self.assertTrue(any("em dash" in e for e in errors), errors)

    def test_wrong_size_and_missing_parts_are_caught(self):
        code, spec_path, svg_path, log = self.build(copy.deepcopy(TEMPLATE))
        raw = svg_path.read_text(encoding="utf-8")
        raw = raw.replace('width="2078" height="1368"', 'width="1000" height="600"', 1)
        raw = re.sub(r'<rect[^>]*data-role="best-before"/>', "", raw)
        raw = re.sub(r'<rect[^>]*data-role="distributor"/>', "", raw)
        svg_path.write_text(raw, encoding="utf-8")
        errors = self.check(spec_path, svg_path)["errors"]
        self.assertTrue(any("size is" in e for e in errors))
        self.assertTrue(any("best-before" in e for e in errors))
        self.assertTrue(any("Distributed by" in e for e in errors))

    def test_check_refuses_entities(self):
        code, spec_path, svg_path, log = self.build(copy.deepcopy(TEMPLATE))
        svg_path.write_text('<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>',
                            encoding="utf-8")
        self.assertTrue(any("DOCTYPE" in e for e in self.check(spec_path, svg_path)["errors"]))

    def test_cli_exit_codes(self):
        code, spec_path, svg_path, log = self.build(copy.deepcopy(TEMPLATE))
        self.assertEqual(quiet(check_label.main, [str(spec_path), str(svg_path)])[0], 0)
        svg_path.write_text(svg_path.read_text(encoding="utf-8").replace(
            "</svg>", '<text x="5" y="5" font-size="30">X</text></svg>'), encoding="utf-8")
        self.assertEqual(quiet(check_label.main, [str(spec_path), str(svg_path)])[0], 1)


# --------------------------------------------------------------------------- geometry helpers
class Geometry(unittest.TestCase):
    def test_waves_meet_at_the_back_seam(self):
        ctx = {"W": 2078, "H": 1368, "ppm": 11.4, "palette": {"secondary": "#5fa8a0", "bg2": "#000000"}}
        _, body = waves(ctx, {"color": "secondary", "layers": 3, "height_pct": 15, "opacity": 0.4,
                              "amplitude_mm": 2.2, "period_mm": 26})
        for d in re.findall(r'd="([^"]+)"', body):
            pts = re.findall(r"L(-?[0-9.]+),(-?[0-9.]+)", d)
            first, last = pts[0], pts[-2]
            self.assertEqual(float(first[0]), 0.0)
            self.assertAlmostEqual(float(last[0]), 2078.0)
            self.assertAlmostEqual(float(first[1]), float(last[1]), delta=0.2)

    def test_wrap_keeps_punctuation_with_emphasis(self):
        runs = [("Ingredients: ", "label"), ("water", False), (", ", False), ("BARLEY MALT", "allergen"),
                (", ", False), ("hops", False), (".", False)]
        lines = wrap_runs(runs, 10000, 28)
        self.assertEqual("".join(t for t, _ in lines[0]), "Ingredients: water, BARLEY MALT, hops.")
        narrow = wrap_runs(runs, 200, 28)
        self.assertTrue(all(not seg.startswith(",") for line in narrow for seg, _ in line[:1]))

    def test_preview_falls_back_to_svg_without_png(self):
        spec, tpl, _ = validate_spec(copy.deepcopy(TEMPLATE))
        with tempfile.TemporaryDirectory() as d:
            out = build_preview(d, spec, tpl, None, "<svg xmlns='http://www.w3.org/2000/svg'/>")
            self.assertIn("data:image/svg+xml;base64,", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
