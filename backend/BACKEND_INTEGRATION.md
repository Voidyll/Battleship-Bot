# Backend Integration Guide

This document is for backend developers integrating the Battleship engine and trained AI with a local-storage-first frontend.

Canonical architecture, endpoint contracts, snapshot schema, and numeric encodings:

- docs/GAME_AI_SOFTWARE_ARCHITECTURE.md

## 1. Crucial Source Files

- game/game.py
- AI/agent.py
- AI/checkpoints/final_model_placement.weights.h5
- AI/checkpoints/final_model_targeting.weights.h5

Recommended for inference-only environments (no TensorFlow):

- AI/checkpoints/final_model_placement.weights.npz
- AI/checkpoints/final_model_targeting.weights.npz

## 2. Objects and Methods You Should Call

From game/game.py:

- Game()
- Game.from_snapshot(snapshot)
- game.load_snapshot(snapshot)
- game.to_snapshot()
- game.place_ship(player, ship_name, row, col, orientation)
- game.fire(player, row, col)
- game.fire_with_auto_ai_turn(player, row, col, ai_player, choose_ai_shot, auto_resolve_ai_turn=True)
- game.get_state(player)
- game.get_ai_state(player)

From AI/agent.py:

- Agent.load("AI/checkpoints/final_model")
- ai_agent.place_all_ships(board, rng)
- ai_agent.choose_shot(ai_state)

Backend/runtime note:

- TensorFlow is required for training and reading `.h5` checkpoints.
- Inference can run without TensorFlow when `.npz` checkpoints exist.
- Training now exports `.npz` alongside `.h5` automatically.

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
- Call game.fire_with_auto_ai_turn(...).
- Return player_shot + ai_shot + updated snapshot + state.

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
turn_result = game.fire_with_auto_ai_turn(
	player=1,
	row=row,
	col=col,
	ai_player=2,
	choose_ai_shot=ai_agent.choose_shot,
	auto_resolve_ai_turn=True,
)
~~~

Example backend endpoint (pseudo-code):

~~~python
def post_fire(payload: dict) -> tuple[dict, int]:
	snapshot = payload.get('snapshot')
	player = int(payload.get('player', 1))
	row = int(payload['row'])
	col = int(payload['col'])
	auto_resolve_ai_turn = bool(payload.get('autoResolveAiTurn', True))

	if snapshot is None:
		return {'error': 'Missing snapshot'}, 400

	game = Game.from_snapshot(snapshot)

	turn_result = game.fire_with_auto_ai_turn(
		player=player,
		row=row,
		col=col,
		ai_player=2,
		choose_ai_shot=ai_agent.choose_shot,
		auto_resolve_ai_turn=auto_resolve_ai_turn,
	)

	response = {
		'playerShot': turn_result['player_shot'],
		'aiShot': turn_result['ai_shot'],
		'snapshot': game.to_snapshot(),
		'state': turn_result['state'],
	}

	status = 200 if response['playerShot'].get('success') else 409
	return response, status
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

## 7. Checkpoint Compatibility for Non-TensorFlow Users

If your environment cannot install TensorFlow (for example newer Python versions),
use `.npz` checkpoints for `Agent.load(...)`.

To generate `.npz` files for existing `.h5` checkpoints, run once in the training environment:

~~~bash
python AI/export_npz_checkpoints.py --checkpoints-dir AI/checkpoints
~~~

## 8. Minimal Backend Acceptance Checklist

- Can create a game and return snapshot + player-safe state.
- Can place all human ships from snapshot-based requests.
- Can resolve player and AI shots in correct turn order.
- Can return clear validation errors.
- Can restore game exactly from snapshot.
