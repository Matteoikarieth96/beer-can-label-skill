# Labelling checklist for beer cans (EU, with Italian specifics)

> **Not legal advice. Confirm every mandatory particular with your producer (the food business operator responsible for the label) and, if in doubt, with a food-law consultant or your Chamber of Commerce.** Rules change; this list was compiled on 2026-10-08. The skill helps lay the text out; it does not make a label compliant.

Status column: **S** = checked against a secondary source on 2026-10-08 (guides from Chambers of Commerce, certification bodies, legal summaries); **K** = from general knowledge of the primary text, not re-read in this session. Nothing here was checked against the official text line by line: read the regulation itself before printing.

## EU: Regulation (EU) No 1169/2011 on food information to consumers

| Item | What to put on the can | Rule | Skill | Status |
|---|---|---|---|---|
| Name of the food | Legal, customary or descriptive name. In Italy the sales name is "birra" with its qualifiers | Art. 9(1)(a), Art. 17 | `beer.denomination` + `beer.style` on the front (Italian default "Birra") | K |
| Alcohol by volume | For beverages over 1.2% vol: figure with at most one decimal, then "% vol", optionally preceded by "alcohol" or "alc." Tolerance for beer: plus or minus 0.5% vol up to 5.5% vol, plus or minus 1% vol above | Art. 9(1)(k), Annex XII | `alc. 4.6% vol` on the front; QA checks the format | K |
| Net quantity | In millilitres or centilitres | Art. 9(1)(e), Art. 23, Annex IX | `330 ml` or `33 cl` on the front | K |
| Same field of vision | Name, net quantity and alcohol strength must be visible together | Art. 13(5) | All three in the front third; QA errors if one is outside the middle half | K |
| Allergens | Annex II cereals containing gluten: wheat (incl. spelt, khorasan), rye, barley, oats. Emphasised in the ingredients list (font, style or background); without a list: "Contains: ..." | Art. 9(1)(c), Art. 21, Annex II | `allergen: true` renders bold uppercase; QA errors on un-emphasised allergen words (EN and IT) | S |
| List of ingredients | **Not mandatory** for beverages over 1.2% vol, but allergens still are. Many brewers list ingredients voluntarily (EU brewers' self-commitment). Alcohol-free beer is not exempt | Art. 16(4) | Ingredients list optional, `allergen_statement` for "Contains:" | S |
| Nutrition declaration | Not mandatory over 1.2% vol (energy often given voluntarily). Sources disagree on details: check | Art. 16(4) | Not generated; add as a note if wanted | S (sources disagree) |
| Food business operator | Name or business name and address of the operator under whose name the food is marketed | Art. 8, Art. 9(1)(h) | Vertical producer strip | K |
| Date of minimum durability | "Best before ..." (day included) or "Best before end ..." (month or year). Not required for beverages with 10% vol or more | Art. 9(1)(f), Art. 24, Annex X | Empty best-before box, date printed later | K |
| Storage conditions | When needed, e.g. "Store in a cool, dark place" | Art. 9(1)(g), Art. 25 | `notes` | K |
| Minimum text size | x-height of at least 1.2 mm (0.9 mm only if the largest surface is under 80 cm2) | Art. 13(2) and (3), Annex IV | QA: mandatory text font size at least `min_x_height_mm / x_height_ratio` | K |
| Language | Easily understood by consumers where sold; Member States may require their language | Art. 15 | `language`: `en` or `it` built in, `strings` to override | S |

Source: <https://eur-lex.europa.eu/eli/reg/2011/1169/oj>

## EU: other rules

| Item | Rule | Skill | Status |
|---|---|---|---|
| Lot | Directive 2011/91/EU: lot indication, preceded by "L" unless clearly distinguishable. It can be omitted when the best-before date gives at least day and month, uncoded | Best-before box has a "Lot:" line, printed later | K |
| Net quantity figures height | Directive 76/211/EEC (prepackages): figures at least 4 mm high from over 200 ml up to 1 l (3 mm up to 200 ml, 6 mm over 1 l). The e-mark is optional | Volume at about 6 mm font; QA warns under 4 mm figures; `beer.e_mark` adds the sign | S |
| Packaging material codes | Commission Decision 97/129/EC: aluminium = ALU 41 | Recycling table | S |
| "Gluten-free" claim | Implementing Regulation (EU) 828/2014: at most 20 mg/kg gluten | Only if the user supplies lab results; never added by default | K |
| Harmonised packaging labels | Regulation (EU) 2025/40 (PPWR) applies from 12 August 2026; harmonised material-sorting labels are expected from 12 August 2028 and will change national schemes such as the Italian one | Note for future reprints | S (secondary, dates to confirm) |

Sources: <https://eur-lex.europa.eu/eli/dir/2011/91/oj>, <https://eur-lex.europa.eu/eli/dir/1976/211/oj>, <https://eur-lex.europa.eu/eli/dec/1997/129/oj>, <https://eur-lex.europa.eu/eli/reg_impl/2014/828/oj>, <https://eur-lex.europa.eu/eli/reg/2025/40/oj>

## Italy

| Item | What it means for the can | Rule | Skill | Status |
|---|---|---|---|---|
| Italian language | Mandatory particulars in Italian for products sold in Italy (other languages may be added). Sanctions under D.Lgs. 231/2017; an ICQRF note of 10 May 2018 covers labels not in Italian | Reg. 1169/2011 Art. 15; D.Lgs. 231/2017 | `"language": "it"` | S |
| Producer and plant | Italian beer law asks for the producer and the plant site; D.Lgs. 145/2017 requires the address of the production or packaging plant for foods made in Italy | L. 1354/1962; D.Lgs. 145/2017 | "Prodotta e confezionata da: <birrificio, via, CAP, comune (PR)>" in the vertical strip | S (L. 1354/1962), K (D.Lgs. 145/2017, check it is still applied) |
| Environmental labelling of packaging | All packaging labelled with the material code (Decision 97/129/EC, e.g. **ALU 41**) and, for consumer packaging, the collection stream (e.g. "Raccolta metalli"). In force from 1 January 2023 after postponements. "Verifica le disposizioni del tuo Comune" is recommended by the guidelines; sources disagree on whether it is mandatory | D.Lgs. 116/2020 amending art. 219(5) of D.Lgs. 152/2006 | Recycling table + note | S |
| "Birra artigianale" | Reserved for beer from an independent small brewery (max 200,000 hl/year, own plant, no licences of others' IP) that is neither pasteurised nor microfiltered | L. 1354/1962 art. 2 c. 4-bis, added by L. 154/2016 art. 35 | Only as a claim the user confirms | S |
| Beer categories | "Birra analcolica", "birra leggera/light", "birra speciale", "birra doppio malto" depend on Plato degrees and alcohol | L. 1354/1962 as amended (DPR 272/1998) | Use only what the producer confirms | K (thresholds not checked) |

Sources: <https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2020-09-03;116>, <https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2006-04-03;152>, <https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2017-12-15;231>, <https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2017-09-15;145>, <https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1962-08-16;1354>, <https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2016-07-28;154>

Secondary sources consulted on 2026-10-08: Chamber of Commerce of Turin beer labelling guide (<https://portale-etichettatura.lab-to.camcom.it/media/questions/institutions/2/docs/guida_etichette_birra-1.pdf>), TUV SUD Italy on environmental labelling (<https://www.tuvsud.com/it-it/risorse-e-pubblicazioni/tuv-italia-blog/sicurezza-del-consumatore/etichettatura-ambientale,-c-,-guida-al-riciclo-degli-imballaggi>), ICQRF note on D.Lgs. 231/2017 (<https://www.alimenti-salute.it/doc/2018.05.10_Nota_MIPAAF_ICQRF_Chiarimenti_applicazione_su_D.Lgs_231_2017.pdf>), EUR-Lex summary on prepackages (<https://eur-lex.europa.eu/EN/legal-content/summary/pre-packed-products-how-to-fill-and-label-the-package.html>).

## What I could not verify

- The exact current wording of each EU article above against EUR-Lex (article numbers are from general knowledge; the Normattiva links were not opened).
- Whether D.Lgs. 145/2017 (plant address) is still applied in full to beer sold in Italy.
- Whether "Verifica le disposizioni del tuo Comune" is mandatory or only recommended on consumer packaging (sources disagree).
- The Plato and alcohol thresholds of the Italian beer categories.
- The current status of the EU revision of alcoholic-beverage labelling (ingredients and energy over 1.2% vol).
- Export markets: for example France requires a pregnancy pictogram on alcoholic drinks and Ireland has adopted health warnings with a postponed start date. Check each destination country.

## Quick pre-print list

- [ ] Name + style, volume, ABV all in the front third
- [ ] Producer name and full address (plant address in Italy) confirmed by the producer
- [ ] Every allergen emphasised (barley, wheat, oats, rye, spelt; lactose for milk stouts; sulphites if declared)
- [ ] Best-before box (and lot) left free for the filling line, 30 x 12 mm or more
- [ ] Recycling code and collection text for the market (Italy: ALU 41, Raccolta metalli)
- [ ] Mandatory text at x-height 1.2 mm or more, volume figures 4 mm or more
- [ ] Text in the market's language
- [ ] Claims ("artigianale", "gluten-free", "unfiltered") confirmed by the producer
- [ ] Distributor logo supplied by the distributor, not redrawn
- [ ] `check_label.py` reports 0 errors
