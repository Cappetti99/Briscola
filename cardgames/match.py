"""A series of hands played to a target, shared by the games that need one.

Briscola is decided in a single game, but Burraco and Scopa are both played
over as many hands as it takes to reach a target, so the running score lives
here rather than in either of them.
"""

from dataclasses import dataclass, field

HUMAN, AI = 0, 1
PLAYERS = (HUMAN, AI)


@dataclass
class Match:
    """The running score of a series of hands played to a target.

    Reaching the target is not enough on its own: a player has to be ahead as
    well, so a match that arrives level carries on into another hand rather
    than ending in a draw nobody played for.

    A target of zero is the special case of a single hand, which is how a
    game that wants no series at all asks for one.
    """

    target: int = 0
    totals: list[int] = field(default_factory=lambda: [0, 0])
    hands: int = 0

    def add_hand(self, scores: list[int]) -> None:
        for player in PLAYERS:
            self.totals[player] += scores[player]
        self.hands += 1

    @property
    def single_hand(self) -> bool:
        return self.target <= 0

    @property
    def over(self) -> bool:
        if self.single_hand:
            return self.hands >= 1
        if max(self.totals) < self.target:
            return False
        return self.totals[HUMAN] != self.totals[AI]

    def leader(self) -> int | None:
        if self.totals[HUMAN] == self.totals[AI]:
            return None
        return HUMAN if self.totals[HUMAN] > self.totals[AI] else AI

    def winner(self) -> int | None:
        return self.leader() if self.over else None

    def to_go(self, player: int) -> int:
        """Points still needed, which is what a player is really playing for."""
        if self.single_hand:
            return 0
        return max(0, self.target - self.totals[player])
