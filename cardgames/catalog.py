"""Shared metadata for the games exposed by the application.

Keeping this information outside the Tk window makes the menu declarative and
gives tests a small, display-free surface to validate.
"""

from dataclasses import dataclass

from . import ui
from .briscola import ai as briscola_ai
from .burraco import ai as burraco_ai
from .burraco import engine as burraco_engine
from .burraco import view as burraco_view
from .scopa import ai as scopa_ai
from .scopa import engine as scopa_engine
from .tressette import ai as tressette_ai
from .tressette import engine as tressette_engine


@dataclass(frozen=True)
class GameSpec:
    """Everything the shared shell needs to describe a game."""

    key: str
    play_keys: str
    levels: tuple[str, ...]
    level_labels: dict[str, str]
    level_blurbs: dict[str, str]
    targets: tuple[int, ...]
    default_target: int
    rules: str


BRISCOLA_RULES = (
    "40 cards, 20 tricks, 120 points in total: first to 61 wins,\n"
    "60-60 is a draw.\n\n"
    "Points: Ace 11, Three 10, King 4, Queen 3, Jack 2, rest 0.\n"
    "Strength in the same suit: A > 3 > K > Q > J > 7 > 6 > 5 > 4 > 2.\n"
    "A French deck without the 8, 9 and 10: the queen stands in for\n"
    "the cavallo of an Italian deck.\n\n"
    "Following suit is not required. The responder only wins with a\n"
    "stronger card of the same suit, or with a trump against a\n"
    "non-trump lead. The winner draws first and leads the next trick.\n\n"
    "Full rules: https://en.wikipedia.org/wiki/Briscola\n\n"
    "Controls: click a card, or press 1 / 2 / 3.")

BURRACO_RULES = (
    "Two 54-card decks, 108 cards. Eleven each, two pots of eleven\n"
    "set aside, the rest is the stock.\n\n"
    "On your turn: draw one card or take the whole discard pile, lay\n"
    "down or extend as many melds as you like, then discard one card.\n\n"
    "Melds are three or more of the same rank, or a run in one suit.\n"
    "Jokers and twos are wild, one per meld. Seven cards or more is a\n"
    "burraco: 200 clean, 100 with a wild card in it.\n\n"
    "Running out of cards the first time earns you the pot; after that\n"
    "it closes the hand, which needs a burraco. Closing is worth 100,\n"
    "and a pot never taken - or taken too late to play - costs 100.\n\n"
    "Full rules: https://en.wikipedia.org/wiki/Buraco\n\n"
    "Controls: click your cards to pick them, then use the buttons.")

TRESSETTE_RULES = (
    "The same 40 cards as Briscola, and no trump suit at all. Ten cards\n"
    "each, twenty face down as the stock.\n\n"
    "Order inside a suit: 3 > 2 > A > K > Q > J > 7 > 6 > 5 > 4.\n"
    "The highest card of the suit led wins, and following suit is\n"
    "compulsory - cards you may not play are greyed out. The winner\n"
    "draws first, then the other; both draws are face up.\n\n"
    "Points are counted in thirds: the ace is worth three, the two, the\n"
    "three and the three faces one each, and the rest nothing. The last\n"
    "trick is worth three more. Your thirds are divided by three and the\n"
    "remainder thrown away, so a deal is worth eleven points.\n\n"
    "Declared from the hand as it is dealt, before a card is played:\n"
    "the ace, two and three of one suit is a napoletana, worth 3; three\n"
    "aces, twos or threes is worth 3, and four of them 4.\n\n"
    "Full rules: https://en.wikipedia.org/wiki/Tressette\n\n"
    "Controls: click a card, or press 1-9 and 0 for the tenth.")

SCOPA_RULES = (
    "The same 40 cards as Briscola. Four go face up on the table and\n"
    "you get three; three more come out when both hands are empty.\n\n"
    "Play a card: if it matches a table card it takes it, and if no\n"
    "single card matches it may take several that add up to it. Face\n"
    "cards count 8, 9 and 10. A card that takes nothing stays on the\n"
    "table. Clearing the table is a scopa, worth a point - except on\n"
    "the very last card of the hand.\n\n"
    "When the deck runs out, whoever captured last takes what is left.\n\n"
    "Then four points: most cards, most coins (diamonds here), the\n"
    "seven of coins, and the primiera - your best card in each suit,\n"
    "counting 7=21, 6=18, A=16, 5=15, 4=14, 3=13, 2=12, faces 10.\n"
    "Every scopa is a point of its own.\n\n"
    "Full rules: https://en.wikipedia.org/wiki/Scopa\n\n"
    "Controls: click a card to play it, or press 1 / 2 / 3. When more\n"
    "than one take is legal, click the table cards you want first.")


def _spec(key, play_keys, levels, labels, blurbs, targets, default, rules):
    return GameSpec(key, play_keys, tuple(levels), labels, blurbs,
                    tuple(targets), default, rules)


GAMES = {
    ui.BRISCOLA: _spec(
        ui.BRISCOLA, "123", briscola_ai.LEVELS, briscola_ai.LEVEL_LABELS,
        {
            briscola_ai.EASY: "Plays almost at random. A gentle start.",
            briscola_ai.NORMAL: "Solid classic play: it ducks and saves its trumps.",
            briscola_ai.HARD: "Counts cards and searches ahead. Hard to beat.",
        }, (), 0, BRISCOLA_RULES),
    ui.BURRACO: _spec(
        ui.BURRACO, "", burraco_view.burraco_ai.LEVELS,
        burraco_view.burraco_ai.LEVEL_LABELS,
        {
            burraco_ai.EASY: "Melds whatever it can, and throws away at random.",
            burraco_ai.NORMAL: "Builds towards burracos and weighs up taking the pile.",
            burraco_ai.HARD: "Experimental, and not currently the strongest.",
        }, burraco_engine.TARGETS, burraco_engine.DEFAULT_TARGET, BURRACO_RULES),
    ui.SCOPA: _spec(
        ui.SCOPA, "123", scopa_ai.LEVELS, scopa_ai.LEVEL_LABELS,
        {
            scopa_ai.EASY: "Takes whatever it happens to pick. A gentle start.",
            scopa_ai.NORMAL: "Takes the valuable cards and avoids handing you a scopa.",
            scopa_ai.HARD: "Deals out the cards it cannot see and plays them out.",
        }, scopa_engine.TARGETS, scopa_engine.DEFAULT_TARGET, SCOPA_RULES),
    ui.TRESSETTE: _spec(
        ui.TRESSETTE, "1234567890", tressette_ai.LEVELS,
        tressette_ai.LEVEL_LABELS,
        {
            tressette_ai.EASY: "Plays any card the rules allow. A gentle start.",
            tressette_ai.NORMAL: "Knows which card commands a suit, and spends nothing.",
            tressette_ai.HARD: "Deals out the cards it cannot see and plays them out.",
        }, tressette_engine.TARGETS, tressette_engine.DEFAULT_TARGET, TRESSETTE_RULES),
}


def spec_for(kind: str) -> GameSpec:
    """Return metadata for a game or raise a useful error for bad input."""
    try:
        return GAMES[kind]
    except KeyError as exc:
        raise ValueError(f"unknown game kind: {kind!r}") from exc
