# Battleship Bot Software Architecture

This document defines the core architecture for the project and is the canonical source for system design decisions.

## 1. Purpose and Scope

This architecture supports a single-player Battleship experience (human vs AI) with:

- Python game engine for game rules and state transitions
- AI model inference for ship placement and shot selection
- Frontend-first persistence using browser local storage
- Stateless backend API requests using snapshots

## 2. System Components

- Frontend UI (web app)
- Stateless Backend API (request processor)
- Game Engine (`game/game.py`)
- AI Agent Runtime (`AI/agent.py` + checkpoint weights)
- Local Storage Persistence (browser)

Model artifact strategy:

- Training environment (TensorFlow): saves `.h5` and `.npz` checkpoint copies.
- Inference-only environment (no TensorFlow): loads `.npz` checkpoints through NumPy backend.

## 3. High-Level Data Flow

1. Frontend starts new game via backend.
2. Backend creates a `Game`, resolves AI setup, returns:
   - full snapshot (authoritative state for save/resume)
   - player-safe render state
3. Frontend stores snapshot in local storage.
4. For every mutation request, frontend sends current snapshot + action.
5. Backend restores `Game` from snapshot, applies action, returns updated snapshot + state.
6. Frontend overwrites local storage snapshot with the new snapshot.

## 4. State Ownership and Persistence

Primary persistence strategy:

- Browser local storage is the primary save mechanism.
- Backend is stateless by default and does not require a session database for core play.

Tradeoffs:

- Pros: simple deployment, easy save/resume, fewer backend storage concerns.
- Cons: snapshot is user-accessible and not tamper-proof.

If requirements later include anti-cheat, multi-device continuity, or analytics-backed replay, add backend authoritative persistence.

## 5. API Contract (Canonical)

All API interfaces should return both:

- `snapshot`: full game snapshot for persistence
- `state`: player-safe game state for rendering

Recommended endpoints:

- `POST /api/game/new`
- `POST /api/game/place-ship`
- `POST /api/game/fire`
- `POST /api/game/state`

Request pattern (mutation):

- Include current `snapshot` and action payload.

Response pattern:

- Include operation result, updated `snapshot`, updated `state`.

## 6. Snapshot Contract (Canonical)

Snapshot must include enough information to restore a `Game` exactly:

- game-level: `phase`, `current_turn`, `winner`, `turn_count`
- per-player board state:
  - `grid`
  - `shot_tracker`
  - ship list with positions/hits/placement flags
  - placement status
  - cumulative stats

Engine methods:

- `game.to_snapshot()`
- `Game.from_snapshot(snapshot)`
- `game.load_snapshot(snapshot)`
- `game.fire_with_auto_ai_turn(...)`

## 7. Domain Encodings (Canonical)

`GridState` values (`your_board.grid`):

- `0`: empty
- `1`: ship present and unhit
- `2`: ship hit
- `3`: miss on your board

`ShotState` values (`your_board.shot_tracker`):

- `0`: unknown
- `-1`: miss on enemy board
- `1`: hit on enemy ship
- `2`: sunk ship segment

## 8. Turn Orchestration

Default behavior:

- Backend calls `game.fire_with_auto_ai_turn(...)`.
- Player shot is applied first.
- If AI turn begins and auto-resolve is enabled, AI shot is applied in the same request.
- Response returns both shot outcomes and updated state (and snapshot via endpoint contract).

This minimizes extra round trips and keeps turn sequencing consistent.

## 9. Security and Trust Boundary

Because local storage is the primary persistence mechanism:

- Client-held snapshot is considered convenient but untrusted.
- Do not use local-storage snapshots as secure proof of gameplay.

For trusted outcomes, backend must become authoritative and validate or own persisted state.

## 10. Error Model and Status Codes

Suggested status mapping:

- `200`: successful action/read
- `400`: invalid request data
- `404`: resource not found (if resource identifiers are introduced)
- `409`: invalid phase/turn/order conflict
- `500`: unexpected server failure

Expected game-rule errors include:

- Not in placement phase
- Not in battle phase
- Not this player's turn
- Coordinates out of bounds
- Cell has already been targeted
- Cannot place ShipName at (r, c)

## 11. Future Evolution

When scaling requirements change:

- Add backend session store and durable persistence.
- Introduce auth and per-user save ownership.
- Add replay/event log format for analytics.
- Keep this document as source-of-truth and have integration docs reference it.
