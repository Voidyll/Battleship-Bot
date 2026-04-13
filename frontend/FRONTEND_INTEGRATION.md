# Frontend Integration Guide

This document is for frontend developers integrating the Battleship UI with a local-storage-first save flow.

Canonical architecture, endpoint contracts, snapshot schema, and numeric encodings:

- docs/GAME_AI_SOFTWARE_ARCHITECTURE.md

## 1. Primary Save Strategy

- Store returned `snapshot` in browser local storage after each successful mutation.
- Treat backend as stateless for core single-player flow.

Recommended keys:

- battleship.activeSnapshot
- battleship.lastState
- battleship.saveVersion

## 2. What Frontend Must Support

1. Placement UX for 5 ships.
2. Battle UX for shot selection and turn feedback.
3. Save/resume through local-storage snapshots.
4. Rendering from backend `state` payloads.
5. Error handling for invalid actions and stale snapshots.

## 3. Runtime Flow (Implementation View)

1. New game
- Call POST /api/game/new.
- Save `snapshot` to local storage.
- Render from `state`.

2. Placement
- Send current `snapshot` + placement action.
- Replace local-storage snapshot with returned `snapshot`.
- Re-render from returned `state`.

3. Battle
- Send current `snapshot` + fire action.
- Backend resolves player shot and AI turn in the same request.
- Replace local-storage snapshot with returned `snapshot`.
- Re-render from returned `state`.

Battle request example:

~~~ts
const res = await fetch('/api/game/fire', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    snapshot: activeSnapshot,
    player: 1,
    row,
    col,
    autoResolveAiTurn: true,
  }),
});

const data = await res.json();
// data.playerShot, data.aiShot, data.snapshot, data.state
~~~

Expected response shape (simplified):

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
  "snapshot": {},
  "state": {}
}
~~~

4. Resume
- On page load, read local-storage snapshot.
- Optionally call POST /api/game/state to rebuild render-safe state.

## 4. UI Interaction Rules

Enable target clicks only when:

- phase is battle
- current_turn is player
- target cell in shot_tracker is unknown

On failure:

- show non-blocking error feedback
- do not overwrite current local-storage snapshot

## 5. Rendering Guidance

- Render your board from `your_board.grid`.
- Render opponent targeting board from `your_board.shot_tracker`.
- Never infer hidden opponent ship locations.

## 6. Suggested Frontend Types

~~~ts
type GameMutationResponse = {
  playerShot?: {
    success: boolean;
    result: "hit" | "miss" | null;
    sunk_ship_name: string | null;
    game_over: boolean;
    winner: 1 | 2 | null;
    error: string | null;
  };
  aiShot?: {
    success: boolean;
    row: number;
    col: number;
    result: "hit" | "miss" | null;
    sunk_ship_name: string | null;
    game_over: boolean;
    winner: 1 | 2 | null;
    error: string | null;
  } | null;
  snapshot: unknown;
  state: {
    phase: "placement" | "battle" | "over";
    current_turn: 1 | 2;
    winner: 1 | 2 | null;
    turn_count: number;
    your_board: {
      grid: number[][];
      shot_tracker?: number[][];
      ships?: unknown[];
    };
    opponent_board: {
      grid: number[][];
      ships_sunk?: unknown[];
    };
  };
};
~~~

## 7. Frontend Acceptance Checklist

- Snapshot is saved after each successful mutation.
- Game restores correctly after page refresh.
- Illegal actions are blocked and explained.
- Hit/miss/sunk/winner are correctly rendered.
- Play Again resets by clearing snapshot and starting a new game.
