"""Card drawing on a Tkinter Canvas (no image files involved)."""

from .cards import RANK_LABELS, Card

# STYLE picks how a card face is laid out:
#   "classic"  pips arranged as on a real French card, red and black
#   "minimal"  no pips: one big rank, one pip, and a lot of white space
STYLE = "classic"

# Two ink schemes. FOUR_COLOUR is the one in use: it keeps the traditional
# shapes but gives every suit its own colour, so the suit reads at a glance,
# which matters in a game where you judge three cards in a moment. Swap
# SUIT_COLORS below for TWO_COLOUR to get the usual red and black.
TWO_COLOUR = {
    "Diamonds": "#c5303a",
    "Hearts": "#c5303a",
    "Spades": "#1d2126",
    "Clubs": "#1d2126",
}
FOUR_COLOUR = {
    "Diamonds": "#2f6fb3",
    "Hearts": "#c5303a",
    "Spades": "#1d2126",
    "Clubs": "#2f7d4f",
}
SUIT_COLORS = FOUR_COLOUR

# Brighter variants, for suit names printed on the dark side panel.
SUIT_COLORS_ON_DARK = {
    "Diamonds": "#7fb2e8",
    "Hearts": "#f0857c",
    "Spades": "#c8d2dc",
    "Clubs": "#6fc794",
}

FACE_BG = "#f8f3e3"
FACE_EDGE = "#3b3428"
BACK_BG = "#7d1f2b"
BACK_EDGE = "#2b1013"
BACK_LINE = "#a8434f"
SHADOW = "#0b3a24"
HILITE = "#f2c14e"

# Pip positions on the card face, as fractions of width and height.
PIP_LAYOUTS = {
    1: [(0.50, 0.50)],
    2: [(0.50, 0.30), (0.50, 0.70)],
    3: [(0.50, 0.26), (0.50, 0.50), (0.50, 0.74)],
    4: [(0.33, 0.30), (0.67, 0.30), (0.33, 0.70), (0.67, 0.70)],
    5: [(0.33, 0.27), (0.67, 0.27), (0.50, 0.50), (0.33, 0.73), (0.67, 0.73)],
    6: [(0.33, 0.24), (0.67, 0.24), (0.33, 0.50), (0.67, 0.50),
        (0.33, 0.76), (0.67, 0.76)],
    7: [(0.33, 0.23), (0.67, 0.23), (0.33, 0.45), (0.67, 0.45),
        (0.50, 0.61), (0.33, 0.78), (0.67, 0.78)],
    8: [(0.33, 0.22), (0.67, 0.22), (0.33, 0.42), (0.67, 0.42),
        (0.33, 0.61), (0.67, 0.61), (0.33, 0.80), (0.67, 0.80)],
    9: [(0.33, 0.21), (0.67, 0.21), (0.33, 0.39), (0.67, 0.39),
        (0.50, 0.50), (0.33, 0.61), (0.67, 0.61), (0.33, 0.79), (0.67, 0.79)],
    10: [(0.33, 0.20), (0.67, 0.20), (0.33, 0.37), (0.67, 0.37),
         (0.50, 0.285), (0.50, 0.715), (0.33, 0.63), (0.67, 0.63),
         (0.33, 0.80), (0.67, 0.80)],
}


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Rounded rectangle, built from a smoothed polygon."""
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def draw_card(canvas, x, y, w, h, card: Card, tags=(), highlight=False,
              dim=False):
    """Draw a face-up card with its top-left corner at (x, y)."""
    color = SUIT_COLORS.get(card.suit, "#7a4fa3")   # jokers get their own ink
    radius = max(6, w * 0.10)

    round_rect(canvas, x + 3, y + 4, x + w + 3, y + h + 4, radius,
               fill=SHADOW, outline="", tags=tags)
    if highlight:
        round_rect(canvas, x - 5, y - 5, x + w + 5, y + h + 5, radius * 1.2,
                   fill=HILITE, outline="", tags=tags)
    round_rect(canvas, x, y, x + w, y + h, radius,
               fill=FACE_BG, outline=FACE_EDGE, width=1, tags=tags)
    round_rect(canvas, x + w * 0.07, y + h * 0.05,
               x + w * 0.93, y + h * 0.95, radius * 0.6,
               fill="", outline=color, width=1, tags=tags)

    label = card.label
    font_small = ("Helvetica", max(9, int(h * 0.11)), "bold")
    canvas.create_text(x + w * 0.17, y + h * 0.11, text=label, fill=color,
                       font=font_small, tags=tags)
    emblem(canvas, card.suit, x + w * 0.82, y + h * 0.11, w * 0.16, color, tags)
    canvas.create_text(x + w * 0.83, y + h * 0.90, text=label, fill=color,
                       font=font_small, tags=tags)

    if card.is_joker:
        _draw_joker(canvas, x, y, w, h, color, tags)
    elif STYLE == "minimal":
        _draw_minimal(canvas, x, y, w, h, card, color, tags)
    elif card.is_face:
        _draw_face_card(canvas, x, y, w, h, card, color, tags)
    else:
        _draw_pips(canvas, x, y, w, h, card, color, tags)

    if dim:
        round_rect(canvas, x, y, x + w, y + h, radius,
                   fill="#0d3f2a", outline="", stipple="gray50", tags=tags)


def draw_card_back(canvas, x, y, w, h, tags=()):
    """Draw a face-down card."""
    radius = max(6, w * 0.10)
    round_rect(canvas, x + 3, y + 4, x + w + 3, y + h + 4, radius,
               fill=SHADOW, outline="", tags=tags)
    round_rect(canvas, x, y, x + w, y + h, radius,
               fill=BACK_BG, outline=BACK_EDGE, width=1, tags=tags)

    # Diagonal lattice, clipped inside the card border.
    inset = radius * 0.5
    px, py = x + inset, y + inset
    pw, ph = w - 2 * inset, h - 2 * inset
    step = max(8, int(w * 0.18))

    for k in range(0, int(pw + ph) + step, step):          # lines x + y = k
        t0, t1 = max(0, k - pw), min(ph, k)
        if t0 < t1:
            canvas.create_line(px + k - t0, py + t0, px + k - t1, py + t1,
                               fill=BACK_LINE, width=1, tags=tags)
    for c in range(-int(ph), int(pw) + step, step):        # lines x - y = c
        t0, t1 = max(0, -c), min(ph, pw - c)
        if t0 < t1:
            canvas.create_line(px + c + t0, py + t0, px + c + t1, py + t1,
                               fill=BACK_LINE, width=1, tags=tags)

    round_rect(canvas, x, y, x + w, y + h, radius,
               fill="", outline=BACK_EDGE, width=2, tags=tags)
    round_rect(canvas, x + w * 0.12, y + h * 0.08,
               x + w * 0.88, y + h * 0.92, radius * 0.6,
               fill="", outline="#e8d7a8", width=1, tags=tags)


def draw_placeholder(canvas, x, y, w, h, text="", tags=(), color="#2c7550"):
    """Empty card outline: an exhausted stock, or a free spot on the table."""
    radius = max(6, w * 0.10)
    round_rect(canvas, x, y, x + w, y + h, radius,
               fill="", outline=color, width=2, tags=tags)
    if text:
        canvas.create_text(x + w / 2, y + h / 2, text=text, fill=color,
                           font=("Helvetica", max(8, int(h * 0.09))), tags=tags)


# --- suit emblems ---------------------------------------------------------

def _draw_minimal(canvas, x, y, w, h, card, color, tags):
    """Rank and one pip, nothing else."""
    canvas.create_text(x + w * 0.5, y + h * 0.44, text=card.label, fill=color,
                       font=("Helvetica", int(h * 0.34), "bold"), tags=tags)
    emblem(canvas, card.suit, x + w * 0.5, y + h * 0.72, w * 0.26, color, tags)


def _draw_joker(canvas, x, y, w, h, color, tags):
    """A jester's cap: the one card that is not a rank in a suit."""
    cx, cy = x + w * 0.5, y + h * 0.52
    r = w * 0.30
    canvas.create_polygon(cx - r, cy + r * 0.55, cx + r, cy + r * 0.55,
                         cx + r * 0.72, cy - r * 0.15, cx, cy - r * 0.75,
                         cx - r * 0.72, cy - r * 0.15,
                         fill=color, outline=color, smooth=True, tags=tags)
    for dx in (-1, 0, 1):
        canvas.create_oval(cx + dx * r * 0.78 - r * 0.2, cy - r * 0.95 - r * 0.2,
                           cx + dx * r * 0.78 + r * 0.2, cy - r * 0.95 + r * 0.2,
                           fill=color, outline=color, tags=tags)


def _draw_pips(canvas, x, y, w, h, card, color, tags):
    positions = PIP_LAYOUTS[card.rank]
    size = w * (0.30 if card.rank == 1 else 0.17)
    for fx, fy in positions:
        emblem(canvas, card.suit, x + w * fx, y + h * fy, size, color, tags)


def _draw_face_card(canvas, x, y, w, h, card, color, tags):
    canvas.create_text(x + w * 0.5, y + h * 0.40,
                       text=RANK_LABELS[card.rank], fill=color,
                       font=("Helvetica", int(h * 0.30), "bold"), tags=tags)
    emblem(canvas, card.suit, x + w * 0.5, y + h * 0.70, w * 0.22, color, tags)
    canvas.create_line(x + w * 0.22, y + h * 0.55, x + w * 0.78, y + h * 0.55,
                       fill=color, width=1, tags=tags)


def emblem(canvas, suit, cx, cy, size, color, tags=()):
    """One French suit pip centred on (cx, cy).

    Drawn from ovals and polygons rather than the unicode glyphs, which do not
    survive the PostScript export the screenshots go through.
    """
    r = size / 2
    if suit == "Diamonds":
        canvas.create_polygon(cx, cy - r, cx + r * 0.72, cy,
                             cx, cy + r, cx - r * 0.72, cy,
                             fill=color, outline=color, tags=tags)

    elif suit == "Hearts":
        lobe = r * 0.54
        for side in (-1, 1):
            canvas.create_oval(cx + side * r * 0.42 - lobe, cy - r * 0.34 - lobe,
                               cx + side * r * 0.42 + lobe, cy - r * 0.34 + lobe,
                               fill=color, outline=color, tags=tags)
        canvas.create_polygon(cx - r * 0.94, cy - r * 0.22,
                             cx + r * 0.94, cy - r * 0.22,
                             cx, cy + r,
                             fill=color, outline=color, tags=tags)

    elif suit == "Spades":
        lobe = r * 0.52
        for side in (-1, 1):
            canvas.create_oval(cx + side * r * 0.44 - lobe, cy + r * 0.28 - lobe,
                               cx + side * r * 0.44 + lobe, cy + r * 0.28 + lobe,
                               fill=color, outline=color, tags=tags)
        canvas.create_polygon(cx - r * 0.94, cy + r * 0.2,
                             cx + r * 0.94, cy + r * 0.2,
                             cx, cy - r,
                             fill=color, outline=color, tags=tags)
        _stem(canvas, cx, cy, r, color, tags)

    else:   # Clubs: three lobes over a stem, spread wide enough that the
            # shape still reads as a club at corner-index size
        lobe = r * 0.44
        for dx, dy in ((0, -r * 0.48), (-r * 0.56, r * 0.2), (r * 0.56, r * 0.2)):
            canvas.create_oval(cx + dx - lobe, cy + dy - lobe,
                               cx + dx + lobe, cy + dy + lobe,
                               fill=color, outline=color, tags=tags)
        _stem(canvas, cx, cy, r, color, tags)


def _stem(canvas, cx, cy, r, color, tags):
    """The little pedestal under a spade or a club."""
    canvas.create_polygon(cx - r * 0.09, cy + r * 0.2,
                         cx + r * 0.09, cy + r * 0.2,
                         cx + r * 0.42, cy + r,
                         cx - r * 0.42, cy + r,
                         fill=color, outline=color, tags=tags)
