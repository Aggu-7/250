"""PlayerView: the ONLY thing an agent ever receives.

Phase 7 keeps this minimal (own hand + public information). Phase 8 will extend it
(publicly_seen_cards, known_friends/antis, beliefs) and add tests proving no leaks.
It deliberately has NO field for other hands or actual teams.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .card import Card, Suit, sort_hand
from .game_state import GameState, Phase


@dataclass(frozen=True)
class PublicTrick:
    leader: int
    plays: Tuple[Tuple[int, Card], ...]
    winner: Optional[int]


@dataclass(frozen=True)
class PlayerView:
    player_id: int
    phase: Phase
    my_hand: Tuple[Card, ...]
    bids: Tuple[Tuple[int, Optional[int]], ...]
    caller: Optional[int]
    bid: Optional[int]
    trump: Optional[Suit]
    called_cards: Optional[Tuple[Card, Card]]
    current_trick: Tuple[Tuple[int, Card], ...]
    trick_history: Tuple[PublicTrick, ...]

    @property
    def publicly_played(self) -> Tuple[Card, ...]:
        cards = [c for t in self.trick_history for _, c in t.plays]
        cards += [c for _, c in self.current_trick]
        return tuple(cards)


def make_view(state: GameState, player_id: int) -> PlayerView:
    """Engine-side factory: copies only what `player_id` may legitimately know."""
    trick = state.current_trick
    return PlayerView(
        player_id=player_id,
        phase=state.phase,
        my_hand=tuple(sort_hand(state.hands[player_id])),
        bids=tuple(state.bids),
        caller=state.caller,
        bid=state.bid,
        trump=state.trump,
        called_cards=state.called_cards,
        current_trick=tuple(trick.plays) if trick else (),
        trick_history=tuple(
            PublicTrick(t.leader, tuple(t.plays), t.winner) for t in state.tricks
        ),
    )
