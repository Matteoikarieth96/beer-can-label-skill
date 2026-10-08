# Hopera can template (default preset `hopera-sleek-330`)

> **Verify with Hopera before printing.** These facts come from earlier label work and from Hopera's public previewer page (checked 2026-10-08). Hopera can change its template, its can format or its print process at any time. This project is independent and is not affiliated with or endorsed by Hopera.

Hopera is an Italian craft beer service with a web3 angle. Its public 3D label previewer is at <https://hopera.xyz/labelPreview>: the page has an "Add your design" section and states a recommended minimum image resolution of 1039 x 684 px.

## Template facts

| Item | Value |
|---|---|
| Can | 330 ml **sleek** can, diameter 58 mm (can height about 146 mm) |
| Printable label band | about 120 mm tall, full wrap |
| Minimum file size | 1039 x 684 px (ratio about 1.52) |
| Render size used by this skill | 2x: **2078 x 1368 px** |
| Wrap ratio check | circumference / band height = pi x 58 / 120 = 1.518, matches 1039 / 684 = 1.519 |
| Pixels per mm at 2x | 1368 / 120 = **11.4 px/mm** |
| Front of the can | the horizontal centre of the image (x = 1039 at 2x) |
| Back seam | the left and right edges of the image meet there |
| Seam safe zone used here | 3% of the width at each edge (62 px, about 5.5 mm) |

## What Hopera-style labels typically carry

Seen on Hopera cans; use as a starting point, not as a legal list (see `labelling-checklist.md`):

- A vertical producer line along one side: "Produced and bottled by: <brewery, town, postcode, province>" (Italian: "Prodotta e confezionata da: ..."). The name and address come from intake, never from this repo.
- An ingredients line with allergens emphasised (bold, uppercase).
- "Distributed by" plus the distributor's logo. The skill leaves a **dashed placeholder box**: the distributor supplies its official logo file. Never download, redraw or trace a third-party logo.
- A recycling box, for example "Can | ALU 41 | Aluminium, metal collection" with "Check your local collection rules" (Italian: "Lattina | ALU 41 | Alluminio, raccolta metalli", "Verifica le disposizioni del tuo Comune").
- An **empty BEST BEFORE box**: the date and the lot are printed later on the filling line.
- Volume, alcohol by volume, beer style.

## Upload steps (the user does this, not Claude)

1. Build and pass QA: `check_label.py` must report 0 errors.
2. Open <https://hopera.xyz/labelPreview> in a browser.
3. In "Add your design", choose `label.png` (2078 x 1368 px). Do not upload the SVG or the HTML there.
4. Rotate the 3D can: the beer name should face you at the start, the producer strip and the panels should read when you turn the can, and the back seam should not cut any text.
5. Compare with `can_preview.html` from this skill; small differences in curvature and colour are normal.
6. Send the final files to Hopera through the channel they gave you (usually `label.png` at 2x plus `label.svg`). Ask them:
   - colour profile and file format they want for print (RGB PNG, CMYK PDF, ...);
   - whether fonts must be converted to outlines (the SVG references Google Fonts);
   - bleed and exact band height for the current can batch;
   - white underprint and metallic ink options;
   - who prints the best-before date and lot, and where.

Claude never uploads files to Hopera or submits forms for the user: those are the user's actions.
