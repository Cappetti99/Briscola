"""The game window: the menu, and the table of whichever game is running.

Everything is drawn on a single Canvas, so the whole window has a consistent
look on every platform and can be exported with `tools/screenshots.py`.
Briscola is drawn here; Burraco and Scopa draw through their own view
modules on the same canvas, and share this shell's menu and record file.
"""

import os
from .briscola.view import BriscolaView
from .features import AppFeatures
from .replay import Replay
from . import i18n
from tkinter import ttk
import time
import traceback
import tkinter as tk
from tkinter import simpledialog

from . import cardart, catalog, records, ui
from .burraco import engine as burraco_engine
from .burraco import view as burraco_view
from .scopa import ai as scopa_ai
from .scopa import engine as scopa_engine
from .scopa import view as scopa_view
from .tressette import ai as tressette_ai
from .tressette import engine as tressette_engine
from .tressette import view as tressette_view
from .briscola import ai
from .cards import KING, QUEEN, RANK_NAMES, Card
from .briscola.engine import AI, HUMAN, TOTAL_POINTS, TRICKS_PER_GAME, WINNING_POINTS, Game

from .ui import (ACCENT, ACCENT_TEXT, CONTENT_W, CONTENT_X, FELT, FELT_DARK,
                  FELT_EDGE, PANEL_BG, PANEL_CARD, PANEL_CARD_HI,
                  PANEL_X, STATUS_H, TABLE_H, TABLE_W, TEXT, TEXT_DIM,
                  WIN_H, WIN_W)

from .briscola.layout import (AI_HAND_Y, CARD_H, CARD_W, CENTER_X, LIFT,
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

def levels_for(kind: str):
    """The levels a game offers, and their labels."""
    spec = catalog.spec_for(kind)
    return spec.levels, spec.level_labels


def targets_for(kind: str):
    """The scores a match may be played to, or none for a one-off game."""
    return catalog.spec_for(kind).targets


class BriscolaApp(AppFeatures, BriscolaView, tk.Tk):
    def __init__(self, records_store: records.Records | None = None,
                 scale: float | None = None):
        super().__init__()
        # Drawing happens at the design size; the canvas is scaled to whatever
        # the screen can hold, so there is one set of coordinates to reason
        # about rather than a layout recomputed for every window size.
        ui.SCALE = scale if scale else ui.scale_for(self.winfo_screenwidth(),
                                                    self.winfo_screenheight())
        self.title("Card games")
        self.configure(bg=PANEL_BG)
        self.resizable(False, False)

        self.records = records_store or records.Records()
        self.player = self.records.current_player
        self.difficulty = ai.NORMAL
        self.game_kind = ui.BRISCOLA
        self.selected: set[int] = set()
        # Scopa picks cards off the table, not out of the hand, so it needs a
        # selection of its own rather than sharing Burraco's.
        self.table_pick: set[int] = set()
        self.hovered: int | None = None
        self.sort_mode = "suit"
        self.hand_first = 0
        self.hand_hidden = False
        self.target = catalog.spec_for(ui.BURRACO).default_target
        self.match: burraco_engine.Match | None = None

        self.game: Game | None = None
        self.state = S_MENU
        self.next_leader = HUMAN
        self.hover: set[int] = set()
        self.log_lines: list[tuple[str, str]] = []
        self.status_text = ""
        self.stats_window: tk.Toplevel | None = None
        self._recorded = False
        self.replay = Replay(self.game_kind)
        self._pending: str | None = None
        self._anim_offset: tuple[float, float] | None = None
        self._anim_tag: str | None = None
        self._anim_seq = 0
        self._new_match = True
        self._anim_afters: set[str] = set()
        self._buttons: dict[str, tuple[int, callable]] = {}
        self._click_serial: int | None = None
        self.overlay: tuple[str, str, tuple] | None = None

        self.init_features()
        self.canvas = i18n.Canvas(self, translator=self.tr, width=int(WIN_W * ui.SCALE),
                                height=int(WIN_H * ui.SCALE), bg=FELT,
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
        self.checkpoint()
        self._cancel_pending()
        self.state = S_MENU
        self.overlay = None
        self.hover.clear()
        self._anim_offset = None
        self.render()

    def start_game(self):
        """Start from the menu, which always begins a fresh match.

        Without this, a match abandoned through the menu carried on when the
        next one was started — and after a change of game it carried on into
        a game it did not belong to, totals, target and all.
        """
        self._new_match = True
        self._training_used = False
        self.new_game()

    # --- game flow --------------------------------------------------------

    def new_match(self):
        """A fresh series, rather than the next hand of the one in progress."""
        self._new_match = True
        self._training_used = False
        self.new_game()

    def new_game(self):
        trace(f"new game: {self.game_kind}")
        if self.game_kind == ui.BRISCOLA:
            self._training_used = False
        self._cancel_pending()
        self.overlay = None
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
        if self.game_kind == ui.SCOPA:
            if self.match is None or self.match.over or self._new_match:
                self.match = scopa_engine.Match(target=self.target)
            self._new_match = False
            self.game = scopa_engine.Game(first_player=self.next_leader)
            self.hovered = None
            self.table_pick.clear()
            self.next_leader = 1 - self.next_leader
            who = ("you start" if self.game.turn == HUMAN
                   else "the computer starts")
            self._set_status(f"New hand of Scopa: {who}.")
            self.after_move()
            return
        if self.game_kind == ui.TRESSETTE:
            if self.match is None or self.match.over or self._new_match:
                self.match = tressette_engine.Match(target=self.target)
            self._new_match = False
            self.game = tressette_engine.Game(first_leader=self.next_leader)
            self.game.sort_hand(HUMAN, self.sort_mode)
            self.hovered = None
            self.next_leader = 1 - self.next_leader
            who = ("you lead" if self.game.turn == HUMAN
                   else "the computer leads")
            said = self._declared_line()
            self._set_status(f"New deal of Tressette. {who}.{said}")
            self.tressette_advance()
            return
        self.game = Game(first_leader=self.next_leader)
        self.next_leader = 1 - self.next_leader
        who = "you lead" if self.game.leader == HUMAN else "the computer leads"
        self._set_status(f"New game. Trump: {self.game.trump_suit}. {who}.")
        self._advance()

    def _cancel_pending(self):
        self.cancel_worker()
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
            self._pending = self.after(self.delay(TRICK_DELAY), self._resolve)
            trace(f"trick complete, resolving in {TRICK_DELAY} ms")
            return

        if game.turn == AI:
            self.state = S_AI
            self.render()
            self._pending = self.after(self.delay(AI_DELAY), self._ai_move)
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
        if self.difficulty == ai.HARD:
            level = self.difficulty
            self.compute_ai(lambda snapshot: ai.choose_card(snapshot, level), self._apply_briscola_ai)
            return
        index = ai.choose_card(game, self.difficulty)
        self._apply_briscola_ai(index)

    def _apply_briscola_ai(self, index):
        game = self.game
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
        x, y = ui.to_design(event.x, event.y)
        if self.game_kind == ui.SCOPA:
            if not spent and self.overlay is None:
                scopa_view.click_at(self, x, y)
            return
        if self.game_kind == ui.TRESSETTE:
            if not spent and self.overlay is None:
                if tressette_view.click_at(self, x, y):
                    self._skip_wait()
            return
        index = self._hand_slot_at(x, y)
        trace(f"click at ({x:.0f},{y:.0f}): state={self.state}"
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
        """Don't make the player wait out a pause they have already read.

        Each game arms its own timers, so the pause has to be finished by the
        function that armed it. Running Briscola's on a Burraco or Scopa table
        raised, and because the timer had already been cancelled the hand was
        left with nothing to carry it on - a freeze, from the seat.
        """
        if self._worker_busy or self._pending is None:
            return
        if self.state == S_SHOW:
            finish = (self._tressette_resolve
                      if self.game_kind == ui.TRESSETTE else self._resolve)
        elif self.state == S_AI:
            finish = {ui.BURRACO: self._burraco_ai_turn,
                      ui.SCOPA: self._scopa_ai_turn,
                      ui.TRESSETTE: self._tressette_ai_move}.get(
                          self.game_kind, self._ai_move)
        else:
            return
        self._cancel_pending()
        finish()

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
            if not self._training_used:
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

        stats = self.records.stats(self.player, self.game_kind)
        self._set_status(f"{msg}  Press 'New game' to play again.")
        detail = (f"{msg}\n\nTricks: {game.tricks_played}   "
                  f"Difficulty: {ai.LEVEL_LABELS[self.difficulty]}\n\n"
                  f"{self.player}: {stats.summary()}\n"
                  f"Streak: {stats.streak_text()}\n\n"
                  + ("Training game: this match will not affect your statistics."
                     if self._training_used else
                     f"Saved to {self.records.path}\nand the matching .txt"))
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
        self.save_preferences()
        self.checkpoint()
        self.update_feature_labels()
        self.canvas.delete("all")
        self._buttons.clear()

        if self.state == S_MENU:
            self._draw_menu()
        elif self.game_kind == ui.BURRACO:
            burraco_view.draw(self)
            burraco_view.draw_panel(self)
            self._draw_status()
        elif self.game_kind == ui.SCOPA:
            scopa_view.draw(self)
            scopa_view.draw_panel(self)
            self._draw_status()
        elif self.game_kind == ui.TRESSETTE:
            tressette_view.draw(self)
            tressette_view.draw_panel(self)
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

        if ui.SCALE != 1.0:
            self.canvas.scale("all", 0, 0, ui.SCALE, ui.SCALE)


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
        if self.state == S_HUMAN and self.game_kind == ui.BURRACO:
            burraco_view.on_motion(self, *ui.to_design(event.x, event.y))
            return
        if self.state == S_HUMAN and self.game_kind == ui.SCOPA:
            scopa_view.on_motion(self, *ui.to_design(event.x, event.y))
            return
        if self.state == S_HUMAN and self.game_kind == ui.TRESSETTE:
            tressette_view.on_motion(self, *ui.to_design(event.x, event.y))
            return
        self._set_hover_index(self._hand_slot_at(*ui.to_design(event.x, event.y)))

    def _on_wheel(self, event):
        """The wheel walks along a Burraco hand too wide to show at once."""
        if self.game_kind != ui.BURRACO or self.state != S_HUMAN:
            return
        burraco_view.scroll_hand(self, -1 if event.delta > 0 else 1)

    def _on_canvas_leave(self, _event=None):
        if self.game_kind == ui.TRESSETTE:
            tressette_view.on_motion(self, -1, -1)
            return
        if self.game_kind == ui.SCOPA:
            # Off the canvas nothing is under the pointer, so put the card
            # back down rather than leaving it standing up on its own.
            scopa_view.on_motion(self, -1, -1)
            return
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
            self.delay(ANIM_MS), lambda: self._animate(tag, dx, dy, left - 1, box["id"]))
        self._anim_afters.add(box["id"])

    def destroy(self):
        """Cancel timers first: one firing after teardown makes Tk complain."""
        self.checkpoint()
        self.cancel_worker()
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


    def _panel_box(self, y, height, fill=PANEL_CARD):
        return cardart.round_rect(self.canvas, CONTENT_X, y,
                                  CONTENT_X + CONTENT_W, y + height, 8,
                                  fill=fill, outline="")

    def _score_box(self, y, title, points):
        c = self.canvas
        self._panel_box(y, 44)
        c.create_text(CONTENT_X + 10, y + 15, text=title, anchor="w",
                      fill=TEXT_DIM, font=ui.font(9, "bold"))
        c.create_text(CONTENT_X + CONTENT_W - 10, y + 15, text=str(points),
                      anchor="e", fill=TEXT, font=ui.font(15, "bold"))
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
                      font=ui.font(font_size,
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
                      fill=ACCENT, font=ui.font(44, "bold"))
        c.create_text(MENU_CX, 338, text="you vs. the computer",
                      fill=TEXT, font=ui.font(13))

        left = MENU_CX - MENU_COL_W / 2
        stats = self.records.stats(self.player, self.game_kind)
        cardart.round_rect(c, left, 372, left + MENU_COL_W, 434, 8,
                           fill=PANEL_CARD, outline="")
        c.create_text(left + 14, 390, text="PLAYER", anchor="w", fill=TEXT_DIM,
                      font=ui.font(9, "bold"))
        c.create_text(left + 14, 409, text=self.player, anchor="w", fill=TEXT,
                      font=ui.font(15, "bold"))
        c.create_text(left + 14, 426, text=stats.summary(), anchor="w",
                      fill=TEXT_DIM, font=ui.font(10))
        self._panel_link(left + MENU_COL_W - 14, 390, "change", "menu_player",
                         self._change_player)

        c.create_text(left, 458, text="GAME", anchor="w", fill=TEXT_DIM,
                      font=ui.font(9, "bold"))
        game_w = (MENU_COL_W - 8 * (len(ui.GAMES) - 1)) / len(ui.GAMES)
        for index, kind in enumerate(ui.GAMES):
            self._button(left + index * (game_w + 8), 468, game_w, 34,
                         ui.GAME_LABELS[kind], f"game_{kind}",
                         lambda kind=kind: self.set_game(kind),
                         selected=(kind == self.game_kind))
        c.create_text(MENU_CX, 518, text=ui.GAME_BLURBS[self.game_kind],
                      fill=TEXT_DIM, font=ui.font(11))

        targets = targets_for(self.game_kind)
        if targets:
            c.create_text(left, 540, text="PLAY UP TO", anchor="w",
                          fill=TEXT_DIM, font=ui.font(9, "bold"))
            pill = (MENU_COL_W - 8 * (len(targets) - 1)) / len(targets)
            for index, target in enumerate(targets):
                self._button(left + index * (pill + 8), 550, pill, 30,
                             "one hand" if target == 0 else str(target),
                             f"target_{target}",
                             lambda target=target: self.set_target(target),
                             selected=(target == self.target), font_size=11)
            difficulty_top = 594
        else:
            difficulty_top = 540
        c.create_text(left, difficulty_top, text="DIFFICULTY", anchor="w",
                      fill=TEXT_DIM, font=ui.font(9, "bold"))
        levels, labels = levels_for(self.game_kind)
        pill_w = (MENU_COL_W - 8 * (len(levels) - 1)) / len(levels)
        for index, level in enumerate(levels):
            self._button(left + index * (pill_w + 8), difficulty_top + 10,
                         pill_w, 34,
                         labels[level], f"level_{level}",
                         lambda level=level: self.set_difficulty(level),
                         selected=(level == self.difficulty))
        c.create_text(MENU_CX, difficulty_top + 60,
                      text=catalog.spec_for(self.game_kind).level_blurbs[self.difficulty],
                      fill=TEXT_DIM, font=ui.font(11))

        # The buttons follow the difficulty row rather than sitting at a fixed
        # height: Burraco adds a row above them, and a fixed height put the
        # Start button straight on top of the difficulty pills.
        start_top = difficulty_top + 82
        self._button(left, start_top, MENU_COL_W, 42, "Start game",
                     "menu_start", self.start_game, primary=True, font_size=15)
        half = (MENU_COL_W - 10) / 2
        self._button(left, start_top + 52, half, 30, "Statistics",
                     "menu_stats", self.show_statistics)
        self._button(left + half + 10, start_top + 52, half, 30, "Rules",
                     "menu_rules", self.show_rules)

        c.create_text(MENU_CX, WIN_H - 26,
                      text="Enter = start    D = difficulty    "
                           "S = statistics    R = rules",
                      fill=TEXT_DIM, font=ui.font(10))

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
                                       font=ui.font(10, "underline"),
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
                      anchor="w", fill=TEXT, font=ui.font(13))
        # render() runs before the timer is armed, so key off the state.
        if self.game_kind == ui.BURRACO:
            hint = ("click cards to pick them - H hide the hand"
                    " - N new hand - M menu - S stats")
        elif self.state in (S_SHOW, S_AI):
            hint = "click or space to carry on"
        elif self.game_kind == ui.TRESSETTE:
            # Ten cards need ten keys, and the tenth of them is the zero.
            hint = "keys: 1-9 and 0 play - N new - M menu - S stats"
        else:
            hint = "keys: 1 2 3 play - N new - M menu - S stats - D difficulty"
        c.create_text(WIN_W - 16, TABLE_H + STATUS_H / 2, text=hint,
                      anchor="e", fill=TEXT_DIM, font=ui.font(10))

    def _log_trick(self, result):
        game = self.game
        assert game is not None
        lead_player, lead_card = result.lead
        follow_card = result.follow[1]
        opener = "you" if lead_player == HUMAN else "pc"
        winner = "you" if result.winner == HUMAN else "pc"
        left = f"{game.tricks_played:>2}. {lead_card.short()} ({opener}) vs {follow_card.short()}"
        self.log_lines.insert(0, (left, f"{winner} +{result.points}"))
        self.record_public_event("trick", result.winner, left,
                                (lead_card.short(), follow_card.short()), result.points)

    def _set_status(self, text: str):
        self.status_text = text

    # --- dialogs ----------------------------------------------------------

    def _change_player(self):
        name = simpledialog.askstring(self.tr("Player"), self.tr("Player name:"),
                                      initialvalue=self.player, parent=self)
        if name is None:
            return
        self.player = self.records.set_player(name)
        self.render()
        if self.stats_window is not None:
            self._refresh_stats_window()

    def cycle_difficulty(self):
        levels, _labels = levels_for(self.game_kind)
        index = levels.index(self.difficulty) if self.difficulty in levels else -1
        self.set_difficulty(levels[(index + 1) % len(levels)])

    # --- Burraco flow -----------------------------------------------------

    def say(self, text: str):
        """Tell the player why something did not work."""
        self._set_status(text)
        self.render()

    def note(self, text: str):
        """Record a move in the panel log."""
        self.log_lines.insert(0, (text, ""))
        self.record_public_event("move", HUMAN if text.startswith("You") else AI, text)
        self._set_status(text)

    def after_move(self):
        """Redraw, then hand over to the computer if it is its turn.

        Shared by Burraco and Scopa: both are played a move at a time by
        whoever's turn it is, rather than in tricks the way Briscola is.
        """
        self._cancel_pending()
        scopa = self.game_kind == ui.SCOPA
        if self.game.game_over:
            self.state = S_OVER
            self.render()
            self._finish_scopa() if scopa else self._finish_burraco()
            return
        if self.game.turn == AI:
            self.state = S_AI
            self.render()
            self._pending = self.after(
                self.delay(AI_DELAY), self._scopa_ai_turn if scopa else self._burraco_ai_turn)
            return
        self.state = S_HUMAN
        self.render()

    def _burraco_ai_turn(self):
        self._pending = None
        burraco_view.computer_turn(self)
        if not self.game.game_over and self.game.turn == HUMAN:
            self._set_status("Your turn: draw a card, or take the pile.")
        self.after_move()

    def _scopa_ai_turn(self):
        self._pending = None
        if self.difficulty == scopa_ai.HARD:
            level = self.difficulty
            self.compute_ai(lambda snapshot: scopa_ai.choose_move(snapshot, AI, level), self._apply_scopa_ai)
            return
        scopa_view.computer_turn(self)
        self.after_move()

    def _apply_scopa_ai(self, move):
        index, taken = move
        play = self.game.play(AI, index, taken)
        self.note(scopa_ai.describe(play))
        if play.swept:
            self.note(f"The computer takes the {len(play.swept)} cards left over")
        self.after_move()

    def _finish_burraco(self):
        game = self.game
        ended = ("someone closed the hand" if game.closed_by is not None
                 else "the stock ran out")
        you, them = game.scores()
        self._finish_match_hand(f"This hand: {you} to {them}, "
                                f"because {ended}.", game.first_player)

    def _finish_scopa(self):
        game = self.game
        you, them = game.scores()
        self._finish_match_hand(f"This hand: {you} to {them}.\n"
                                f"{self._scopa_breakdown()}", game.first_player)

    def _scopa_breakdown(self):
        """Who took each of the five points, which is the whole score."""
        mine, theirs = self.game.tallies()
        parts = []
        for (name, ours), (_name, yours) in zip(mine.lines(), theirs.lines()):
            if name == "Scope":
                parts.append(f"scope {ours}-{yours}")
            elif ours:
                parts.append(f"{name.lower()}: you")
            elif yours:
                parts.append(f"{name.lower()}: the computer")
            else:
                parts.append(f"{name.lower()}: level")
        return ", ".join(parts) + "."

    def _finish_match_hand(self, headline: str, first: int):
        """The end of a hand of a game played as a match, and what follows.

        Burraco and Scopa both run a series of hands to a target, so the
        overlay, the record and the choice of what to do next are one piece
        of code with a different sentence at the top.
        """
        match = self.match
        newly_recorded = not self._recorded
        if newly_recorded:
            self._recorded = True
            match.add_hand(self.game.scores())

        hand = (f"{headline}\n"
                f"Match after {match.hands} hand"
                f"{'s' if match.hands != 1 else ''}: "
                f"{match.totals[HUMAN]} to {match.totals[AI]}.")

        if self._training_used:
            hand += "\n\nTraining game: this match will not affect your statistics."

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

        if newly_recorded and not self._training_used:
            self.records.add_match(
                self.player, match.totals[HUMAN], match.totals[AI],
                self.difficulty, "you" if first == HUMAN else "computer",
                game=self.game_kind)
        winner = match.winner()
        if winner is None:
            title = "Draw"
        elif winner == HUMAN:
            title = "You win the match!"
        else:
            title = "You lose the match"
        stats = self.records.stats(self.player, self.game_kind)
        self.show_overlay(title, f"{hand}\n\n{self.player}: {stats.summary()}",
                          actions=(("New match", self._overlay_new_match),
                                   ("Statistics", self.show_statistics),
                                   ("Menu", self._overlay_menu)))

    # --- Tressette flow ---------------------------------------------------
    #
    # Tressette is played in tricks like Briscola, so it has the same three
    # states and the same two pauses, both of which a click skips.

    def tressette_advance(self):
        """Move the deal on: resolve, let the computer play, or wait for you."""
        game = self.game
        self._cancel_pending()
        if game.game_over:
            self.state = S_OVER
            self.render()
            self._finish_tressette()
            return
        if game.trick_complete:
            self.state = S_SHOW
            self.render()
            self._pending = self.after(self.delay(TRICK_DELAY), self._tressette_resolve)
            return
        if game.turn == AI:
            self.state = S_AI
            self.render()
            self._pending = self.after(self.delay(AI_DELAY), self._tressette_ai_move)
            return
        self.state = S_HUMAN
        if game.lead_card is None:
            self._set_status("Your turn: lead a card.")
        else:
            self._set_status(f"The computer led {game.lead_card}. Your answer?")
        self.render()

    def _tressette_ai_move(self):
        self._pending = None
        if self.difficulty == tressette_ai.HARD:
            level = self.difficulty
            self.compute_ai(lambda snapshot: tressette_ai.choose_card(snapshot, AI, level), self._apply_tressette_ai)
            return
        index = tressette_ai.choose_card(self.game, AI, self.difficulty)
        self._apply_tressette_ai(index)

    def _apply_tressette_ai(self, index):
        card = self.game.play_card(AI, index)
        verb = "answers with" if self.game.trick_complete else "leads"
        self._set_status(f"The computer {verb} {card}.")
        self.tressette_advance()

    def _tressette_resolve(self):
        self._pending = None
        result = self.game.resolve_trick()
        # The card just drawn goes where it belongs, which is what a player
        # does with it; the hover is dropped because the hand moved under it.
        tressette_view.sort_hand(self, self.sort_mode)
        who = "You take" if result.winner == HUMAN else "The computer takes"
        last = " - the last trick" if result.last else ""
        self._set_status(f"{who} the trick: +{result.thirds} thirds{last}.")
        self.log_lines.insert(0, tressette_view.describe_trick(result))
        self.tressette_advance()

    def _declared_line(self):
        """What was announced from the dealt hands, which scores before a card."""
        said = []
        for player, who in ((HUMAN, "You"), (AI, "The computer")):
            declared = self.game.declared[player]
            if declared:
                said.append(f"{who} declared "
                            + ", ".join(str(one) for one in declared))
        return ("  " + ". ".join(said) + "." if said else "")

    def _finish_tressette(self):
        game = self.game
        you, them = game.scores()
        detail = (f"This deal: {you} to {them}, "
                  f"on {game.thirds[HUMAN]} thirds against "
                  f"{game.thirds[AI]}.")
        if game.bonus[HUMAN] or game.bonus[AI]:
            detail += (f"\nDeclared: you {game.bonus[HUMAN]}, "
                       f"the computer {game.bonus[AI]}.")
        self._finish_match_hand(detail, game.first_leader)

    def set_game(self, kind: str):
        """Pick which game the Start button will deal.

        The three games do not offer the same levels, nor the same targets,
        so a setting the new game has no place for falls back to its normal
        one rather than being carried across and quietly meaning nothing.
        """
        if kind != self.game_kind and self.state != S_MENU:
            # Only the menu offers this, so it should not be reachable with a
            # game running - but the table about to be drawn belongs to the
            # game being left, and drawing it would fail on the wrong state.
            self.show_menu()
        self.game_kind = kind
        levels, _labels = levels_for(kind)
        if self.difficulty not in levels:
            self.difficulty = ai.NORMAL         # the one level every game has
        targets = targets_for(kind)
        if targets and self.target not in targets:
            self.target = catalog.spec_for(kind).default_target
        self.render()

    def set_target(self, target: int):
        """How many points a match is played to; zero means a single hand."""
        self.target = target
        self.render()

    def set_difficulty(self, level: str):
        self.difficulty = level
        _levels, labels = levels_for(self.game_kind)
        self._set_status(f"Difficulty set to {labels[level]}"
                         " - it applies from the next move on.")
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
        text = c.create_text(0, -2000, text=body, anchor="nw", fill=TEXT, width=564,
                             font=ui.font(12), justify="left")
        left, top, right, bottom = c.bbox(text)
        width = 620
        height = 62 + (bottom - top) + 24 + 52
        x = MENU_CX - width / 2
        y = (WIN_H - height) / 2

        c.create_rectangle(0, 0, WIN_W, WIN_H, fill="#04241a",
                           stipple="gray50", outline="")
        cardart.round_rect(c, x, y, x + width, y + height, 12,
                           fill=PANEL_BG, outline=ACCENT, width=2)
        c.create_text(x + 28, y + 34, text=title, anchor="w", fill=ACCENT,
                      font=ui.font(18, "bold"))
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
        """The rules of whichever game the menu is on."""
        label = ui.GAME_LABELS[self.game_kind]
        self.show_overlay(f"Rules of {label}",
                          i18n.RULES_IT[self.game_kind] if self.language == "it"
                          else catalog.spec_for(self.game_kind).rules)

    def show_statistics(self):
        if self.stats_window is not None:
            self.stats_window.lift()
            return
        window = tk.Toplevel(self)
        window.title(f"{self.tr('Statistics')} - {self.player}")
        window.configure(bg=PANEL_BG)
        window.resizable(False, False)
        filters = ttk.Frame(window)
        filters.pack(fill="x", padx=8, pady=6)
        self.stats_game = tk.StringVar(value=self.game_kind)
        self.stats_level = tk.StringVar(value="all")
        for variable, values, labels in (
                (self.stats_game, ("all", *ui.GAMES), ("All games", *ui.GAME_LABELS.values())),
                (self.stats_level, ("all", "easy", "normal", "hard"), ("All levels", "Easy", "Normal", "Expert"))):
            box = ttk.Combobox(filters, state="readonly", width=22,
                               values=[self.tr(label) for label in labels])
            box.current(values.index(variable.get()))
            box.pack(side="left", padx=4)
            def changed(event, variable=variable, values=values, box=box):
                variable.set(values[box.current()])
                self._refresh_stats_window()
            box.bind("<<ComboboxSelected>>", changed)
        canvas = i18n.Canvas(window, translator=self.tr, width=int(STATS_W * ui.SCALE),
                           height=int(STATS_H * ui.SCALE), bg=PANEL_BG,
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
        kind = self.stats_game.get()
        level = self.stats_level.get()
        kind = None if kind == "all" else kind
        level = None if level == "all" else level
        draw_statistics(self.stats_canvas, self.player,
                        self.records.stats(self.player, kind, level),
                        self.records.matches(self.player, kind, level),
                        self.records.path, self.records.text_path,
                        aggregate=kind is None)
        if ui.SCALE != 1.0:
            self.stats_canvas.scale("all", 0, 0, ui.SCALE, ui.SCALE)

    # --- input ------------------------------------------------------------

    def _on_key(self, event):
        # One character or none: `event.char` is empty for the arrows, the
        # shifts and the function keys.
        char = event.char.lower() if len(event.char) == 1 else ""
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

        keys = catalog.spec_for(self.game_kind).play_keys
        if char and char in keys:
            # Ten cards in Tressette, so the tenth of them is on the zero.
            index = (int(char) - 1) % 10
            if self.game_kind == ui.BRISCOLA:
                self._play_human(index)
            elif self.game_kind == ui.SCOPA:
                scopa_view.click_card(self, index)
            else:
                tressette_view.play(self, index)
        elif char == " " or keysym in ("Return", "KP_Enter"):
            self._skip_wait()
        elif char == "n":
            (self.new_game() if self.game_kind == ui.BRISCOLA
             else self.new_match())
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


from .statistics import STATS_W, STATS_H, STATS_ROWS, draw_statistics


def main():
    BriscolaApp().mainloop()
