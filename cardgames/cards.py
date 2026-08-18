"""Cards and decks shared by the games.

Ranks are the real ones, 1 to 13, so a card means the same thing in every
game: an eight is an eight, and the jack, queen and king are 11, 12 and 13.
Briscola simply leaves the 8s, 9s and 10s out of its deck; Burraco uses the
full deck twice over, jokers included.
"""

from dataclasses import dataclass

SUITS = ("Diamonds", "Hearts", "Spades", "Clubs")

ACE = 1
JACK, QUEEN, KING = 11, 12, 13
JOKER_RANK = 0
JOKER_SUIT = "Joker"

RANKS = tuple(range(ACE, KING + 1))

# Briscola drops these three, which leaves 40 cards matching an Italian deck
# one for one, with the queen standing in for the cavallo.
BRISCOLA_RANKS = tuple(r for r in RANKS if r not in (8, 9, 10))

RANK_NAMES = {ACE: "Ace", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
              6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
              JACK: "Jack", QUEEN: "Queen", KING: "King",
              JOKER_RANK: "Joker"}

RANK_LABELS = {ACE: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7",
               8: "8", 9: "9", 10: "10", JACK: "J", QUEEN: "Q", KING: "K",
               JOKER_RANK: "JK"}

# Briscola's own scales, reached through Card.points and Card.strength below.
# They deliberately cover only the 40 cards Briscola plays with, so using them
# on an eight, a nine, a ten or a joker raises instead of quietly returning a
# wrong number in another game.
POINTS = {ACE: 11, 3: 10, KING: 4, QUEEN: 3, JACK: 2,
          2: 0, 4: 0, 5: 0, 6: 0, 7: 0}
STRENGTH = {ACE: 10, 3: 9, KING: 8, QUEEN: 7, JACK: 6,
            7: 5, 6: 4, 5: 3, 4: 2, 2: 1}


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    @property
    def points(self) -> int:
        """Briscola's card points. Other games bring their own table."""
        return POINTS[self.rank]

    @property
    def strength(self) -> int:
        """Briscola's order within a suit. Other games bring their own."""
        return STRENGTH[self.rank]

    @property
    def label(self) -> str:
        return RANK_LABELS[self.rank]

    @property
    def is_face(self) -> bool:
        return self.rank >= JACK

    @property
    def is_joker(self) -> bool:
        return self.rank == JOKER_RANK

    def short(self) -> str:
        """Compact form for the move log, e.g. "A/di" for the ace of diamonds."""
        if self.is_joker:
            return "JK"
        return f"{self.label}/{self.suit[:2].lower()}"

    def __str__(self) -> str:
        if self.is_joker:
            return "Joker"
        return f"{RANK_NAMES[self.rank]} of {self.suit}"


def new_deck() -> list[Card]:
    """The 40 cards Briscola plays with, in a fixed order."""
    return [Card(rank, suit) for suit in SUITS for rank in BRISCOLA_RANKS]


def french_deck(jokers: int = 2) -> list[Card]:
    """One full 52-card deck, plus its jokers."""
    cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]
    return cards + [Card(JOKER_RANK, JOKER_SUIT) for _ in range(jokers)]


def burraco_deck() -> list[Card]:
    """Two full decks with two jokers each: 108 cards.

    Cards repeat, so anything counting them has to use lists or Counters —
    a set would silently swallow the second copy.
    """
    return french_deck() + french_deck()
