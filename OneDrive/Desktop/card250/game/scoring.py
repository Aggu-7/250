"""Point values and round scoring (Phase 6)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set, TYPE_CHECKING

from .card import Card, Rank, Q_SPADES
from .deck import build_deck
from .player import PLAYER_IDS

if TYPE_CHECKING:
    from .game_state import GameState

_POINTS = {Rank.ACE: 20, Rank.KING: 15, Rank.QUEEN: 10, Rank.JACK: 5}
Q_SPADES_POINTS = 60


def card_points(card: Card) -> int:
    if card == Q_SPADES:
        return Q_SPADES_POINTS
    return _POINTS.get(card.rank, 0)


def total_deck_points() -> int:
    return sum(card_points(c) for c in build_deck())  # == 250


def cards_points(cards: Iterable[Card]) -> int:
    return sum(card_points(c) for c in cards)


@dataclass
class RoundResult:
    caller: int
    bid: int
    friends: Set[int]
    team_points: int
    success: bool
    points_won: Dict[int, int]
    deltas: Dict[int, int]


def score_round(state: "GameState") -> RoundResult:
    """Caller team = caller + holders of the called cards.

    Team succeeds if it collects at least `bid` points.
    Assumed payout (easy to change): caller ±bid, each friend ±bid//2, antis 0.
    """
    team = state.caller_team()
    team_pts = sum(state.points_won[p] for p in team)
    success = team_pts >= state.bid
    sign = 1 if success else -1
    deltas = {p: 0 for p in PLAYER_IDS}
    deltas[state.caller] = sign * state.bid
    for f in state.friends:
        deltas[f] = sign * (state.bid // 2)
    return RoundResult(state.caller, state.bid, set(state.friends), team_pts,
                       success, dict(state.points_won), deltas)
