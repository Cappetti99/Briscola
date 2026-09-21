"""Look and feel shared by every game window."""

# Everything is drawn at this design size and then scaled to the window that
# actually fits the screen, so there is one set of coordinates to reason about
# rather than a layout that has to be recomputed for every size.
SCALE = 1.0
MIN_SCALE, MAX_SCALE = 0.65, 1.7

# Room left for the title bar, the menu bar and the dock.
SCREEN_MARGIN_W, SCREEN_MARGIN_H = 60, 140


def scale_for(screen_w: int, screen_h: int) -> float:
    """The largest whole-window scale that still fits the screen."""
    fits = min((screen_w - SCREEN_MARGIN_W) / WIN_W,
               (screen_h - SCREEN_MARGIN_H) / WIN_H)
    return round(max(MIN_SCALE, min(MAX_SCALE, fits)), 3)


def font(size: int, weight: str | None = None, *, family: str = "Helvetica"):
    """A font in design points, sized for the window actually on screen."""
    scaled = max(6, int(round(size * SCALE)))
    return (family, scaled, weight) if weight else (family, scaled)


def to_design(x: float, y: float) -> tuple[float, float]:
    """Turn a pointer position on screen back into design coordinates."""
    return x / SCALE, y / SCALE


# Window geometry.
TABLE_W, TABLE_H = 940, 770
PANEL_W = 320
STATUS_H = 46
WIN_W, WIN_H = TABLE_W + PANEL_W, TABLE_H + STATUS_H

# Panel layout.
PANEL_X = TABLE_W
PAD = 16
CONTENT_X = PANEL_X + PAD
CONTENT_W = PANEL_W - 2 * PAD

# Palette.
FELT = "#14603c"
FELT_DARK = "#0f4d30"
FELT_EDGE = "#2c7550"
PANEL_BG = "#10382a"
PANEL_CARD = "#17523b"
PANEL_CARD_HI = "#1e6448"
TEXT = "#f2ede0"
TEXT_DIM = "#9fc4b0"
ACCENT = "#f2c14e"
ACCENT_TEXT = "#1b2b16"

# The games on offer, in menu order.
BRISCOLA, BURRACO = "briscola", "burraco"
SCOPA, TRESSETTE = "scopa", "tressette"
GAMES = (BRISCOLA, BURRACO, SCOPA, TRESSETTE)
GAME_LABELS = {BRISCOLA: "Briscola", BURRACO: "Burraco", SCOPA: "Scopa",
               TRESSETTE: "Tressette"}
GAME_BLURBS = {
    BRISCOLA: "Trick taking with 40 cards. Short, sharp, first to 61.",
    BURRACO: "Melds, wild cards and the pot. Longer, and more to think about.",
    SCOPA: "Match cards off the table. Quick, and all about what you leave.",
    TRESSETTE: "No trumps, and you must follow suit. Ten cards, and counting.",
}
