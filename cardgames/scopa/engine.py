"""Scopa: rules and match state for two players.

Rules reference: https://en.wikipedia.org/wiki/Scopa

The same forty cards Briscola uses. Four go face up on the table and each
player gets three; on your turn you play one card, and if it matches a table
card — or the sum of several — you take them. Clearing the table is a *scopa*
and scores a point of its own. When both hands are empty three more cards
come out, until the deck is spent; whoever captured last takes what is left
on the table, and then the hand is scored.

Only the four points and the scope are counted here, which is the game as it
is usually played: no napola, no re bello, and no redeal on four kings.
"""

import random
from dataclasses import dataclass, field
from itertools import combinations

from ..cards import ACE, JACK, KING, QUEEN, Card, new_deck
from ..match import Match           # noqa: F401  (re-exported for the window)

HUMAN, AI = 0, 1
PLAYERS = (HUMAN, AI)

HAND_SIZE = 3
TABLE_SIZE = 4

# The French suit standing in for denari, as the queen stands in for the
# cavallo: it is the suit the coin points are counted in.
COINS = "Diamonds"

# What a card takes with. The numbers speak for themselves; the three faces
# carry on where the seven leaves off.
VALUES = {rank: rank for rank in range(ACE, 8)}
VALUES.update({JACK: 8, QUEEN: 9, KING: 10})

# Primiera, scored on the best card held in each suit. The order is the odd
# one in this game: the seven leads, then the six, and only then the ace.
PRIME = {7: 21, 6: 18, ACE: 16, 5: 15, 4: 14, 3: 13, 2: 12,
         JACK: 10, QUEEN: 10, KING: 10}

SETTEBELLO = Card(7, COINS)

# A hand is worth four points plus the scope, so a match is short.
TARGETS = (0, 11, 16, 21)
DEFAULT_TARGET = 11


class Ambiguous(Exception):
    """More than one legal capture: the player has to say which."""


class IllegalCapture(Exception):
    """Those table cards are not a legal take for that card."""


@dataclass
class Tally:
    """One player's hand score, broken down the way it is announced."""

    cards: int = 0
    coins: int = 0
    settebello: int = 0
    prime: int = 0
    scope: int = 0

    @property
    def total(self) -> int:
        return (self.cards + self.coins + self.settebello + self.prime
                + self.scope)

    def lines(self) -> list[tuple[str, int]]:
        return [("Cards", self.cards), ("Coins", self.coins),
                ("Settebello", self.settebello), ("Primiera", self.prime),
                ("Scope", self.scope)]


@dataclass
class Play:
    """What one card did: the log, the animation and the AI all read this."""

    player: int
    card: Card
    taken: tuple[Card, ...] = ()
    scopa: bool = False
    swept: tuple[Card, ...] = ()

    @property
    def captured(self) -> bool:
        return bool(self.taken)


def prime_score(cards: list[Card]) -> int:
    """Primiera: the best card of each suit, added up.

    A suit you hold nothing in simply contributes nothing, which is why a
    player who has taken very little can still be far behind on this point
    without ever having lost a seven.
    """
    best: dict[str, int] = {}
    for card in cards:
        value = PRIME[card.rank]
        if value > best.get(card.suit, 0):
            best[card.suit] = value
    return sum(best.values())


def _best(values: list[int]) -> int | None:
    """Who leads on a count, or nobody when it is level."""
    if values[HUMAN] == values[AI]:
        return None
    return HUMAN if values[HUMAN] > values[AI] else AI


@dataclass
class Game:
    """One hand of Scopa, from the first four cards to the last sweep."""

    seed: int | None = None
    first_player: int = HUMAN

    hands: list[list[Card]] = field(default_factory=list)
    table: list[Card] = field(default_factory=list)
    captured: list[list[Card]] = field(default_factory=list)
    scope: list[int] = field(default_factory=list)
    stock: list[Card] = field(default_factory=list)
    turn: int = HUMAN
    last_capture: int | None = None
    swept: bool = False

    def __post_init__(self):
        rng = random.Random(self.seed)
        deck = new_deck()
        rng.shuffle(deck)
        self.table = deck[:TABLE_SIZE]
        self.stock = deck[TABLE_SIZE:]
        self.hands = [[], []]
        self.captured = [[], []]
        self.scope = [0, 0]
        self.turn = self.first_player
        self.last_capture = None
        self.swept = False
        self._deal()

    # --- state ------------------------------------------------------------

    @property
    def game_over(self) -> bool:
        return not self.stock and not self.hands[HUMAN] and not self.hands[AI]

    @property
    def cards_left(self) -> int:
        """Cards still to come out of the deck, which paces the whole hand."""
        return len(self.stock)

    def _deal(self) -> None:
        """Three each, but only once both hands are empty."""
        if self.hands[HUMAN] or self.hands[AI] or not self.stock:
            return
        for player in (self.first_player, 1 - self.first_player):
            self.hands[player] = self.stock[:HAND_SIZE]
            del self.stock[:HAND_SIZE]

    # --- capture ----------------------------------------------------------

    def capture_options(self, card: Card) -> list[tuple[Card, ...]]:
        """Every legal way of taking with this card.

        A single card of the same value must be taken when there is one: only
        if the table holds none may a sum be taken instead. That rule is what
        stops a player taking the table apart at will — it is why leaving a
        seven out is safer than leaving a three and a four.
        """
        value = VALUES[card.rank]
        singles = [(one,) for one in self.table if VALUES[one.rank] == value]
        if singles:
            return singles
        found = []
        for size in range(2, len(self.table) + 1):
            for combo in combinations(self.table, size):
                if sum(VALUES[one.rank] for one in combo) == value:
                    found.append(combo)
        return found

    def play(self, player: int, index: int,
             taking: list[Card] | tuple[Card, ...] | None = None) -> Play:
        """Play the index-th card, taking `taking` if a choice has to be made.

        With no choice on offer the capture is automatic — there is only one
        thing the rules allow. With a choice, `taking` has to say which, and
        leaving it out raises `Ambiguous` rather than picking for the player.
        """
        self._check_turn(player)
        if not 0 <= index < len(self.hands[player]):
            raise RuntimeError("no such card in your hand")

        card = self.hands[player][index]
        options = self.capture_options(card)
        if taking is None:
            if len(options) > 1:
                raise Ambiguous(f"{card} can take in {len(options)} ways")
            chosen = options[0] if options else ()
        else:
            chosen = tuple(taking)
            # Compared as multisets, not as sets: a caller that names the same
            # card twice would otherwise match a legal single and then try to
            # take a card off the table that is no longer there.
            wanted = sorted(map(str, chosen))
            if chosen and wanted not in [sorted(map(str, one)) for one in options]:
                raise IllegalCapture(f"{card} cannot take those cards")
            if not chosen and options:
                raise IllegalCapture(f"{card} has to take: it matches the table")

        del self.hands[player][index]
        scopa = False
        if chosen:
            for one in chosen:
                self.table.remove(one)
            self.captured[player].extend(chosen)
            self.captured[player].append(card)
            self.last_capture = player
            # The last card of the hand clears a table nobody could have
            # played on anyway, so it never scores the point.
            scopa = not self.table and not self._last_card_played()
            if scopa:
                self.scope[player] += 1
        else:
            self.table.append(card)

        self.turn = 1 - player
        self._deal()
        result = Play(player, card, chosen, scopa)
        if self.game_over:
            result.swept = self.sweep()
        return result

    def _last_card_played(self) -> bool:
        return not self.stock and not self.hands[HUMAN] and not self.hands[AI]

    def sweep(self) -> tuple[Card, ...]:
        """What is left on the table goes to whoever captured last."""
        if self.swept or self.last_capture is None:
            return ()
        left = tuple(self.table)
        self.captured[self.last_capture].extend(left)
        self.table = []
        self.swept = True
        return left

    # --- scoring ----------------------------------------------------------

    def tallies(self) -> list[Tally]:
        """Both hands scored at once: three of the five points are contests."""
        out = [Tally(scope=self.scope[player]) for player in PLAYERS]
        counts = {
            "cards": [len(self.captured[p]) for p in PLAYERS],
            "coins": [sum(1 for card in self.captured[p] if card.suit == COINS)
                      for p in PLAYERS],
            "prime": [prime_score(self.captured[p]) for p in PLAYERS],
        }
        for point, values in counts.items():
            leader = _best(values)
            if leader is not None:
                setattr(out[leader], point, 1)
        for player in PLAYERS:
            if SETTEBELLO in self.captured[player]:
                out[player].settebello = 1
        return out

    def score(self, player: int) -> int:
        return self.tallies()[player].total

    def scores(self) -> list[int]:
        return [tally.total for tally in self.tallies()]

    def winner(self) -> int | None:
        you, them = self.scores()
        if you == them:
            return None
        return HUMAN if you > them else AI

    # --- helpers ----------------------------------------------------------

    def _check_turn(self, player: int) -> None:
        if self.game_over:
            raise RuntimeError("the hand is over")
        if player != self.turn:
            raise RuntimeError(f"it is not player {player}'s turn")
