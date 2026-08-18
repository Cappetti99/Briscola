"""Burraco: rules and match state for two players.

Rules reference: https://en.wikipedia.org/wiki/Buraco

Two full decks with two jokers each, 108 cards. Both players get eleven, two
pots (pozzetti) of eleven are set aside, and the rest is the stock. On your
turn you draw — one card from the stock, or the whole discard pile — then lay
down or extend as many melds as you like, and finish by discarding one card.
Running out of cards the first time hands you a pot; you may only close once
you have taken your pot and built at least one burraco.
"""

import random
from collections import Counter
from dataclasses import dataclass, field

from ..cards import (ACE, JOKER_RANK, KING, RANKS, SUITS, Card,
                     burraco_deck)

HUMAN = 0
AI = 1
PLAYERS = (HUMAN, AI)

HAND_SIZE = 11
POT_SIZE = 11
MIN_MELD = 3
BURRACO_SIZE = 7

# What a card is worth when it ends up in a meld, or against you in hand.
CARD_POINTS = {JOKER_RANK: 30, 2: 20, ACE: 15,
               KING: 10, 12: 10, 11: 10, 10: 10, 9: 10, 8: 10,
               7: 5, 6: 5, 5: 5, 4: 5, 3: 5}

BURRACO_CLEAN = 200
BURRACO_DIRTY = 100
CLOSING_BONUS = 100
POT_NOT_TAKEN = -100

SET, RUN = "set", "run"

# An ace closes a run either below the two or above the king, so runs are
# checked on both readings.
ACE_HIGH = KING + 1


def is_wild(card: Card) -> bool:
    """Jokers and twos stand in for any card — one per meld at most."""
    return card.is_joker or card.rank == 2


class InvalidMeld(Exception):
    """Raised when cards cannot legally sit together on the table."""


@dataclass
class Meld:
    """Cards on the table, as a set of equal ranks or a run in one suit."""

    cards: list[Card]
    kind: str
    wilds: int = 0

    @property
    def is_burraco(self) -> bool:
        return len(self.cards) >= BURRACO_SIZE

    @property
    def is_clean(self) -> bool:
        """A burraco with no wild card standing in for anything."""
        return self.wilds == 0

    def card_points(self) -> int:
        return sum(CARD_POINTS[card.rank] for card in self.cards)

    def bonus(self) -> int:
        if not self.is_burraco:
            return 0
        return BURRACO_CLEAN if self.is_clean else BURRACO_DIRTY

    def points(self) -> int:
        return self.card_points() + self.bonus()

    def suit(self) -> str | None:
        for card in self.cards:
            if not is_wild(card):
                return card.suit
        return None

    def rank(self) -> int | None:
        for card in self.cards:
            if not is_wild(card):
                return card.rank
        return None

    def __len__(self) -> int:
        return len(self.cards)


# --- meld validation ------------------------------------------------------

def build_meld(cards: list[Card]) -> Meld:
    """Turn a pile of cards into a legal meld, or say why it is not one."""
    if len(cards) < MIN_MELD:
        raise InvalidMeld(f"a meld needs at least {MIN_MELD} cards")

    as_set = _try_set(cards)
    if as_set is not None:
        return as_set
    as_run = _try_run(cards)
    if as_run is not None:
        return as_run
    raise InvalidMeld("these cards are neither a set nor a run")


def _try_set(cards: list[Card]) -> Meld | None:
    jokers = [c for c in cards if c.is_joker]
    naturals = [c for c in cards if not c.is_joker]
    if len(jokers) > 1 or not naturals:
        return None

    ranks = {c.rank for c in naturals}
    if len(ranks) == 1 and not jokers:
        # A set of twos is a set of natural twos, not of wild cards.
        return Meld(list(cards), SET, wilds=0)
    if len(ranks) == 1 and jokers:
        return Meld(list(cards), SET, wilds=1)

    # One wild two propping up a set of some other rank.
    twos = [c for c in naturals if c.rank == 2]
    others = [c for c in naturals if c.rank != 2]
    if jokers or len(twos) != 1 or not others:
        return None
    if len({c.rank for c in others}) == 1:
        return Meld(list(cards), SET, wilds=1)
    return None


def _try_run(cards: list[Card]) -> Meld | None:
    """A run needs one suit, consecutive ranks, and at most one wild.

    A two of the run's own suit can serve either as itself or as the wild, so
    both readings are tried; the same goes for an ace, which may sit below the
    two or above the king.
    """
    jokers = [c for c in cards if c.is_joker]
    naturals = [c for c in cards if not c.is_joker]
    if len(jokers) > 1 or not naturals:
        return None

    for wild_two in _wild_two_choices(naturals, bool(jokers)):
        rest = list(naturals)
        if wild_two is not None:
            rest.remove(wild_two)
        wilds = len(jokers) + (1 if wild_two is not None else 0)
        if wilds > 1 or len(rest) + wilds != len(cards):
            continue
        if _run_fits(rest, wilds):
            return Meld(list(cards), RUN, wilds=wilds)
    return None


def _wild_two_choices(naturals: list[Card], has_joker: bool):
    """Which two, if any, could be acting as the wild card here."""
    yield None
    if has_joker:
        return              # one wild per meld, and the joker already is it
    seen = set()
    for card in naturals:
        if card.rank == 2 and card not in seen:
            seen.add(card)
            yield card


def _run_fits(naturals: list[Card], wilds: int) -> bool:
    if not naturals:
        return False
    if len({card.suit for card in naturals}) != 1:
        return False

    readings = [[card.rank for card in naturals]]
    if any(card.rank == ACE for card in naturals):
        readings.append([ACE_HIGH if r == ACE else r
                         for r in readings[0]])

    for ranks in readings:
        if len(set(ranks)) != len(ranks):
            continue                    # the same card twice is not a run
        span = max(ranks) - min(ranks) + 1
        total = len(ranks) + wilds
        if span > total:
            continue                    # too big a gap for the wilds to fill
        if min(ranks) < ACE or max(ranks) > ACE_HIGH:
            continue
        # The wilds have to sit somewhere inside A..K(+A), not past the ends.
        room = (max(ranks) - ACE) + (ACE_HIGH - min(ranks))
        if total - span > room:
            continue
        return True
    return False


def wild_stands_for(meld: Meld) -> list[Card]:
    """The natural cards that could take the wild card's place in a meld.

    Worked out by trying every ranked card and keeping the ones that leave a
    legal meld of the same size with no wild left in it. Brute force over 52
    candidates, which costs nothing and means runs and sets need no separate
    reasoning — the gap in A-3-4-5 and the fourth nine of a set both fall out
    of the same check.
    """
    if meld.wilds != 1:
        return []
    wild = next(card for card in meld.cards if is_wild(card))
    rest = list(meld.cards)
    rest.remove(wild)

    candidates = []
    for suit in SUITS:
        for rank in RANKS:
            card = Card(rank, suit)
            if is_wild(card):
                continue
            try:
                grown = build_meld(rest + [card])
            except InvalidMeld:
                continue
            if grown.wilds == 0 and len(grown) == len(meld):
                candidates.append(card)
    return candidates


def can_extend(meld: Meld, card: Card) -> bool:
    """Whether one more card may join a meld already on the table."""
    try:
        build_meld(meld.cards + [card])
    except InvalidMeld:
        return False
    return True


# --- match state ----------------------------------------------------------

@dataclass
class Turn:
    """What the player still has to do this turn."""

    drawn: bool = False
    took_pile: bool = False


@dataclass
class Game:
    """One hand of Burraco between two players."""

    seed: int | None = None
    first_player: int = HUMAN

    hands: list[list[Card]] = field(default_factory=list)
    melds: list[list[Meld]] = field(default_factory=list)
    pots: list[list[Card]] = field(default_factory=list)
    pot_taken: list[bool] = field(default_factory=list)
    stock: list[Card] = field(default_factory=list)
    discards: list[Card] = field(default_factory=list)
    turn: int = HUMAN
    phase: Turn = field(default_factory=Turn)
    closed_by: int | None = None
    exhausted: bool = False

    def __post_init__(self):
        rng = random.Random(self.seed)
        deck = burraco_deck()
        rng.shuffle(deck)

        self.hands = [deck[:HAND_SIZE], deck[HAND_SIZE:2 * HAND_SIZE]]
        rest = deck[2 * HAND_SIZE:]
        self.pots = [rest[:POT_SIZE], rest[POT_SIZE:2 * POT_SIZE]]
        self.stock = rest[2 * POT_SIZE:]
        self.pot_taken = [False, False]
        self.melds = [[], []]
        self.discards = []
        self.turn = self.first_player
        self.phase = Turn()

    # --- state ------------------------------------------------------------

    @property
    def game_over(self) -> bool:
        """Someone closed, or the stock ran out.

        Ending the hand with the stock is a simplification: the full rules let
        play carry on as long as a player keeps taking the discard pile, which
        with two players can circle forever — take one card, discard one card,
        neither hand ever shrinking. Ending on the stock keeps every hand
        finite, and the scoring below then decides it.
        """
        return self.closed_by is not None or self.exhausted

    def has_burraco(self, player: int) -> bool:
        return any(meld.is_burraco for meld in self.melds[player])

    def may_close(self, player: int) -> bool:
        """Closing needs the pot taken, a burraco, and an empty hand after."""
        return self.pot_taken[player] and self.has_burraco(player)

    # --- the three steps of a turn ----------------------------------------

    def draw(self, player: int) -> Card:
        self._check_turn(player)
        if self.phase.drawn:
            raise RuntimeError("you have already drawn this turn")
        if not self.stock:
            self.exhausted = True
            raise RuntimeError("the stock is empty")
        card = self.stock.pop(0)
        self.hands[player].append(card)
        self.phase.drawn = True
        return card

    def take_discards(self, player: int) -> list[Card]:
        self._check_turn(player)
        if self.phase.drawn:
            raise RuntimeError("you have already drawn this turn")
        if not self.discards:
            raise RuntimeError("the discard pile is empty")
        taken, self.discards = self.discards, []
        self.hands[player].extend(taken)
        self.phase.drawn = True
        self.phase.took_pile = True
        return taken

    def lay_meld(self, player: int, cards: list[Card]) -> Meld:
        self._check_turn(player)
        self._require_drawn()
        self._take_from_hand(player, cards)
        try:
            meld = build_meld(cards)
        except InvalidMeld:
            self.hands[player].extend(cards)      # put them back, unchanged
            raise
        self.melds[player].append(meld)
        self._after_hand_shrinks(player)
        return meld

    def extend_meld(self, player: int, meld: Meld, cards: list[Card]) -> Meld:
        self._check_turn(player)
        self._require_drawn()
        if meld not in self.melds[player]:
            raise RuntimeError("that meld belongs to the other player")
        self._take_from_hand(player, cards)
        try:
            grown = build_meld(meld.cards + cards)
        except InvalidMeld:
            self.hands[player].extend(cards)
            raise
        meld.cards, meld.kind, meld.wilds = grown.cards, grown.kind, grown.wilds
        return meld

    def substitute_wild(self, player: int, meld: Meld, card: Card) -> Card:
        """Put the natural card in and take the wild card back into hand.

        The pinella is worth more in your hand than propping up a meld you
        can complete properly, so a player holding the card the wild stands
        for may swap them over.
        """
        self._check_turn(player)
        self._require_drawn()
        if meld not in self.melds[player]:
            raise RuntimeError("that meld belongs to the other player")
        if card not in wild_stands_for(meld):
            raise InvalidMeld("that card is not what the wild stands for")

        self._take_from_hand(player, [card])
        wild = next(one for one in meld.cards if is_wild(one))
        replaced = [card if one is wild else one for one in meld.cards]
        grown = build_meld(replaced)
        meld.cards, meld.kind, meld.wilds = grown.cards, grown.kind, grown.wilds
        self.hands[player].append(wild)
        return wild

    def discard(self, player: int, card: Card) -> None:
        self._check_turn(player)
        self._require_drawn()
        self._take_from_hand(player, [card])
        self.discards.append(card)
        self._after_hand_shrinks(player)
        if self.closed_by is None:
            self.turn = 1 - player
            self.phase = Turn()

    def end_turn(self, player: int) -> None:
        """Hand over without discarding, which only an empty hand allows."""
        self._check_turn(player)
        self._require_drawn()
        if self.hands[player]:
            raise RuntimeError("discard before ending your turn")
        if self.closed_by is None:
            self.turn = 1 - player
            self.phase = Turn()

    # --- pot and closing --------------------------------------------------

    def _after_hand_shrinks(self, player: int) -> None:
        """Emptying your hand takes the pot, or closes if you already have it.

        This fires on melding as well as on discarding: laying every last card
        down is a legal way to run out, and the pot then comes into the same
        turn, which is how the rules read.
        """
        if self.hands[player]:
            return
        if not self.pot_taken[player]:
            self.hands[player] = self.pots[player]
            self.pots[player] = []
            self.pot_taken[player] = True
        elif self.may_close(player):
            self.closed_by = player

    # --- tidying ----------------------------------------------------------

    def sort_hand(self, player: int, by: str = "suit") -> None:
        """Put a hand in order: by suit, or by rank across the suits.

        Wild cards go to the end either way, where they are easy to find and
        hard to discard by accident.
        """
        order = {suit: index for index, suit in enumerate(SUITS)}

        def key(card: Card):
            wild = 1 if is_wild(card) else 0
            if by == "rank":
                return (wild, card.rank, order.get(card.suit, 9))
            return (wild, order.get(card.suit, 9), card.rank)

        self.hands[player].sort(key=key)

    # --- scoring ----------------------------------------------------------

    def score(self, player: int) -> int:
        total = sum(meld.points() for meld in self.melds[player])
        total -= sum(CARD_POINTS[card.rank] for card in self.hands[player])
        if not self.pot_taken[player]:
            total += POT_NOT_TAKEN
        if self.closed_by == player:
            total += CLOSING_BONUS
        return total

    def scores(self) -> list[int]:
        return [self.score(player) for player in PLAYERS]

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

    def _require_drawn(self) -> None:
        if not self.phase.drawn:
            raise RuntimeError("draw before melding or discarding")

    def _take_from_hand(self, player: int, cards: list[Card]) -> None:
        """Remove exactly these cards, duplicates and all."""
        hand = Counter(self.hands[player])
        if not (Counter(cards) <= hand):
            raise RuntimeError("those cards are not all in your hand")
        for card in cards:
            self.hands[player].remove(card)
