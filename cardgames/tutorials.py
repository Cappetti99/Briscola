"""Short, interactive rule lessons for each game."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    title: str
    body: str


TUTORIALS = {
    "briscola": (
        Step("The aim", "Win tricks containing valuable cards. The trump suit beats every other suit."),
        Step("Your turn", "Following suit is optional. Play a stronger card of the lead suit, or use a trump."),
        Step("Points", "An ace is worth 11 and a three 10. You need at least 61 of the 120 points."),
    ),
    "scopa": (
        Step("The aim", "Capture cards from the table and collect the four scoring points."),
        Step("A capture", "A card must take a single card of the same value when one is available."),
        Step("A scopa", "Clearing the table earns one extra point, except on the final card."),
    ),
    "burraco": (
        Step("The aim", "Build sets and same-suit runs, then take your pozzetto and close with a burraco."),
        Step("A meld", "A meld needs at least three cards. Use at most one wild card in each meld."),
        Step("A turn", "Draw or take the discard pile, meld as much as possible, then discard one card."),
    ),
    "tressette": (
        Step("The aim", "Win tricks and collect thirds. There are no trumps."),
        Step("Follow suit", "You must follow the suit led when you can. The highest card of that suit wins."),
        Step("Counting", "The ace is worth three thirds; the two, three and face cards are worth one."),
    ),
}


def steps_for(game: str) -> tuple[Step, ...]:
    return TUTORIALS[game]
