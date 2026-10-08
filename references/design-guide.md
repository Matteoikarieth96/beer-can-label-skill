# Design guide: full-wrap can labels

## 1. Wrap geometry

```
 x = 0                     W/3              W/2              2W/3                   x = W
 | seam |strip| LEFT PANEL  |      FRONT (middle third)      | RIGHT PANEL  | seam |
 | 3 %  |     | story,      |  emblem / frame                | distributor, | 3 %  |
 |      |     | ingredients,|  NAME                          | recycling,   |      |
 |      |     | claims      |  style, volume . ABV           | best before  |      |
 <- back seam                         front of the can                      back seam ->
```

- The image is the whole circumference. **The horizontal centre is the front**; the left and right edges meet at the **back seam**.
- At the Hopera size (2078 x 1368 px for a 120 mm band) the scale is **11.4 px per mm**. In general: `px_per_mm = height_px / label_height_mm`.
- The middle third spans plus or minus 60 degrees around the can. Seen straight on, it covers about 87% of the visible width (projection `r x sin 60`). Everything outside it is foreshortened fast: between 60 and 90 degrees only 13% of the visible width remains.
- **Front third**: name, emblem, style, volume and ABV. EU rules want the name, the net quantity and the alcohol strength in the same field of vision, so keep all three in the front third.
- **Side panels**: read when the can is turned. Left: story, ingredients and allergens, claims, notes. Right: "Distributed by" box, recycling table, best-before box.
- **Back seam safe zone**: no text within 3% of the width of either edge (62 px or about 5.5 mm at Hopera size). The seam is glued or overlapped and can drift by a few millimetres.
- **Top and bottom margins**: no text within 4 mm of the top or bottom edge of the band. Decorative bands and backgrounds may bleed to the edge.
- **Patterns across the seam**: anything that crosses the seam must repeat with a period that divides the width. The built-in Greek key, zigzag, waves and mountains do this automatically; the radial background is centred on the front so both edges match.

## 2. Curvature

A horizontal line of text at angle `a` from the viewer is compressed by `cos a`: 71% at 45 degrees, 50% at 60 degrees. So:

- Keep the name inside the front third (the builder caps it at `W/3 - 2 mm`).
- Long legal lines belong on the side panels, where the reader turns the can, or in a **vertical strip**: text running along the can axis is not distorted by the curvature, which is why the producer line is vertical.
- Avoid thin horizontal rules that span the whole wrap behind text: they bend visually.

## 3. Text size

| Text | Minimum | At Hopera 2x |
|---|---|---|
| Mandatory particulars (producer, ingredients, allergens, ABV, recycling, best-before label) | x-height 1.2 mm (Reg. 1169/2011 Art. 13(2); the 0.9 mm exception is for packs whose largest surface is under 80 cm2, a 330 ml wrap is about 218 cm2) | font size 2.4 mm = 27.4 px with `x_height_ratio` 0.5 |
| Net volume figures | 4 mm high for 200 ml to 1 l (Directive 76/211/EEC, see the checklist) | font about 5.7 mm = 65 px |
| Body text (story) | 2.2 mm font, 2.8 mm preferred | 25 to 32 px |
| Anything else | 1.8 mm font (QA warns below) | 20.5 px |

The x-height of a font is 0.45 to 0.55 of its font size. If the chosen body font has a small x-height, lower `qa.x_height_ratio` (e.g. 0.46) so the QA asks for bigger text. Condensed body fonts (IBM Plex Sans Condensed, Roboto Condensed, Barlow Condensed) fit more legal text at the same height; set `design.fonts.body.width` (about 0.85) so the line wrapping estimates match.

## 4. Contrast and legibility

- Aim for WCAG 4.5:1 for small text and 3:1 for large text (6.35 mm, or 4.94 mm bold). Print loses contrast compared with a screen, so treat these as floors.
- Legal text: one solid colour, no gradient or metallic fill, no busy texture behind it. With scenery motifs (waves, mountains) the builder puts a solid backdrop behind the side panels (`design.panel_backdrop`).
- Emphasise allergens with weight (bold) and case (uppercase). Colour alone is not enough.
- Left-aligned paragraphs, line height 1.3 or more, no justified text, no hairline weights under 3 mm.

## 5. Colour, gradients and metallic inks

- The metallic look on screen is a vertical gradient (`url(#metal)`) derived from the primary colour. In print, ask the printer for a metallic ink (for example a Pantone metallic) or for areas with **no white underprint** so the aluminium shows through.
- White underprint: on aluminium, colours without a white base turn darker and more transparent. Ask whether the printer applies a full white base or a selective one.
- Gradients print well when they span enough values; avoid long, very subtle gradients (banding).
- Keep a palette of 5 to 7 roles: `bg`, `bg2`, `primary`, `secondary`, `text`, `muted`, `panel`. Built-in palettes: `midnight-brass`, `forest-cream`, `hazy-gold`, `arctic-ink`, `coral-sunset`, `stout-copper` (all pass 4.5:1 for text, muted and primary).

## 6. Motif library

| Motif | Role | Parameters (defaults) |
|---|---|---|
| `sunburst` | background rays from the emblem | `color` (primary), `rays` 12 to 120 (40), `opacity` (0.08), `reach` x label height (0.8) |
| `laurel` | frame around the emblem | `color` (primary), `leaves` 6 to 18 (12), `berries` (true) |
| `roundel` | frame: double ring with ring text and stars | `color` (primary), `ring_text` (up to 80 chars), `stars` 0 to 9 (3) |
| `hop` | emblem when there is no logo | `color` (secondary; try a green such as #6b8f3a), `leaf_color` (primary) |
| `greek-key` | top and bottom bands | `color` (primary), `height_mm` 3 to 10 (5.5) |
| `zigzag` | top and bottom bands | `color` (primary), `height_mm` (5), `lines` 1 to 3 (2) |
| `waves` | scenery along the bottom | `color` (secondary), `layers` 1 to 5 (3), `height_pct` (14), `opacity` (0.35), `amplitude_mm` (2.2), `period_mm` (26) |
| `mountains` | scenery along the bottom | `color` (secondary), `layers` 1 to 4 (3), `height_pct` (18), `opacity` (0.4), `peaks` (9), `seed` (7), `snow` (false) |

One motif per role. Colours accept a palette role name or `#rrggbb`. Without a logo and without `hop`, the emblem is a monogram of the beer's first letter.

## 7. Concept directions (step 2 of the skill)

Describe two or three directions in words before building. Each direction names: the mood in one line, the palette, the two fonts, the motifs, and what goes in the emblem. Examples:

- **Harbour classic**: navy and brass, Playfair Display + IBM Plex Sans Condensed, roundel with the club's name, waves along the bottom, zigzag bands.
- **Alpine morning**: cream and coral, Bebas Neue + Inter, hop cone emblem, Greek key bands, snowy mountains.
- **Night shift stout**: dark brown and copper, Oswald + Inter, roundel with monogram, single zigzag.

## 8. Logos

- Prefer SVG. SVG logos are sanitized (scripts, `<style>` blocks, embedded bitmaps, event handlers, external references and entities removed or refused) and embedded as an image, so their own fonts must be converted to outlines and their colours set with presentation attributes (`fill="#c8553d"`, `fill="url(#gradient)"`), not CSS.
- PNG/JPEG: at least 600 px on the long side for a 35 mm emblem at 2x.
- Third-party logos (distributor, certification marks, recycling marks) come from their owner. The builder leaves a dashed placeholder box for the distributor.

## 9. Before you call it done

Run `check_label.py`, then look at the flat PNG and turn the 3D can: the name faces you at the start, the side panels read when turned, nothing important is cut at the back seam, and the best-before box has room for an inkjet date and lot (30 x 12 mm or more).
