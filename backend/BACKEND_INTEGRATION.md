# Backend Integration Guide

This document is for backend developers integrating the Battleship game engine and trained AI into HTTP endpoints.

## 1. Crucial Source Files

- game/game.py
- AI/agent.py
- AI/checkpoints/final_model_placement.weights.h5
- AI/checkpoints/final_model_targeting.weights.h5

These are the only runtime-critical files for web gameplay integration.

## 2. Runtime Responsibilities

Backend must provide:

1. Session management: one Game instance per active game.
2. Turn-safe mutation of game state through HTTP endpoints.
3. AI move generation using the trained agent.
4. Player-specific game state responses for UI rendering.

Recommended in-memory structure:

- sessions: dict[str, GameSession]
- GameSession fields:
  - game: Game
  - mode: str (for example human-vs-ai)
  - ai_player: int (usually 2)
  - created_at: datetime
  - updated_at: datetime

## 3. Objects and Methods You Should Call

From game/game.py:

- Game()
- game.place_ship(player, ship_name, row, col, orientation)
- game.fire(player, row, col)
- game.get_state(player)
- game.get_ai_state(player)
- game.is_over()
- game.reset()

From AI/agent.py:

- Agent.load("AI/checkpoints/final_model")
- ai_agent.place_all_ships(board, rng)
- ai_agent.choose_shot(ai_state)

Important:

- Agent.load uses base path without extension.
- It auto-loads matching placement and targeting weight files.

## 4. Canonical Game Lifecycle

1. Create session
- Create Game() and store it by game_id.
- Load AI agent once at process start, not per request.

2. Placement phase
- Human places ships via endpoint calls to game.place_ship(1, ...).
- AI places ships by calling ai_agent.place_all_ships(game.boards[2], rng).
- Game transitions to battle phase automatically once both boards are fully placed.

3. Battle phase
- Human fires using game.fire(1, row, col).
- If game is not over and current_turn becomes AI player:
  - ai_state = game.get_ai_state(2)
  - row, col = ai_agent.choose_shot(ai_state)
  - game.fire(2, row, col)

4. End of game
- game.phase becomes over.
- game.winner is set.
- Return final game state to client.

## 5. Recommended REST Endpoints

## 5.1 Create game

POST /api/games

Request body:

~~~json
{
  "mode": "human-vs-ai",
  "aiPlayer": 2
}
~~~

Response:

~~~json
{
  "gameId": "b6b8c1d2",
  "phase": "placement",
  "currentTurn": 1,
  "winner": null
}
~~~

## 5.2 Place a ship

POST /api/games/{gameId}/place-ship

Request body:

~~~json
{
  "player": 1,
  "shipName": "Carrier",
  "row": 0,
  "col": 0,
  "orientation": "H"
}
~~~

Backend call:

- game.place_ship(player, ship_name, row, col, orientation)

Response:

~~~json
{
  "success": true,
  "error": null,
  "phase": "placement"
}
~~~

When player 1 completes placement, backend should place AI ships immediately if not already placed.

## 5.3 Get current state for a player

GET /api/games/{gameId}/state?player=1

Backend call:

- game.get_state(player)

Response (shape mirrors game.get_state):

~~~json
{
  "phase": "battle",
  "current_turn": 1,
  "winner": null,
  "turn_count": 14,
  "your_board": {
    "grid": [[0,0,0],[...]],
    "ships": [
      {"name":"Carrier","size":5,"positions":[[0,0]],"hits":[],"sunk":false}
    ],
    "shot_tracker": [[0,0,-1],[...]]
  },
  "opponent_board": {
    "grid": [[0,0,2],[...]],
    "ships_sunk": []
  }
}
~~~

Note:

- opponent_board never reveals hidden ship locations.

## 5.4 Player fires

POST /api/games/{gameId}/fire

Request body:

~~~json
{
  "player": 1,
  "row": 4,
  "col": 7,
  "autoResolveAiTurn": true
}
~~~

Backend behavior:

1. Execute human shot.
2. If successful and not game_over and AI turn begins, execute AI shot.
3. Return both shot results in one response.

Response:

~~~json
{
  "playerShot": {
    "success": true,
    "result": "hit",
    "sunk_ship_name": null,
    "game_over": false,
    "winner": null,
    "error": null
  },
  "aiShot": {
    "success": true,
    "row": 2,
    "col": 3,
    "result": "miss",
    "sunk_ship_name": null,
    "game_over": false,
    "winner": null,
    "error": null
  },
  "state": {}
}
~~~

## 5.5 Explicit AI move endpoint (optional)

POST /api/games/{gameId}/ai-move

Use this when frontend wants strict step-by-step turn orchestration.

Response:

~~~json
{
  "row": 2,
  "col": 3,
  "result": "miss",
  "sunk_ship_name": null,
  "game_over": false,
  "winner": null
}
~~~

## 5.6 Reset game

POST /api/games/{gameId}/reset

Backend calls game.reset(), optionally auto-place AI ships.

## 6. Numeric Encodings Used by the Engine

GridState values for your_board.grid:

- 0 empty
- 1 ship present and unhit
- 2 ship hit
- 3 miss on your board

ShotState values for your_board.shot_tracker:

- 0 unknown
- -1 miss on enemy board
- 1 hit on enemy ship
- 2 sunk ship segment

These should be mapped to frontend display tokens.

## 7. Error Semantics from game.fire

Possible non-success errors:

- Not in battle phase
- Not this player's turn
- Coordinates out of bounds
- Cell has already been targeted

Always pass through these errors so frontend can display actionable feedback.

## 8. AI Integration Pattern (Production Safe)

At app startup:

~~~python
from AI.agent import Agent
ai_agent = Agent.load("AI/checkpoints/final_model")
~~~

During requests:

~~~python
ai_state = game.get_ai_state(ai_player)
row, col = ai_agent.choose_shot(ai_state)
result = game.fire(ai_player, row, col)
~~~

For AI placement:

~~~python
import numpy as np
rng = np.random.default_rng()
ai_agent.place_all_ships(game.boards[ai_player], rng)
~~~

## 9. Concurrency and Session Notes

- Protect each session with a lock if requests can race.
- Do not share one Game object across multiple game IDs.
- Expire old sessions to avoid memory growth.
- Persist minimal replay data if you need analytics.

## 10. Suggested Status Codes

- 200: successful game mutation or read
- 400: invalid request body or invalid move attempt
- 404: unknown gameId
- 409: action violates game phase or turn order
- 500: unexpected server error

## 11. Minimal Backend Acceptance Checklist

- Can create a game and return state.
- Can place all human ships.
- Can place AI ships and transition to battle.
- Can fire legal shots with full validation.
- Can execute AI move from get_ai_state plus choose_shot.
- Can return player-safe state from get_state(player).
- Can end game correctly with winner set.
