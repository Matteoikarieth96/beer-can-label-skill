#!/usr/bin/env python3
"""Build a print-ready full-wrap beer can label from spec.json.

Usage:
  python3 scripts/build_label.py path/to/spec.json -o path/to/out/
  python3 scripts/build_label.py spec.json -o out/ --no-render     # SVG + HTML only, no Chrome

Writes into the output folder:
  label.svg         vector artwork (fonts referenced from Google Fonts)
  label.html        the SVG in a page with the web fonts, used for rendering
  label.png         exact template size (Hopera: 2078 x 1368), via headless Chrome
  can_preview.html  rotating 3D can (three.js r128 from cdnjs) with the label as texture

The output folder must be inside the spec's folder or the current directory.
Exit codes: 0 ok, 2 invalid spec or unsafe input, 3 render failure.
"""
import argparse
import html as htmllib
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labelkit import chrome  # noqa: E402
from labelkit.compose import compose  # noqa: E402
from labelkit.preview import build_preview, json_for_script  # noqa: E402
from labelkit.safety import (UnsafeInput, atomic_write, ensure_output_dir, load_logo, parse_xml,  # noqa: E402
                             refuse_symlinks)

OUTPUT_NAMES = ("label.svg", "label.html", "label.png", "can_preview.html")
from labelkit.spec import SpecError, load_spec, placeholders  # noqa: E402

FIT_SCRIPT = r"""
(async function () {
  var out = document.getElementById('fitout');
  var cfg = JSON.parse(document.getElementById('fitcfg').textContent);
  var missing = [];
  try {
    for (var i = 0; i < cfg.fonts.length; i++) {
      var f = cfg.fonts[i];
      for (var j = 0; j < f.weights.length; j++) {
        try { await document.fonts.load(f.weights[j] + ' 32px "' + f.family + '"'); } catch (e) { /* offline */ }
      }
      try { if (!document.fonts.check('32px "' + f.family + '"')) { missing.push(f.family); } } catch (e) { missing.push(f.family); }
    }
    try { await document.fonts.ready; } catch (e) { /* ignore */ }
    var svg = document.querySelector('svg');
    var groups = new Map();
    svg.querySelectorAll('text[data-maxw]').forEach(function (t, i) {
      var k = t.getAttribute('data-fit') || ('solo' + i);
      if (!groups.has(k)) { groups.set(k, []); }
      groups.get(k).push(t);
    });
    groups.forEach(function (list) {
      var scale = 1;
      list.forEach(function (t) {
        var w = t.getComputedTextLength(), m = parseFloat(t.getAttribute('data-maxw'));
        if (w > m && w > 0) { scale = Math.min(scale, m / w); }
      });
      if (scale < 1) {
        list.forEach(function (t) {
          var fs = parseFloat(t.getAttribute('font-size'));
          var minfs = parseFloat(t.getAttribute('data-minfs') || '0');
          var ls = parseFloat(t.getAttribute('letter-spacing') || '0');
          var nfs = Math.floor(fs * scale * 0.995 * 10) / 10;
          if (nfs < minfs) { nfs = minfs; }
          t.setAttribute('font-size', nfs.toFixed(1));
          if (ls) { t.setAttribute('letter-spacing', (ls * nfs / fs).toFixed(2)); }
        });
      }
    });
    svg.querySelectorAll('text').forEach(function (t) {
      var w = t.getComputedTextLength();
      t.setAttribute('data-w', w.toFixed(1));
      var m = parseFloat(t.getAttribute('data-maxw'));
      if (m && w > m + 0.5) { t.setAttribute('data-overflow', '1'); }
    });
    if (missing.length) { svg.setAttribute('data-fonts-missing', missing.join(',')); }
    svg.setAttribute('data-fitted', '1');
    out.textContent = new XMLSerializer().serializeToString(svg);
  } catch (e) {
    out.textContent = 'FIT-ERROR ' + e;
  }
})();
"""


def font_links(label):
    links = []
    for q in label.font_css():
        url = f"https://fonts.googleapis.com/css2?{q}&display=block"
        links.append(f'<link rel="stylesheet" href="{htmllib.escape(url, quote=True)}">')
    return "\n".join(links)


def page(label, svg, extra_body=""):
    title = htmllib.escape(label.spec["beer"]["name"], quote=True)
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
            f"<title>{title}: flat label</title>\n"
            "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n"
            "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>\n"
            f"{font_links(label)}\n"
            "<style>html,body{margin:0;padding:0;background:#777}svg{display:block}</style>\n"
            f"</head><body>\n{svg}\n{extra_body}</body></html>\n")


def fit_with_chrome(chrome_bin, label, svg, workdir):
    cfg = {"fonts": [{"family": label.fonts[r]["family"], "weights": label.fonts[r]["weights"]}
                     for r in ("display", "body")]}
    extra = ('<textarea id="fitout" hidden></textarea>\n'
             f'<script type="application/json" id="fitcfg">{json_for_script(cfg)}</script>\n'
             f"<script>{FIT_SCRIPT}</script>\n")
    fit_html = Path(workdir) / "fit.html"
    atomic_write(fit_html, page(label, svg, extra))  # fresh private temp dir, still never via a link
    dom = chrome.dump_dom(chrome_bin, fit_html)
    m = re.search(r'<textarea id="fitout"[^>]*>(.*?)</textarea>', dom, re.S)
    if not m:
        raise RuntimeError("fit pass returned no SVG")
    fitted = htmllib.unescape(m.group(1))
    if not fitted.startswith("<svg"):
        raise RuntimeError(f"fit pass failed: {fitted[:200]}")
    parse_xml(fitted.encode("utf-8"), "fitted SVG")  # must be well-formed, guarded XML
    return fitted


def fonts_missing_warning(svg):
    """Warning text when the fit pass flagged missing web fonts on the root <svg>, else None.

    Read from the parsed root element only, so label text that merely contains
    'data-fonts-missing="..."' cannot inject a warning line.
    """
    try:
        root = parse_xml(svg.encode("utf-8"), "SVG")
    except UnsafeInput:
        return None
    missing = root.get("data-fonts-missing")
    if not missing:
        return None
    return (f"web fonts did not load ({missing}); the PNG uses a fallback font. "
            "Check the family names on fonts.google.com and your network.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", help="path to spec.json")
    ap.add_argument("-o", "--out", required=True, help="output folder (inside the spec folder or the current directory)")
    ap.add_argument("--no-render", action="store_true", help="skip headless Chrome (no PNG, no font-accurate fitting)")
    ap.add_argument("--chrome", help="path to Chrome or Chromium (default: CHROME_PATH or the usual install paths)")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec).expanduser().resolve()
    try:
        spec, tpl, warnings = load_spec(spec_path)
        out = ensure_output_dir(args.out, [spec_path.parent, Path.cwd()])
        refuse_symlinks(out, OUTPUT_NAMES)
        assets = {}
        if spec["design"]["logo"]["path"]:
            assets["logo"] = load_logo(spec_path.parent, spec["design"]["logo"]["path"], "design.logo")
        if spec["distributor"]["logo"]:
            assets["distributor_logo"] = load_logo(spec_path.parent, spec["distributor"]["logo"], "distributor.logo")
    except SpecError as exc:
        print("Spec problems:", file=sys.stderr)
        for p in exc.problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    except (UnsafeInput, OSError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2

    for key, asset in assets.items():
        for line in asset["report"]:
            warnings.append(f"{key} sanitizer: {line}")

    svg, label = compose(spec, tpl, assets)
    warnings.extend(label.warnings)

    chrome_bin = None if args.no_render else chrome.find_chrome(args.chrome)
    if not args.no_render and not chrome_bin:
        warnings.append("Chrome or Chromium not found: wrote SVG and HTML only (set CHROME_PATH to render the PNG)")

    if chrome_bin:
        with tempfile.TemporaryDirectory(prefix="bcl-fit-") as work:
            try:
                svg = fit_with_chrome(chrome_bin, label, svg, work)
                warn = fonts_missing_warning(svg)
                if warn:
                    warnings.append(warn)
            except (RuntimeError, UnsafeInput, OSError) as exc:
                warnings.append(f"font-accurate fitting skipped: {exc}")

    try:
        atomic_write(out / "label.svg", svg)
        atomic_write(out / "label.html", page(label, svg))
    except (UnsafeInput, OSError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    png = out / "label.png"
    status = 0
    if chrome_bin:
        try:
            w, h = chrome.screenshot(chrome_bin, out / "label.html", png, tpl["width_px"], tpl["height_px"])
            if (w, h) != (tpl["width_px"], tpl["height_px"]):
                print(f"ERROR: label.png is {w}x{h}, expected {tpl['width_px']}x{tpl['height_px']}", file=sys.stderr)
                status = 3
        except (RuntimeError, UnsafeInput, OSError) as exc:
            print(f"ERROR: PNG render failed: {exc}", file=sys.stderr)
            status = 3
    try:
        build_preview(out, spec, tpl, png if png.exists() and chrome_bin else None, svg)
    except (UnsafeInput, OSError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2

    print(f"Template: {tpl['title']}, {tpl['width_px']} x {tpl['height_px']} px, "
          f"{tpl['px_per_mm']:.2f} px/mm, can {tpl['can_diameter_mm']:g} mm")
    for name in ("label.svg", "label.html", "label.png", "can_preview.html"):
        p = out / name
        if p.exists():
            print(f"  wrote {p} ({p.stat().st_size // 1024} KB)")
    for w in warnings:
        print(f"WARN: {w}")
    open_items = placeholders(spec)
    if open_items:
        print("Open placeholders to confirm with the user:")
        for item in open_items:
            print(f"  - {item}")
    print(f"Next: python3 {Path(__file__).resolve().parent / 'check_label.py'} {spec_path} {out / 'label.svg'}")
    return status


if __name__ == "__main__":
    sys.exit(main())
