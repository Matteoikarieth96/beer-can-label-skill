# Security

## Threat model

The skill turns user-supplied content into files that are opened in browsers and print software:

- **Spec text** (beer name, story, producer, ingredients, ring text) could carry markup meant to break out of SVG or HTML (`</text><script>`, quotes, `&`).
- **Logo files** are untrusted. SVG can contain scripts, event handlers, `foreignObject` HTML, external references that fetch URLs, and XML entity declarations (billion laughs, external entities). Raster files can be mislabelled.
- **File paths** in the spec could point outside the project (`../../etc/passwd`, absolute paths, symlinks).
- **Font names** end up in CSS and in Google Fonts URLs.
- **Headless Chrome** renders the pages; a careless invocation could use the user's profile or a shell.
- **The 3D preview** loads a third-party script from a CDN.
- **Instructions hidden in inputs** (for example text inside a logo or a brief) are data, not commands.

## Mitigations (where they live)

| Risk | Mitigation | File |
|---|---|---|
| Markup injection in SVG/HTML | Every text value goes through `html.escape(..., quote=True)`; colours, numbers and motif names are validated, so no raw user text reaches attributes | `scripts/labelkit/safety.py` (`esc`), `scripts/labelkit/compose.py`, `scripts/labelkit/spec.py` |
| Injection in the 3D page | User text is written with `textContent`; configuration travels in `<script type="application/json">` with `<`, `>` and `&` escaped; the URL hash is parsed with a whitelist (`u`, `spin`, numbers only) | `scripts/labelkit/preview.py` |
| Malicious SVG logos | `<!DOCTYPE` / `<!ENTITY` refused before parsing; non-SVG roots refused; whitelist of drawing elements (script, foreignObject, animation, `a`, `feImage`, metadata dropped); `on*` attributes dropped; `href`/`xlink:href` kept only for `#internal` ids (and `data:image/png|jpeg` on `<image>`); `url(...)` to anything but `#id`, `javascript:`, `vbscript:`, `expression()`, `@import` removed; editor namespaces removed | `scripts/labelkit/safety.py` (`sanitize_svg`) |
| Defence in depth for logos | Sanitized SVG is embedded as an `<image>` data URI, never inlined, so it renders in the browser's static image mode (no script, no external loads) | `scripts/labelkit/compose.py` |
| Mislabelled or huge rasters | PNG/JPEG magic bytes checked, 5 MB cap, dimension sanity check | `scripts/labelkit/safety.py` (`load_logo`) |
| Path traversal | Logo paths resolved (symlinks included) and required to stay inside the spec folder; output folders must be inside the spec folder or the current directory | `scripts/labelkit/safety.py` (`resolve_inside`, `ensure_output_dir`), `scripts/build_label.py`, `scripts/snapshot_can.py` |
| CSS / URL injection via fonts | Family names must match `^[A-Za-z0-9 ]{1,40}$`; weights are integers 100 to 900 | `scripts/labelkit/spec.py` |
| Oversized or hostile inputs | Spec JSON capped at 256 KB, unknown keys rejected, text lengths capped, control characters rejected; the QA refuses SVGs with DOCTYPE/ENTITY and files over 40 MB | `scripts/labelkit/spec.py`, `scripts/check_label.py` |
| Chrome invocation | Argument lists only (no shell), throwaway `--user-data-dir`, no extensions, no first-run, background networking disabled, timeouts and forced termination | `scripts/labelkit/chrome.py` |
| CDN script | three.js pinned to r128 on cdnjs with a Subresource Integrity hash and `crossorigin="anonymous"`; if it does not load, the page shows the flat label | `scripts/labelkit/preview.py` |
| Publishing | Nothing is published or uploaded by the scripts. The skill offers a private Artifact only when the host has one, and never uploads to Hopera for the user | `SKILL.md` |

Tests for these cases are in `tests/test_label.py` (escaping, malicious SVG, entities, path traversal, symlinks, bad font names, raster checks, output folder containment).

## Residual risks

- Rendering requests the two font stylesheets and files from Google Fonts, and opening `label.svg` in a browser does too (the SVG `@import`s them). This reveals your IP address and the font names to Google. Font CSS cannot be pinned with SRI.
- The 3D preview requests three.js from cdnjs (SRI-protected) and sends no data.
- Chrome's image and SVG decoders still parse the user's logo files. Keep Chrome up to date.
- The SVG sanitizer is a whitelist, but SVG is large. It is backed by the image-mode embedding; do not reuse `sanitize_svg` output to inline SVG elsewhere.
- The QA is heuristic and cannot detect every legibility or legal problem.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**. Do not open a public issue for security problems.
