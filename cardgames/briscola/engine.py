"""Game engine: match state and Briscola rules for two players.

Rules reference: https://en.wikipedia.org/wiki/Briscola
"""

import random
from dataclasses import dataclass, field

from ..cards import Card, new_deck

HUMAN = 0
AI = 1
PLAYERS = (HUMAN, AI)

TOTAL_POINTS = 120
WINNING_POINTS = 61
TRICKS_PER_GAME = 20


@dataclass
class TrickResult:
    """Outcome of one completed trick."""

    winner: int
    points: int
    lead: tuple[int, Card]
    follow: tuple[int, Card]
    drawn: dict[int, Card | None] = field(default_factory=dict)


class Game:
    """A full game of 20 tricks.

    Cards on the table live in `table` as (player, card) pairs in play order,
    so the first entry is always the player who led.
    """

    def __init__(self, seed: int | None = None, first_leader: int = HUMAN):
        rng = random.Random(seed)
        deck = new_deck()
        rng.shuffle(deck)

        self.hands: list[list[Card]] = [deck[0:3], deck[3:6]]
        rest = deck[6:]
        # The trump card sits at the bottom of the stock, so it is drawn last.
        self.trump_card: Card | None = rest[-1]
        self.trump_suit: str = rest[-1].suit
        self.stock: list[Card] = rest[:-1]

        self.points: list[int] = [0, 0]
        self.captured: list[list[Card]] = [[], []]
        self.table: list[tuple[int, Card]] = []
        self.leader: int = first_leader
        self.first_leader: int = first_leader
        self.turn: int = first_leader
        self.tricks_played: int = 0
        self.history: list[TrickResult] = []

    # --- state ------------------------------------------------------------

    @property
    def cards_left(self) -> int:
        """Cards still to be drawn, including the face-up trump card."""
        return len(self.stock) + (1 if self.trump_card is not None else 0)

    @property
    def trick_complete(self) -> bool:
        return len(self.table) == 2

    @property
    def game_over(self) -> bool:
        return not self.hands[HUMAN] and not self.hands[AI] and not self.table

    @property
    def lead_card(self) -> Card | None:
        return self.table[0][1] if self.table else None

    def final_winner(self) -> int | None:
        """0/1 for the winner, or None when the game ends 60-60."""
        if self.points[HUMAN] == self.points[AI]:
            return None
        return HUMAN if self.points[HUMAN] > self.points[AI] else AI

    # --- actions ----------------------------------------------------------

    def play_card(self, player: int, index: int) -> Card:
        if self.game_over:
            raise RuntimeError("the game is over")
        if player != self.turn:
            raise RuntimeError(f"it is not player {player}'s turn")
        if self.trick_complete:
            raise RuntimeError("the current trick must be resolved first")

        card = self.hands[player].pop(index)
        self.table.append((player, card))
        self.turn = 1 - player
        return card

    def trick_winner(self) -> int:
        """Who wins the trick currently on the table."""
        if not self.trick_complete:
            raise RuntimeError("the trick is incomplete")
        (lead_player, lead_card), (follow_player, follow_card) = self.table
        if beats_lead(lead_card, follow_card, self.trump_suit):
            return follow_player
        return lead_player

    def resolve_trick(self) -> TrickResult:
        """Award the trick, draw new cards and pass the lead to the winner."""
        if not self.trick_complete:
            raise RuntimeError("the trick is incomplete")

        lead, follow = self.table
        winner = self.trick_winner()
        points = lead[1].points + follow[1].points

        self.points[winner] += points
        self.captured[winner].extend([lead[1], follow[1]])
        self.table = []
        self.tricks_played += 1

        # The winner draws first, then the opponent.
        drawn: dict[int, Card | None] = {}
        for player in (winner, 1 - winner):
            card = self._draw()
            drawn[player] = card
            if card is not None:
                self.hands[player].append(card)

        self.leader = winner
        self.turn = winner

        result = TrickResult(winner=winner, points=points, lead=lead,
                            follow=follow, drawn=drawn)
        self.history.append(result)
        return result

    def _draw(self) -> Card | None:
        if self.stock:
            return self.stock.pop(0)
        if self.trump_card is not None:
            card, self.trump_card = self.trump_card, None
            return card
        return None


def beats_lead(lead: Card, follow: Card, trump_suit: str) -> bool:
    """True when the responding card wins the trick.

    Briscola does not require following suit: the responder only wins by
    playing a stronger card of the same suit, or a trump against a
    non-trump lead.
    """
    if follow.suit == lead.suit:
        return follow.strength > lead.strength
    return follow.suit == trump_suit and lead.suit != trump_suit
