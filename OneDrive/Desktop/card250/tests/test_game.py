import random

import pytest

from ai.random_ai import RandomAI
from game.card import Card, Suit, Rank, Q_SPADES, A_SPADES
from game.deck import build_deck, shuffled_deck
from game.game import Game
from game.game_state import GameState, Phase
from game.player import PLAYER_IDS
from game.rules import (IllegalMove, begin_play, get_legal_cards, play_card,
                        set_call, validate_call)
from game.scoring import card_points, total_deck_points, score_round
from game.trick import trick_winner
from game.view import make_view

C = Card.parse


def make_state(hands, trump="D", caller=1, bid=150):
    """Build a PLAY-phase state from {pid: 'AS KH ...'} for rule tests."""
    hs = {p: [C(x) for x in hands.get(p, "").split()] for p in PLAYER_IDS}
    s = GameState(hands=hs)
    s.caller, s.bid, s.phase = caller, bid, Phase.CALLING
    s.trump = Suit[{"S": "SPADES", "H": "HEARTS", "D": "DIAMONDS", "C": "CLUBS"}[trump]]
    begin_play(s)
    return s


# ---- deck / points ----
def test_deck_size_and_deal():
    d = shuffled_deck(random.Random(1))
    assert len(d) == 40 and len(set(d)) == 40
    s = GameState.new(random.Random(1))
    assert all(len(h) == 4 for h in s.hands.values())
    s.deal_remaining()
    assert all(len(h) == 8 for h in s.hands.values())
    all_cards = [c for h in s.hands.values() for c in h]
    assert sorted(map(str, all_cards)) == sorted(map(str, build_deck()))


@pytest.mark.parametrize("card,pts", [("AH", 20), ("KD", 15), ("QC", 10), ("JS", 5),
                                      ("10H", 0), ("9D", 0), ("5C", 0), ("QS", 60)])
def test_card_points(card, pts):
    assert card_points(C(card)) == pts


def test_total_points_250():
    assert total_deck_points() == 250


# ---- calling ----
def test_cannot_call_ace_of_spades():
    with pytest.raises(ValueError):
        validate_call(Suit.HEARTS, (A_SPADES, C("AH")))


def test_cannot_call_same_card_twice():
    with pytest.raises(ValueError):
        validate_call(Suit.HEARTS, (C("AH"), C("AH")))


def test_called_cards_identify_friends():
    hands = {1: "AH 5S 6S 7S", 2: "5H 6H 7H 8H", 3: "AD 9S 9H 9D", 4: "5C 6C 7C 8C", 5: "5D 6D 7D 8D"}
    s = GameState(hands={p: [C(x) for x in h.split()] for p, h in hands.items()})
    s.caller, s.phase = 1, Phase.CALLING
    set_call(s, Suit.DIAMONDS, (C("AH"), C("AD")))
    s.deal_remaining()
    assert s.friends == {3}
    assert s.caller_team() == {1, 3}


def test_caller_holding_both_cards_is_alone():
    s = GameState(hands={p: [] for p in PLAYER_IDS})
    s.hands[1] = [C("AH"), C("AD")]
    s.caller, s.phase = 1, Phase.CALLING
    set_call(s, Suit.CLUBS, (C("AH"), C("AD")))
    s.deal_remaining()
    assert s.friends == set() and s.caller_team() == {1}


# ---- legality / winner ----
def test_must_follow_suit():
    s = make_state({1: "5H 6S", 2: "KH 9S 8D"})
    play_card(s, 1, C("5H"))
    assert set(get_legal_cards(2, s)) == {C("KH")}


def test_may_cut_or_discard_when_void():
    s = make_state({1: "5H 6S", 2: "9S 8D 7C"}, trump="D")
    play_card(s, 1, C("5H"))
    assert set(get_legal_cards(2, s)) == {C("9S"), C("8D"), C("7C")}


def test_leader_may_play_anything_and_turn_enforced():
    s = make_state({1: "5H 6S", 2: "KH"})
    assert set(get_legal_cards(1, s)) == {C("5H"), C("6S")}
    with pytest.raises(IllegalMove):
        play_card(s, 2, C("KH"))


def test_illegal_card_rejected():
    s = make_state({1: "5H", 2: "KH 9S"})
    play_card(s, 1, C("5H"))
    with pytest.raises(IllegalMove):
        play_card(s, 2, C("9S"))


def test_trump_beats_non_trump():
    plays = [(1, C("AH")), (2, C("5D")), (3, C("KH")), (4, C("9S")), (5, C("6H"))]
    assert trick_winner(plays, Suit.DIAMONDS) == 2


def test_highest_trump_wins():
    plays = [(1, C("AH")), (2, C("5D")), (3, C("KD")), (4, C("9S")), (5, C("6H"))]
    assert trick_winner(plays, Suit.DIAMONDS) == 3


def test_highest_led_suit_wins_without_trump():
    plays = [(1, C("9H")), (2, C("AS")), (3, C("KH")), (4, C("5H")), (5, C("AC"))]
    assert trick_winner(plays, Suit.DIAMONDS) == 3


def test_trick_points_and_winner_collects_including_q_spades():
    s = make_state({1: "5H 6H", 2: "QS 7C", 3: "KH 6C", 4: "9H 7C", 5: "8H 8C"}, trump="D")
    for pid, c in [(1, "5H"), (2, "QS"), (3, "KH"), (4, "9H"), (5, "8H")]:
        t = play_card(s, pid, C(c))
    # QS is off-suit for hearts led, KH wins; trick has 60+15
    assert t.winner == 3 and t.points == 75
    assert s.points_won[3] == 75 and s.to_play == 3


# ---- scoring ----
def test_score_round_success_and_failure():
    s = make_state({}, bid=100)
    s.friends = {3}
    s.points_won = {1: 60, 2: 10, 3: 50, 4: 80, 5: 50}
    r = score_round(s)
    assert r.team_points == 110 and r.success
    assert r.deltas[1] == 100 and r.deltas[3] == 50 and r.deltas[2] == 0
    s.points_won = {1: 20, 2: 10, 3: 50, 4: 100, 5: 70}
    r = score_round(s)
    assert not r.success and r.deltas[1] == -100 and r.deltas[3] == -50


# ---- full random games ----
def test_random_games_complete_with_proper_bidding():
    for seed in range(150):
        rng = random.Random(seed)
        agents = {p: RandomAI(p, random.Random(rng.random())) for p in PLAYER_IDS}
        g = Game(agents, rng, log=lambda m: None, fixed_caller=None)
        r = g.run()
        s = g.state
        assert r.caller in PLAYER_IDS and r.bid >= 100
        assert s.bids
        assert s.phase == Phase.DONE
        assert len(s.tricks) == 8
        assert all(len(h) == 0 for h in s.hands.values())
        assert sum(s.points_won.values()) == 250
        assert len(set(s.played_cards())) == 40
        assert r.team_points == sum(s.points_won[p] for p in s.caller_team())


# ---- Phase 8 preview: view carries no hidden truth ----
def test_view_has_no_hidden_fields_and_only_own_hand():
    s = GameState.new(random.Random(3))
    v = make_view(s, 2)
    assert set(v.my_hand) == set(s.hands[2])
    for forbidden in ("hands", "actual_hands", "teams", "actual_teams", "friends", "undealt"):
        assert not hasattr(v, forbidden)
