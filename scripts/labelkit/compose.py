"""Compose the full-wrap label SVG from a validated spec.

Geometry (x grows to the right, label centre = front of the can):

  | seam | producer strip | left panel | FRONT (middle third) | right panel | seam |
  0                       W/3                 W/2               2W/3                W

Text never enters the seam safe zone (layout.seam_safe_pct of W at each edge)
or the top and bottom margins. Every text element carries data attributes the
QA script reads: data-role, data-legal, data-bg, data-maxw, data-minfs.
"""
from .colors import contrast, darken, lighten, mix
from .motifs import DRAW, MOTIFS
from .safety import esc
from .textfit import balance_two_lines, est_width, fit_size, wrap_runs, wrap_text


def _fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


class Label:
    def __init__(self, spec, tpl, assets):
        self.spec, self.tpl, self.assets = spec, tpl, assets or {}
        self.W, self.H = tpl["width_px"], tpl["height_px"]
        self.ppm = tpl["px_per_mm"]
        self.pal = spec["design"]["palette"]
        self.fonts = spec["design"]["fonts"]
        self.st = spec["strings"]
        self.lay = spec["layout"]
        self.defs, self.back, self.mid, self.front = [], [], [], []
        self.warnings = []
        qa = spec["qa"]
        self.legal_min = self.mm(qa["min_x_height_mm"] / qa["x_height_ratio"])
        self.legal_fs = self.mm(self.lay["legal_font_mm"])
        if self.legal_fs < self.legal_min:
            self.warnings.append(f"layout.legal_font_mm {self.lay['legal_font_mm']} is below the legal minimum "
                                 f"({self.legal_min / self.ppm:.2f} mm font size); raised to the minimum")
            self.legal_fs = self.legal_min
        self.motifs = {MOTIFS[m["type"]]["role"]: m for m in spec["design"]["motifs"]}

    # ------------------------------------------------------------------ helpers
    def mm(self, v):
        return v * self.ppm

    def worst_bg(self, fill, candidates):
        return min(candidates, key=lambda c: contrast(fill, c))

    def text(self, x, y, content, fs, *, cls="body", fill=None, weight=400, anchor="start", ls_em=0.0,
             role=None, legal=False, bg=None, maxw=None, minfs=None, fit=None, transform=None,
             data_fill=None, extra="", raw=False):
        fill = fill or self.pal["text"]
        attrs = [f'class="{cls}"', f'font-size="{fs:.1f}"']
        if transform:
            attrs.append(f'transform="{transform}"')
            attrs.append('x="0" y="0"')
        else:
            attrs.append(f'x="{x:.1f}" y="{y:.1f}"')
        if weight != 400:
            attrs.append(f'font-weight="{weight}"')
        if anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if ls_em:
            attrs.append(f'letter-spacing="{fs * ls_em:.2f}"')
        attrs.append(f'fill="{fill}"')
        if data_fill:
            attrs.append(f'data-fill="{data_fill}"')
        if role:
            attrs.append(f'data-role="{role}"')
        if legal:
            attrs.append('data-legal="1"')
        if bg:
            attrs.append(f'data-bg="{bg}"')
        if maxw:
            attrs.append(f'data-maxw="{maxw:.1f}"')
            attrs.append(f'data-minfs="{(minfs if minfs is not None else fs * 0.8):.1f}"')
        if fit:
            attrs.append(f'data-fit="{fit}"')
        if extra:
            attrs.append(extra)
        if raw:
            inner = content  # caller escaped every piece
        elif isinstance(content, str):
            inner = esc(content)
        else:
            parts = []
            for seg, emph in content:
                if not emph:
                    parts.append(esc(seg))
                    continue
                lead = " " if seg.startswith(" ") else ""
                role_attr = ' data-role="allergen"' if emph == "allergen" else ""
                parts.append(f'{lead}<tspan font-weight="700"{role_attr}>{esc(seg.strip())}</tspan>')
            inner = "".join(parts)
        return f'<text {" ".join(attrs)}>{inner}</text>'

    # ------------------------------------------------------------------ geometry
    def geometry(self):
        W, H, mm = self.W, self.H, self.mm
        self.seam = W * self.lay["seam_safe_pct"] / 100.0
        margin = mm(self.lay["margin_mm"])
        self.band_offset = mm(2.0)
        band = self.motifs.get("band")
        if band:
            band_h = mm(band["params"]["height_mm"])
            self.content_top = max(margin, self.band_offset + band_h + mm(2.5))
        else:
            self.content_top = margin + mm(1.5)
        self.content_bottom = H - self.content_top
        scen = self.motifs.get("scenery")
        self.scen_top = H * (1 - scen["params"]["height_pct"] / 100.0) if scen else None
        self.cx = W / 2.0

        st, prod = self.st, self.spec["producer"]
        self.producer_text = f'{st["produced_by"]} {prod["name"]}, {prod["address"]}'
        self.lh_legal = self.legal_fs * 1.32
        bw = self.fonts["body"]["width"]
        strip_len = self.content_bottom - self.content_top
        self.strip_lines = wrap_text(self.producer_text, strip_len, self.legal_fs, False,
                                     self.legal_fs * 0.04, bw)
        if len(self.strip_lines) > 3:
            self.warnings.append("producer line needs more than 3 vertical lines; shorten the address")
        strip_w = len(self.strip_lines) * self.lh_legal
        if self.lay["producer_strip"] == "left":
            self.strip_x0 = self.seam + mm(1.5)
            self.left_x0 = self.strip_x0 + strip_w + mm(3.5)
            self.right_x1 = W - self.seam - mm(1.5)
        else:
            self.strip_x1 = W - self.seam - mm(1.5)
            self.right_x1 = self.strip_x1 - strip_w - mm(3.5)
            self.left_x0 = self.seam + mm(1.5)
        self.left_x1 = W / 3.0 - mm(4)
        self.right_x0 = 2 * W / 3.0 + mm(4)
        self.front_w = W / 3.0 - mm(2)
        self.strip_w = strip_w

        p = self.pal
        side_bgs = [p["bg"], p["bg2"], mix(p["bg"], p["bg2"], 0.5)]
        if self.spec["design"]["panel_backdrop"]:
            side_bgs = [mix(c, p["panel"], 0.9) for c in (p["bg"], p["bg2"])]
        self.side_bgs = side_bgs
        self.front_bgs = [p["bg"], mix(p["bg"], p["bg2"], 0.35)]

    # ------------------------------------------------------------------ layers
    def background(self):
        p, W, H = self.pal, self.W, self.H
        self.defs.append(f'<radialGradient id="bg" cx="50%" cy="40%" r="75%">'
                         f'<stop offset="0" stop-color="{p["bg"]}"/><stop offset="1" stop-color="{p["bg2"]}"/>'
                         f'</radialGradient>')
        pr = p["primary"]
        self.defs.append(f'<linearGradient id="metal" x1="0" y1="0" x2="0" y2="1">'
                         f'<stop offset="0" stop-color="{lighten(pr, .5)}"/>'
                         f'<stop offset=".35" stop-color="{lighten(pr, .12)}"/>'
                         f'<stop offset=".55" stop-color="{darken(pr, .25)}"/>'
                         f'<stop offset=".78" stop-color="{lighten(pr, .28)}"/>'
                         f'<stop offset="1" stop-color="{darken(pr, .12)}"/></linearGradient>')
        self.defs.append(f'<filter id="lift" x="-5%" y="-20%" width="110%" height="140%">'
                         f'<feDropShadow dx="0" dy="{self.mm(.45):.1f}" stdDeviation="{self.mm(.45):.1f}" '
                         f'flood-color="#000" flood-opacity=".35"/></filter>')
        self.back.append(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')

    def motif_ctx(self, **extra):
        ctx = {"W": self.W, "H": self.H, "ppm": self.ppm, "cx": self.cx, "palette": self.pal,
               "metallic": self.spec["design"]["metallic"], "band_offset": self.band_offset}
        ctx.update(getattr(self, "hero", {}))
        ctx.update(extra)
        return ctx

    def draw_motif(self, role, layer, **extra):
        m = self.motifs.get(role)
        if not m:
            return
        d, body = DRAW[m["type"]](self.motif_ctx(**extra), m["params"])
        if d:
            self.defs.append(d)
        layer.append(body)

    # ------------------------------------------------------------------ front
    def front_panel(self):
        mm, spec, st = self.mm, self.spec, self.st
        beer = spec["beer"]
        dfont = self.fonts["display"]
        wf = dfont["width"]
        name = beer["name"].upper() if spec["design"]["name_case"] == "upper" else beer["name"]
        lines = [(x.upper() if spec["design"]["name_case"] == "upper" else x) for x in beer["name_lines"]] or [name]
        maxw = self.front_w
        if not beer["name_lines"]:
            one = fit_size(name, maxw, mm(16), mm(4), True, 0.03, wf)
            if one < mm(10) and " " in name:
                lines = balance_two_lines(name)
        cap = {1: mm(16), 2: mm(12.5), 3: mm(10)}[min(3, len(lines))]
        fs_name = min(fit_size(l, maxw, cap, mm(4), True, 0.03, wf) for l in lines)
        name_lh = fs_name * 0.98
        tag_fs, style_fs, row_fs = mm(3.4), mm(4.0), mm(6.0)

        heights = [mm(4.5), fs_name * 0.74 + (len(lines) - 1) * name_lh]
        if beer["tagline"]:
            heights.append(mm(3.2) + tag_fs * 0.74)
        heights.append(mm(3.6) + style_fs * 0.74)
        heights.append(mm(4.2) + row_fs * 0.74)
        vol = beer["volume_ml"]
        self.vol_txt = f"{_fmt(vol)} ml" if beer["volume_unit"] == "ml" else f"{_fmt(vol / 10)} cl"
        if beer["e_mark"]:
            self.vol_txt += " \u212e"
        abv = f'{beer["abv"]:.1f}'.replace(".", st["decimal"])
        self.abv_txt = f'{st["alc_prefix"]} {abv}% vol'.strip()
        row = self.vol_txt + "\u00a0\u00a0\u2022\u00a0\u00a0" + self.abv_txt
        # one centred line when it fits with 4 mm figures (5.7 mm font), else two lines
        self.two_rows = est_width(row, mm(5.7), True, 0, self.fonts["body"]["width"]) > self.front_w
        if self.two_rows:
            heights.append(row_fs * 0.8 * 1.25)
        stack_h = sum(heights)
        bottom = self.content_bottom
        if self.scen_top is not None:
            bottom -= max(0.0, (self.content_bottom - self.scen_top) * 0.45)
        avail = bottom - self.content_top - stack_h
        hero_d = max(mm(22), min(mm(46), avail))
        spare = max(0.0, avail - hero_d)
        hero_r = hero_d / 2
        hero_cy = self.content_top + spare * 0.35 + hero_r
        frame = self.motifs.get("frame")
        inner = {"laurel": 0.70, "roundel": 0.74}.get(frame["type"] if frame else "", 0.95) * hero_r
        self.hero = {"hero_cy": hero_cy, "hero_r": hero_r, "emblem_size": inner * 1.45}

        # background motif, then the frame and the emblem
        self.draw_motif("background", self.back)
        if frame:
            self.mid.append(f'<circle cx="{self.cx:.1f}" cy="{hero_cy:.1f}" r="{inner * 1.04:.1f}" '
                            f'fill="{mix(self.pal["bg"], self.pal["bg2"], .6)}" opacity=".55"/>')
            self.draw_motif("frame", self.mid)
        logo = self.assets.get("logo")
        if logo:
            size = mm(spec["design"]["logo"]["size_mm"]) if spec["design"]["logo"]["size_mm"] else inner * 1.45
            self.mid.append(f'<image x="{self.cx - size / 2:.1f}" y="{hero_cy - size / 2:.1f}" width="{size:.1f}" '
                            f'height="{size:.1f}" preserveAspectRatio="xMidYMid meet" data-role="logo" '
                            f'xlink:href="{logo["data_uri"]}"/>')
        elif "emblem" in self.motifs:
            self.draw_motif("emblem", self.mid)
        else:
            mono = (beer["name"][:1] or "B").upper()
            fill = "url(#metal)" if spec["design"]["metallic"] else self.pal["primary"]
            self.mid.append(self.text(self.cx, hero_cy + inner * 0.36, mono, inner * 1.0, cls="display",
                                      weight=self._bold("display"), anchor="middle", fill=fill,
                                      data_fill=self.pal["primary"], role="monogram",
                                      bg=self.worst_bg(self.pal["primary"], self.front_bgs)))

        y = hero_cy + hero_r + spare * 0.35 + heights[0]
        name_fill = "url(#metal)" if spec["design"]["metallic"] else self.pal["primary"]
        y += fs_name * 0.74
        for i, line in enumerate(lines):
            self.front.append(self.text(self.cx, y, line, fs_name, cls="display", weight=self._bold("display"),
                                        anchor="middle", ls_em=0.03, fill=name_fill, data_fill=self.pal["primary"],
                                        role="name", bg=self.worst_bg(self.pal["primary"], self.front_bgs),
                                        maxw=maxw, minfs=mm(4), fit="name", extra='filter="url(#lift)"'))
            if i < len(lines) - 1:
                y += name_lh
        k = 2
        if beer["tagline"]:
            y += heights[k]
            k += 1
            self.front.append(self.text(self.cx, y, beer["tagline"], tag_fs, fill=self.pal["muted"], anchor="middle",
                                        role="tagline", bg=self.worst_bg(self.pal["muted"], self.front_bgs),
                                        maxw=self.front_w, minfs=mm(2.4)))
        y += heights[k]
        k += 1
        style = f'{beer["denomination"]} {beer["style"]}'.strip().upper()
        self.front.append(self.text(self.cx, y, style, style_fs, weight=self._bold("body"), anchor="middle",
                                    ls_em=0.16, fill=self.pal["primary"], role="style", legal=True,
                                    bg=self.worst_bg(self.pal["primary"], self.front_bgs),
                                    maxw=self.front_w, minfs=self.legal_min))
        y += heights[k]
        bg = self.worst_bg(self.pal["text"], self.front_bgs)
        bold = self._bold("body")
        if not self.two_rows:
            sep = "\u00a0\u00a0\u2022\u00a0\u00a0"
            raw = (f'<tspan data-role="volume">{esc(self.vol_txt)}</tspan>'
                   f'<tspan fill="{self.pal["primary"]}">{sep}</tspan>'
                   f'<tspan data-role="abv">{esc(self.abv_txt)}</tspan>')
            self.front.append(self.text(self.cx, y, raw, row_fs, weight=bold, anchor="middle", role="volume-abv",
                                        legal=True, bg=bg, maxw=self.front_w, minfs=mm(5.7), raw=True))
        else:
            self.front.append(self.text(self.cx, y, self.vol_txt, row_fs, weight=bold, anchor="middle",
                                        role="volume", legal=True, bg=bg, maxw=self.front_w, minfs=mm(5.7)))
            y += heights[k + 1]
            self.front.append(self.text(self.cx, y, self.abv_txt, row_fs * 0.8, weight=bold, anchor="middle",
                                        role="abv", legal=True, bg=bg, maxw=self.front_w, minfs=self.legal_min))

    def _bold(self, role):
        weights = self.fonts[role]["weights"]
        return 700 if 700 in weights else max(weights)

    # ------------------------------------------------------------------ side panels
    def backdrops(self):
        if not self.spec["design"]["panel_backdrop"]:
            for x in (self.W / 3.0, 2 * self.W / 3.0):
                self.mid.append(f'<line x1="{x:.1f}" y1="{self.content_top + self.mm(6):.1f}" x2="{x:.1f}" '
                                f'y2="{self.content_bottom - self.mm(6):.1f}" stroke="{self.pal["primary"]}" '
                                f'stroke-width="{self.mm(.15):.1f}" opacity=".35"/>')
            return
        pad, mm = self.mm(2.5), self.mm
        y0, y1 = self.content_top - mm(1), self.content_bottom + mm(1)
        if self.lay["producer_strip"] == "left":
            lx0, rx1 = self.strip_x0 - mm(1.5), self.right_x1 + mm(1.5)
        else:
            lx0, rx1 = self.left_x0 - mm(1.5), self.strip_x1 + mm(1.5)
        for x0, x1 in ((lx0, self.left_x1 + pad), (self.right_x0 - pad, rx1)):
            self.mid.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" '
                            f'rx="{mm(2):.1f}" fill="{self.pal["panel"]}" opacity=".9"/>')

    def producer_strip(self):
        fs = self.legal_fs
        fill = self.pal["text"]
        bg = self.worst_bg(fill, self.side_bgs)
        maxw = self.content_bottom - self.content_top
        for i, line in enumerate(self.strip_lines):
            if self.lay["producer_strip"] == "left":
                x = self.strip_x0 + fs * 0.8 + i * self.lh_legal
                tr = f"translate({x:.1f},{self.content_bottom:.1f}) rotate(-90)"
            else:
                x = self.strip_x1 - fs * 0.8 - i * self.lh_legal
                tr = f"translate({x:.1f},{self.content_top:.1f}) rotate(90)"
            self.front.append(self.text(0, 0, line, fs, transform=tr, fill=fill, ls_em=0.04, role="producer",
                                        legal=True, bg=bg, maxw=maxw, minfs=self.legal_min, fit="producer"))

    def left_panel(self):
        spec, st, mm = self.spec, self.st, self.mm
        x0, x1 = self.left_x0, self.left_x1
        pw = x1 - x0
        bw = self.fonts["body"]["width"]
        top, bottom = self.content_top + mm(1), self.content_bottom
        text_fill, muted = self.pal["text"], self.pal["muted"]

        runs = []
        if spec["ingredients"]:
            runs.append((st["ingredients"] + " ", "label"))
            for i, it in enumerate(spec["ingredients"]):
                txt = it["text"].upper() if it["allergen"] else it["text"]
                runs.append((txt, "allergen" if it["allergen"] else False))
                runs.append((", " if i < len(spec["ingredients"]) - 1 else ".", False))
        contains = []
        if spec["allergen_statement"]:
            contains = [(st["contains"] + " ", "label"),
                        (spec["allergen_statement"].rstrip(".").upper(), "allergen"), (".", False)]
        paragraphs_legal = []
        if runs:
            paragraphs_legal.append(("ingredients", runs))
        if contains:
            paragraphs_legal.append(("contains", contains))
        if spec["claims"]:
            paragraphs_legal.append(("claims", [(". ".join(c.rstrip(".") for c in spec["claims"]) + ".", False)]))
        for note in spec["notes"]:
            paragraphs_legal.append(("note", [(note, False)]))
        if spec["producer"]["website"]:
            paragraphs_legal.append(("website", [(spec["producer"]["website"], "label")]))

        story_fs = mm(self.lay["body_font_mm"])
        legal_fs = self.legal_fs
        heading_fs = mm(3.6)
        for attempt in range(14):
            out = []
            # legal block, anchored to the bottom
            legal_lines = []
            for kind, prs in paragraphs_legal:
                for ln in wrap_runs(prs, pw, legal_fs, legal_fs * 0.01, bw):
                    legal_lines.append((kind, ln))
                legal_lines.append((None, None))
            if legal_lines:
                legal_lines.pop()
            lh = legal_fs * 1.36
            gap = mm(1.6)
            legal_h = sum(lh if k else gap for k, _ in legal_lines)
            y = bottom - legal_h + legal_fs * 0.74
            legal_top = bottom - legal_h
            for kind, ln in legal_lines:
                if kind is None:
                    y += gap
                    continue
                fill = muted if kind in ("note", "website") else text_fill
                role = {"ingredients": "ingredients", "contains": "contains", "claims": "claims"}.get(kind, "note")
                out.append(self.text(x0, y, ln, legal_fs, fill=fill, role=role, legal=kind in ("ingredients", "contains"),
                                     bg=self.worst_bg(fill, self.side_bgs), maxw=pw, minfs=self.legal_min,
                                     fit="legal-left"))
                y += lh
            # heading + story from the top
            y = top + heading_fs * 0.74
            out.append(self.text(x0, y, spec["beer"]["name"].upper(), heading_fs, cls="display",
                                 weight=self._bold("display"), ls_em=0.06, fill=self.pal["primary"], role="heading",
                                 bg=self.worst_bg(self.pal["primary"], self.side_bgs), maxw=pw, minfs=mm(2.4)))
            y += mm(2.2)
            out.append(f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x0 + min(pw, mm(18)):.1f}" y2="{y:.1f}" '
                       f'stroke="{self.pal["primary"]}" stroke-width="{mm(.25):.1f}"/>')
            y += mm(2.6)
            slh = story_fs * 1.4
            story_bottom = y
            y += story_fs * 0.74
            for n, para in enumerate(spec["story"]):
                if n:
                    y += mm(1.4)
                for ln in wrap_text(para, pw, story_fs, False, 0, bw):
                    out.append(self.text(x0, y, ln, story_fs, fill=text_fill, role="story",
                                         bg=self.worst_bg(text_fill, self.side_bgs), maxw=pw, minfs=mm(2.0),
                                         fit="story"))
                    story_bottom = y + story_fs * 0.3
                    y += slh
            if story_bottom + mm(3) <= legal_top:
                break
            if story_fs > mm(2.2):
                story_fs = max(mm(2.2), story_fs * 0.94)
            elif legal_fs > self.legal_min:
                legal_fs = max(self.legal_min, legal_fs * 0.96)
            else:
                self.warnings.append("left panel overflows: shorten the story or the notes")
                out = [o.replace("<text ", '<text data-overflow="1" ', 1) if 'data-role="story"' in o else o
                       for o in out]
                break
        self.front.extend(out)

    def right_panel(self):
        spec, st, mm = self.spec, self.st, self.mm
        x0, x1 = self.right_x0, self.right_x1
        pw = x1 - x0
        fs = self.legal_fs
        bwf = self.fonts["body"]["width"]
        text_fill, muted = self.pal["text"], self.pal["muted"]
        y = self.content_top + mm(1)
        if spec["distributor"]["show"]:
            y += fs * 0.74
            self.front.append(self.text(x0, y, st["distributed_by"].upper(), fs, weight=self._bold("body"),
                                        ls_em=0.12, fill=muted, role="distributor-label",
                                        bg=self.worst_bg(muted, self.side_bgs), maxw=pw, minfs=self.legal_min))
            y += mm(2)
            bw_, bh_ = min(pw, mm(36)), mm(15)
            self.front.append(f'<rect x="{x0:.1f}" y="{y:.1f}" width="{bw_:.1f}" height="{bh_:.1f}" rx="{mm(1.2):.1f}" '
                              f'fill="none" stroke="{muted}" stroke-width="{mm(.2):.1f}" '
                              f'stroke-dasharray="{mm(1):.1f} {mm(1):.1f}" data-role="distributor"/>')
            dlogo = self.assets.get("distributor_logo")
            if dlogo:
                pad = mm(1.5)
                self.front.append(f'<image x="{x0 + pad:.1f}" y="{y + pad:.1f}" width="{bw_ - 2 * pad:.1f}" '
                                  f'height="{bh_ - 2 * pad:.1f}" preserveAspectRatio="xMidYMid meet" '
                                  f'data-role="distributor-logo" xlink:href="{dlogo["data_uri"]}"/>')
            else:
                self.front.append(self.text(x0 + bw_ / 2, y + bh_ / 2 - mm(.2), st["distributor_placeholder"], mm(2.6),
                                            weight=self._bold("body"), anchor="middle", fill=muted,
                                            role="placeholder", bg=self.worst_bg(muted, self.side_bgs),
                                            maxw=bw_ - mm(3), minfs=mm(2)))
                self.front.append(self.text(x0 + bw_ / 2, y + bh_ / 2 + mm(3.4), st["distributor_hint"], mm(2.2),
                                            anchor="middle", fill=muted, role="placeholder",
                                            bg=self.worst_bg(muted, self.side_bgs), maxw=bw_ - mm(3), minfs=mm(1.8)))
            y += bh_
        top_free = y + mm(5)

        # best-before box, anchored to the bottom
        bb_top = self.content_bottom
        if spec["best_before"]["show"]:
            pad = mm(2)
            bb_lines = wrap_text(st["best_before"].upper(), pw - 2 * pad, fs, True, fs * 0.08, bwf)
            box_h = max(mm(16), pad + len(bb_lines) * fs * 1.3 + mm(5) + fs * 1.3 + mm(4))
            bb_top = self.content_bottom - box_h
            self.front.append(f'<rect x="{x0:.1f}" y="{bb_top:.1f}" width="{pw:.1f}" height="{box_h:.1f}" '
                              f'rx="{mm(1.2):.1f}" fill="{self.pal["panel"]}" stroke="{self.pal["primary"]}" '
                              f'stroke-width="{mm(.25):.1f}" data-role="best-before"/>')
            box_bg = self.pal["panel"]
            yy = bb_top + pad + fs * 0.74
            for ln in bb_lines:
                self.front.append(self.text(x0 + pad, yy, ln, fs, weight=self._bold("body"), ls_em=0.08,
                                            fill=text_fill, role="best-before-label", legal=True,
                                            bg=self.worst_bg(text_fill, [box_bg]), maxw=pw - 2 * pad,
                                            minfs=self.legal_min, fit="bb"))
                yy += fs * 1.3
            yy += mm(5)
            self.front.append(self.text(x0 + pad, yy, st["lot"].upper(), fs, weight=self._bold("body"), ls_em=0.08,
                                        fill=text_fill, role="lot-label", legal=True,
                                        bg=self.worst_bg(text_fill, [box_bg]), maxw=pw - 2 * pad,
                                        minfs=self.legal_min, fit="bb"))

        # recycling table, centred in the free space between the two
        rec = spec["recycling"]
        row_h = fs * 2.0
        note_lines = wrap_text(rec["note"], pw, fs, False, 0, bwf) if rec["note"] else []
        rec_h = 2 * row_h + mm(1) + mm(1.2) + len(note_lines) * fs * 1.1 + fs * 0.3
        free = bb_top - mm(5) - top_free
        if free < rec_h:
            self.warnings.append("right panel is crowded: the recycling block touches the best-before box")
        y = top_free + max(0.0, (free - rec_h) / 2)
        row_fill = mix(self.pal["panel"], self.pal["primary"], 0.12)
        row_bg = self.worst_bg(text_fill, [row_fill])
        g = ['<g data-role="recycling">']
        g.append(f'<rect x="{x0:.1f}" y="{y:.1f}" width="{pw:.1f}" height="{row_h:.1f}" rx="{mm(.8):.1f}" '
                 f'fill="{row_fill}" data-role="recycling-box"/>')
        base = y + row_h / 2 + fs * 0.36
        g.append(self.text(x0 + mm(2), base, rec["item"], fs, fill=text_fill, role="recycling", legal=True,
                           bg=row_bg, maxw=pw * 0.55, minfs=self.legal_min))
        g.append(self.text(x1 - mm(2), base, rec["code"], fs, weight=self._bold("body"), anchor="end",
                           fill=text_fill, role="recycling-code", legal=True, bg=row_bg, maxw=pw * 0.4,
                           minfs=self.legal_min))
        y += row_h + mm(1)
        g.append(f'<rect x="{x0:.1f}" y="{y:.1f}" width="{pw:.1f}" height="{row_h:.1f}" rx="{mm(.8):.1f}" '
                 f'fill="{row_fill}"/>')
        g.append(self.text(x0 + mm(2), y + row_h / 2 + fs * 0.36, rec["material"], fs, fill=text_fill,
                           role="recycling", legal=True, bg=row_bg, maxw=pw - mm(4), minfs=self.legal_min))
        y += row_h + mm(1.2)
        g.append("</g>")
        self.front.extend(g)
        for ln in note_lines:
            y += fs * 1.1
            self.front.append(self.text(x0, y, ln, fs, fill=muted, role="recycling-note",
                                        bg=self.worst_bg(muted, self.side_bgs), maxw=pw, minfs=self.legal_min,
                                        fit="rec-note"))

    # ------------------------------------------------------------------ assembly
    def build(self):
        self.geometry()
        self.background()
        self.front_panel()
        self.draw_motif("scenery", self.back)
        self.draw_motif("band", self.mid)
        self.backdrops()
        self.producer_strip()
        self.left_panel()
        self.right_panel()
        if self.spec["design"]["grain"]:
            self.defs.append('<filter id="grain" x="0" y="0" width="100%" height="100%">'
                             '<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7"/>'
                             '<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .05 0"/></filter>')
            self.front.append(f'<rect width="{self.W}" height="{self.H}" filter="url(#grain)" pointer-events="none"/>')
        return self.svg()

    def font_css(self):
        fams = []
        for role in ("display", "body"):
            f = self.fonts[role]
            fams.append(f'family={f["family"].replace(" ", "+")}:wght@{";".join(str(w) for w in f["weights"])}')
        return fams

    def svg(self):
        d, b = self.fonts["display"]["family"], self.fonts["body"]["family"]
        tpl = self.tpl
        imports = "".join(f"@import url('https://fonts.googleapis.com/css2?{q}&display=block');"
                          for q in self.font_css())
        style = (f"{imports} .display{{font-family:'{d}',sans-serif}} .body{{font-family:'{b}',sans-serif}} "
                 f"text{{font-kerning:normal}}")
        attrs = (f'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                 f'width="{self.W}" height="{self.H}" viewBox="0 0 {self.W} {self.H}" '
                 f'data-generator="beer-can-label" data-template="{esc(tpl["preset"])}" '
                 f'data-px-per-mm="{self.ppm:.4f}" data-seam-px="{self.seam:.1f}" '
                 f'data-content-top="{self.content_top:.1f}" data-content-bottom="{self.content_bottom:.1f}"')
        title = esc(f'{self.spec["beer"]["name"]}, {self.spec["beer"]["style"]}: can label')
        style = style.replace("&", "&amp;")
        return (f'<svg {attrs}>\n<title>{title}</title>\n<defs>\n<style>{style}</style>\n' + "\n".join(self.defs)
                + "\n</defs>\n" + "\n".join(self.back) + "\n" + "\n".join(self.mid) + "\n"
                + "\n".join(self.front) + "\n</svg>\n")


def compose(spec, tpl, assets=None):
    lab = Label(spec, tpl, assets)
    svg = lab.build()
    return svg, lab
