# Backend Integration Guide

This document is for backend developers integrating the Battleship engine and trained AI with a local-storage-first frontend.

Canonical architecture, endpoint contracts, snapshot schema, and numeric encodings:

- docs/SOFTWARE_ARCHITECTURE.md

## 1. Crucial Source Files

- game/game.py
- AI/agent.py
- AI/checkpoints/final_model_placement.weights.h5
- AI/checkpoints/final_model_targeting.weights.h5

## 2. Objects and Methods You Should Call

From game/game.py:

- Game()
- Game.from_snapshot(snapshot)
- game.load_snapshot(snapshot)
- game.to_snapshot()
- game.place_ship(player, ship_name, row, col, orientation)
- game.fire(player, row, col)
- game.get_state(player)
- game.get_ai_state(player)

From AI/agent.py:

- Agent.load("AI/checkpoints/final_model")
- ai_agent.place_all_ships(board, rng)
- ai_agent.choose_shot(ai_state)

## 3. Request Flow (Implementation View)

1. Start game
- Create Game().
- Place AI ships.
- Return snapshot + player-safe state.

2. Placement action
- Restore Game.from_snapshot(snapshot).
- Apply place_ship for player 1.
- Return updated snapshot + state.

3. Fire action
- Restore Game.from_snapshot(snapshot).
- Apply player fire.
- If AI turn begins, resolve AI turn in same request.
- Return shot results + updated snapshot + state.

4. Save/resume
- Frontend persists snapshot in local storage.
- On resume, backend rebuilds state from snapshot.

## 4. Error Semantics from game.fire

Possible non-success errors:

- Not in battle phase
- Not this player's turn
- Coordinates out of bounds
- Cell has already been targeted

Pass these through directly so frontend can display actionable feedback.

## 5. AI Integration Pattern

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

## 6. Concurrency Notes

- Keep each request isolated to one snapshot instance.
- If a server-side session mode is added later, lock per game/session.
- Do not share one mutable Game across independent games.

## 7. Minimal Backend Acceptance Checklist

- Can create a game and return snapshot + player-safe state.
- Can place all human ships from snapshot-based requests.
- Can resolve player and AI shots in correct turn order.
- Can return clear validation errors.
- Can restore game exactly from snapshot.
