"""Texas Hold'em for two: rules, betting and hand evaluation.

Rules reference: https://en.wikipedia.org/wiki/Texas_hold_%27em

Two hole cards each, five community cards in the middle, and four betting
rounds around them — preflop, flop, turn, river. The best five cards out of
the seven take the pot.

Heads-up the button posts the small blind and acts first before the flop,
and the big blind acts first after it: the reverse of a full ring, and the
detail that is usually written down backwards.

Chips only ever move between two stacks, so there are no side pots to work
out. When the betting ends, whatever one side put in beyond the other is
returned, and the rest is the pot. Each hand starts from a hundred chips
apiece and the stacks it finishes with are its score, which is how the
window records it beside the other games.
"""

import random
from collections import Counter
from itertools import combinations

from ..cards import ACE, RANK_NAMES, Card, french_deck
from ..match import Match           # noqa: F401  (re-exported for the window)

HUMAN, AI = 0, 1
PLAYERS = (HUMAN, AI)

STARTING_STACK = 100
SMALL_BLIND = 1
BIG_BLIND = 2

# A hand is worth 200 chips between the two, so a match runs two or three
# hands — a target of zero asks for a single hand, as the other games do.
TARGETS = (0, 200, 400)
DEFAULT_TARGET = 200

# Cards still to come at the end of each street. The river shows none: the
# betting that follows it is the last.
STREETS = {"preflop": 3, "flop": 1, "turn": 1}
NEXT_PHASE = {"preflop": "flop", "flop": "turn", "turn": "river"}

# Category, from the strongest down. Straight flush beats four of a kind,
# and so on; the tie-breaks behind each category are the kickers.
STRAIGHT_FLUSH, FOUR, FULL_HOUSE, FLUSH, STRAIGHT = 8, 7, 6, 5, 4
THREE, TWO_PAIR, PAIR, HIGH_CARD = 3, 2, 1, 0

CATEGORY_NAMES = {
    STRAIGHT_FLUSH: "straight flush", FOUR: "four of a kind",
    FULL_HOUSE: "full house", FLUSH: "flush", STRAIGHT: "straight",
    THREE: "three of a kind", TWO_PAIR: "two pair", PAIR: "pair",
    HIGH_CARD: "high card",
}


class IllegalAction(Exception):
    """A move the rules of this position do not allow."""


# --- hand evaluation ------------------------------------------------------

def _value(rank: int) -> int:
    """The rank as poker ranks it: the ace is high in every hand."""
    return 14 if rank == ACE else rank


def _name(rank: int) -> str:
    """A rank in reading words; 14 is how the evaluator stores an ace."""
    return RANK_NAMES[ACE if rank == 14 else rank].lower()


def _plural(rank: int) -> str:
    """Plural of a rank, for reading a hand out: sixes, not sixs."""
    return "sixes" if rank == 6 else _name(rank) + "s"


def _five(cards: list[Card]) -> tuple[int, ...]:
    """Exactly five cards: a category, then whatever breaks a tie."""
    values = sorted((_value(card.rank) for card in cards), reverse=True)
    flush = all(card.suit == cards[0].suit for card in cards)
    unique = sorted(set(values), reverse=True)

    straight_high = 0
    if len(unique) == 5:
        if unique[0] - unique[4] == 4:
            straight_high = unique[0]
        elif unique == [14, 5, 4, 3, 2]:
            straight_high = 5      # the wheel: the ace plays low only here

    groups = sorted(Counter(values).items(),
                    key=lambda pair: (pair[1], pair[0]), reverse=True)
    shape = tuple(count for _rank, count in groups)
    ordered = tuple(rank for rank, _count in groups)

    if flush and straight_high:
        return (STRAIGHT_FLUSH, straight_high)
    if shape == (4, 1):
        return (FOUR, *ordered)
    if shape == (3, 2):
        return (FULL_HOUSE, *ordered)
    if flush:
        return (FLUSH, *values)
    if straight_high:
        return (STRAIGHT, straight_high)
    if shape == (3, 1, 1):
        return (THREE, *ordered)
    if shape == (2, 2, 1):
        return (TWO_PAIR, *ordered)
    if shape == (2, 1, 1, 1):
        return (PAIR, *ordered)
    return (HIGH_CARD, *values)


def best_hand(cards) -> tuple[int, ...]:
    """The best five cards inside five, six or seven of them.

    Comparable with `>`: the category leads, and everything after it is the
    kickers in the order a reader would name them.
    """
    cards = list(cards)
    if len(cards) < 5:
        raise ValueError("a poker hand needs five cards")
    if len(cards) == 5:
        return _five(cards)
    return max(_five(combo) for combo in combinations(cards, 5))


def describe(cards) -> str:
    """What a hand is called, read out the way a showdown announces it."""
    key = best_hand(cards)
    category, first = key[0], key[1]
    if category == STRAIGHT_FLUSH:
        return f"a straight flush to the {_name(first)}"
    if category == FOUR:
        return f"four of a kind, {_plural(first)}"
    if category == FULL_HOUSE:
        return f"a full house, {_plural(first)} full of {_plural(key[2])}"
    if category == FLUSH:
        return f"a flush, {_name(first)} high"
    if category == STRAIGHT:
        return f"a straight to the {_name(first)}"
    if category == THREE:
        return f"three of a kind, {_plural(first)}"
    if category == TWO_PAIR:
        return f"two pair, {_plural(first)} and {_plural(key[2])}"
    if category == PAIR:
        return f"a pair of {_plural(first)}"
    return f"{_name(first)} high"


def poker_deck() -> list[Card]:
    """The 52 cards Hold'em is dealt from: nothing left out, no jokers."""
    return french_deck(0)


def _who(player: int) -> str:
    return "You" if player == HUMAN else "The computer"


# --- the hand -------------------------------------------------------------

class Game:
    """One hand of heads-up Hold'em, from the blinds to the last chip."""

    def __init__(self, seed: int | None = None, first_player: int = HUMAN):
        rng = random.Random(seed)
        deck = poker_deck()
        rng.shuffle(deck)
        self.hands = [deck[:2], deck[2:4]]
        self.stock = deck[4:]
        self.table: list[Card] = []          # the community cards
        self.mucked: list[Card] = []         # folded hole cards
        self.stacks = [STARTING_STACK, STARTING_STACK]
        self.committed = [0, 0]              # this street, in front of each
        self.total = [0, 0]                  # this hand, put in by each
        self.folded = [False, False]
        self.acted = [False, False]          # has had the option this street
        self.all_in = [False, False]
        self.phase = "preflop"
        self.dealer = first_player
        self.turn = first_player
        self.winner: int | None = None       # set at the end; None on a split
        self.split = False
        self.showdown = False
        self.names = ["", ""]                # what each side held, at showdown
        self.result_text = ""
        self._post_blinds()

    # --- state ------------------------------------------------------------

    @property
    def first_player(self) -> int:
        """The button, under the name the window's match code reads."""
        return self.dealer

    @property
    def game_over(self) -> bool:
        return self.phase == "done"

    @property
    def pot(self) -> int:
        return self.total[HUMAN] + self.total[AI]

    def to_call(self, player: int) -> int:
        """Chips still needed to stay in, zero when nobody is betting."""
        return max(self.committed) - self.committed[player]

    def max_to(self, player: int) -> int:
        """The most this player may commit on this street: everything in."""
        return self.committed[player] + self.stacks[player]

    def min_to(self, player: int) -> int:
        """The standard minimum for a bet or a raise.

        An all-in may come in for less; this is the size to show on a
        button, so it never asks for more chips than are left.
        """
        standard = max(self.committed) + BIG_BLIND
        return min(standard, self.max_to(player))

    def legal_actions(self, player: int) -> tuple[str, ...]:
        """What this player may do, in the order the panel shows them.

        Facing a bet the choice is fold, call or raise; with nothing to
        call it is check or bet. A player who is all in, folded, or simply
        not to move has nothing to do — which is what keeps the window from
        waiting on somebody who cannot answer.
        """
        if (self.phase == "done" or player != self.turn
                or self.folded[player] or self.all_in[player]):
            return ()
        if self.to_call(player) > 0:
            actions = ["fold", "call"]
            if self.stacks[player] > self.to_call(player):
                actions.append("raise")
            return tuple(actions)
        actions = ["check"]
        if self.stacks[player] > 0:
            actions.append("bet")
        return tuple(actions)

    def scores(self) -> list[int]:
        """The stacks the hand ends with: its score, like points elsewhere."""
        return list(self.stacks)

    # --- actions ----------------------------------------------------------

    def act(self, player: int, kind: str, amount: int | None = None) -> str:
        """Fold, check, call, bet or raise, and say what was done.

        The returned line is what goes in the move log and the replay, so it
        never names a card nobody may see.
        """
        if self.phase == "done":
            raise IllegalAction("the hand is over")
        if player != self.turn:
            raise IllegalAction(f"it is not player {player}'s turn")
        legal = self.legal_actions(player)
        if kind not in legal:
            raise IllegalAction(f"{kind} is not on in this position")
        if kind in ("bet", "raise"):
            amount = self._checked_amount(player, kind, amount)

        other = 1 - player
        if kind == "fold":
            self.folded[player] = True
            self._finish_fold(other)
            return ("You fold" if player == HUMAN
                    else "The computer folds")

        if kind == "check":
            line = f"{_who(player)} checks"
        elif kind == "call":
            pay = min(self.to_call(player), self.stacks[player])
            self._pay(player, pay)
            line = f"{_who(player)} calls {pay}"
        else:
            self._pay(player, amount - self.committed[player])
            line = (f"{_who(player)} raises to {amount}" if kind == "raise"
                    else f"{_who(player)} bets {amount}")
            # A raise puts the answer back on the other side; a call does
            # not, which is how the big blind gets its option.
            if not self.folded[other] and not self.all_in[other]:
                self.acted[other] = False
        self.acted[player] = True
        if self._round_complete():
            self._advance()
        elif not self.folded[other] and not self.all_in[other]:
            self.turn = other
        # Otherwise the other side is all in and the answer is still ours:
        # calling it off is the only move left, so the turn stays put.
        return line

    def _checked_amount(self, player: int, kind: str, amount: int | None) -> int:
        if type(amount) is not int or amount <= 0:
            raise IllegalAction("how many chips?")
        top = self.max_to(player)
        if amount > top:
            raise IllegalAction("you do not have that many chips")
        if kind == "bet":
            if amount < min(BIG_BLIND, top):
                raise IllegalAction(f"a bet starts at {min(BIG_BLIND, top)}")
            return amount
        # A raise has to pass the bet in front of it, unless it passes it
        # by putting every chip in — coming in short of a minimum raise is
        # allowed only that way.
        if amount <= max(self.committed):
            raise IllegalAction("a raise has to go past the current bet")
        if amount < max(self.committed) + BIG_BLIND and amount != top:
            raise IllegalAction(f"a raise starts at {self.min_to(player)}")
        return amount

    def _pay(self, player: int, pay: int) -> None:
        if pay < 0 or pay > self.stacks[player]:
            raise IllegalAction("that is more chips than are left")
        self.stacks[player] -= pay
        self.committed[player] += pay
        self.total[player] += pay
        if self.stacks[player] == 0:
            self.all_in[player] = True

    def _post_blinds(self) -> None:
        for player, amount in ((self.dealer, SMALL_BLIND),
                               (1 - self.dealer, BIG_BLIND)):
            self._pay(player, min(amount, self.stacks[player]))

    # --- moving the hand on ----------------------------------------------

    def _round_complete(self) -> bool:
        """Nobody owes chips and everybody has had the option.

        All-in players are skipped: they can owe nothing and can no longer
        answer, which is what closes a street when one side is already in.
        """
        top = max(self.committed)
        for player in PLAYERS:
            if self.folded[player] or self.all_in[player]:
                continue
            if self.committed[player] < top:
                return False
            if not self.acted[player]:
                return False
        return True

    def _advance(self) -> None:
        if self.phase == "done" or not self._round_complete():
            return
        self.committed = [0, 0]
        self.acted = [False, False]
        if self.phase == "river" or self.all_in[0] or self.all_in[1]:
            self._runout()
            return
        self._deal_next_street()
        # Heads-up: after the flop the big blind is first to act.
        self.turn = 1 - self.dealer

    def _deal_next_street(self) -> None:
        count = STREETS[self.phase]
        self.table.extend(self.stock[:count])
        del self.stock[:count]
        self.phase = NEXT_PHASE[self.phase]

    def _runout(self) -> None:
        """No more betting: give back what was never matched, deal it out."""
        self._refund()
        while self.phase != "river":
            self._deal_next_street()
        self._showdown()

    def _refund(self) -> None:
        """Return the part of a bet nobody was left to match.

        Heads-up this is simply the difference between the two totals: one
        number, not the side-pot arithmetic a table of several needs.
        """
        if self.total[HUMAN] > self.total[AI]:
            excess = self.total[HUMAN] - self.total[AI]
            self.stacks[HUMAN] += excess
            self.total[HUMAN] -= excess
        elif self.total[AI] > self.total[HUMAN]:
            excess = self.total[AI] - self.total[HUMAN]
            self.stacks[AI] += excess
            self.total[AI] -= excess

    def _finish_fold(self, winner: int) -> None:
        self._refund()
        loser = 1 - winner
        # The loser's cards go to the muck: nothing is shown when nobody
        # called, which is exactly what a fold is for.
        self.mucked.extend(self.hands[loser])
        self.hands[loser] = []
        pot = self.pot
        self.stacks[winner] += pot
        self.winner = winner
        self.split = False
        self.showdown = False
        if winner == HUMAN:
            self.result_text = f"You win {pot}: the computer folds."
        else:
            self.result_text = f"The computer wins {pot}: you fold."
        self.phase = "done"

    def _showdown(self) -> None:
        keys = {player: best_hand(self.hands[player] + self.table)
                for player in PLAYERS}
        self.names = [describe(self.hands[player] + self.table)
                      for player in PLAYERS]
        self.showdown = True
        pot = self.pot
        if keys[HUMAN] == keys[AI]:
            share = pot // 2
            lucky = 1 - self.dealer      # the odd chip goes left of the button
            self.stacks[lucky] += share + (pot - 2 * share)
            self.stacks[1 - lucky] += share
            self.winner = None
            self.split = True
            self.result_text = (f"Split pot of {pot}: both have "
                                f"{self.names[HUMAN]}.")
        else:
            winner = HUMAN if keys[HUMAN] > keys[AI] else AI
            self.stacks[winner] += pot
            self.winner = winner
            self.split = False
            self.result_text = (
                f"You win {pot} with {self.names[HUMAN]}."
                if winner == HUMAN
                else f"The computer wins {pot} with {self.names[AI]}.")
        self.phase = "done"
