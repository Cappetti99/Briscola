"""Shared seating and team rules for future four-player games."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Participant:
    name: str
    human: bool = True


@dataclass(frozen=True)
class Team:
    name: str
    members: tuple[int, ...]


class Table:
    """A validated clockwise table for two players or two pairs."""

    def __init__(self, players: tuple[Participant, ...], teams: tuple[Team, ...] | None = None,
                 first: int = 0):
        if len(players) not in (2, 4):
            raise ValueError("a table needs two or four players")
        if len({player.name.strip() for player in players}) != len(players):
            raise ValueError("player names must be unique")
        if not 0 <= first < len(players):
            raise ValueError("invalid first player")
        self.players = players
        self.first = first
        if teams is None:
            teams = tuple(Team(player.name, (index,)) for index, player in enumerate(players))
        self.teams = teams
        self._validate_teams()

    def _validate_teams(self) -> None:
        if len(self.players) == 2:
            if len(self.teams) != 2 or any(len(team.members) != 1 for team in self.teams):
                raise ValueError("two-player tables need one team per player")
        elif len(self.teams) != 2 or any(len(team.members) != 2 for team in self.teams):
            raise ValueError("four-player tables need two pairs")
        members = [member for team in self.teams for member in team.members]
        if sorted(members) != list(range(len(self.players))):
            raise ValueError("teams must cover every player exactly once")

    @property
    def size(self) -> int:
        return len(self.players)

    def next_player(self, player: int) -> int:
        if not 0 <= player < self.size:
            raise ValueError("invalid player")
        return (player + 1) % self.size

    def partner(self, player: int) -> int | None:
        for team in self.teams:
            if player in team.members:
                partners = [member for member in team.members if member != player]
                return partners[0] if partners else None
        raise ValueError("player is not seated")

    def team_index(self, player: int) -> int:
        for index, team in enumerate(self.teams):
            if player in team.members:
                return index
        raise ValueError("player is not seated")

    def team_score(self, scores: list[int], team: int) -> int:
        if len(scores) != self.size:
            raise ValueError("one score is required for each player")
        if not 0 <= team < len(self.teams):
            raise ValueError("invalid team")
        return sum(scores[player] for player in self.teams[team].members)
