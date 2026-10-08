# Security

## Threat model

The skill turns user-supplied content into files that are opened in browsers and print software:

- **Spec text** (beer name, story, producer, ingredients, ring text) could carry markup meant to break out of SVG or HTML (`</text><script>`, quotes, `&`), or line breaks and characters that make the SVG invalid or control whole lines of an output file.
- **Logo files** are untrusted. SVG can contain scripts, event handlers, `foreignObject` HTML, CSS that fetches URLs (`@import`, `url()`, CSS escapes such as `@\69mport`, `image-set()`), `xml:base`, nested rasters, deep nesting, XML entity declarations (billion laughs, external entities) and non-UTF-8 encodings. Raster files can be mislabelled or carry misleading headers.
- **File paths** in the spec could point outside the project (`../../etc/passwd`, absolute paths, symlinks), and an attacker with write access to the output folder could pre-place symlinks so that our writes land elsewhere.
- **Font names** end up in CSS and in Google Fonts URLs.
- **Headless Chrome** renders the pages; a careless invocation could use the user's profile or a shell.
- **The 3D preview** loads a third-party script from a CDN.
- **Instructions hidden in inputs** (for example text inside a logo or a brief) are data, not commands.

## Mitigations (where they live)

| Risk | Mitigation | File |
|---|---|---|
| Markup injection in SVG/HTML | Every text value goes through `html.escape(..., quote=True)`; colours, numbers and motif names are validated, so no raw user text reaches attributes | `scripts/labelkit/safety.py` (`esc`), `scripts/labelkit/compose.py`, `scripts/labelkit/spec.py` |
| Line breaks and bad characters in text | Every spec text field is one line: CR, LF, tab, other C0/C1 controls, DEL, unpaired surrogates and characters XML 1.0 forbids (U+FFFE, U+FFFF) are rejected at validation; paragraphs are list items. Wrong container types are reported as spec problems, not crashes | `scripts/labelkit/safety.py` (`text_problem`), `scripts/labelkit/spec.py`, `scripts/labelkit/motifs.py` |
| Writes through planted symlinks | All outputs go through `atomic_write`: it refuses a symlink target (dangling ones too), writes a new temp file in the same folder (`mkstemp`, O_EXCL) and `os.replace`s it, which replaces a link instead of following it. The build refuses to start if any output name is a symlink. Chrome writes its screenshot into a fresh private `mkdtemp` folder and the PNG is then installed with `atomic_write`; there is no predictable temp name in the output folder | `scripts/labelkit/safety.py` (`atomic_write`, `refuse_symlinks`), `scripts/labelkit/chrome.py`, `scripts/labelkit/preview.py`, `scripts/build_label.py`, `scripts/snapshot_can.py` |
| Injection in the 3D page | User text is written with `textContent`; configuration travels in `<script type="application/json">` with `<`, `>` and `&` escaped; the page template is filled in a single regex pass, so a value cannot inject another placeholder; the URL hash is parsed with a whitelist (`u`, `spin`, numbers only) | `scripts/labelkit/preview.py` |
| Hostile XML (logos and the QA input) | `parse_xml`: NUL bytes refused (so BOM-less UTF-16 cannot pass as UTF-8), UTF-8 only, `<!DOCTYPE` / `<!ENTITY` and non-UTF-8 encoding declarations refused in the text, and again by expat handlers (doctype, entity, external entity) with the encoding forced to UTF-8; nesting deeper than 64 levels refused | `scripts/labelkit/safety.py` (`parse_xml`), `scripts/check_label.py` |
| Malicious SVG logos | Whitelist of drawing elements: `script`, `style`, `image`, `foreignObject`, animation, `a`, `feImage`, metadata are dropped; `on*` attributes dropped; `xml:` attributes other than `xml:space`/`xml:lang` (so `xml:base`) dropped; `href`/`xlink:href` kept only for `#internal` ids; any attribute value with a backslash (CSS escapes), `url()` to anything but `#id`, `@import`, `image-set()`, `image()`, `src()`, `expression`, `-moz-binding`, `behavior`, `data:` or script URLs is dropped; `style` attributes are dropped if they contain `@`, `url(` or any of those. Every removal is reported in the build log so the user is told | `scripts/labelkit/safety.py` (`sanitize_svg`) |
| Defence in depth for logos | Sanitized SVG is embedded as an `<image>` data URI, never inlined, so it renders in the browser's static image mode (no script, no external loads) | `scripts/labelkit/compose.py` |
| Mislabelled or huge rasters | PNG/JPEG magic bytes checked, 5 MB cap, 12000 px per side. JPEG markers are walked like libjpeg (0xFF fill bytes skipped, standalone markers without length, scan data skipped) and every frame header must be within the cap. Nested rasters inside SVG logos are removed | `scripts/labelkit/safety.py` (`load_logo`, `_jpeg_size`) |
| Path traversal | Logo paths resolved (symlinks included) and required to stay inside the spec folder; output folders must be inside the spec folder or the current directory | `scripts/labelkit/safety.py` (`resolve_inside`, `ensure_output_dir`), `scripts/build_label.py`, `scripts/snapshot_can.py` |
| CSS / URL injection via fonts and colours | Family names must fully match `[A-Za-z0-9 ]{1,40}` (`fullmatch`, so a trailing newline fails); weights are integers 100 to 900; colours must fully match `#rrggbb` | `scripts/labelkit/spec.py`, `scripts/labelkit/colors.py` |
| Forged log lines | The "web fonts did not load" warning is read from the parsed root `<svg>` attribute only, never by searching the SVG text, so label text cannot print a fake warning | `scripts/build_label.py` (`fonts_missing_warning`) |
| Oversized or hostile inputs | Spec JSON capped at 256 KB, unknown keys rejected, text lengths capped; the QA uses `parse_xml` and refuses files over 40 MB | `scripts/labelkit/spec.py`, `scripts/check_label.py` |
| Chrome invocation | Argument lists only (no shell), throwaway `--user-data-dir`, no extensions, no first-run, background networking disabled, timeouts and forced termination. The PNG render runs with `--disable-gpu`; the SwiftShader flags (`--use-angle=swiftshader --enable-unsafe-swiftshader`) are used only by `snapshot_can.py` for the 3D view, which loads the generated preview and three.js from cdnjs | `scripts/labelkit/chrome.py` |
| CDN script | three.js pinned to r128 on cdnjs with a Subresource Integrity hash and `crossorigin="anonymous"`; if it does not load, the page shows the flat label | `scripts/labelkit/preview.py` |
| Instructions inside inputs | SKILL.md tells Claude that briefs, documents, logos and pages are data: quote embedded instructions to the user instead of following them | `SKILL.md` |
| Publishing | Nothing is published or uploaded by the scripts. The skill offers a private Artifact only when the host has one, and never uploads to Hopera for the user | `SKILL.md` |

Tests for these cases are in `tests/test_label.py` (escaping, malicious SVG, entities, path traversal, symlinks, bad font names, raster checks, output folder containment) and `tests/test_security_regressions.py` (symlinked and dangling outputs, a fake Chrome that proves screenshots never land in the output folder, each SVG sanitizer bypass, BOM-less UTF-16, deep nesting, bad characters, JPEG fill bytes and multiple frames, forged warnings, full-match regexes, single-pass templating).

## Residual risks

- Rendering requests the two font stylesheets and files from Google Fonts, and opening `label.svg` in a browser does too (the SVG `@import`s them). This reveals your IP address and the font names to Google. Font CSS cannot be pinned with SRI.
- The 3D preview requests three.js from cdnjs (SRI-protected) and sends no data.
- Chrome's image and SVG decoders still parse the user's logo files. Keep Chrome up to date.
- The SVG sanitizer is a whitelist, but SVG is large. It is backed by the image-mode embedding; do not reuse `sanitize_svg` output to inline SVG elsewhere. It is strict on purpose: logos that rely on `<style>` blocks, `style="fill:url(#g)"` or embedded bitmaps lose those parts (the build log lists every removal); re-export them with presentation attributes.
- `snapshot_can.py` enables SwiftShader (software WebGL) in a throwaway headless profile to draw the 3D can; it only loads the generated preview page and the SRI-pinned three.js.
- `atomic_write` protects files we create, but someone who controls the output folder can still delete or swap our results after the build: keep outputs in a folder only you can write.
- The QA is heuristic and cannot detect every legibility or legal problem.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**. Do not open a public issue for security problems.
