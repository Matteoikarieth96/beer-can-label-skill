# Intake questions

Ask in the user's language. Skip anything already answered in the request or in attached files. Use `AskUserQuestion` when available (at most 4 questions per call, 2 to 4 options each, recommended option first with "(Recommended)" in its label; the user can always type "Other"), otherwise a numbered plain-text list. At most 2 rounds before showing progress: round 1 is the essentials, round 2 only fills real gaps.

Anything still unknown after intake goes into the spec with `TBC` in the value. The build and the QA list every `TBC` as an open placeholder, and the final message repeats them.

## Round 1: the essentials

| # | Question | Why it matters | Default if skipped |
|---|---|---|---|
| 1 | **Beer name and style** (e.g. "Harbour Lantern, Session Pale Ale") | The name is the hero of the front; the style is a mandatory-looking line and drives the mood | Ask again: the name cannot be invented. Style: `TBC` |
| 2 | **ABV and volume** | Mandatory on the front, in the same field of vision as the name | Volume 330 ml (sleek can). ABV: `TBC`, rendered as a placeholder |
| 3 | **Who is it for, the occasion, the mood** (a club anniversary, a wedding, a taproom launch; festive, elegant, playful, rugged) | Picks the concept directions, motifs and palette | "Friendly craft beer, no special occasion" |
| 4 | **Colours and fonts**: brand colours (hex if known) and fonts, or "surprise me" | Palette and two Google Fonts | "Surprise me": Claude proposes palettes in the concept step |

## Round 2: content and production (only what is missing)

| # | Question | Why it matters | Default if skipped |
|---|---|---|---|
| 5 | **Logo files**: paths to SVG or PNG/JPEG (max 5 MB, inside the project folder) | Placed in the front emblem; SVGs are sanitized and embedded as images | No logo: a hop cone, a monogram or a frame motif |
| 6 | **Imagery motif** (laurel, sunburst, waves, mountains, hop cone, Greek key, zigzag, roundel with ring text, or an idea in words) | The visual identity | Chosen with the concept direction |
| 7 | **Required text**: producer name and full address (as on the brewery's documents), ingredients, which ones are allergens, any extra claims ("unfiltered", "gluten-free" ...) | Mandatory particulars; allergens must be emphasised | Producer: `TBC`. Ingredients: water, **barley malt**, hops, yeast marked `TBC` |
| 8 | **Label language(s)** | In Italy the mandatory text must be in Italian; other markets have their own rules | Same language as the user; Italian if the beer is sold in Italy |
| 9 | **Template**: Hopera (default) or custom (width x height px, can diameter, label height in mm) | Fixes the pixel size, the wrap ratio and the 3D can | Hopera 330 ml sleek, 2078 x 1368 px |
| 10 | **Print notes**: metallic ink? white underprint? bare aluminium areas? | Changes how the colours and metallic effects should be designed | Normal four-colour print on a white base; metallic simulated with gradients |
| 11 | **Deliverables**: PNG + SVG + 3D preview (default), a shareable page, extra sizes | What to hand over at the end | PNG at 2x, SVG, `can_preview.html`; an Artifact (private) if the host has one |

## Summary before building

End intake with a short summary and wait for a "yes" before the concept and build steps, for example:

> Here is what I will build: a 330 ml sleek can label for **Harbour Lantern** (Session Pale Ale, 4.6% vol) for the Sampletown Rowing Club's 50th regatta. Mood: nautical and festive. Palette: navy and brass, or a surprise. Logo: `logo.svg`. Text in English. Open: producer address (TBC). Hopera template, 2078 x 1368 px. OK to continue?

## Things never to invent

- The producer's name and address, lot or date: they come from the user or stay `TBC`.
- Allergens: ask which ingredients contain gluten or other Annex II allergens; never remove one to make the text fit.
- Third-party logos (distributor, certifications): the owner supplies the file. Leave the placeholder box.
