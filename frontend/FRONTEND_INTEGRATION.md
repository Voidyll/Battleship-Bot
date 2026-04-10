# Frontend Integration Guide

This document is for frontend developers integrating the Battleship UI with the backend game and AI APIs.

## 1. What Frontend Must Support

1. Placement UX for 5 ships.
2. Battle UX for shot selection and turn feedback.
3. Rendering of your board and opponent board from backend state.
4. Error handling for invalid moves and stale turns.
5. Endgame display with winner information.

## 2. Data You Receive

Primary payload comes from GET /api/games/{gameId}/state?player=1.

Important fields:

- phase: placement | battle | over
- current_turn: 1 or 2
- winner: null, 1, or 2
- turn_count: integer
- your_board.grid: 10x10 int matrix
- your_board.shot_tracker: 10x10 int matrix
- your_board.ships: ship metadata for local display
- opponent_board.grid: opponent-safe visibility only
- opponent_board.ships_sunk: list of sunk enemy ships

## 3. Cell Value Mapping for UI

Map numeric values to visual states.

From your_board.grid:

- 0: empty water
- 1: your ship segment (unhit)
- 2: your ship segment hit
- 3: enemy miss on your board

From your_board.shot_tracker:

- 0: unknown on enemy board
- -1: your miss
- 1: your hit
- 2: enemy ship confirmed sunk segment

Recommendation:

- Render opponent target board from shot_tracker.
- Render your own fleet board from your_board.grid.

## 4. Frontend Game Flow

## 4.1 Create session

- Call POST /api/games once.
- Store gameId in page state or route parameter.

## 4.2 Placement phase

- Allow rotate and drag/click placement per ship.
- Submit each ship via POST /api/games/{id}/place-ship.
- After last ship placement, fetch fresh state.
- Backend may auto-place AI ships and switch to battle.

## 4.3 Battle phase

- Enable target clicks only when:
  - phase is battle
  - current_turn is player
  - target cell in shot_tracker is unknown

On click:

1. POST /api/games/{id}/fire with player row col.
2. Show returned playerShot result.
3. If backend auto-resolves AI turn, show aiShot result.
4. Refresh full state from response or follow-up GET.

## 4.4 End phase

- If phase is over, disable all interactions.
- Show winner banner.
- Offer Play Again action that calls reset/new game endpoint.

## 5. Suggested Frontend Types

~~~ts
type ShipView = {
  name: string;
  size: number;
  positions: [number, number][];
  hits: [number, number][];
  sunk: boolean;
};

type BoardView = {
  grid: number[][];
  ships?: ShipView[];
  shot_tracker?: number[][];
  ships_sunk?: ShipView[];
};

type GameStateResponse = {
  phase: "placement" | "battle" | "over";
  current_turn: 1 | 2;
  winner: 1 | 2 | null;
  turn_count: number;
  your_board: BoardView;
  opponent_board: BoardView;
};
~~~

## 6. Rendering Guidance

Your board panel:

- Uses your_board.grid and your_board.ships.
- During placement, preview orientation and collision before submit.

Opponent board panel:

- Use your_board.shot_tracker for all target interactions.
- Never infer hidden enemy ships from opponent_board.grid.

Hit feedback:

- Show result string from fire response immediately.
- On sunk_ship_name, highlight ship sunk event in log/toast.

## 7. Error Handling UX

Expect these backend errors:

- Not in placement phase
- Not in battle phase
- Not this player's turn
- Coordinates out of bounds
- Cell has already been targeted
- Cannot place ShipName at (r, c)

UI behavior:

- Show non-blocking toast for invalid action.
- Keep board state unchanged on failed mutation.
- Re-fetch state on turn mismatch to resync.

## 8. Networking Strategy

Turn-based play can use simple request-response calls.

Recommended:

- Use fire endpoint that can auto-resolve AI turn for fewer round trips.
- Re-fetch state after mutations if not already included in response.
- Debounce repeated click input during in-flight requests.

Optional:

- Poll GET state every 1 to 2 seconds if multi-client spectators are needed.

## 9. UX Checklist for Integration Completion

- Placement works for all 5 ships with orientation toggle.
- Illegal placements are blocked and explained.
- Battle board accepts legal shots only.
- Hit miss sunk and winner are correctly displayed.
- AI move appears reliably after player turn.
- Board is fully resettable for new game.

## 10. Quick Request Sequence Example

1. POST /api/games
2. POST /api/games/{id}/place-ship x5
3. GET /api/games/{id}/state?player=1
4. POST /api/games/{id}/fire repeatedly until phase is over
5. GET /api/games/{id}/state?player=1 for final render

This flow is sufficient for a complete single-player human-vs-AI UI.
