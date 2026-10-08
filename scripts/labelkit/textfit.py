"""Text width estimates and line wrapping.

The estimates are deliberately generous (they assume a regular-width font), so
wrapped lines rarely overflow. When headless Chrome is available the build
measures every line with the real web font and shrinks any line that still
overflows (see build_label.FIT_SCRIPT).
"""

import re

NARROW = set("il.,:;'!|ijtfI1()[] ")
WIDE = set("MWmw@%&")


def char_em(ch, bold=False):
    if ch in (" ", "\u00a0"):
        w = 0.28
    elif ch in NARROW:
        w = 0.32
    elif ch in WIDE:
        w = 0.92
    elif ch.isupper():
        w = 0.68
    elif ch.isdigit():
        w = 0.58
    elif ch.islower():
        w = 0.54
    else:
        w = 0.6
    return w * (1.07 if bold else 1.0)


def est_width(text, font_size, bold=False, letter_spacing=0.0, width_factor=1.0):
    if not text:
        return 0.0
    em = sum(char_em(c, bold) for c in text)
    return em * font_size * width_factor + letter_spacing * max(0, len(text) - 1)


def fit_size(text, max_width, max_size, min_size, bold=False, ls_em=0.0, width_factor=1.0):
    """Largest font size (<= max_size) that fits max_width by estimate."""
    w1 = est_width(text, 1.0, bold, ls_em, width_factor)
    if w1 <= 0:
        return max_size
    return max(min_size, min(max_size, max_width / w1))


def wrap_runs(runs, max_width, font_size, letter_spacing=0.0, width_factor=1.0):
    """Greedy wrap of styled runs.

    runs: list of (text, emphasised). Spaces inside the run texts decide where
    lines may break, so ("malt", True), (", ", False) keeps the comma glued to
    "malt". Returns a list of lines; each line is a list of (text, emphasised)
    segments with the spaces already included. Emphasised text counts as bold.
    """
    tokens = []
    pending_space = True
    for text, emph in runs:
        for part in re.split(r"( +)", text):
            if not part:
                continue
            if part.startswith(" "):
                pending_space = True
                continue
            if tokens and not pending_space:
                tokens[-1].append((part, emph))
            else:
                tokens.append([(part, emph)])
            pending_space = False

    def tok_w(tok):
        return sum(est_width(t, font_size, e, letter_spacing, width_factor) for t, e in tok)

    space = est_width(" ", font_size, False, letter_spacing, width_factor) + letter_spacing
    lines, cur, cur_w = [], [], 0.0
    for tok in tokens:
        w = tok_w(tok)
        if cur and cur_w + space + w > max_width:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur_w += (space if cur else 0.0) + w
        cur.append(tok)
    if cur:
        lines.append(cur)

    out = []
    for line in lines:
        segs = []
        for i, tok in enumerate(line):
            for j, (text, emph) in enumerate(tok):
                if i > 0 and j == 0:
                    text = " " + text
                if segs and segs[-1][1] == emph:
                    segs[-1] = (segs[-1][0] + text, emph)
                else:
                    segs.append((text, emph))
        out.append(segs)
    return out


def wrap_text(text, max_width, font_size, bold=False, letter_spacing=0.0, width_factor=1.0):
    lines = wrap_runs([(text, bold)], max_width, font_size, letter_spacing, width_factor)
    return ["".join(t for t, _ in line) for line in lines]


def balance_two_lines(text):
    """Split text into two lines of similar length at a space."""
    words = text.split()
    if len(words) < 2:
        return [text]
    best, best_diff = None, None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        diff = abs(len(a) - len(b))
        if best_diff is None or diff < best_diff:
            best, best_diff = [a, b], diff
    return best
