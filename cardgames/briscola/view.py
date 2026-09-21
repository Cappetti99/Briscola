"""Briscola table rendering, separate from the application shell."""
from .. import cardart, ui, records
from ..cards import KING, QUEEN, RANK_NAMES, Card
from ..ui import (ACCENT, CONTENT_W, CONTENT_X, FELT, FELT_DARK, FELT_EDGE, PANEL_BG, PANEL_X, TABLE_H, TABLE_W, TEXT, TEXT_DIM, WIN_W)
from . import ai
from .engine import AI, HUMAN, TOTAL_POINTS, WINNING_POINTS, TRICKS_PER_GAME
from .layout import (AI, AI_HAND_Y, CARD_H, CARD_W, CENTER_X, HUMAN, LIFT, LOG_LINES, PLAYER_HAND_Y, STOCK_X, STOCK_Y, TABLE_W, TABLE_Y, hand_x, table_slot)

class BriscolaView:
    def _draw_felt(self):
        c = self.canvas
        c.create_rectangle(0, 0, TABLE_W, TABLE_H, fill=FELT, outline="")
        c.create_oval(CENTER_X - 200, TABLE_Y - 48, CENTER_X + 200,
                      TABLE_Y + CARD_H + 110, fill=FELT_DARK, outline="")
        c.create_text(TABLE_W - 14, AI_HAND_Y + CARD_H / 2, text="COMPUTER",
                      fill=FELT_EDGE, font=ui.font(11, "bold"),
                      anchor="e", angle=90)
        c.create_text(TABLE_W - 14, PLAYER_HAND_Y + CARD_H / 2, text="YOU",
                      fill=FELT_EDGE, font=ui.font(11, "bold"),
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
                          fill=ACCENT, font=ui.font(10, "bold"))
        else:
            cardart.draw_placeholder(c, STOCK_X, STOCK_Y, CARD_W, CARD_H,
                                     "trump\ndrawn")

        if game.stock:
            cardart.draw_card_back(c, stock_x, STOCK_Y, CARD_W, CARD_H)
            c.create_text(stock_x + CARD_W / 2, STOCK_Y + CARD_H + 18,
                          text=f"{len(game.stock)} in stock", fill=TEXT_DIM,
                          font=ui.font(10))
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
                              fill=TEXT_DIM, font=ui.font(10))


    def _draw_player_hand(self, game):
        c = self.canvas
        hand = game.hands[HUMAN]
        playable = self.state == "human"
        for i, card in enumerate(hand):
            x = self._hand_x(len(hand), i)
            y = PLAYER_HAND_Y - (LIFT if i in self.hover else 0)
            tag = f"hand{i}"
            # Hovering lifts the card; the gold frame is reserved for the
            # card that wins a trick, so the two signals never look alike.
            cardart.draw_card(c, x, y, CARD_W, CARD_H, card, tags=(tag,))
            c.create_text(x + CARD_W / 2, PLAYER_HAND_Y + CARD_H + 16,
                          text=str(i + 1), fill=TEXT_DIM,
                          font=ui.font(10, "bold"))
        if not playable:
            self.hover.clear()


    def _draw_panel(self, game):
        c = self.canvas
        c.create_rectangle(PANEL_X, 0, WIN_W, TABLE_H, fill=PANEL_BG, outline="")

        c.create_text(CONTENT_X, 26, text="BRISCOLA", anchor="w", fill=ACCENT,
                      font=ui.font(19, "bold"))
        c.create_text(CONTENT_X, 48, text="you vs. the computer", anchor="w",
                      fill=TEXT_DIM, font=ui.font(11))
        self._panel_link(CONTENT_X + CONTENT_W, 26, "menu", "back",
                         self.show_menu)

        stats = self.records.stats(self.player, self.game_kind)
        self._panel_box(66, 60)
        c.create_text(CONTENT_X + 10, 80, text="PLAYER", anchor="w",
                      fill=TEXT_DIM, font=ui.font(9, "bold"))
        c.create_text(CONTENT_X + 10, 99, text=self.player, anchor="w",
                      fill=TEXT, font=ui.font(14, "bold"))
        c.create_text(CONTENT_X + 10, 116, text=stats.summary(), anchor="w",
                      fill=TEXT_DIM, font=ui.font(10))
        self._panel_link(CONTENT_X + CONTENT_W - 10, 80, "change",
                         "player", self._change_player)

        suit = game.trump_suit
        taken = " (drawn)" if game.trump_card is None else \
            f" - {RANK_NAMES[game.trump_card.rank]}"
        self._panel_box(134, 52)
        c.create_text(CONTENT_X + 10, 148, text="TRUMP SUIT", anchor="w",
                      fill=TEXT_DIM, font=ui.font(9, "bold"))
        suit_color = cardart.SUIT_COLORS_ON_DARK[suit]
        c.create_text(CONTENT_X + 10, 168,
                      text=f"{suit}{taken}", anchor="w",
                      fill=suit_color, font=ui.font(12, "bold"))
        cardart.emblem(c, suit, CONTENT_X + CONTENT_W - 22, 158, 22, suit_color)

        self._score_box(194, "YOU", game.points[HUMAN])
        self._score_box(244, "COMPUTER", game.points[AI])

        c.create_text(CONTENT_X, 300,
                      text=f"Cards to draw: {game.cards_left}", anchor="w",
                      fill=TEXT_DIM, font=ui.font(10))
        c.create_text(CONTENT_X, 316,
                      text=f"Tricks: {game.tricks_played}/{TRICKS_PER_GAME}"
                           f"   Still in play: {TOTAL_POINTS - sum(game.points)}",
                      anchor="w", fill=TEXT_DIM, font=ui.font(10))

        c.create_text(CONTENT_X, 340, text="LAST TRICKS", anchor="w", fill=TEXT,
                      font=ui.font(9, "bold"))
        for row, (left, right) in enumerate(self.log_lines[:LOG_LINES]):
            y = 360 + row * 17
            c.create_text(CONTENT_X, y, text=left, anchor="w", fill=TEXT_DIM,
                          font=ui.font(10))
            c.create_text(CONTENT_X + CONTENT_W, y, text=right, anchor="e",
                          fill=TEXT, font=ui.font(10, "bold"))

        self._panel_button(612, "New game", "new", self.new_game, primary=True)
        self._panel_button(652, "Statistics", "stats", self.show_statistics)
        self._panel_button(688, f"Difficulty: {ai.LEVEL_LABELS[self.difficulty]}",
                           "level", self.cycle_difficulty)
        self._panel_button(724, "Rules", "rules", self.show_rules)


