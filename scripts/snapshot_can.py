#!/usr/bin/env python3
"""Screenshot the 3D can preview with headless Chrome (WebGL via SwiftShader).

Usage:
  python3 scripts/snapshot_can.py out/can_preview.html -o out/can_front.png --view three-quarter

Views: front (u=0.5), three-quarter (u=0.45), left (0.2), right (0.8), back (0.0),
or --u 0..1 for any position on the wrap. If WebGL cannot run headless, the page
shows the flat label with a message instead: look at the image before using it.
The output file must be inside the preview's folder or the current directory.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from labelkit import chrome  # noqa: E402
from labelkit.safety import UnsafeInput, ensure_output_dir, refuse_symlinks  # noqa: E402

VIEWS = {"front": 0.5, "three-quarter": 0.45, "left": 0.2, "right": 0.8, "back": 0.0}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Screenshot can_preview.html at a given view.")
    ap.add_argument("html", help="path to can_preview.html")
    ap.add_argument("-o", "--out", required=True, help="PNG to write")
    ap.add_argument("--view", choices=sorted(VIEWS), default="three-quarter")
    ap.add_argument("--u", type=float, help="texture position 0..1 facing the camera (overrides --view)")
    ap.add_argument("--size", default="1000x820", help="WIDTHxHEIGHT in CSS px")
    ap.add_argument("--chrome", help="path to Chrome or Chromium")
    args = ap.parse_args(argv)

    html = Path(args.html).expanduser().resolve()
    if not html.is_file() or html.suffix.lower() != ".html":
        print("Refused: the input must be an existing .html file", file=sys.stderr)
        return 2
    m = re.fullmatch(r"(\d{2,4})x(\d{2,4})", args.size)
    if not m:
        print("Refused: --size must look like 1000x820", file=sys.stderr)
        return 2
    u = VIEWS[args.view] if args.u is None else args.u
    if not 0.0 <= u <= 1.0:
        print("Refused: --u must be between 0 and 1", file=sys.stderr)
        return 2
    out = Path(args.out).expanduser()
    try:
        folder = ensure_output_dir(out.parent, [html.parent, Path.cwd()])
        refuse_symlinks(folder, [out.name])
    except UnsafeInput as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    exe = chrome.find_chrome(args.chrome)
    if not exe:
        print("Chrome or Chromium not found (set CHROME_PATH)", file=sys.stderr)
        return 3
    url = f"{html.as_uri()}#u={u:.3f}&spin=0"
    try:
        w, h = chrome.screenshot(exe, url, folder / out.name, int(m.group(1)), int(m.group(2)),
                                 budget_ms=15000, webgl=True)
    except (UnsafeInput, RuntimeError, OSError) as exc:
        print(f"Refused or failed: {exc}", file=sys.stderr)
        return 3
    print(f"wrote {folder / out.name} ({w} x {h}). Check it: without WebGL the page shows the flat label.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
