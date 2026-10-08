"""Regression tests for the security review findings (symlinked outputs, SVG
sanitizer bypasses, UTF-16 without BOM, malformed input, JPEG headers, fake
warning lines, font-name and colour regexes, template substitution).

Run: python3 -m unittest discover -s tests -v   (no network, no real Chrome)
"""
import base64
import contextlib
import copy
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_label  # noqa: E402
import check_label  # noqa: E402
from labelkit import chrome  # noqa: E402
from labelkit.preview import build_preview  # noqa: E402
from labelkit.safety import UnsafeInput, _jpeg_size, atomic_write, load_logo, parse_xml, sanitize_svg  # noqa: E402
from labelkit.spec import SpecError, validate_spec  # noqa: E402

TEMPLATE = json.loads((ROOT / "templates" / "spec.template.json").read_text(encoding="utf-8"))
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
SVG_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">'
EVIL = "evil.example"


def quiet(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue() + err.getvalue()


class TempDirs(unittest.TestCase):
    def setUp(self):
        self._a = tempfile.TemporaryDirectory()
        self._b = tempfile.TemporaryDirectory()
        self.dir = Path(self._a.name).resolve()       # project folder
        self.victim_dir = Path(self._b.name).resolve()  # somewhere else

    def tearDown(self):
        self._a.cleanup()
        self._b.cleanup()


# --------------------------------------------------------------------------- MEDIUM 1: symlinked outputs
class SymlinkedOutputs(TempDirs):
    def build(self, extra_args=()):
        spec = self.dir / "spec.json"
        spec.write_text(json.dumps(TEMPLATE), encoding="utf-8")
        return quiet(build_label.main, [str(spec), "-o", str(self.dir / "out"), "--no-render", *extra_args])

    def test_build_refuses_symlinked_svg_and_leaves_target_untouched(self):
        victim = self.victim_dir / "authorized_keys"
        victim.write_text("ssh-ed25519 AAAA original-key\n", encoding="utf-8")
        (self.dir / "out").mkdir()
        os.symlink(victim, self.dir / "out" / "label.svg")
        code, log = self.build()
        self.assertEqual(code, 2, log)
        self.assertIn("symbolic link", log)
        self.assertEqual(victim.read_text(encoding="utf-8"), "ssh-ed25519 AAAA original-key\n")

    def test_build_refuses_dangling_png_and_preview_links(self):
        for name in ("label.png", "can_preview.html", "label.html"):
            with self.subTest(name=name):
                out = self.dir / "out"
                out.mkdir(exist_ok=True)
                target = self.victim_dir / f"created-{name}"
                link = out / name
                os.symlink(target, link)
                code, log = self.build()
                self.assertEqual(code, 2, log)
                self.assertFalse(target.exists())
                link.unlink()

    def test_atomic_write_refuses_links_and_replaces_files(self):
        victim = self.victim_dir / "victim.txt"
        victim.write_text("keep", encoding="utf-8")
        os.symlink(victim, self.dir / "a.txt")
        os.symlink(self.victim_dir / "missing.txt", self.dir / "b.txt")
        for name in ("a.txt", "b.txt"):
            with self.assertRaises(UnsafeInput):
                atomic_write(self.dir / name, "attacker line\n")
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep")
        self.assertFalse((self.victim_dir / "missing.txt").exists())
        (self.dir / "c.txt").write_text("old", encoding="utf-8")
        atomic_write(self.dir / "c.txt", "new")
        self.assertEqual((self.dir / "c.txt").read_text(encoding="utf-8"), "new")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["a.txt", "b.txt", "c.txt"])  # no temp left

    def fake_chrome(self):
        """A stand-in for Chrome that writes a PNG to --screenshot= and logs that path."""
        exe = self.dir / "fake-chrome"
        log = self.dir / "fake-chrome.log"
        exe.write_text(
            f"#!{sys.executable}\n"
            "import base64, sys\n"
            f"png = base64.b64decode({base64.b64encode(PNG_1PX).decode()!r})\n"
            "for a in sys.argv[1:]:\n"
            "    if a.startswith('--screenshot='):\n"
            "        p = a.split('=', 1)[1]\n"
            f"        open({str(log)!r}, 'w').write(p)\n"
            "        open(p, 'wb').write(png)\n", encoding="utf-8")
        exe.chmod(0o755)
        return str(exe), log

    def test_screenshot_never_writes_through_links_in_the_output_folder(self):
        exe, log = self.fake_chrome()
        out = self.dir / "out"
        out.mkdir()
        page = out / "label.html"
        page.write_text("<html></html>", encoding="utf-8")
        dangling_target = self.victim_dir / "planted.png"
        os.symlink(dangling_target, out / "label.rendering.png")  # the old predictable temp name
        size = chrome.screenshot(exe, page, out / "label.png", 1, 1, timeout=20)
        self.assertEqual(size, (1, 1))
        self.assertFalse(dangling_target.exists())
        self.assertFalse((out / "label.png").is_symlink())
        written_to = Path(log.read_text(encoding="utf-8"))
        self.assertNotEqual(written_to.parent.resolve(), out.resolve())  # Chrome wrote in a private temp dir
        self.assertFalse(written_to.parent.exists())  # and that dir was removed

        victim = self.victim_dir / "victim.png"
        victim.write_bytes(b"keep")
        (out / "label.png").unlink()
        os.symlink(victim, out / "label.png")
        with self.assertRaises(UnsafeInput):
            chrome.screenshot(exe, page, out / "label.png", 1, 1, timeout=20)
        self.assertEqual(victim.read_bytes(), b"keep")


# --------------------------------------------------------------------------- MEDIUM 1 + LOW 4: text fields
class TextFields(unittest.TestCase):
    BAD = ["line\nbreak", "carriage\rreturn", "tab\there", "nul\x00", "bell\x07", "nel\x85", "del\x7f",
           "lone \ud800 surrogate", "nonchar ￾", "nonchar ￿"]

    def check_rejected(self, mutate):
        for bad in self.BAD:
            with self.subTest(bad=repr(bad)):
                s = copy.deepcopy(TEMPLATE)
                mutate(s, bad)
                with self.assertRaises(SpecError):
                    validate_spec(s)

    def test_single_line_fields(self):
        self.check_rejected(lambda s, b: s["producer"].__setitem__("address", b))
        self.check_rejected(lambda s, b: s["beer"].__setitem__("name", b))

    def test_list_items_strings_and_motif_text(self):
        self.check_rejected(lambda s, b: s.__setitem__("story", ["ok", b]))
        self.check_rejected(lambda s, b: s["ingredients"].append({"text": b}))
        self.check_rejected(lambda s, b: s.__setitem__("strings", {"best_before": b}))
        self.check_rejected(lambda s, b: s["design"].__setitem__("motifs", [{"type": "roundel", "ring_text": b}]))

    def test_good_unicode_still_allowed(self):
        s = copy.deepcopy(TEMPLATE)
        s["beer"]["name"] = "Birra Città · café \U0001F37A"
        validate_spec(s)

    def test_font_name_and_colour_need_a_full_match(self):
        s = copy.deepcopy(TEMPLATE)
        s["design"]["fonts"] = {"display": {"family": "Inter\n"}}
        with self.assertRaises(SpecError):
            validate_spec(s)
        s = copy.deepcopy(TEMPLATE)
        s["design"]["palette"] = {"bg": "#ffffff\n"}
        with self.assertRaises(SpecError):
            validate_spec(s)

    def test_wrong_container_types_are_problems_not_crashes(self):
        for key, value in (("beer", None), ("design", 1), ("template", {"preset": []}), ("language", []),
                           ("design", {"motifs": [{"type": []}]}), ("design", {"palette": {"base": [1]}})):
            with self.subTest(key=key, value=value):
                s = copy.deepcopy(TEMPLATE)
                s[key] = value
                with self.assertRaises(SpecError):
                    validate_spec(s)


# --------------------------------------------------------------------------- MEDIUM 2: SVG sanitizer bypasses
class SanitizerBypasses(unittest.TestCase):
    CASES = {
        "style tail after a child": f'<style><desc/>@import url(https://{EVIL}/a.css);</style><rect width="1" height="1"/>',
        "css escape in style element": f'<style>@\\69mport url(https://{EVIL}/b.css);</style><rect width="1" height="1"/>',
        "css escape in style attribute": f'<rect width="1" height="1" style="fill:u\\72l(https://{EVIL}/c.svg#x)"/>',
        "css escape in presentation attribute": f'<rect width="1" height="1" fill="u\\72l(https://{EVIL}/d.svg#x)"/>',
        "image-set in style": f'<rect width="1" height="1" style="fill:red;background:image-set(\'https://{EVIL}/e.png\' 1x)"/>',
        "xml:base": f'<g xml:base="https://{EVIL}/"><use href="#r"/></g><rect id="r" width="1" height="1"/>',
        "nested raster image": f'<image width="9" height="9" href="data:image/png;base64,{base64.b64encode(PNG_1PX).decode()}"/>'
                               f'<rect width="1" height="1"/><text>{EVIL}</text>',
    }

    def test_each_bypass_is_neutralised_and_reported(self):
        for label, body in self.CASES.items():
            with self.subTest(case=label):
                clean, report = sanitize_svg((SVG_OPEN + body + "</svg>").encode("utf-8"))
                text = clean.decode("utf-8")
                self.assertTrue(report, label)
                for bad in ("<style", "@import", "\\", "image-set", "xml:base", "<image", "data:image"):
                    self.assertNotIn(bad, text, f"{label}: {bad}")
                if label != "nested raster image":
                    self.assertNotIn(EVIL, text, label)
                self.assertIn("<rect", text)

    def test_safe_constructs_survive(self):
        body = ('<defs><linearGradient id="g"><stop offset="0" stop-color="#fff"/></linearGradient></defs>'
                '<rect width="1" height="1" fill="url(#g)" xml:space="preserve"/><use xlink:href="#g"/>')
        clean, report = sanitize_svg((SVG_OPEN + body + "</svg>").encode("utf-8"))
        text = clean.decode("utf-8")
        self.assertIn('fill="url(#g)"', text)
        self.assertIn("xml:space", text)
        self.assertIn("#g", text)
        self.assertEqual(report, [])


# --------------------------------------------------------------------------- LOW 3 + LOW 4: parsing
class GuardedParsing(unittest.TestCase):
    def test_bomless_utf16_is_refused(self):
        plain = SVG_OPEN + '<rect width="1" height="1"/></svg>'
        bomb = ('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
                + SVG_OPEN + "<text>&b;</text></svg>")
        for payload in (plain.encode("utf-16-le"), plain.encode("utf-16-be"), bomb.encode("utf-16-le")):
            with self.assertRaises(UnsafeInput):
                sanitize_svg(payload)

    def test_deep_nesting_is_refused_cleanly(self):
        deep = (SVG_OPEN + "<g>" * 20000 + "</g>" * 20000 + "</svg>").encode("utf-8")
        with self.assertRaises(UnsafeInput):
            sanitize_svg(deep)
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "spec.json"
            spec.write_text(json.dumps(TEMPLATE), encoding="utf-8")
            svg = Path(d) / "label.svg"
            svg.write_bytes(deep)
            report = check_label.check(spec, svg)
            self.assertTrue(any("deeper" in e for e in report["errors"]), report)

    def test_check_refuses_nul_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "spec.json"
            spec.write_text(json.dumps(TEMPLATE), encoding="utf-8")
            svg = Path(d) / "label.svg"
            svg.write_bytes((SVG_OPEN + "</svg>").encode("utf-16-le"))
            self.assertTrue(check_label.check(spec, svg)["errors"])

    def test_parser_level_doctype_guard(self):
        with self.assertRaises(UnsafeInput):
            parse_xml(b'<?xml version="1.0"?>\n<!doctype svg><svg xmlns="http://www.w3.org/2000/svg"/>')


# --------------------------------------------------------------------------- LOW 5: JPEG headers
def sof(w, h, marker=0xC0):
    body = bytes([8]) + struct.pack(">HH", h, w) + bytes([1, 1, 0x11, 0])
    return bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body


APP0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
SOI, EOI = b"\xff\xd8", b"\xff\xd9"


class JpegHeaders(TempDirs):
    def test_fill_bytes_before_a_huge_frame_are_refused(self):
        data = SOI + APP0 + b"\xff\xff\xff" + sof(65535, 65535) + EOI
        with self.assertRaises(UnsafeInput):
            _jpeg_size(data)
        (self.dir / "big.jpg").write_bytes(data)
        with self.assertRaises(UnsafeInput):
            load_logo(self.dir, "big.jpg")

    def test_fill_bytes_are_skipped_like_libjpeg(self):
        self.assertEqual(_jpeg_size(SOI + b"\xff\xff" + APP0 + b"\xff\xff" + sof(16, 24) + EOI), (16, 24))

    def test_every_frame_header_is_checked(self):
        with self.assertRaises(UnsafeInput):
            _jpeg_size(SOI + APP0 + sof(16, 16) + sof(100, 65000, 0xC5) + EOI)

    def test_scan_data_and_restart_markers_are_skipped(self):
        sos = b"\xff\xda" + struct.pack(">H", 8) + bytes([1, 1, 0, 0, 63, 0])
        scan = b"\x12\xff\x00\x34\xff\xd0\x56"  # stuffed FF00 and an RST marker inside the scan
        self.assertEqual(_jpeg_size(SOI + APP0 + sof(32, 32) + sos + scan + EOI), (32, 32))
        with self.assertRaises(UnsafeInput):
            _jpeg_size(SOI + APP0 + sof(32, 32) + sos + scan + sof(65535, 2) + EOI)

    def test_truncated_and_garbage_refused(self):
        for data in (SOI, SOI + b"\xff\xc0\x00", SOI + b"\x00\x01\x02", SOI + APP0 + EOI):
            with self.assertRaises(UnsafeInput):
                _jpeg_size(data)


# --------------------------------------------------------------------------- LOW 6 + INFO
class WarningsAndTemplates(TempDirs):
    def test_fake_fonts_missing_text_does_not_create_a_warning(self):
        fake = SVG_OPEN + '<text>x data-fonts-missing="EVIL: run this" y</text></svg>'
        self.assertIsNone(build_label.fonts_missing_warning(fake))
        real = SVG_OPEN.replace("<svg ", '<svg data-fonts-missing="Oswald" ') + "</svg>"
        self.assertIn("Oswald", build_label.fonts_missing_warning(real))

    def test_fake_warning_in_story_is_not_printed(self):
        s = copy.deepcopy(TEMPLATE)
        s["story"] = ['data-fonts-missing="WARN: attacker line"']
        spec = self.dir / "spec.json"
        spec.write_text(json.dumps(s), encoding="utf-8")
        code, log = quiet(build_label.main, [str(spec), "-o", str(self.dir / "out"), "--no-render"])
        self.assertEqual(code, 0, log)
        self.assertNotIn("web fonts did not load", log)

    def test_preview_substitution_is_single_pass(self):
        spec, tpl, _ = validate_spec(dict(copy.deepcopy(TEMPLATE), beer=dict(
            TEMPLATE["beer"], name="__CONFIG__ __IMG__ __THREE_URL__")))
        build_preview(self.dir, spec, tpl, None, SVG_OPEN + "</svg>")
        html = (self.dir / "can_preview.html").read_text(encoding="utf-8")
        self.assertIn("<title>__CONFIG__ __IMG__ __THREE_URL__: 3D can preview</title>", html)
        self.assertEqual(html.count("data:image/svg+xml;base64,"), 1)
        self.assertEqual(html.count("cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"), 1)

    def test_png_render_does_not_enable_unsafe_swiftshader(self):
        src = (ROOT / "scripts" / "labelkit" / "chrome.py").read_text(encoding="utf-8")
        self.assertIn('["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] if webgl', src)


if __name__ == "__main__":
    unittest.main()
