# Frontend Integration Guide

This document is for frontend developers integrating the Battleship UI with a local-storage-first save flow.

Canonical architecture, endpoint contracts, snapshot schema, and numeric encodings:

- docs/SOFTWARE_ARCHITECTURE.md

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
- Use auto-resolve AI turn for fewer round trips.
- Replace local-storage snapshot with returned `snapshot`.
- Re-render from returned `state`.

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
