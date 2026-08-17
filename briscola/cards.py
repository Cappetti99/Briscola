"""Cards, deck, point values and card strength for Briscola.

Rules reference: https://en.wikipedia.org/wiki/Briscola
"""

from dataclasses import dataclass

# A French deck, as Briscola is commonly played in Italy: drop the 8, 9 and 10
# and the remaining 40 cards match the Italian deck one for one, with the
# knight (cavallo) taking the queen's place.
SUITS = ("Diamonds", "Hearts", "Spades", "Clubs")

# Ranks 8, 9 and 10 are the face cards: Jack, Queen, King.
RANKS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

JACK, QUEEN, KING = 8, 9, 10
ACE = 1

RANK_NAMES = {
    ACE: "Ace",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    JACK: "Jack",
    QUEEN: "Queen",
    KING: "King",
}

# Short label printed on the card face.
RANK_LABELS = {ACE: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7",
               JACK: "J", QUEEN: "Q", KING: "K"}

# Card points; the whole deck is worth 120.
POINTS = {ACE: 11, 3: 10, KING: 4, QUEEN: 3, JACK: 2,
          2: 0, 4: 0, 5: 0, 6: 0, 7: 0}

# Strength when comparing two cards of the same suit:
# Ace > Three > King > Queen > Jack > 7 > 6 > 5 > 4 > 2
STRENGTH = {ACE: 10, 3: 9, KING: 8, QUEEN: 7, JACK: 6,
            7: 5, 6: 4, 5: 3, 4: 2, 2: 1}


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    @property
    def points(self) -> int:
        return POINTS[self.rank]

    @property
    def strength(self) -> int:
        return STRENGTH[self.rank]

    @property
    def label(self) -> str:
        return RANK_LABELS[self.rank]

    @property
    def is_face(self) -> bool:
        return self.rank >= JACK

    def short(self) -> str:
        """Compact form used in the move log, e.g. "A/co" for the Ace of Coins."""
        return f"{self.label}/{self.suit[:2].lower()}"

    def __str__(self) -> str:
        return f"{RANK_NAMES[self.rank]} of {self.suit}"


def new_deck() -> list[Card]:
    """The 40 cards in a fixed order."""
    return [Card(rank, suit) for suit in SUITS for rank in RANKS]
