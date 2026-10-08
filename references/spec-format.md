# spec.json format

Start from `templates/spec.template.json`. Unknown keys are errors (they catch typos). Text fields are plain text: the builder escapes everything, so never put markup in them. Put `TBC` in any value that is not confirmed yet: build and QA list it as an open placeholder.

| Key | Type | Notes |
|---|---|---|
| `template.preset` | `hopera-sleek-330` or `custom` | Hopera: 1039 x 684 px base, 58 mm can, 120 mm band |
| `template.scale` | 1, 2, 3 | Hopera only; default 2 (2078 x 1368 px) |
| `template.width_px`, `height_px`, `can_diameter_mm`, `label_height_mm`, `can_height_mm`, `distributor_box` | numbers, bool | `custom` only. The width should be about `pi x diameter / label height x height_px` (warning if more than 2% off) |
| `language` | `en` or `it` | Picks the built-in strings (producer line, best before, recycling, decimal comma, "Birra") |
| `strings.<key>` | text | Override any built-in string: `produced_by`, `ingredients`, `contains`, `distributed_by`, `distributor_placeholder`, `distributor_hint`, `best_before`, `lot`, `recycling_item`, `recycling_code`, `recycling_material`, `recycling_note`, `denomination`, `alc_prefix`, `decimal`. Use this for bilingual labels ("Ingredienti / Ingredients:") |
| `beer.name` | text, required | Max 60 chars. Front hero, uppercase unless `design.name_case` is `as-is` |
| `beer.name_lines` | list of text | Manual line breaks for the name (max 3) |
| `beer.tagline` | text | One line under the name |
| `beer.style` | text, required | "Session Pale Ale" |
| `beer.denomination` | text | Prefix to the style; default "" (en) or "Birra" (it) |
| `beer.abv` | number 0 to 20, required | Rendered with one decimal |
| `beer.volume_ml` | number, required | 330 default |
| `beer.volume_unit` | `ml` or `cl` | |
| `beer.e_mark` | bool | Adds the estimated sign after the volume |
| `producer.name`, `producer.address` | text, required | Vertical strip: "<produced_by> name, address" |
| `producer.website` | text | Printed as text on the left panel (never a link) |
| `ingredients` | list of `{"text", "allergen"}` or text | Allergens render bold uppercase |
| `allergen_statement` | text | "barley, wheat (gluten)": rendered "Contains: BARLEY, WHEAT (GLUTEN)." |
| `story` | list of paragraphs | Left panel, max 6 x 600 chars |
| `claims` | list of short text | Joined as sentences ("Unfiltered. Unpasteurised.") |
| `notes` | list of text | Storage, serving |
| `distributor.show` | bool | Default true on the Hopera preset |
| `distributor.logo` | path | Only a file the distributor supplied; else the dashed placeholder stays |
| `recycling.item`, `code`, `material`, `note` | text | Defaults from the language |
| `best_before.show` | bool | Keep true for beer under 10% vol |
| `design.palette` | preset name or object | Presets: `midnight-brass`, `forest-cream`, `hazy-gold`, `arctic-ink`, `coral-sunset`, `stout-copper`. Object: `base` preset + any of `bg`, `bg2`, `primary`, `secondary`, `text`, `muted`, `panel` as `#rrggbb` |
| `design.fonts.display`, `design.fonts.body` | `{"family", "weights", "width"}` or a family name | Google Fonts family, `^[A-Za-z0-9 ]{1,40}$`. `weights` must exist for that family (e.g. Bebas Neue only has `[400]`). `width` 0.5 to 1.5 tunes wrap estimates (condensed about 0.8) |
| `design.motifs` | list | See `design-guide.md` section 6. One per role |
| `design.logo.path` | path | SVG, PNG or JPEG inside the spec folder, max 5 MB |
| `design.logo.size_mm` | number | 0 = automatic |
| `design.metallic` | bool | Gradient "metal" fill for name, frame and primary accents |
| `design.panel_backdrop` | bool | Solid panels behind side text; default on with scenery motifs |
| `design.grain` | bool | Subtle noise; makes the PNG much larger |
| `design.name_case` | `upper` or `as-is` | |
| `layout.producer_strip` | `left` or `right` | Which edge carries the vertical producer line |
| `layout.seam_safe_pct` | 1 to 10 | Default 3 |
| `layout.margin_mm` | 1 to 15 | Top and bottom text margin, default 4 |
| `layout.legal_font_mm` | 1.5 to 6 | Raised to the legal minimum if lower |
| `layout.body_font_mm` | 1.5 to 6 | Story text |
| `qa.min_x_height_mm` | number | Default 1.2 |
| `qa.x_height_ratio` | number | x-height / font size of the body font, default 0.5 |
