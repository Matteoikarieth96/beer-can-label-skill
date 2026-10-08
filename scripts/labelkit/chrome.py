"""Headless Chrome helpers: find the binary, dump a DOM, take a screenshot.

Chrome runs with a throwaway profile (--user-data-dir in a temp folder), no
extensions and no first-run UI. Some Chrome builds keep running after writing
their output, so both helpers poll for the result and then stop the process.
Arguments are always passed as a list (no shell).
"""
import os
import shutil
import struct
import subprocess
import tempfile
import time
from pathlib import Path

from .safety import UnsafeInput, atomic_write

MAC_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
LINUX_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]


def find_chrome(explicit=None):
    for cand in [explicit, os.environ.get("CHROME_PATH")]:
        if cand and Path(cand).is_file() and os.access(cand, os.X_OK):
            return cand
    for cand in MAC_PATHS:
        if Path(cand).is_file():
            return cand
    for name in LINUX_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def _base_args(chrome, profile):
    return [chrome, "--headless=new", "--hide-scrollbars", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
            "--disable-component-update", "--disable-sync", "--mute-audio"]


def _stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(5)


def dump_dom(chrome, html_path, budget_ms=10000, timeout=90):
    """Load a local page, let scripts and web fonts settle, return the serialized DOM."""
    profile = tempfile.mkdtemp(prefix="bcl-chrome-")
    out_fd, out_path = tempfile.mkstemp(prefix="bcl-dom-", suffix=".html")
    try:
        with os.fdopen(out_fd, "wb") as out:
            args = _base_args(chrome, profile) + ["--disable-gpu", f"--virtual-time-budget={budget_ms}",
                                                  "--dump-dom", Path(html_path).resolve().as_uri()]
            proc = subprocess.Popen(args, stdout=out, stderr=subprocess.DEVNULL)
            start = time.time()
            text = ""
            try:
                while time.time() - start < timeout:
                    time.sleep(0.25)
                    text = Path(out_path).read_text(encoding="utf-8", errors="replace")
                    if "</html>" in text or proc.poll() is not None:
                        time.sleep(0.2)
                        text = Path(out_path).read_text(encoding="utf-8", errors="replace")
                        break
            finally:
                _stop(proc)
        if "</html>" not in text:
            raise RuntimeError("headless Chrome did not return the page in time")
        return text
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        try:
            os.unlink(out_path)
        except OSError:
            pass


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if not head.startswith(b"\x89PNG\r\n\x1a\n") or head[12:16] != b"IHDR":
        raise RuntimeError(f"{path} is not a PNG")
    return struct.unpack(">II", head[16:24])


def screenshot(chrome, url_or_path, png_path, width, height, budget_ms=10000, timeout=120, webgl=False):
    """Render a page at exactly width x height CSS pixels (device scale 1) to png_path.

    Chrome writes into a fresh private temp folder (mkdtemp, mode 0700); the PNG
    is then installed with atomic_write, which refuses symlinks. Nothing is
    written in the output folder under a predictable temp name. The SwiftShader
    flags (software WebGL) are only used for the 3D snapshot (webgl=True).
    """
    png_path = Path(png_path)
    if png_path.is_symlink():
        raise UnsafeInput(f"refusing to write through the symbolic link {png_path}")
    profile = tempfile.mkdtemp(prefix="bcl-chrome-")
    work = tempfile.mkdtemp(prefix="bcl-shot-")
    tmp_png = Path(work) / "shot.png"
    target = url_or_path if "://" in str(url_or_path) else Path(url_or_path).resolve().as_uri()
    gpu = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] if webgl \
        else ["--disable-gpu"]
    args = _base_args(chrome, profile) + gpu + [
        "--force-device-scale-factor=1", f"--window-size={int(width)},{int(height)}",
        f"--virtual-time-budget={budget_ms}", f"--screenshot={tmp_png}", target]
    try:
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        start, last, stable = time.time(), -1, 0
        try:
            while time.time() - start < timeout:
                time.sleep(0.3)
                if tmp_png.exists():
                    size = tmp_png.stat().st_size
                    stable = stable + 1 if size == last and size > 0 else 0
                    last = size
                    if stable >= 2:
                        break
                elif proc.poll() is not None:
                    break
        finally:
            _stop(proc)
        if not tmp_png.is_file() or tmp_png.is_symlink():
            raise RuntimeError("headless Chrome did not write a screenshot")
        size = png_size(tmp_png)
        atomic_write(png_path, tmp_png.read_bytes())
        return size
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
