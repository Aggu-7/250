"""FastAPI adapter for the 250 game. The full GameState stays server-side."""
from __future__ import annotations

import random
import secrets
import threading
import os
from dataclasses import dataclass, field
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from ai.random_ai import RandomAI
from game.card import Card, Rank, Suit, A_SPADES
from game.deck import build_deck
from game.game_state import GameState, Phase
from game.player import PLAYER_IDS, next_player
from game.rules import begin_play, get_legal_cards, play_card, set_call, validate_call
from game.scoring import RoundResult, score_round
from game.view import make_view

MIN_BID = 100
MAX_BID = 250
BID_STEP = 5
FACE_RANKS = (Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE)

app = FastAPI(title="250 Card Game API", version="1.0.0")
origins = [origin.strip() for origin in
           os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
           if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(HTTPException)
async def http_error_response(_request: Request, exc: HTTPException) -> JSONResponse:
    code = {400: "invalid_action", 401: "unauthorized", 404: "not_found",
            409: "game_complete"}.get(exc.status_code, "request_error")
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"code": code, "message": str(exc.detail)}})


class NewGameRequest(BaseModel):
    seed: Optional[int] = None


class ActionRequest(BaseModel):
    type: Literal["bid", "pass", "call", "play"]
    amount: Optional[int] = None
    trump: Optional[str] = None
    friend_cards: Optional[list[str]] = None
    card: Optional[str] = None


@dataclass
class GameSession:
    game_id: str
    access_token: str
    rng: random.Random
    state: GameState
    agents: dict
    active_bidders: list[int] = field(default_factory=lambda: list(PLAYER_IDS))
    bid_high: Optional[int] = None
    bidder: Optional[int] = None
    bid_pid: int = 1
    prompt: Optional[str] = None
    result: Optional[RoundResult] = None
    lock: threading.RLock = field(default_factory=threading.RLock)


_games: dict[str, GameSession] = {}
_games_lock = threading.RLock()


def _suit_from_text(value: str) -> Suit:
    for suit in Suit:
        if value == suit.value or value.upper() == suit.letter:
            return suit
    raise ValueError("Suit must be one of ♠, ♥, ♦, ♣ or S, H, D, C")


def _card_from_text(value: str) -> Card:
    return Card.parse(value)


def _finish_call(session: GameSession, trump: Suit, friends: tuple[Card, Card]) -> None:
    set_call(session.state, trump, friends)
    session.state.deal_remaining()
    begin_play(session.state)


def _record_bid(session: GameSession, player_id: int, amount: Optional[int]) -> None:
    state = session.state
    floor = MIN_BID if session.bid_high is None else session.bid_high + BID_STEP
    if amount is None:
        session.active_bidders.remove(player_id)
        state.bids.append((player_id, None))
    else:
        if amount < floor or amount > MAX_BID or amount % BID_STEP:
            raise HTTPException(400, f"Bid must be a multiple of 5 between {floor} and {MAX_BID}.")
        session.bid_high, session.bidder = amount, player_id
        state.bids.append((player_id, amount))


def _advance(session: GameSession) -> None:
    """Run bot turns until P1 needs input or the round is over."""
    state = session.state
    while True:
        if state.phase == Phase.BIDDING:
            if len(session.active_bidders) <= 1:
                state.caller = session.active_bidders[0]
                state.bid = session.bid_high if session.bid_high is not None else MIN_BID
                state.phase = Phase.CALLING
                continue

            pid = session.bid_pid
            floor = MIN_BID if session.bid_high is None else session.bid_high + BID_STEP
            if pid in session.active_bidders and pid != session.bidder:
                if pid == 1 and floor <= MAX_BID:
                    session.prompt = "bid"
                    return
                if floor > MAX_BID:
                    amount = None
                else:
                    amount = session.agents[pid].bid(make_view(state, pid), floor, MAX_BID)
                _record_bid(session, pid, amount)
            session.bid_pid = next_player(pid)
            continue

        if state.phase == Phase.CALLING:
            if state.caller == 1:
                session.prompt = "call"
                return
            view = make_view(state, state.caller)
            trump, friends = session.agents[state.caller].choose_call(view)
            _finish_call(session, trump, friends)
            continue

        if state.phase == Phase.PLAY:
            pid = state.to_play
            if pid == 1:
                session.prompt = "play"
                return
            legal = get_legal_cards(pid, state)
            card = session.agents[pid].choose_card(make_view(state, pid), legal)
            play_card(state, pid, card)
            continue

        if state.phase == Phase.DONE:
            session.result = score_round(state)
            session.prompt = None
            return

        raise RuntimeError(f"Unexpected phase {state.phase}")


def _trick_json(trick) -> dict:
    return {
        "leader": trick.leader,
        "plays": [{"player_id": pid, "card": str(card)} for pid, card in trick.plays],
        "winner": trick.winner,
    }


def _response(session: GameSession, include_token: bool = False) -> dict:
    state = session.state
    view = make_view(state, 1)
    action_options = {}
    if session.prompt == "bid":
        action_options = {
            "bid_min": MIN_BID if session.bid_high is None else session.bid_high + BID_STEP,
            "bid_max": MAX_BID,
            "bid_step": BID_STEP,
        }
    elif session.prompt == "call":
        action_options = {
            "trump_suits": [s.value for s in Suit],
            "friend_cards": [str(c) for c in build_deck()
                             if c.rank in FACE_RANKS and c != A_SPADES],
        }
    elif session.prompt == "play":
        action_options = {"legal_cards": [str(c) for c in get_legal_cards(1, state)]}

    # This is intentionally built from PlayerView. Do not add hands/friends/
    # undealt fields from GameState to an active-game response.
    payload = {
        "game_id": session.game_id,
        "status": "done" if state.phase == Phase.DONE else "active",
        "prompt": session.prompt,
        "view": {
            "player_id": view.player_id,
            "phase": view.phase.value,
            "my_hand": [str(c) for c in view.my_hand],
            "bids": [{"player_id": pid, "amount": amount} for pid, amount in view.bids],
            "caller": view.caller,
            "bid": view.bid,
            "trump": view.trump.value if view.trump else None,
            "called_cards": [str(c) for c in view.called_cards] if view.called_cards else None,
            "current_trick": _trick_json(state.current_trick) if state.current_trick else None,
            "trick_history": [_trick_json(t) for t in state.tricks],
            "to_play": state.to_play,
            "points_won": {str(pid): points for pid, points in state.points_won.items()},
            "revealed_friends": sorted({
                pid
                for trick in [*state.tricks, *([state.current_trick] if state.current_trick else [])]
                for pid, card in trick.plays
                if view.called_cards and card in view.called_cards
            }),
        },
        "action_options": action_options,
    }
    if include_token:
        payload["access_token"] = session.access_token
    if session.result:
        result = session.result
        payload["result"] = {
            "caller": result.caller,
            "bid": result.bid,
            "friends": sorted(result.friends),
            "team_points": result.team_points,
            "success": result.success,
            "points_won": {str(pid): points for pid, points in result.points_won.items()},
            "score_delta": {str(pid): delta for pid, delta in result.deltas.items()},
        }
    return payload


def _get_session(game_id: str, authorization: Optional[str]) -> GameSession:
    with _games_lock:
        session = _games.get(game_id)
    if session is None:
        raise HTTPException(404, "Game not found.")
    expected = f"Bearer {session.access_token}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(401, "Missing or invalid game access token.")
    return session


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/games")
def create_game(request: NewGameRequest) -> dict:
    seed = request.seed if request.seed is not None else secrets.randbelow(2**32)
    rng = random.Random(seed)
    agents = {pid: RandomAI(pid, random.Random(rng.random())) for pid in PLAYER_IDS if pid != 1}
    session = GameSession(
        game_id=secrets.token_urlsafe(18),
        access_token=secrets.token_urlsafe(32),
        rng=rng,
        state=GameState.new(rng),
        agents=agents,
    )
    _advance(session)
    with _games_lock:
        _games[session.game_id] = session
    return _response(session, include_token=True)


@app.get("/api/games/{game_id}")
def get_game(game_id: str, authorization: Optional[str] = Header(default=None)) -> dict:
    session = _get_session(game_id, authorization)
    with session.lock:
        return _response(session)


@app.post("/api/games/{game_id}/actions")
def submit_action(game_id: str, action: ActionRequest,
                  authorization: Optional[str] = Header(default=None)) -> dict:
    session = _get_session(game_id, authorization)
    with session.lock:
        if session.prompt is None:
            raise HTTPException(409, "This game is already complete.")

        state = session.state
        expected = session.prompt
        if expected == "bid":
            if action.type == "pass":
                _record_bid(session, 1, None)
            elif action.type == "bid" and action.amount is not None:
                _record_bid(session, 1, action.amount)
            else:
                raise HTTPException(400, "Expected a bid or pass action.")
            session.bid_pid = next_player(1)

        elif expected == "call":
            if action.type != "call" or action.trump is None or action.friend_cards is None:
                raise HTTPException(400, "Expected trump and two friend_cards.")
            try:
                trump = _suit_from_text(action.trump)
                friends = tuple(_card_from_text(c) for c in action.friend_cards)
                if len(friends) != 2:
                    raise ValueError("Choose exactly two friend cards.")
                if any(c.rank not in FACE_RANKS for c in friends):
                    raise ValueError("Friend cards must be face cards (J, Q, K, or A).")
                validate_call(trump, friends)
                _finish_call(session, trump, friends)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

        elif expected == "play":
            if action.type != "play" or action.card is None:
                raise HTTPException(400, "Expected a play action with a card.")
            try:
                card = _card_from_text(action.card)
                if card not in get_legal_cards(1, state):
                    raise ValueError("That card is not legal now.")
                play_card(state, 1, card)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

        _advance(session)
        return _response(session)
