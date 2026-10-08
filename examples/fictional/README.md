# Fictional example: Harbour Lantern

**Everything here is fictional:** the beer "Harbour Lantern", the brewery "Example Brewing Co.", the town "Sampletown", the rowing club, the address, the website (`brewing.example`, a reserved domain) and the lighthouse logo were invented for this example.

Brief used for the intake: a 4.6% vol session pale ale in a 330 ml sleek can (Hopera template), brewed for the 50th regatta of a rowing club. Mood: nautical and festive. Palette: navy and brass. Allergens: barley, wheat and oats.

| File | What it is |
|---|---|
| `spec.json` | The filled spec (roundel with ring text, sunburst, zigzag bands, waves) |
| `logo.svg` | Fictional lighthouse logo, embedded through the SVG sanitizer |
| `label.svg` | Vector artwork, 2078 x 1368 |
| `label.html` | The SVG with its web fonts, used for rendering |
| `label.png` | Rendered at 2078 x 1368 px with headless Chrome |
| `can_preview.html` | Self-contained 3D preview (open it in a browser) |

Rebuild from the repository root:

```bash
python3 scripts/build_label.py examples/fictional/spec.json -o examples/fictional/
python3 scripts/check_label.py examples/fictional/spec.json examples/fictional/label.svg
```
