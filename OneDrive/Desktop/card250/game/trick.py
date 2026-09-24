"""A single trick and its deterministic resolution (Phase 5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .card import Card, Suit
from .player import NUM_PLAYERS
from .scoring import cards_points


def trick_winner(plays: List[Tuple[int, Card]], trump: Suit) -> int:
    """Highest trump wins; otherwise highest card of the led suit."""
    led = plays[0][1].suit
    trumps = [(p, c) for p, c in plays if c.suit == trump]
    pool = trumps if trumps else [(p, c) for p, c in plays if c.suit == led]
    return max(pool, key=lambda pc: int(pc[1].rank))[0]


@dataclass
class Trick:
    leader: int
    plays: List[Tuple[int, Card]] = field(default_factory=list)
    winner: Optional[int] = None

    @property
    def led_suit(self) -> Optional[Suit]:
        return self.plays[0][1].suit if self.plays else None

    @property
    def is_complete(self) -> bool:
        return len(self.plays) == NUM_PLAYERS

    @property
    def points(self) -> int:
        return cards_points(c for _, c in self.plays)

    def add(self, pid: int, card: Card) -> None:
        self.plays.append((pid, card))
