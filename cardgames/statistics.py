"""Statistics presentation shared by the application and screenshot tools."""
from . import cardart, ui, records
from .ui import (ACCENT, PANEL_BG, PANEL_CARD, TEXT, TEXT_DIM)
from .briscola import ai

# --- statistics view ------------------------------------------------------

STATS_W, STATS_H = 560, 540
STATS_ROWS = 12


def draw_statistics(canvas, player, stats, matches, json_path, text_path, aggregate=False):
    """Draw the statistics window; kept module level so tools can reuse it."""
    canvas.delete("all")
    canvas.create_rectangle(0, 0, STATS_W, STATS_H, fill=PANEL_BG, outline="")
    canvas.create_text(24, 30, text="STATISTICS", anchor="w", fill=ACCENT,
                       font=ui.font(18, "bold"))
    canvas.create_text(STATS_W - 24, 30, text=player, anchor="e", fill=TEXT,
                       font=ui.font(14, "bold"))

    tiles = [
        ("Played", str(stats.played)),
        ("Won", str(stats.won)),
        ("Lost", str(stats.lost)),
        ("Win rate", f"{stats.win_rate:.0f}%"),
        ("Avg points", "—" if aggregate else f"{stats.avg_points:.0f}"),
        ("Best score", "—" if aggregate else str(stats.best)),
    ]
    tile_w = (STATS_W - 48 - 5 * 8) / 6
    for i, (title, value) in enumerate(tiles):
        x = 24 + i * (tile_w + 8)
        cardart.round_rect(canvas, x, 56, x + tile_w, 116, 8,
                           fill=PANEL_CARD, outline="")
        canvas.create_text(x + tile_w / 2, 74, text=title, fill=TEXT_DIM,
                           font=ui.font(9))
        canvas.create_text(x + tile_w / 2, 98, text=value, fill=TEXT,
                           font=ui.font(17, "bold"))

    canvas.create_text(24, 138, text=f"Current streak: {stats.streak_text()}",
                       anchor="w", fill=TEXT, font=ui.font(11))
    canvas.create_text(24, 158,
                       text=f"Best winning streak: {stats.best_streak}",
                       anchor="w", fill=TEXT_DIM, font=ui.font(11))

    by_level = "  ".join(
        f"{ai.LEVEL_LABELS.get(level, level)} {won}/{total}"
        for level, (won, total) in sorted(stats.by_difficulty.items())
    ) or "-"
    canvas.create_text(24, 178, text=f"Wins by difficulty: {by_level}",
                       anchor="w", fill=TEXT_DIM, font=ui.font(11))

    canvas.create_text(24, 208, text="RECENT MATCHES", anchor="w", fill=TEXT,
                       font=ui.font(9, "bold"))
    headers = [(24, "date"), (170, "result"), (250, "score"),
               (360, "difficulty"), (470, "Game")]
    for x, label in headers:
        canvas.create_text(x, 228, text=label, anchor="w", fill=TEXT_DIM,
                           font=ui.font(9))

    recent = list(reversed(matches))[:STATS_ROWS]
    if not recent:
        canvas.create_text(24, 252, text="No games recorded yet.", anchor="w",
                           fill=TEXT_DIM, font=ui.font(11))
    for row, match in enumerate(recent):
        y = 250 + row * 21
        if row % 2 == 0:
            canvas.create_rectangle(20, y - 9, STATS_W - 20, y + 10,
                                    fill=PANEL_CARD, outline="")
        color = {records.WIN: "#7ede9f", records.LOSS: "#e8897f"}.get(
            match.result, TEXT)
        cells = [(24, match.label(), TEXT_DIM),
                 (170, records.RESULT_LABELS.get(match.result, match.result), color),
                 (250, f"{match.you} - {match.ai}", TEXT),
                 (360, ai.LEVEL_LABELS.get(match.difficulty, match.difficulty), TEXT_DIM),
                 (470, ui.GAME_LABELS.get(match.game, match.game), TEXT_DIM)]
        for x, text, fill in cells:
            canvas.create_text(x, y, text=text, anchor="w", fill=fill,
                               font=ui.font(10))

    canvas.create_text(24, STATS_H - 44, text="Records are saved to:", anchor="w",
                       fill=TEXT_DIM, font=ui.font(9, "bold"))
    canvas.create_text(24, STATS_H - 28, text=str(json_path), anchor="w",
                       fill=TEXT_DIM, font=ui.font(9))
    canvas.create_text(24, STATS_H - 14, text=str(text_path), anchor="w",
                       fill=TEXT_DIM, font=ui.font(9))

