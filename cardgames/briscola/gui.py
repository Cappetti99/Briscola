"""Tkinter interface for Briscola.

Everything is drawn on a single Canvas, so the whole window has a consistent
look on every platform and can be exported with `tools/screenshots.py`.
"""

import os
import time
import traceback
import tkinter as tk
from tkinter import simpledialog

from .. import cardart, records, ui
from ..burraco import engine as burraco_engine
from ..burraco import view as burraco_view
from . import ai
from ..cards import KING, QUEEN, RANK_NAMES, Card
from .engine import AI, HUMAN, TOTAL_POINTS, TRICKS_PER_GAME, WINNING_POINTS, Game

from ..ui import (ACCENT, ACCENT_TEXT, CONTENT_W, CONTENT_X, FELT, FELT_DARK,
                  FELT_EDGE, PANEL_BG, PANEL_CARD, PANEL_CARD_HI, PANEL_W,
                  PANEL_X, STATUS_H, TABLE_H, TABLE_W, TEXT, TEXT_DIM,
                  WIN_H, WIN_W)

from .layout import (AI_HAND_Y, CARD_H, CARD_W, CENTER_X, HAND_GAP, LIFT,
                     LOG_LINES, PLAYER_HAND_Y, STOCK_X, STOCK_Y, TABLE_Y,
                     hand_slot_at, hand_x, table_slot)

# Pacing (ms). Both waits can be skipped with a click or the space bar.
AI_DELAY = 550
TRICK_DELAY = 1000
ANIM_STEPS = 8
ANIM_MS = 18

# Set BRISCOLA_DEBUG=1 to trace what the interface does, for diagnosing a
# freeze on a machine you cannot watch.
DEBUG = bool(os.environ.get("BRISCOLA_DEBUG"))
_START = time.time()


def trace(message: str) -> None:
    if DEBUG:
        print(f"[{time.time() - _START:8.3f}] {message}", flush=True)


# UI state machine.
S_MENU, S_HUMAN, S_AI, S_SHOW, S_OVER = "menu", "human", "ai", "show", "over"

# Opening screen layout.
MENU_CX = WIN_W // 2
MENU_COL_W = 380

LEVEL_BLURBS = {
    ai.EASY: "Plays almost at random. A gentle start.",
    ai.NORMAL: "Solid classic play: it ducks and saves its trumps.",
    ai.HARD: "Counts cards and searches ahead. Hard to beat.",
}


class BriscolaApp(tk.Tk):
    def __init__(self, records_store: records.Records | None = None):
        super().__init__()
        self.title("Briscola")
        self.configure(bg=PANEL_BG)
        self.resizable(False, False)

        self.records = records_store or records.Records()
        self.player = self.records.current_player
        self.difficulty = ai.NORMAL
        self.game_kind = ui.BRISCOLA
        self.selected: set[int] = set()
        self.hovered: int | None = None
        self.sort_mode = "suit"
        self.hand_first = 0
        self.hand_hidden = False
        self.target = burraco_engine.DEFAULT_TARGET
        self.match: burraco_engine.Match | None = None

        self.game: Game | None = None
        self.state = S_MENU
        self.next_leader = HUMAN
        self.hover: set[int] = set()
        self.log_lines: list[tuple[str, str]] = []
        self.status_text = ""
        self.stats_window: tk.Toplevel | None = None
        self._recorded = False
        self._pending: str | None = None
        self._anim_offset: tuple[float, float] | None = None
        self._anim_tag: str | None = None
        self._anim_seq = 0
        self._new_match = True
        self._anim_afters: set[str] = set()
        self._buttons: dict[str, tuple[int, callable]] = {}
        self._click_serial: int | None = None
        self.overlay: tuple[str, str, tuple] | None = None

        self.canvas = tk.Canvas(self, width=WIN_W, height=WIN_H, bg=FELT,
                                highlightthickness=0)
        self.canvas.pack()

        self.bind("<Key>", self._on_key)
        # A click anywhere skips whichever pause is running.
        self.canvas.bind("<Button-1>", self._on_canvas_click, add="+")
        self.canvas.bind("<Motion>", self._on_motion, add="+")
        self.canvas.bind("<Leave>", self._on_canvas_leave, add="+")
        self.canvas.bind("<MouseWheel>", self._on_wheel, add="+")
        self.show_menu()

    # --- menu -------------------------------------------------------------

    def show_menu(self):
        """Back to the opening screen; any game in progress is dropped."""
        self._cancel_pending()
        self.state = S_MENU
        self.hover.clear()
        self._anim_offset = None
        self.render()

    def start_game(self):
        self.new_game()

    # --- game flow --------------------------------------------------------

    def new_match(self):
        """A fresh series, rather than the next hand of the one in progress."""
        self._new_match = True
        self.new_game()

    def new_game(self):
        trace(f"new game: {self.game_kind}")
        self._cancel_pending()
        self.hover.clear()
        self.selected.clear()
        self.log_lines.clear()
        self._recorded = False
        self._anim_offset = None
        if self.game_kind == ui.BURRACO:
            if self.match is None or self.match.over or self._new_match:
                self.match = burraco_engine.Match(target=self.target)
            self._new_match = False
            self.game = burraco_engine.Game(first_player=self.next_leader)
            self.hovered = None
            self.hand_first = 0
            self.hand_hidden = False
            self.game.sort_hand(HUMAN, self.sort_mode)
            self.next_leader = 1 - self.next_leader
            who = ("you start" if self.game.turn == HUMAN
                   else "the computer starts")
            self._set_status(f"New hand of Burraco. {who}: draw a card, "
                             "or take the discard pile.")
            self.after_move()
            return
        self.game = Game(first_leader=self.next_leader)
        self.next_leader = 1 - self.next_leader
        who = "you lead" if self.game.leader == HUMAN else "the computer leads"
        self._set_status(f"New game. Trump: {self.game.trump_suit}. {who}.")
        self._advance()

    def _cancel_pending(self):
        if self._pending is not None:
            self.after_cancel(self._pending)
            self._pending = None

    def _advance(self):
        game = self.game
        assert game is not None

        if game.game_over:
            self.state = S_OVER
            self.render()
            self._finish_game()
            return

        if game.trick_complete:
            self.state = S_SHOW
            self.render()
            self._pending = self.after(TRICK_DELAY, self._resolve)
            trace(f"trick complete, resolving in {TRICK_DELAY} ms")
            return

        if game.turn == AI:
            self.state = S_AI
            self.render()
            self._pending = self.after(AI_DELAY, self._ai_move)
            trace(f"computer to play in {AI_DELAY} ms")
            return

        self.state = S_HUMAN
        trace(f"waiting for you: hand={[str(c) for c in game.hands[HUMAN]]}")
        if game.lead_card is None:
            self._set_status("Your turn: lead a card.")
        else:
            self._set_status(f"The computer led {game.lead_card}. Your answer?")
        self.render()

    def _ai_move(self):
        self._pending = None
        game = self.game
        assert game is not None
        started = time.time()
        index = ai.choose_card(game, self.difficulty)
        trace(f"computer chose in {1000 * (time.time() - started):.0f} ms"
              f" ({self.difficulty})")
        source_x = self._hand_x(len(game.hands[AI]), index)
        card = game.play_card(AI, index)
        self._queue_animation(source_x, AI_HAND_Y, AI)
        verb = "answers with" if game.trick_complete else "leads"
        self._set_status(f"The computer {verb} {card}.")
        self._advance()

    def _play_human(self, index: int):
        trace(f"play card {index + 1}: state={self.state}"
              f" overlay={self.overlay is not None}")
        if self.state != S_HUMAN or self.overlay is not None:
            trace("  ignored: not your turn")
            return
        game = self.game
        assert game is not None
        if index >= len(game.hands[HUMAN]):
            return
        source_x = self._hand_x(len(game.hands[HUMAN]), index)
        self.hover.discard(index)
        game.play_card(HUMAN, index)
        self._queue_animation(source_x, PLAYER_HAND_Y, HUMAN)
        self._advance()

    def _on_canvas_click(self, event):
        """Every click on the table lands here.

        Which card was clicked comes from the same fixed-geometry hit test the
        hover uses, not from where the card item currently sits. Relying on the
        item left a dead strip: hovering lifted the card out of the bottom of
        its own hover zone, so a click there hit bare felt and did nothing.
        """
        if self.game_kind == ui.BURRACO:
            return          # every Burraco control is an item binding of its own
        spent = (self._click_serial is not None
                 and getattr(event, "serial", None) == self._click_serial)
        index = self._hand_slot_at(event.x, event.y)
        trace(f"click at ({event.x},{event.y}): state={self.state}"
              f" card={index} spent={spent}"
              f" pending={self._pending is not None}"
              f" overlay={self.overlay is not None}")
        if spent or self.overlay is not None:
            return
        if index is not None:
            self._play_human(index)
            return
        self._skip_wait()

    def _skip_wait(self, _event=None):
        """Don't make the player wait out a pause they have already read."""
        if self._pending is None:
            return
        if self.state == S_SHOW:
            self._cancel_pending()
            self._resolve()
        elif self.state == S_AI:
            self._cancel_pending()
            self._ai_move()

    def _resolve(self):
        trace("resolving the trick")
        self._pending = None
        game = self.game
        assert game is not None
        result = game.resolve_trick()
        who = "You take" if result.winner == HUMAN else "The computer takes"
        self._set_status(f"{who} the trick: +{result.points} points.")
        self._log_trick(result)
        self._advance()

    def _finish_game(self):
        game = self.game
        assert game is not None
        you, them = game.points[HUMAN], game.points[AI]
        winner = game.final_winner()

        if not self._recorded:
            self._recorded = True
            self.records.add_match(
                self.player, you, them, self.difficulty,
                "you" if game.first_leader == HUMAN else "computer")
            self.render()

        if winner is None:
            title, msg = "Draw", f"Draw, {you} to {them}."
        elif winner == HUMAN:
            title, msg = "You win!", f"You win {you} to {them}."
        else:
            title, msg = "You lose", f"The computer wins {them} to {you}."

        stats = self.records.stats(self.player)
        self._set_status(f"{msg}  Press 'New game' to play again.")
        detail = (f"{msg}\n\nTricks: {game.tricks_played}   "
                  f"Difficulty: {ai.LEVEL_LABELS[self.difficulty]}\n\n"
                  f"{self.player}: {stats.summary()}\n"
                  f"Streak: {stats.streak_text()}\n\n"
                  f"Saved to {self.records.path}\nand the matching .txt")
        self.show_overlay(title, detail, actions=(
            ("New game", self._overlay_new_game),
            ("Statistics", self.show_statistics),
            ("Menu", self._overlay_menu)))
        if self.stats_window is not None:
            self._refresh_stats_window()

    def _overlay_new_game(self):
        self.overlay = None
        self.new_game()

    def _overlay_next_hand(self):
        """Carry the running score into another hand of the same match."""
        self.overlay = None
        self.new_game()

    def _overlay_new_match(self):
        self.overlay = None
        self.new_match()

    def _overlay_menu(self):
        self.overlay = None
        self.show_menu()

    # --- drawing ----------------------------------------------------------

    def render(self):
        self.canvas.delete("all")
        self._buttons.clear()

        if self.state == S_MENU:
            self._draw_menu()
        elif self.game_kind == ui.BURRACO:
            burraco_view.draw(self)
            burraco_view.draw_panel(self)
            self._draw_status()
        else:
            game = self.game
            assert game is not None
            self._draw_felt()
            self._draw_ai_hand(game)
            self._draw_stock(game)
            self._draw_table(game)
            self._draw_player_hand(game)
            self._draw_panel(game)
            self._draw_status()
            self._start_animation()

        if self.overlay is not None:
            self._draw_overlay()

    def _draw_felt(self):
        c = self.canvas
        c.create_rectangle(0, 0, TABLE_W, TABLE_H, fill=FELT, outline="")
        c.create_oval(CENTER_X - 200, TABLE_Y - 48, CENTER_X + 200,
                      TABLE_Y + CARD_H + 110, fill=FELT_DARK, outline="")
        c.create_text(TABLE_W - 14, AI_HAND_Y + CARD_H / 2, text="COMPUTER",
                      fill=FELT_EDGE, font=("Helvetica", 11, "bold"),
                      anchor="e", angle=90)
        c.create_text(TABLE_W - 14, PLAYER_HAND_Y + CARD_H / 2, text="YOU",
                      fill=FELT_EDGE, font=("Helvetica", 11, "bold"),
                      anchor="e", angle=90)

    def _hand_x(self, count: int, index: int) -> float:
        return hand_x(count, index)

    def _table_slot(self, player: int) -> tuple[float, float]:
        return table_slot(player)

    def _draw_ai_hand(self, game):
        for i in range(len(game.hands[AI])):
            cardart.draw_card_back(self.canvas, self._hand_x(len(game.hands[AI]), i),
                                   AI_HAND_Y, CARD_W, CARD_H)

    def _draw_stock(self, game):
        c = self.canvas
        stock_x = STOCK_X + CARD_W + 12

        if game.trump_card is not None:
            cardart.draw_card(c, STOCK_X, STOCK_Y, CARD_W, CARD_H, game.trump_card)
            c.create_text(STOCK_X + CARD_W / 2, STOCK_Y - 16, text="TRUMP",
                          fill=ACCENT, font=("Helvetica", 10, "bold"))
        else:
            cardart.draw_placeholder(c, STOCK_X, STOCK_Y, CARD_W, CARD_H,
                                     "trump\ndrawn")

        if game.stock:
            cardart.draw_card_back(c, stock_x, STOCK_Y, CARD_W, CARD_H)
            c.create_text(stock_x + CARD_W / 2, STOCK_Y + CARD_H + 18,
                          text=f"{len(game.stock)} in stock", fill=TEXT_DIM,
                          font=("Helvetica", 10))
        else:
            cardart.draw_placeholder(c, stock_x, STOCK_Y, CARD_W, CARD_H,
                                     "stock\nempty")

    def _draw_table(self, game):
        c = self.canvas
        played = {player for player, _card in game.table}
        for player in (AI, HUMAN):
            if player not in played:
                x, y = self._table_slot(player)
                cardart.draw_placeholder(c, x, y, CARD_W, CARD_H)
        if not game.table:
            return

        winner = game.trick_winner() if game.trick_complete else None
        last = len(game.table) - 1
        for order, (player, card) in enumerate(game.table):
            x, y = self._table_slot(player)
            # A stable tag per seat, plus the throwaway one the slide moves.
            tags = [f"table{player}"]
            if order == last and self._anim_offset and self._anim_tag:
                tags.append(self._anim_tag)
            cardart.draw_card(c, x, y, CARD_W, CARD_H, card, tags=tuple(tags),
                              highlight=(player == winner))
            if order == 0 and not game.trick_complete:
                c.create_text(x + CARD_W / 2, y - 14, text="led",
                              fill=TEXT_DIM, font=("Helvetica", 10))

    def _draw_player_hand(self, game):
        c = self.canvas
        hand = game.hands[HUMAN]
        playable = self.state == S_HUMAN
        for i, card in enumerate(hand):
            x = self._hand_x(len(hand), i)
            y = PLAYER_HAND_Y - (LIFT if i in self.hover else 0)
            tag = f"hand{i}"
            # Hovering lifts the card; the gold frame is reserved for the
            # card that wins a trick, so the two signals never look alike.
            cardart.draw_card(c, x, y, CARD_W, CARD_H, card, tags=(tag,))
            c.create_text(x + CARD_W / 2, PLAYER_HAND_Y + CARD_H + 16,
                          text=str(i + 1), fill=TEXT_DIM,
                          font=("Helvetica", 10, "bold"))
        if not playable:
            self.hover.clear()

    def _bind_click(self, tag: str, command):
        """Bind a click on a canvas item so it cannot also act on the table.

        Tk runs the item binding first and the canvas-wide binding after, and
        an item binding cannot stop it — a "break" return is ignored there.
        Nor can the canvas handler work out afterwards what was clicked: the
        item handler has already redrawn the canvas by then. So the two are
        paired by the event's serial number, which Tk gives identically to
        both handlers of one click and never repeats for another.

        This is not hypothetical tidiness. Pressing Start on the menu is one
        click whose position falls straight into the hand area of the table
        that replaces it, so without the pairing it would deal a game and
        immediately play a card. A sticky "already handled" flag also worked,
        until a handler that blocks — a modal prompt — meant the canvas
        handler never ran to clear it, and the next click was swallowed.
        """
        def handler(event=None):
            self._click_serial = getattr(event, "serial", None)
            command()

        self.canvas.tag_bind(tag, "<Button-1>", handler)

    # --- hover ------------------------------------------------------------
    #
    # Hover is worked out from the pointer position against the fixed slot
    # geometry, never from Tk's per-item <Enter>/<Leave>. Those bindings
    # locked the window up: lifting a card by LIFT pixels moved it out from
    # under a pointer resting near its bottom edge, Tk sent <Leave>, the card
    # dropped back under the pointer, <Enter> fired, and the two chased each
    # other forever at full CPU while real clicks never got processed. The
    # hit test below cannot do that, because its answer does not depend on
    # where the card has been moved to.

    def _hand_slot_at(self, x: float, y: float) -> int | None:
        """The pointer's card, or None. The sums live in layout.py."""
        game = self.game
        if game is None or self.state != S_HUMAN or self.overlay is not None:
            return None
        if self.game_kind != ui.BRISCOLA:
            return None     # Burraco lays its hand out differently entirely
        return hand_slot_at(x, y, len(game.hands[HUMAN]))

    def _on_motion(self, event):
        if self.game_kind == ui.BURRACO and self.state == S_HUMAN:
            burraco_view.on_motion(self, event.x, event.y)
            return
        self._set_hover_index(self._hand_slot_at(event.x, event.y))

    def _on_wheel(self, event):
        """The wheel walks along a Burraco hand too wide to show at once."""
        if self.game_kind != ui.BURRACO or self.state != S_HUMAN:
            return
        burraco_view.scroll_hand(self, -1 if event.delta > 0 else 1)

    def _on_canvas_leave(self, _event=None):
        self._set_hover_index(None)

    def _set_hover_index(self, index: int | None):
        if self.hover == ({index} if index is not None else set()):
            return
        for other in list(self.hover):
            if other != index:
                self.canvas.move(f"hand{other}", 0, LIFT)
                self.hover.discard(other)
        if index is not None:
            self.canvas.move(f"hand{index}", 0, -LIFT)
            self.hover.add(index)
        self.canvas.config(cursor="hand2" if index is not None else "")

    # --- played-card animation --------------------------------------------

    def _queue_animation(self, source_x, source_y, player):
        """Slide the card just played from the hand to its slot on the table."""
        target_x, target_y = self._table_slot(player)
        # Every slide gets its own tag: a leftover step from an earlier slide
        # would otherwise keep nudging whatever card is tagged now.
        self._anim_seq += 1
        self._anim_tag = f"anim{self._anim_seq}"
        self._anim_offset = (source_x - target_x, source_y - target_y)

    def _start_animation(self):
        if not self._anim_offset or self._anim_tag is None:
            return
        dx, dy = self._anim_offset
        tag = self._anim_tag
        self._anim_offset = None
        self.canvas.move(tag, dx, dy)
        self.canvas.tag_raise(tag)
        self._animate(tag, dx, dy, ANIM_STEPS)

    def _animate(self, tag, dx, dy, left, handle=None):
        # Two slides can overlap, so the pending steps are a set: a single
        # slot let a second slide overwrite the first one's handle, leaving a
        # timer nobody could cancel.
        self._anim_afters.discard(handle)
        if left <= 0 or not self.canvas.find_withtag(tag):
            return
        self.canvas.move(tag, -dx / ANIM_STEPS, -dy / ANIM_STEPS)
        box = {}
        box["id"] = self.after(
            ANIM_MS, lambda: self._animate(tag, dx, dy, left - 1, box["id"]))
        self._anim_afters.add(box["id"])

    def destroy(self):
        """Cancel timers first: one firing after teardown makes Tk complain."""
        handles = list(self._anim_afters)
        self._anim_afters.clear()
        if self._pending is not None:
            handles.append(self._pending)
            self._pending = None
        for handle in handles:
            try:
                self.after_cancel(handle)
            except tk.TclError:
                pass
        super().destroy()

    # --- failure reporting -------------------------------------------------

    def report_callback_exception(self, exc, value, tb):
        """Never fail silently.

        Tk prints callback exceptions to stderr and carries on, but if one
        lands mid-move the game can be left with no timer armed and no way
        forward — which just looks like a freeze. So say so on screen too.
        """
        traceback.print_exception(exc, value, tb)
        self.status_text = (f"Something went wrong: {value!r}"
                            " - press N for a new game.")
        try:
            self.render()
        except Exception:       # the renderer itself is the likely suspect
            traceback.print_exc()

    # --- side panel -------------------------------------------------------

    def _draw_panel(self, game):
        c = self.canvas
        c.create_rectangle(PANEL_X, 0, WIN_W, TABLE_H, fill=PANEL_BG, outline="")

        c.create_text(CONTENT_X, 26, text="BRISCOLA", anchor="w", fill=ACCENT,
                      font=("Helvetica", 19, "bold"))
        c.create_text(CONTENT_X, 48, text="you vs. the computer", anchor="w",
                      fill=TEXT_DIM, font=("Helvetica", 11))
        self._panel_link(CONTENT_X + CONTENT_W, 26, "menu", "back",
                         self.show_menu)

        stats = self.records.stats(self.player)
        self._panel_box(66, 60)
        c.create_text(CONTENT_X + 10, 80, text="PLAYER", anchor="w",
                      fill=TEXT_DIM, font=("Helvetica", 9, "bold"))
        c.create_text(CONTENT_X + 10, 99, text=self.player, anchor="w",
                      fill=TEXT, font=("Helvetica", 14, "bold"))
        c.create_text(CONTENT_X + 10, 116, text=stats.summary(), anchor="w",
                      fill=TEXT_DIM, font=("Helvetica", 10))
        self._panel_link(CONTENT_X + CONTENT_W - 10, 80, "change",
                         "player", self._change_player)

        suit = game.trump_suit
        taken = " (drawn)" if game.trump_card is None else \
            f" - {RANK_NAMES[game.trump_card.rank]}"
        self._panel_box(134, 52)
        c.create_text(CONTENT_X + 10, 148, text="TRUMP SUIT", anchor="w",
                      fill=TEXT_DIM, font=("Helvetica", 9, "bold"))
        suit_color = cardart.SUIT_COLORS_ON_DARK[suit]
        c.create_text(CONTENT_X + 10, 168,
                      text=f"{suit}{taken}", anchor="w",
                      fill=suit_color, font=("Helvetica", 12, "bold"))
        cardart.emblem(c, suit, CONTENT_X + CONTENT_W - 22, 158, 22, suit_color)

        self._score_box(194, "YOU", game.points[HUMAN])
        self._score_box(244, "COMPUTER", game.points[AI])

        c.create_text(CONTENT_X, 300,
                      text=f"Cards to draw: {game.cards_left}", anchor="w",
                      fill=TEXT_DIM, font=("Helvetica", 10))
        c.create_text(CONTENT_X, 316,
                      text=f"Tricks: {game.tricks_played}/{TRICKS_PER_GAME}"
                           f"   Still in play: {TOTAL_POINTS - sum(game.points)}",
                      anchor="w", fill=TEXT_DIM, font=("Helvetica", 10))

        c.create_text(CONTENT_X, 340, text="LAST TRICKS", anchor="w", fill=TEXT,
                      font=("Helvetica", 9, "bold"))
        for row, (left, right) in enumerate(self.log_lines[:LOG_LINES]):
            y = 360 + row * 17
            c.create_text(CONTENT_X, y, text=left, anchor="w", fill=TEXT_DIM,
                          font=("Helvetica", 10))
            c.create_text(CONTENT_X + CONTENT_W, y, text=right, anchor="e",
                          fill=TEXT, font=("Helvetica", 10, "bold"))

        self._panel_button(612, "New game", "new",
                           self.new_match if self.game_kind == ui.BURRACO
                           else self.new_game, primary=True)
        self._panel_button(652, "Statistics", "stats", self.show_statistics)
        self._panel_button(688, f"Difficulty: {ai.LEVEL_LABELS[self.difficulty]}",
                           "level", self.cycle_difficulty)
        self._panel_button(724, "Rules", "rules", self.show_rules)

    def _panel_box(self, y, height, fill=PANEL_CARD):
        return cardart.round_rect(self.canvas, CONTENT_X, y,
                                  CONTENT_X + CONTENT_W, y + height, 8,
                                  fill=fill, outline="")

    def _score_box(self, y, title, points):
        c = self.canvas
        self._panel_box(y, 44)
        c.create_text(CONTENT_X + 10, y + 15, text=title, anchor="w",
                      fill=TEXT_DIM, font=("Helvetica", 9, "bold"))
        c.create_text(CONTENT_X + CONTENT_W - 10, y + 15, text=str(points),
                      anchor="e", fill=TEXT, font=("Helvetica", 15, "bold"))
        bar_x1, bar_x2 = CONTENT_X + 10, CONTENT_X + CONTENT_W - 10
        bar_y = y + 32
        c.create_rectangle(bar_x1, bar_y, bar_x2, bar_y + 6,
                           fill="#0d2b20", outline="")
        width = (bar_x2 - bar_x1) * min(points, TOTAL_POINTS) / TOTAL_POINTS
        if width > 0:
            color = ACCENT if points >= WINNING_POINTS else "#4ea87a"
            c.create_rectangle(bar_x1, bar_y, bar_x1 + width, bar_y + 6,
                               fill=color, outline="")
        mark = bar_x1 + (bar_x2 - bar_x1) * WINNING_POINTS / TOTAL_POINTS
        c.create_line(mark, bar_y - 2, mark, bar_y + 8, fill=TEXT, width=1)

    def _panel_button(self, y, text, key, command, primary=False, height=30):
        self._button(CONTENT_X, y, CONTENT_W, height, text, key, command,
                     primary=primary)

    def _button(self, x, y, w, h, text, key, command, primary=False,
                selected=False, font_size=12):
        c = self.canvas
        tag = f"btn_{key}"
        if primary:
            bg, fg, hover = ACCENT, ACCENT_TEXT, "#f7d375"
        elif selected:
            bg, fg, hover = PANEL_CARD_HI, ACCENT, PANEL_CARD_HI
        else:
            bg, fg, hover = PANEL_CARD, TEXT, PANEL_CARD_HI
        rect = cardart.round_rect(c, x, y, x + w, y + h, 8, fill=bg,
                                  outline=ACCENT if selected else "",
                                  width=2 if selected else 1, tags=(tag,))
        c.create_text(x + w / 2, y + h / 2, text=text, fill=fg,
                      font=("Helvetica", font_size,
                            "bold" if primary or selected else "normal"),
                      tags=(tag,))
        self._bind_click(tag, command)
        c.tag_bind(tag, "<Enter>", lambda _e: self._button_hover(rect, hover, True))
        c.tag_bind(tag, "<Leave>", lambda _e: self._button_hover(rect, bg, False))
        self._buttons[key] = (rect, command)
        return rect

    # --- opening screen ---------------------------------------------------

    def _draw_menu(self):
        c = self.canvas
        c.create_rectangle(0, 0, WIN_W, WIN_H, fill=FELT, outline="")
        c.create_oval(MENU_CX - 520, -200, MENU_CX + 520, 366,
                      fill=FELT_DARK, outline="")

        self._draw_menu_fan()

        # The title follows the choice below it: this menu deals two games.
        c.create_text(MENU_CX, 300, text=ui.GAME_LABELS[self.game_kind].upper(),
                      fill=ACCENT, font=("Helvetica", 44, "bold"))
        c.create_text(MENU_CX, 338, text="you vs. the computer",
                      fill=TEXT, font=("Helvetica", 13))

        left = MENU_CX - MENU_COL_W / 2
        stats = self.records.stats(self.player)
        cardart.round_rect(c, left, 372, left + MENU_COL_W, 434, 8,
                           fill=PANEL_CARD, outline="")
        c.create_text(left + 14, 390, text="PLAYER", anchor="w", fill=TEXT_DIM,
                      font=("Helvetica", 9, "bold"))
        c.create_text(left + 14, 409, text=self.player, anchor="w", fill=TEXT,
                      font=("Helvetica", 15, "bold"))
        c.create_text(left + 14, 426, text=stats.summary(), anchor="w",
                      fill=TEXT_DIM, font=("Helvetica", 10))
        self._panel_link(left + MENU_COL_W - 14, 390, "change", "menu_player",
                         self._change_player)

        c.create_text(left, 458, text="GAME", anchor="w", fill=TEXT_DIM,
                      font=("Helvetica", 9, "bold"))
        game_w = (MENU_COL_W - 8) / 2
        for index, kind in enumerate(ui.GAMES):
            self._button(left + index * (game_w + 8), 468, game_w, 34,
                         ui.GAME_LABELS[kind], f"game_{kind}",
                         lambda kind=kind: self.set_game(kind),
                         selected=(kind == self.game_kind))
        c.create_text(MENU_CX, 518, text=ui.GAME_BLURBS[self.game_kind],
                      fill=TEXT_DIM, font=("Helvetica", 11))

        if self.game_kind == ui.BURRACO:
            c.create_text(left, 540, text="PLAY UP TO", anchor="w",
                          fill=TEXT_DIM, font=("Helvetica", 9, "bold"))
            pill = (MENU_COL_W - 8 * 3) / 4
            for index, target in enumerate(burraco_engine.TARGETS):
                self._button(left + index * (pill + 8), 550, pill, 30,
                             "one hand" if target == 0 else str(target),
                             f"target_{target}",
                             lambda target=target: self.set_target(target),
                             selected=(target == self.target), font_size=11)
            difficulty_top = 594
        else:
            difficulty_top = 540
        c.create_text(left, difficulty_top, text="DIFFICULTY", anchor="w",
                      fill=TEXT_DIM, font=("Helvetica", 9, "bold"))
        levels = (ai.LEVELS if self.game_kind == ui.BRISCOLA
                  else burraco_view.burraco_ai.LEVELS)
        labels = (ai.LEVEL_LABELS if self.game_kind == ui.BRISCOLA
                  else burraco_view.burraco_ai.LEVEL_LABELS)
        pill_w = (MENU_COL_W - 8 * (len(levels) - 1)) / len(levels)
        for index, level in enumerate(levels):
            self._button(left + index * (pill_w + 8), difficulty_top + 10,
                         pill_w, 34,
                         labels[level], f"level_{level}",
                         lambda level=level: self.set_difficulty(level),
                         selected=(level == self.difficulty))
        c.create_text(MENU_CX, difficulty_top + 60,
                      text=LEVEL_BLURBS[self.difficulty],
                      fill=TEXT_DIM, font=("Helvetica", 11))

        self._button(left, 622, MENU_COL_W, 42, "Start game", "menu_start",
                     self.start_game, primary=True, font_size=15)
        half = (MENU_COL_W - 10) / 2
        self._button(left, 676, half, 30, "Statistics", "menu_stats",
                     self.show_statistics)
        self._button(left + half + 10, 676, half, 30, "Rules", "menu_rules",
                     self.show_rules)

        c.create_text(MENU_CX, WIN_H - 26,
                      text="Enter = start    D = difficulty    "
                           "S = statistics    R = rules",
                      fill=TEXT_DIM, font=("Helvetica", 10))

    def _draw_menu_fan(self):
        """A spread of cards as the header image."""
        show = [Card(1, "Spades"), Card(KING, "Hearts"), Card(3, "Diamonds"),
                Card(QUEEN, "Clubs"), Card(7, "Hearts")]
        width, height, step = 116, 176, 84
        start = MENU_CX - (len(show) - 1) * step / 2 - width / 2
        for index, card in enumerate(show):
            lift = abs(index - (len(show) - 1) / 2) * 9
            cardart.draw_card(self.canvas, start + index * step, 70 + lift,
                              width, height, card)

    def _button_hover(self, item, color, entering):
        self.canvas.itemconfig(item, fill=color)
        self.canvas.config(cursor="hand2" if entering else "")

    def _panel_link(self, x, y, text, key, command):
        tag = f"link_{key}"
        item = self.canvas.create_text(x, y, text=text, anchor="e", fill=ACCENT,
                                       font=("Helvetica", 10, "underline"),
                                       tags=(tag,))
        self._bind_click(tag, command)
        self.canvas.tag_bind(tag, "<Enter>",
                             lambda _e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>",
                             lambda _e: self.canvas.config(cursor=""))
        return item

    def _draw_status(self):
        c = self.canvas
        c.create_rectangle(0, TABLE_H, WIN_W, WIN_H, fill=FELT_DARK, outline="")
        c.create_text(16, TABLE_H + STATUS_H / 2, text=self.status_text,
                      anchor="w", fill=TEXT, font=("Helvetica", 13))
        # render() runs before the timer is armed, so key off the state.
        if self.game_kind == ui.BURRACO:
            hint = ("click cards to pick them - H hide the hand"
                    " - N new hand - M menu - S stats")
        elif self.state in (S_SHOW, S_AI):
            hint = "click or space to carry on"
        else:
            hint = "keys: 1 2 3 play - N new - M menu - S stats - D difficulty"
        c.create_text(WIN_W - 16, TABLE_H + STATUS_H / 2, text=hint,
                      anchor="e", fill=TEXT_DIM, font=("Helvetica", 10))

    def _log_trick(self, result):
        game = self.game
        assert game is not None
        lead_player, lead_card = result.lead
        follow_card = result.follow[1]
        opener = "you" if lead_player == HUMAN else "pc"
        winner = "you" if result.winner == HUMAN else "pc"
        left = f"{game.tricks_played:>2}. {lead_card.short()} ({opener}) vs {follow_card.short()}"
        self.log_lines.insert(0, (left, f"{winner} +{result.points}"))

    def _set_status(self, text: str):
        self.status_text = text

    # --- dialogs ----------------------------------------------------------

    def _change_player(self):
        name = simpledialog.askstring("Player", "Player name:",
                                      initialvalue=self.player, parent=self)
        if name is None:
            return
        self.player = self.records.set_player(name)
        self.render()
        if self.stats_window is not None:
            self._refresh_stats_window()

    def cycle_difficulty(self):
        index = ai.LEVELS.index(self.difficulty)
        self.set_difficulty(ai.LEVELS[(index + 1) % len(ai.LEVELS)])

    # --- Burraco flow -----------------------------------------------------

    def say(self, text: str):
        """Tell the player why something did not work."""
        self._set_status(text)
        self.render()

    def note(self, text: str):
        """Record a move in the panel log."""
        self.log_lines.insert(0, (text, ""))
        self._set_status(text)

    def after_move(self):
        """Redraw, then hand over to the computer if it is its turn."""
        self._cancel_pending()
        if self.game.game_over:
            self.state = S_OVER
            self.render()
            self._finish_burraco()
            return
        if self.game.turn == AI:
            self.state = S_AI
            self.render()
            self._pending = self.after(AI_DELAY, self._burraco_ai_turn)
            return
        self.state = S_HUMAN
        self.render()

    def _burraco_ai_turn(self):
        self._pending = None
        burraco_view.computer_turn(self)
        if not self.game.game_over and self.game.turn == HUMAN:
            self._set_status("Your turn: draw a card, or take the pile.")
        self.after_move()

    def _finish_burraco(self):
        game = self.game
        match = self.match
        if not self._recorded:
            self._recorded = True
            match.add_hand(game.scores())
        you, them = game.scores()

        ended = ("someone closed the hand" if game.closed_by is not None
                 else "the stock ran out")
        hand = (f"This hand: {you} to {them}, because {ended}.\n"
                f"Match after {match.hands} hand"
                f"{'s' if match.hands != 1 else ''}: "
                f"{match.totals[HUMAN]} to {match.totals[AI]}.")

        if not match.over:
            ahead = match.leader()
            standing = ("level" if ahead is None
                        else "you are ahead" if ahead == HUMAN
                        else "the computer is ahead")
            self.show_overlay(
                "Hand over",
                f"{hand}\n\nPlaying to {match.target}: {standing}, "
                f"and you need {match.to_go(HUMAN)} more.",
                actions=(("Next hand", self._overlay_next_hand),
                         ("Statistics", self.show_statistics),
                         ("Menu", self._overlay_menu)))
            return

        self.records.add_match(
            self.player, match.totals[HUMAN], match.totals[AI],
            self.difficulty,
            "you" if game.first_player == HUMAN else "computer",
            game=ui.BURRACO)
        winner = match.winner()
        if winner is None:
            title = "Draw"
        elif winner == HUMAN:
            title = "You win the match!"
        else:
            title = "You lose the match"
        stats = self.records.stats(self.player)
        self.show_overlay(title, f"{hand}\n\n{self.player}: {stats.summary()}",
                          actions=(("New match", self._overlay_new_match),
                                   ("Statistics", self.show_statistics),
                                   ("Menu", self._overlay_menu)))

    def set_game(self, kind: str):
        """Pick which game the Start button will deal."""
        self.game_kind = kind
        if kind == ui.BURRACO and self.difficulty not in burraco_view.burraco_ai.LEVELS:
            self.difficulty = burraco_view.burraco_ai.NORMAL
        self.render()

    def set_target(self, target: int):
        """How many points a match is played to; zero means a single hand."""
        self.target = target
        self.render()

    def set_difficulty(self, level: str):
        self.difficulty = level
        self._set_status(f"Difficulty set to {ai.LEVEL_LABELS[level]}"
                         " - it applies from the next trick on.")
        self.render()

    # --- in-window dialogs ------------------------------------------------

    def show_overlay(self, title: str, body: str, actions=()):
        """A panel drawn inside the window.

        Native message boxes can open behind the main window on macOS, which
        looks exactly like a frozen game, so every message the game needs to
        show is drawn on the canvas instead.
        """
        self.overlay = (title, body, tuple(actions))
        self.render()

    def close_overlay(self):
        if self.overlay is not None:
            self.overlay = None
            self.render()

    def _draw_overlay(self):
        title, body, actions = self.overlay
        c = self.canvas

        # Lay the text out off-screen first: measuring beats guessing at the
        # height, which left a gap between the text and the buttons.
        text = c.create_text(0, -2000, text=body, anchor="nw", fill=TEXT,
                             font=("Helvetica", 12), justify="left")
        left, top, right, bottom = c.bbox(text)
        width = max(360, min(620, right - left + 56))
        height = 62 + (bottom - top) + 24 + 52
        x = MENU_CX - width / 2
        y = (WIN_H - height) / 2

        c.create_rectangle(0, 0, WIN_W, WIN_H, fill="#04241a",
                           stipple="gray50", outline="")
        cardart.round_rect(c, x, y, x + width, y + height, 12,
                           fill=PANEL_BG, outline=ACCENT, width=2)
        c.create_text(x + 28, y + 34, text=title, anchor="w", fill=ACCENT,
                      font=("Helvetica", 18, "bold"))
        c.coords(text, x + 28, y + 58)
        c.tag_raise(text)

        buttons = actions or (("Close", self.close_overlay),)
        button_w = min(180, (width - 56 - 10 * (len(buttons) - 1)) / len(buttons))
        total = len(buttons) * button_w + 10 * (len(buttons) - 1)
        start = MENU_CX - total / 2
        for index, (label, command) in enumerate(buttons):
            self._button(start + index * (button_w + 10),
                         y + height - 52, button_w, 36, label,
                         f"overlay_{index}", command,
                         primary=(index == 0))

    def show_rules(self):
        self.show_overlay(
            "Rules",
            "40 cards, 20 tricks, 120 points in total: first to 61 wins,\n"
            "60-60 is a draw.\n\n"
            "Points: Ace 11, Three 10, King 4, Queen 3, Jack 2, rest 0.\n"
            "Strength in the same suit: A > 3 > K > Q > J > 7 > 6 > 5 > 4 > 2.\n"
            "A French deck without the 8, 9 and 10: the queen stands in for\n"
            "the cavallo of an Italian deck.\n\n"
            "Following suit is not required. The responder only wins with a\n"
            "stronger card of the same suit, or with a trump against a\n"
            "non-trump lead. The winner draws first and leads the next trick.\n\n"
            "Full rules: https://en.wikipedia.org/wiki/Briscola\n\n"
            "Controls: click a card, or press 1 / 2 / 3.")

    def show_statistics(self):
        if self.stats_window is not None:
            self.stats_window.lift()
            return
        window = tk.Toplevel(self)
        window.title(f"Statistics - {self.player}")
        window.configure(bg=PANEL_BG)
        window.resizable(False, False)
        canvas = tk.Canvas(window, width=STATS_W, height=STATS_H, bg=PANEL_BG,
                           highlightthickness=0)
        canvas.pack()
        window.bind("<Escape>", lambda _e: self._close_stats_window())
        window.protocol("WM_DELETE_WINDOW", self._close_stats_window)
        self.stats_window = window
        self.stats_canvas = canvas
        self._refresh_stats_window()

    def _close_stats_window(self):
        if self.stats_window is not None:
            self.stats_window.destroy()
            self.stats_window = None

    def _refresh_stats_window(self):
        draw_statistics(self.stats_canvas, self.player,
                        self.records.stats(self.player),
                        self.records.matches(self.player),
                        self.records.path, self.records.text_path)

    # --- input ------------------------------------------------------------

    def _on_key(self, event):
        char = event.char.lower()
        keysym = getattr(event, "keysym", "")
        if self.overlay is not None:
            if keysym in ("Escape", "Return", "KP_Enter") or char == " ":
                self.close_overlay()
            return
        if self.state == S_MENU:
            if keysym in ("Return", "KP_Enter") or char == " ":
                self.start_game()
            elif char == "d":
                self.cycle_difficulty()
            elif char == "s":
                self.show_statistics()
            elif char == "r":
                self.show_rules()
            return

        if char in "123" and self.game_kind == ui.BRISCOLA:
            self._play_human(int(char) - 1)
        elif char == " " or keysym in ("Return", "KP_Enter"):
            self._skip_wait()
        elif char == "n":
            self.new_match() if self.game_kind == ui.BURRACO else self.new_game()
        elif char == "h" and self.game_kind == ui.BURRACO:
            burraco_view.toggle_hand(self)
        elif char == "m":
            self.show_menu()
        elif char == "s":
            self.show_statistics()
        elif char == "d":
            self.cycle_difficulty()
        elif char == "r":
            self.show_rules()


# --- statistics view ------------------------------------------------------

STATS_W, STATS_H = 560, 540
STATS_ROWS = 12


def draw_statistics(canvas, player, stats, matches, json_path, text_path):
    """Draw the statistics window; kept module level so tools can reuse it."""
    canvas.delete("all")
    canvas.create_rectangle(0, 0, STATS_W, STATS_H, fill=PANEL_BG, outline="")
    canvas.create_text(24, 30, text="STATISTICS", anchor="w", fill=ACCENT,
                       font=("Helvetica", 18, "bold"))
    canvas.create_text(STATS_W - 24, 30, text=player, anchor="e", fill=TEXT,
                       font=("Helvetica", 14, "bold"))

    tiles = [
        ("Played", str(stats.played)),
        ("Won", str(stats.won)),
        ("Lost", str(stats.lost)),
        ("Win rate", f"{stats.win_rate:.0f}%"),
        ("Avg points", f"{stats.avg_points:.0f}"),
        ("Best score", str(stats.best)),
    ]
    tile_w = (STATS_W - 48 - 5 * 8) / 6
    for i, (title, value) in enumerate(tiles):
        x = 24 + i * (tile_w + 8)
        cardart.round_rect(canvas, x, 56, x + tile_w, 116, 8,
                           fill=PANEL_CARD, outline="")
        canvas.create_text(x + tile_w / 2, 74, text=title, fill=TEXT_DIM,
                           font=("Helvetica", 9))
        canvas.create_text(x + tile_w / 2, 98, text=value, fill=TEXT,
                           font=("Helvetica", 17, "bold"))

    canvas.create_text(24, 138, text=f"Current streak: {stats.streak_text()}",
                       anchor="w", fill=TEXT, font=("Helvetica", 11))
    canvas.create_text(24, 158,
                       text=f"Best winning streak: {stats.best_streak}",
                       anchor="w", fill=TEXT_DIM, font=("Helvetica", 11))

    by_level = "  ".join(
        f"{ai.LEVEL_LABELS.get(level, level)} {won}/{total}"
        for level, (won, total) in sorted(stats.by_difficulty.items())
    ) or "-"
    canvas.create_text(24, 178, text=f"Wins by difficulty: {by_level}",
                       anchor="w", fill=TEXT_DIM, font=("Helvetica", 11))

    canvas.create_text(24, 208, text="RECENT MATCHES", anchor="w", fill=TEXT,
                       font=("Helvetica", 9, "bold"))
    headers = [(24, "date"), (170, "result"), (250, "score"),
               (360, "difficulty"), (470, "opened")]
    for x, label in headers:
        canvas.create_text(x, 228, text=label, anchor="w", fill=TEXT_DIM,
                           font=("Helvetica", 9))

    recent = list(reversed(matches))[:STATS_ROWS]
    if not recent:
        canvas.create_text(24, 252, text="No games recorded yet.", anchor="w",
                           fill=TEXT_DIM, font=("Helvetica", 11))
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
                 (470, match.opened, TEXT_DIM)]
        for x, text, fill in cells:
            canvas.create_text(x, y, text=text, anchor="w", fill=fill,
                               font=("Helvetica", 10))

    canvas.create_text(24, STATS_H - 44, text="Records are saved to:", anchor="w",
                       fill=TEXT_DIM, font=("Helvetica", 9, "bold"))
    canvas.create_text(24, STATS_H - 28, text=str(json_path), anchor="w",
                       fill=TEXT_DIM, font=("Helvetica", 9))
    canvas.create_text(24, STATS_H - 14, text=str(text_path), anchor="w",
                       fill=TEXT_DIM, font=("Helvetica", 9))


def main():
    BriscolaApp().mainloop()
