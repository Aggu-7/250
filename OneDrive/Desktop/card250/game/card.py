"""Cards, suits and ranks. Pure data; no game logic."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class Suit(Enum):
    SPADES = "♠"
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"

    @property
    def letter(self) -> str:
        return self.name[0]  # S, H, D, C

    def __str__(self) -> str:
        return self.value


class Rank(IntEnum):
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def label(self) -> str:
        return {11: "J", 12: "Q", 13: "K", 14: "A"}.get(int(self), str(int(self)))


_LABEL_TO_RANK = {r.label: r for r in Rank}
_LETTER_TO_SUIT = {s.letter: s for s in Suit}
_SYMBOL_TO_SUIT = {s.value: s for s in Suit}
_SUIT_ORDER = {s: i for i, s in enumerate(Suit)}


@dataclass(frozen=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.label}{self.suit.value}"

    __repr__ = __str__

    @property
    def sort_key(self):
        return (_SUIT_ORDER[self.suit], -int(self.rank))

    @staticmethod
    def parse(text: str) -> "Card":
        """Parse 'AH', 'ah', 'A♥', '10D', 'qs' ..."""
        t = text.strip().upper()
        if len(t) < 2:
            raise ValueError(f"Cannot parse card: {text!r}")
        suit_ch, rank_txt = t[-1], t[:-1]
        suit = _SYMBOL_TO_SUIT.get(suit_ch) or _LETTER_TO_SUIT.get(suit_ch)
        rank = _LABEL_TO_RANK.get(rank_txt)
        if suit is None or rank is None:
            raise ValueError(f"Cannot parse card: {text!r}")
        return Card(rank, suit)


Q_SPADES = Card(Rank.QUEEN, Suit.SPADES)
A_SPADES = Card(Rank.ACE, Suit.SPADES)


def sort_hand(cards) -> list:
    return sorted(cards, key=lambda c: c.sort_key)
