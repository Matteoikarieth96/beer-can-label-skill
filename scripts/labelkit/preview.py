"""can_preview.html: a rotating 3D can with the label as its texture.

three.js r128 is loaded from cdnjs with an exact version and a Subresource
Integrity hash. If the script cannot load or WebGL is missing, the page shows
the flat label instead. The label image is embedded as a data URI so the page
works when opened from disk (browsers refuse file:// textures in WebGL).
Configuration travels in a <script type="application/json"> block with "<"
escaped, and the page writes user text with textContent only.
"""
import base64
import json
from pathlib import Path

from .safety import esc

THREE_URL = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
THREE_SRI = "sha512-dLxUelApnYxpLt6K2iomGngnHO83iUvZytA3YjDUCjT0HDOHKXnVYdf3hU4JjM8uEhxf9nD1/ey98U3t2vZ0qQ=="
MAX_EMBED_BYTES = 12 * 1024 * 1024

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f3f0ea;--fg:#1d1b19;--muted:#6a635b;--btn:#ffffff;--btn-line:#d6cfc4;--btn-on:#1d1b19;--btn-on-fg:#ffffff}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151413;--fg:#eeeae4;--muted:#a69e94;--btn:#24221f;--btn-line:#3b3733;--btn-on:#eeeae4;--btn-on-fg:#151413}}
:root[data-theme="dark"]{--bg:#151413;--fg:#eeeae4;--muted:#a69e94;--btn:#24221f;--btn-line:#3b3733;--btn-on:#eeeae4;--btn-on-fg:#151413}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:16px}
h1{font-size:18px;font-weight:600;margin:4px 0 8px;text-align:center}
#stage{position:relative;height:min(72vh,640px);min-height:340px;touch-action:none;cursor:grab;outline:none}
#stage:active{cursor:grabbing}
#stage canvas{display:block;width:100%;height:100%}
.controls{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:12px 0}
button{font:inherit;padding:8px 16px;border-radius:999px;border:1px solid var(--btn-line);background:var(--btn);color:var(--fg);cursor:pointer;min-width:72px}
button[aria-pressed="true"]{background:var(--btn-on);color:var(--btn-on-fg);border-color:var(--btn-on)}
button:focus-visible,#stage:focus-visible{outline:2px solid #3b82f6;outline-offset:2px}
.note{color:var(--muted);font-size:13px;text-align:center;margin:8px 0}
#fallback{text-align:center}
#fallback img{max-width:100%;height:auto;border-radius:6px;box-shadow:0 2px 12px rgba(0,0,0,.25)}
[hidden]{display:none !important}
</style>
</head>
<body>
<main>
<h1 id="title"></h1>
<div id="stage" tabindex="0" role="img" aria-label="3D can preview. Drag or use the arrow keys to rotate."></div>
<div class="controls" id="controls" role="group" aria-label="Can views">
<button type="button" data-u="front">Front</button>
<button type="button" data-u="left">Left</button>
<button type="button" data-u="right">Right</button>
<button type="button" data-u="back">Back</button>
<button type="button" id="spin" aria-pressed="false">Spin</button>
</div>
<div id="fallback" hidden>
<p id="fallback-msg" role="status"></p>
<img id="label-img" alt="Flat label artwork" src="__IMG__">
</div>
<p class="note">Screen preview only: colours, metallic inks and the exact wrap differ in print. The back seam is where the left and right edges of the label meet.</p>
<noscript><p class="note">This preview needs JavaScript. Open label.png to see the flat artwork.</p></noscript>
</main>
<script type="application/json" id="cfg">__CONFIG__</script>
<script src="__THREE_URL__" integrity="__THREE_SRI__" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<script>
(function () {
  'use strict';
  var cfg = JSON.parse(document.getElementById('cfg').textContent);
  var stage = document.getElementById('stage');
  var controls = document.getElementById('controls');
  var fallback = document.getElementById('fallback');
  var img = document.getElementById('label-img');
  document.getElementById('title').textContent = cfg.title;

  function showFallback(msg) {
    stage.hidden = true;
    controls.hidden = true;
    document.getElementById('fallback-msg').textContent = msg;
    fallback.hidden = false;
  }
  if (!window.THREE) {
    showFallback('The 3D viewer could not load three.js from cdnjs (offline or blocked). Showing the flat label instead.');
    return;
  }
  var probe = document.createElement('canvas');
  var hasGL = false;
  try { hasGL = !!(probe.getContext('webgl2') || probe.getContext('webgl')); } catch (e) { hasGL = false; }
  if (!hasGL) {
    showFallback('WebGL is not available in this browser, so the 3D can cannot be drawn. Showing the flat label instead.');
    return;
  }
  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  } catch (e) {
    showFallback('WebGL could not start. Showing the flat label instead.');
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  stage.appendChild(renderer.domElement);

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(30, 1, 1, 4000);

  // studio environment for the metallic aluminium
  var env = document.createElement('canvas');
  env.width = 512; env.height = 256;
  var g = env.getContext('2d');
  var grad = g.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0, '#ffffff'); grad.addColorStop(0.45, '#c9ccd4');
  grad.addColorStop(0.55, '#5a5f6b'); grad.addColorStop(1, '#1b1d22');
  g.fillStyle = grad; g.fillRect(0, 0, 512, 256);
  g.fillStyle = 'rgba(255,255,255,0.85)'; g.fillRect(90, 40, 40, 150); g.fillRect(360, 60, 24, 120);
  var envTex = new THREE.CanvasTexture(env);
  envTex.mapping = THREE.EquirectangularReflectionMapping;
  envTex.encoding = THREE.sRGBEncoding;
  var pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromEquirectangular(envTex).texture;

  scene.add(new THREE.AmbientLight(0xffffff, 0.12));
  var key = new THREE.DirectionalLight(0xfff4e6, 1.35); key.position.set(-160, 120, 200); scene.add(key);
  var rim = new THREE.DirectionalLight(0xdfe8ff, 0.7); rim.position.set(220, 60, -120); scene.add(rim);

  // can body (lathe profile in mm), scaled from the can diameter and height
  var r = cfg.can.diameter / 2, Hc = cfg.can.height, bodyBottom = 8, bodyTop = Hc - 18;
  var prof = [[0, 4], [0.55 * r, 2], [0.79 * r, 0], [0.914 * r, 0.8], [0.986 * r, 4], [r, bodyBottom], [r, bodyTop],
    [0.966 * r, bodyTop + 5], [0.883 * r, bodyTop + 10.5], [0.848 * r, Hc - 4.5], [0.848 * r, Hc - 2.6],
    [0.883 * r, Hc - 1.8], [0.883 * r, Hc], [0.807 * r, Hc], [0.8 * r, Hc - 2.4], [0, Hc - 2.4]]
    .map(function (p) { return new THREE.Vector2(p[0], p[1]); });
  var can = new THREE.Group();
  var alu = new THREE.MeshStandardMaterial({ color: 0xd9d9e2, metalness: 1, roughness: 0.28 });
  can.add(new THREE.Mesh(new THREE.LatheGeometry(prof, 128), alu));
  var tab = new THREE.Mesh(new THREE.BoxGeometry(0.48 * r, 0.8, 0.76 * r), alu);
  tab.position.set(0, Hc + 0.3, 0.14 * r); can.add(tab);
  var labelMat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.2, roughness: 0.42, envMapIntensity: 0.7 });
  var labelH = Math.min(cfg.can.label, bodyTop - bodyBottom);
  // thetaStart = PI puts texture u = 0.5 (the label centre) in front of the camera
  var sleeve = new THREE.Mesh(new THREE.CylinderGeometry(r + 0.25, r + 0.25, labelH, 192, 1, true, Math.PI, Math.PI * 2), labelMat);
  sleeve.position.y = (bodyBottom + bodyTop) / 2;
  can.add(sleeve);
  can.position.y = -Hc / 2;
  var pivot = new THREE.Group(); pivot.add(can); scene.add(pivot);

  function useImage() {
    var c = document.createElement('canvas');
    var max = renderer.capabilities.maxTextureSize || 4096;
    var s = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
    c.width = Math.round(img.naturalWidth * s); c.height = Math.round(img.naturalHeight * s);
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    var t = new THREE.CanvasTexture(c);
    t.encoding = THREE.sRGBEncoding;
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    labelMat.map = t; labelMat.needsUpdate = true;
  }
  if (img.complete && img.naturalWidth) { useImage(); }
  else {
    img.addEventListener('load', useImage);
    img.addEventListener('error', function () { showFallback('The label image could not be loaded.'); });
  }

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var TAU = Math.PI * 2;
  var angle = 0, target = 0;
  var spinning = !reduce && cfg.autoSpin;
  var spinBtn = document.getElementById('spin');
  function setSpin(on) { spinning = on; spinBtn.setAttribute('aria-pressed', on ? 'true' : 'false'); }

  // optional view from the URL hash, for screenshots: #u=0.42&spin=0
  var hash = {};
  location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
    var p = kv.split('=');
    if (p.length === 2 && /^[a-z]+$/.test(p[0]) && /^[0-9.]+$/.test(p[1])) { hash[p[0]] = parseFloat(p[1]); }
  });
  function angleFor(u) { return (0.5 - u) * TAU; }
  if (typeof hash.u === 'number' && hash.u >= 0 && hash.u <= 1) { target = angle = angleFor(hash.u); }
  if (hash.spin === 0) { spinning = false; }
  setSpin(spinning);

  function goTo(u) {
    var want = angleFor(u);
    var delta = ((want - target) % TAU + TAU * 1.5) % TAU - Math.PI;
    target += delta;
    if (reduce) { angle = target; }
  }
  Array.prototype.forEach.call(document.querySelectorAll('button[data-u]'), function (b) {
    b.addEventListener('click', function () { setSpin(false); goTo(cfg.views[b.getAttribute('data-u')]); });
  });
  spinBtn.addEventListener('click', function () { setSpin(!spinning); });

  var dragging = false, lastX = 0;
  stage.addEventListener('pointerdown', function (e) {
    dragging = true; lastX = e.clientX; setSpin(false);
    try { stage.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
  });
  stage.addEventListener('pointermove', function (e) {
    if (!dragging) { return; }
    target += (e.clientX - lastX) * 0.012; angle = target; lastX = e.clientX;
  });
  function endDrag() { dragging = false; }
  stage.addEventListener('pointerup', endDrag);
  stage.addEventListener('pointercancel', endDrag);
  stage.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') { setSpin(false); target -= 0.3; if (reduce) { angle = target; } e.preventDefault(); }
    if (e.key === 'ArrowRight') { setSpin(false); target += 0.3; if (reduce) { angle = target; } e.preventDefault(); }
  });

  function resize() {
    var w = stage.clientWidth || 600, h = stage.clientHeight || 500;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    var fitH = Hc * 1.12, fitW = cfg.can.diameter * 2.2;
    var vfov = camera.fov * Math.PI / 180;
    var dist = Math.max(fitH / 2 / Math.tan(vfov / 2), fitW / 2 / (Math.tan(vfov / 2) * camera.aspect));
    camera.position.set(0, Hc * 0.12, dist);
    camera.lookAt(0, Hc * 0.02, 0);
    camera.updateProjectionMatrix();
  }
  if (window.ResizeObserver) { new ResizeObserver(resize).observe(stage); } else { window.addEventListener('resize', resize); }
  resize();

  var last = performance.now();
  function frame(now) {
    var dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (spinning) { target += dt * 0.6; }
    angle += (target - angle) * (reduce ? 1 : Math.min(1, dt * 6));
    pivot.rotation.y = angle;
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
</script>
</body>
</html>
"""


def json_for_script(obj):
    return json.dumps(obj, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_preview(out_dir, spec, tpl, png_path=None, svg_text=None):
    """Write can_preview.html. Uses label.png when present, else the SVG."""
    if png_path and Path(png_path).is_file() and Path(png_path).stat().st_size <= MAX_EMBED_BYTES:
        img = "data:image/png;base64," + base64.b64encode(Path(png_path).read_bytes()).decode("ascii")
    elif svg_text is not None:
        img = "data:image/svg+xml;base64," + base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
    else:
        img = "label.png"
    cfg = {
        "title": f'{spec["beer"]["name"]}: 3D can preview',
        "can": {"diameter": tpl["can_diameter_mm"], "height": tpl["can_height_mm"], "label": tpl["label_height_mm"]},
        "views": {"front": 0.5, "left": 0.2, "right": 0.8, "back": 0.0},
        "autoSpin": True,
    }
    html = (PAGE.replace("__TITLE__", esc(cfg["title"]))
            .replace("__CONFIG__", json_for_script(cfg))
            .replace("__THREE_URL__", THREE_URL)
            .replace("__THREE_SRI__", THREE_SRI)
            .replace("__IMG__", esc(img)))
    out = Path(out_dir) / "can_preview.html"
    out.write_text(html, encoding="utf-8")
    return out
