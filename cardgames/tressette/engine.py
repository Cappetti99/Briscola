"""Tressette for two: rules and match state.

Rules reference: https://en.wikipedia.org/wiki/Tressette

The same forty cards as Briscola, and no trump suit at all. Ten cards each,
twenty face down as the stock; the highest card of the suit led wins the
trick, **and following suit is compulsory** — that obligation is the game.
After each trick the winner draws first and leads the next one.

Points are counted in thirds and the remainder is thrown away, which is why a
deal is worth eleven points and not eleven and two thirds: the ace is three
thirds, the two, three and the three faces are one each, and the last trick is
worth three more.
"""

import random
from collections import Counter
from dataclasses import dataclass, field

from ..cards import ACE, JACK, KING, QUEEN, SUITS, Card, new_deck
from ..match import Match           # noqa: F401  (re-exported for the window)

HUMAN = 0
AI = 1
PLAYERS = (HUMAN, AI)

HAND_SIZE = 10
TRICKS_PER_GAME = 20

# Strength inside a suit: the three leads, then the two, and only then the
# ace — which is what makes an unguarded ace such an expensive card to lead.
ORDER = (3, 2, ACE, KING, QUEEN, JACK, 7, 6, 5, 4)
STRENGTH = {rank: len(ORDER) - index for index, rank in enumerate(ORDER)}

THIRDS = {ACE: 3, 2: 1, 3: 1, KING: 1, QUEEN: 1, JACK: 1,
          7: 0, 6: 0, 5: 0, 4: 0}
LAST_TRICK_THIRDS = 3
TOTAL_THIRDS = 4 * 8 + LAST_TRICK_THIRDS      # eight a suit, plus the last
TOTAL_POINTS = TOTAL_THIRDS // 3

# Declared from the hand as it is dealt, before a card is played.
NAPOLETANA = (ACE, 2, 3)
NAPOLETANA_POINTS = 3
GOOD_GAME_RANKS = (ACE, 2, 3)
GOOD_GAME_POINTS = {3: 3, 4: 4}

# A match is short: hands are worth eleven points between the two players.
TARGETS = (0, 21, 31)
DEFAULT_TARGET = 21


class MustFollowSuit(Exception):
    """Raised by a card that leaves a playable card of the led suit behind."""


@dataclass
class Declaration:
    """One announced combination, and what it is worth."""

    kind: str                 # "napoletana" or "good game"
    rank: int | None          # the rank held three or four times
    suit: str | None          # the suit of a napoletana
    points: int

    def __str__(self) -> str:
        if self.kind == "napoletana":
            return f"napoletana in {self.suit}"
        name = {ACE: "aces", 2: "twos", 3: "threes"}[self.rank]
        return f"{'four' if self.points == 4 else 'three'} {name}"


@dataclass
class TrickResult:
    """Outcome of one completed trick."""

    winner: int
    thirds: int
    lead: tuple[int, Card]
    follow: tuple[int, Card]
    drawn: dict[int, Card | None] = field(default_factory=dict)
    last: bool = False


def declarations(hand: list[Card]) -> list[Declaration]:
    """What a dealt hand may announce.

    Three or four of the aces, twos or threes is *buon gioco*; the ace, two
    and three of one suit is a *napoletana*. A hand can hold several, and a
    card can serve in both — three aces and a napoletana in coins both count.
    """
    found = []
    counts = Counter(card.rank for card in hand if card.rank in GOOD_GAME_RANKS)
    for rank in GOOD_GAME_RANKS:
        held = counts.get(rank, 0)
        if held in GOOD_GAME_POINTS:
            found.append(Declaration("good game", rank, None,
                                     GOOD_GAME_POINTS[held]))
    for suit in SUITS:
        ranks = {card.rank for card in hand if card.suit == suit}
        if set(NAPOLETANA) <= ranks:
            found.append(Declaration("napoletana", None, suit,
                                     NAPOLETANA_POINTS))
    return found


def beats_lead(lead: Card, follow: Card) -> bool:
    """True when the responding card wins the trick.

    There is no trump: a card of another suit never wins, which is the whole
    reason following suit has to be compulsory.
    """
    if follow.suit != lead.suit:
        return False
    return STRENGTH[follow.rank] > STRENGTH[lead.rank]


class Game:
    """One deal of twenty tricks."""

    def __init__(self, seed: int | None = None, first_leader: int = HUMAN):
        rng = random.Random(seed)
        deck = new_deck()
        rng.shuffle(deck)

        self.hands: list[list[Card]] = [deck[:HAND_SIZE],
                                        deck[HAND_SIZE:2 * HAND_SIZE]]
        self.stock: list[Card] = deck[2 * HAND_SIZE:]

        self.thirds: list[int] = [0, 0]
        self.bonus: list[int] = [0, 0]        # whole points, from declarations
        self.declared: list[list[Declaration]] = [
            declarations(self.hands[player]) for player in PLAYERS]
        for player in PLAYERS:
            self.bonus[player] = sum(one.points
                                     for one in self.declared[player])

        self.captured: list[list[Card]] = [[], []]
        self.table: list[tuple[int, Card]] = []
        self.leader: int = first_leader
        self.first_leader: int = first_leader
        self.turn: int = first_leader
        self.tricks_played: int = 0
        self.drawn: dict[int, Card | None] = {}
        self.history: list[TrickResult] = []

    # --- state ------------------------------------------------------------

    @property
    def cards_left(self) -> int:
        return len(self.stock)

    @property
    def trick_complete(self) -> bool:
        return len(self.table) == 2

    @property
    def game_over(self) -> bool:
        return not self.hands[HUMAN] and not self.hands[AI] and not self.table

    @property
    def lead_card(self) -> Card | None:
        return self.table[0][1] if self.table else None

    def legal_cards(self, player: int) -> list[int]:
        """The indices this player is allowed to play.

        Everything, when leading or when holding nothing of the suit led;
        otherwise only the suit led. Nothing else in this game is a rule the
        interface has to enforce, and everything else follows from it.
        """
        hand = self.hands[player]
        lead = self.lead_card
        if lead is None:
            return list(range(len(hand)))
        matching = [index for index, card in enumerate(hand)
                    if card.suit == lead.suit]
        return matching or list(range(len(hand)))

    def points(self, player: int) -> int:
        """Whole points: the thirds taken, plus anything declared."""
        return self.thirds[player] // 3 + self.bonus[player]

    def scores(self) -> list[int]:
        return [self.points(player) for player in PLAYERS]

    def final_winner(self) -> int | None:
        you, them = self.scores()
        if you == them:
            return None
        return HUMAN if you > them else AI

    # --- tidying ----------------------------------------------------------

    def sort_hand(self, player: int, by: str = "suit") -> None:
        """Put a hand in order: by suit, or by rank across the suits.

        "By rank" means this game's order and not the number on the card. A
        hand sorted by number would stand the three next to the four and put
        the ace between the two and the king, which is precisely backwards:
        the point of ordering a Tressette hand is to see what commands what.
        """
        order = {suit: index for index, suit in enumerate(SUITS)}

        def key(card: Card):
            if by == "rank":
                return (-STRENGTH[card.rank], order.get(card.suit, 9))
            return (order.get(card.suit, 9), -STRENGTH[card.rank])

        self.hands[player].sort(key=key)

    # --- actions ----------------------------------------------------------

    def play_card(self, player: int, index: int) -> Card:
        if self.game_over:
            raise RuntimeError("the game is over")
        if player != self.turn:
            raise RuntimeError(f"it is not player {player}'s turn")
        if self.trick_complete:
            raise RuntimeError("the current trick must be resolved first")
        if not 0 <= index < len(self.hands[player]):
            raise RuntimeError("no such card in your hand")
        if index not in self.legal_cards(player):
            suit = self.lead_card.suit
            raise MustFollowSuit(f"you have to follow suit: play {suit}")

        card = self.hands[player].pop(index)
        self.table.append((player, card))
        self.turn = 1 - player
        return card

    def trick_winner(self) -> int:
        if not self.trick_complete:
            raise RuntimeError("the trick is incomplete")
        (lead_player, lead_card), (follow_player, follow_card) = self.table
        return follow_player if beats_lead(lead_card, follow_card) else lead_player

    def resolve_trick(self) -> TrickResult:
        """Award the trick, draw new cards and pass the lead to the winner."""
        if not self.trick_complete:
            raise RuntimeError("the trick is incomplete")

        lead, follow = self.table
        winner = self.trick_winner()
        thirds = THIRDS[lead[1].rank] + THIRDS[follow[1].rank]

        self.captured[winner].extend([lead[1], follow[1]])
        self.table = []
        self.tricks_played += 1

        last = not self.stock and not self.hands[HUMAN] and not self.hands[AI]
        if last:
            thirds += LAST_TRICK_THIRDS
        self.thirds[winner] += thirds

        # The winner draws first, and both cards are shown: with a stock this
        # small, what the other side picked up is part of what you may count.
        drawn: dict[int, Card | None] = {}
        for player in (winner, 1 - winner):
            card = self.stock.pop(0) if self.stock else None
            drawn[player] = card
            if card is not None:
                self.hands[player].append(card)
        self.drawn = drawn

        self.leader = winner
        self.turn = winner

        result = TrickResult(winner=winner, thirds=thirds, lead=lead,
                             follow=follow, drawn=drawn, last=last)
        self.history.append(result)
        return result
