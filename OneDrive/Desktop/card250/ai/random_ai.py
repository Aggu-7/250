"""Random baseline agent (Phase 7)."""
from __future__ import annotations

import random
import math
from typing import Optional, Sequence, Tuple

from game.card import Card, Suit, Rank, A_SPADES
from game.deck import build_deck
from game.player import PLAYER_IDS, next_player
from game.trick import trick_winner
from game.view import PlayerView
from .base_ai import BaseAI


class RandomAI(BaseAI):
    def __init__(self, player_id: int, rng: Optional[random.Random] = None):
        super().__init__(player_id)
        self.rng = rng or random.Random()

    def _trump_strength(self, hand, trump: Suit) -> float:
        """Estimate opening-hand strength if `trump` is selected."""
        counts = {suit: 0 for suit in Suit}
        score = 0.0
        for card in hand:
            counts[card.suit] += 1
            if card.suit == trump:
                score += {
                    Rank.ACE: 10.0, Rank.KING: 7.0,
                    Rank.QUEEN: 4.0, Rank.JACK: 2.0,
                }.get(card.rank, 0.0)
            elif card.rank == Rank.ACE and card != A_SPADES:
                score += 7.0
            elif card.rank == Rank.KING:
                score += 3.0
            elif card.rank == Rank.QUEEN:
                score += 1.0
            elif card.rank == Rank.JACK:
                score += 0.5

            # Q♠ is the 60-point card, so its impact is large in every suit.
            if card == Card(Rank.QUEEN, Suit.SPADES):
                score += 6.0

        score += {1: 0.0, 2: 1.0, 3: 2.0, 4: 3.0}.get(counts[trump], 0.0)

        # Friend-call options add expected team strength. A♠ is never callable.
        called_options = []
        trump_ace = Card(Rank.ACE, trump)
        if trump != Suit.SPADES and trump_ace not in hand:
            called_options.append((trump_ace, 2.5))
        for suit in (Suit.DIAMONDS, Suit.HEARTS, Suit.CLUBS):
            ace = Card(Rank.ACE, suit)
            if ace not in hand and ace not in [c for c, _ in called_options]:
                called_options.append((ace, 1.5))
        if A_SPADES in hand:
            queen_spades = Card(Rank.QUEEN, Suit.SPADES)
            if queen_spades not in hand:
                called_options.append((queen_spades, 1.0))
        king_trump = Card(Rank.KING, trump)
        if king_trump not in hand and king_trump not in [c for c, _ in called_options]:
            called_options.append((king_trump, 0.75))
        called_options.sort(key=lambda item: item[1], reverse=True)
        score += sum(weight for _, weight in called_options[:2])
        if trump == Suit.SPADES and A_SPADES not in hand:
            score -= 3.0
        return score

    def _best_trump(self, view: PlayerView) -> tuple[Suit, float]:
        scored = [(suit, self._trump_strength(view.my_hand, suit)) for suit in Suit]
        best = max(score for _, score in scored)
        choices = [suit for suit, score in scored if score == best]
        return self.rng.choice(choices), best

    def bid(self, view: PlayerView, min_amount: int, max_amount: int) -> Optional[int]:
        # Evaluate every possible trump from our own first four cards and keep
        # that decision for the calling phase.
        trump, strength = self._best_trump(view)
        self.planned_trump = trump

        has_ace = any(c.rank == Rank.ACE and
                      (c.suit != Suit.SPADES or trump == Suit.SPADES)
                      for c in view.my_hand)
        trump_count = sum(c.suit == trump for c in view.my_hand)
        exceptional_without_ace = strength >= 18.0 and (
            trump_count >= 3 or Card(Rank.QUEEN, Suit.SPADES) in view.my_hand)
        # A hand without a useful Ace normally should not enter at 180.
        if not has_ace and not exceptional_without_ace:
            return None

        if strength < 7.0:
            ceiling = 175
        elif strength < 10.0:
            ceiling = 185
        elif strength < 13.0:
            ceiling = 195
        elif strength < 16.0:
            ceiling = 205
        elif strength < 19.0:
            ceiling = 215
        elif strength < 23.0:
            ceiling = 220
        elif strength < 27.0:
            ceiling = 230
        else:
            ceiling = 250

        top = min(max_amount, ceiling)
        first = max(180, ((min_amount + 4) // 5) * 5)
        if first > top:
            return None
        bids = list(range(first, top + 1, 5))
        target = min(210.0, 195.0 + max(0.0, strength - 13.0) * 1.25)
        weights = [math.exp(-0.5 * ((bid - target) / 7.0) ** 2) for bid in bids]
        return self.rng.choices(bids, weights=weights, k=1)[0]

    def choose_call(self, view: PlayerView) -> Tuple[Suit, Tuple[Card, Card]]:
        trump = getattr(self, "planned_trump", None)
        if trump is None:
            trump, _ = self._best_trump(view)

        # Name meaningful high cards, with priorities guided by our hand.
        # Calling a card already held would point to ourselves as a friend.
        face_ranks = (Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)
        pool = [c for c in build_deck()
                if c not in view.my_hand and c != A_SPADES and c.rank in face_ranks]
        chosen = []
        trump_ace = Card(Rank.ACE, trump)
        if trump_ace in pool:
            chosen.append(trump_ace)  # always first when it is callable
            pool.remove(trump_ace)

        def weight(card: Card) -> float:
            if card.rank == Rank.ACE:
                return 8.0
            if card == Card(Rank.KING, trump):
                return 5.0
            if card == Card(Rank.QUEEN, Suit.SPADES) and A_SPADES in view.my_hand:
                return 3.0
            return 0.5

        while len(chosen) < 2:
            candidates = [c for c in pool if c not in chosen]
            if not candidates:
                break
            card = self.rng.choices(candidates, weights=[weight(c) for c in candidates], k=1)[0]
            chosen.append(card)
            pool.remove(card)

        # A normal eight-card hand always leaves enough callable face cards.
        # Keep custom or partial views valid as well.
        if len(chosen) < 2:
            fallback = [c for c in build_deck()
                        if c != A_SPADES and c.rank in face_ranks and c not in chosen]
            chosen.extend(self.rng.sample(fallback, 2 - len(chosen)))
        return trump, (chosen[0], chosen[1])

    def choose_card(self, view: PlayerView, legal_cards: Sequence[Card]) -> Card:
        if view.current_trick and view.trump is not None:
            plays = list(view.current_trick)
            winner_now = trick_winner(plays, view.trump)
            winning_card = next(c for p, c in plays if p == winner_now)
            allies = {view.caller} if view.caller is not None else set()
            # A played called card publicly identifies its holder as a friend.
            for trick in view.trick_history:
                allies.update(p for p, c in trick.plays if c in (view.called_cards or ()))
            allies.update(p for p, c in plays if c in (view.called_cards or ()))
            self_is_friend = (self.player_id in allies or
                              bool(set(view.my_hand) & set(view.called_cards or ())))

            # An Ace that overtakes the current winner is a real winning play.
            # Friends can use a led-suit Ace to take a trick for their team,
            # but should not burn the trump Ace to overtake the caller's lead.
            winning_aces = [c for c in legal_cards if c.rank == Rank.ACE
                            and trick_winner(plays + [(self.player_id, c)], view.trump)
                            == self.player_id]
            caller_is_winning = view.caller is not None and winner_now == view.caller
            if winning_aces:
                if self_is_friend and caller_is_winning:
                    led_suit_aces = [c for c in winning_aces
                                     if c.suit == plays[0][1].suit]
                    if led_suit_aces:
                        return led_suit_aces[0]
                elif not (self_is_friend and caller_is_winning):
                    return winning_aces[0]

            # If a known teammate already has the trick, avoid cutting them.
            # Also avoid wasting a trump that cannot beat the trump already in
            # the trick (e.g. throwing 10♦ under A♦). Prefer a cheap discard.
            winner_is_friend = winner_now in allies
            avoid_overtake = self_is_friend and caller_is_winning
            cannot_win_with_trump = (winning_card.suit == view.trump and
                                     all(c.suit != view.trump or
                                         int(c.rank) <= int(winning_card.rank)
                                         for c in legal_cards))
            if avoid_overtake or (winner_is_friend and cannot_win_with_trump):
                discards = [c for c in legal_cards if c.suit != view.trump]
                if discards:
                    return min(discards, key=lambda c: int(c.rank))
                nonwinning = [c for c in legal_cards
                              if trick_winner(plays + [(self.player_id, c)], view.trump)
                              != self.player_id]
                if nonwinning:
                    return min(nonwinning, key=lambda c: int(c.rank))

        # When leading, an Ace is currently unbeatable in its suit. Estimate
        # the chance that a later player can void that suit and cut with trump
        # by sampling plausible unseen hands. Long suits in our hand reduce
        # the unseen supply and therefore naturally lower the cut risk.
        if not view.current_trick and view.trump is not None:
            aces = [c for c in legal_cards if c.rank == Rank.ACE]
            if aces:
                unseen = [c for c in build_deck()
                          if c not in view.my_hand and c not in view.publicly_played]
                opponents = [p for p in PLAYER_IDS if p != self.player_id]
                counts = {p: 8 - sum(1 for t in view.trick_history
                                     for pid, _ in t.plays if pid == p)
                          for p in opponents}
                samples = 160
                survival = {}
                for ace in aces:
                    wins = 0
                    for _ in range(samples):
                        pool = list(unseen)
                        hands = {}
                        for pid in opponents:
                            n = max(0, min(counts[pid], len(pool)))
                            hands[pid] = self.rng.sample(pool, n)
                            chosen = set(hands[pid])
                            pool = [c for c in pool if c not in chosen]
                        plays = [(self.player_id, ace)]
                        pid = next_player(self.player_id)
                        for _turn in range(4):
                            hand = hands[pid]
                            follow = [c for c in hand if c.suit == ace.suit]
                            options = follow or hand
                            if not options:
                                break
                            card = self.rng.choice(options)
                            hand.remove(card)
                            plays.append((pid, card))
                            pid = next_player(pid)
                        if len(plays) == 5 and trick_winner(plays, view.trump) == self.player_id:
                            wins += 1
                    survival[ace] = wins / samples
                # Prefer the Ace most likely to hold the trick; play it when
                # the estimate says it is more likely than not to survive.
                best = max(aces, key=lambda c: survival[c])
                if survival[best] >= 0.5:
                    return best
        return self.rng.choice(list(legal_cards))
