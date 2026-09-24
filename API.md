# 250 HTTP API

The API keeps `GameState` on the server and returns only P1's `PlayerView` plus public game information. P2–P5 take their turns automatically. Interactive docs are available at `/docs` while the server is running.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn api:app --reload
```

The API listens at `http://127.0.0.1:8000`. CORS defaults to local Vite and React development origins. Set `FRONTEND_ORIGINS` to a comma-separated list of allowed frontend origins when deployed.

## Endpoints

### `GET /api/health`

Returns `{ "ok": true }`.

### `POST /api/games`

Starts one game and returns the first P1 prompt. `seed` is optional.

```json
{ "seed": 123 }
```

The response includes `game_id` and a one-game `access_token`. Store the token for this game and send it as `Authorization: Bearer <access_token>` on later requests. Example response:

```json
{
  "game_id": "opaque-game-id",
  "access_token": "one-game-token",
  "status": "active",
  "prompt": "bid",
  "view": {
    "player_id": 1,
    "phase": "bidding",
    "my_hand": ["A♥", "K♣", "9♦", "5♠"],
    "bids": [],
    "caller": null,
    "bid": null,
    "trump": null,
    "called_cards": null,
    "current_trick": null,
    "trick_history": [],
    "to_play": null,
    "points_won": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
    "revealed_friends": []
  },
  "action_options": {"bid_min": 100, "bid_max": 250, "bid_step": 5}
}
```

### `GET /api/games/{game_id}`

Returns the latest P1 view. Requires the game bearer token.

### `POST /api/games/{game_id}/actions`

Submits one human action. The server validates it, plays bot turns, then returns the next P1 prompt or the final result. Requires the game bearer token.

```json
{ "type": "bid", "amount": 205 }
{ "type": "pass" }
{ "type": "call", "trump": "♦", "friend_cards": ["A♦", "A♣"] }
{ "type": "play", "card": "A♥" }
```

Active responses contain `status`, `prompt` (`bid`, `call`, or `play`), `view`, and `action_options`. The view includes only `my_hand`, bids, public trick history, public points, and called cards. It never includes opponents' hands, undealt cards, or hidden team membership. `revealed_friends` lists only players whose called card has appeared.

When `status` is `done`, the response also contains `result` with the caller, bid, revealed final friends, points, success, and score changes. Errors use `{ "error": { "code": "...", "message": "..." } }`.

The initial implementation stores active games in process memory. Restarting the API loses those games; use a persistent store before running multiple backend instances or requiring games to survive deploys.
