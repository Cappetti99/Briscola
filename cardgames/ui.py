"""Look and feel shared by every game window."""

# Window geometry.
TABLE_W, TABLE_H = 800, 660
PANEL_W = 292
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
GAMES = (BRISCOLA, BURRACO)
GAME_LABELS = {BRISCOLA: "Briscola", BURRACO: "Burraco"}
GAME_BLURBS = {
    BRISCOLA: "Trick taking with 40 cards. Short, sharp, first to 61.",
    BURRACO: "Melds, wild cards and the pot. Longer, and more to think about.",
}
