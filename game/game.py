"""
Battleship Game Logic
=====================
Standard rules: 10×10 grid, 5 ships, alternating turns.

Ships (name, length):
  Carrier    – 5
  Battleship – 4
  Cruiser    – 3
  Submarine  – 3
  Destroyer  – 2

Usage (game loop):
    game = Game()
    game.place_ship(1, 'Carrier',    0, 0, Orientation.HORIZONTAL)
    ...  # place all 5 ships for both players
    result = game.fire(1, 3, 7)  # player 1 fires at row 3, col 7

AI integration:
    state = game.get_ai_state(player)   # neural-net input dict
    stats = game.get_stats(player)      # fitness data after game ends

Backend integration (TODO for backend team):
    - Create one Game instance per active game session.
    - Persist instances keyed by game_id in a session store.
    - Expose place_ship(), fire(), and get_state() via HTTP endpoints.
    - Call game.load_ai_model() to attach the baked-in AI agent.
"""

import numpy as np
from enum import IntEnum
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOARD_SIZE = 10

SHIP_DEFINITIONS: list[tuple[str, int]] = [
    ('Carrier',    5),
    ('Battleship', 4),
    ('Cruiser',    3),
    ('Submarine',  3),
    ('Destroyer',  2),
]

SHIP_NAMES: list[str] = [name for name, _ in SHIP_DEFINITIONS]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ShotState(IntEnum):
    """
    Values in a player's shot_tracker — what they know about the opponent's board.
    Used as neural-network input encoding.
    """
    UNKNOWN = 0   # cell not yet targeted
    MISS    = -1  # shot was a miss
    HIT     = 1   # shot was a hit (ship not yet sunk)
    SUNK    = 2   # hit cell belonging to a now-fully-sunk ship


class GridState(IntEnum):
    """
    Values in a player's own internal board grid.
    This is the full-knowledge view (only visible to the board's owner).
    """
    EMPTY = 0  # unoccupied, not yet targeted
    SHIP  = 1  # ship occupies this cell, not yet hit
    HIT   = 2  # opponent hit a ship here
    MISS  = 3  # opponent's shot missed here


class Orientation(IntEnum):
    HORIZONTAL = 0
    VERTICAL   = 1


class GamePhase:
    PLACEMENT = 'placement'
    BATTLE    = 'battle'
    OVER      = 'over'


# ---------------------------------------------------------------------------
# Ship
# ---------------------------------------------------------------------------

class Ship:
    def __init__(self, name: str, size: int) -> None:
        self.name: str = name
        self.size: int = size
        self.positions: list[tuple[int, int]] = []   # (row, col) pairs
        self.hits: set[tuple[int, int]] = set()
        self.placed: bool = False

    def place(self, row: int, col: int, orientation: Orientation) -> list[tuple[int, int]]:
        """Set ship positions from a start coordinate and orientation. Returns positions."""
        self.positions = []
        for i in range(self.size):
            if orientation == Orientation.HORIZONTAL:
                self.positions.append((row, col + i))
            else:
                self.positions.append((row + i, col))
        self.placed = True
        return self.positions

    def receive_hit(self, row: int, col: int) -> bool:
        """Record a hit. Returns True if (row, col) is on this ship."""
        if (row, col) in self.positions:
            self.hits.add((row, col))
            return True
        return False

    def is_sunk(self) -> bool:
        return len(self.hits) >= self.size

    def to_dict(self) -> dict:
        return {
            'name':      self.name,
            'size':      self.size,
            'positions': self.positions,
            'hits':      list(self.hits),
            'sunk':      self.is_sunk(),
        }


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

class Board:
    """
    Represents one player's board.

    grid:         Internal full-knowledge grid (EMPTY / SHIP / HIT / MISS).
                  Only shown to the board's owner.
    shot_tracker: This player's knowledge of the *opponent's* board
                  (UNKNOWN / MISS / HIT / SUNK). Used as neural-net input.
    """

    def __init__(self) -> None:
        self.grid = np.full(
            (BOARD_SIZE, BOARD_SIZE), int(GridState.EMPTY), dtype=np.int8
        )
        self.shot_tracker = np.full(
            (BOARD_SIZE, BOARD_SIZE), int(ShotState.UNKNOWN), dtype=np.int8
        )
        self.ships: list[Ship] = [Ship(name, size) for name, size in SHIP_DEFINITIONS]
        self._placed: set[str] = set()

        # Per-game stats (used by fitness function)
        self.shots_fired:    int = 0
        self.hits_made:      int = 0
        self.times_hit:      int = 0
        self.ships_sunk_by_me: int = 0

    # ---------------------------------------------------------------- placement

    def can_place(self, ship: Ship, row: int, col: int, orientation: Orientation) -> bool:
        for i in range(ship.size):
            r = row + (i if orientation == Orientation.VERTICAL   else 0)
            c = col + (i if orientation == Orientation.HORIZONTAL else 0)
            if not (0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE):
                return False
            if self.grid[r, c] != int(GridState.EMPTY):
                return False
        return True

    def place_ship(
        self, ship_name: str, row: int, col: int, orientation: Orientation
    ) -> bool:
        """Place a named ship. Returns True on success, False if invalid."""
        ship = self.get_ship(ship_name)
        if ship is None or ship_name in self._placed:
            return False
        if not self.can_place(ship, row, col, orientation):
            return False
        for r, c in ship.place(row, col, orientation):
            self.grid[r, c] = int(GridState.SHIP)
        self._placed.add(ship_name)
        return True

    def all_ships_placed(self) -> bool:
        return len(self._placed) == len(SHIP_DEFINITIONS)

    # ----------------------------------------------------------------- combat

    def receive_shot(self, row: int, col: int) -> dict:
        """
        Process an incoming shot fired by the opponent.

        Returns:
            result:    'hit' | 'miss' | 'already_shot'
            sunk_ship: Ship object if this shot completed a sinking, else None
        """
        cell = int(self.grid[row, col])
        if cell in (int(GridState.HIT), int(GridState.MISS)):
            return {'result': 'already_shot', 'sunk_ship': None}

        for ship in self.ships:
            if ship.receive_hit(row, col):
                self.grid[row, col] = int(GridState.HIT)
                self.times_hit += 1
                if ship.is_sunk():
                    return {'result': 'hit', 'sunk_ship': ship}
                return {'result': 'hit', 'sunk_ship': None}

        self.grid[row, col] = int(GridState.MISS)
        return {'result': 'miss', 'sunk_ship': None}

    def record_shot_result(
        self, row: int, col: int, result: str, sunk_ship: Optional[Ship] = None
    ) -> None:
        """
        Update this player's shot_tracker after they fired at the opponent.
        Call this after receive_shot() resolves on the opponent's board.
        """
        self.shots_fired += 1
        if result == 'miss':
            self.shot_tracker[row, col] = int(ShotState.MISS)
        elif sunk_ship is not None:
            # Mark all positions of the now-sunk ship (including prior hits)
            for r, c in sunk_ship.positions:
                self.shot_tracker[r, c] = int(ShotState.SUNK)
            self.hits_made += 1
            self.ships_sunk_by_me += 1
        else:
            self.shot_tracker[row, col] = int(ShotState.HIT)
            self.hits_made += 1

    def all_ships_sunk(self) -> bool:
        return all(s.is_sunk() for s in self.ships)

    # ----------------------------------------------------------------- helpers

    def get_ship(self, name: str) -> Optional[Ship]:
        return next((s for s in self.ships if s.name == name), None)

    def get_unshot_cells(self) -> list[tuple[int, int]]:
        """Returns all cells in shot_tracker still marked UNKNOWN."""
        rows, cols = np.where(self.shot_tracker == int(ShotState.UNKNOWN))
        return list(zip(rows.tolist(), cols.tolist()))

    # ---------------------------------------------------------------- serialization

    def to_dict(self, reveal: bool = False) -> dict:
        """
        Serialize board state.

        reveal=True:  Full view (for the board's owner). Includes ship positions.
        reveal=False: Opponent-safe view. Shows only HIT / MISS cells, not SHIP.
        """
        if reveal:
            return {
                'grid':         self.grid.tolist(),
                'ships':        [s.to_dict() for s in self.ships],
                'shot_tracker': self.shot_tracker.tolist(),
            }
        visible = np.where(
            self.grid == int(GridState.HIT),  int(GridState.HIT),
            np.where(
                self.grid == int(GridState.MISS), int(GridState.MISS),
                int(GridState.EMPTY)
            )
        ).tolist()
        return {
            'grid':        visible,
            'ships_sunk':  [s.to_dict() for s in self.ships if s.is_sunk()],
        }


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:
    """
    Manages a full Battleship game between two players (human or AI).

    Players are 1 and 2.
    Phases: 'placement' → 'battle' → 'over'

    Quick reference:
        game.place_ship(player, ship_name, row, col, orientation)
        game.fire(player, row, col)          → result dict
        game.get_state(player)               → JSON-serializable state dict
        game.get_ai_state(player)            → neural-net input dict
        game.get_stats(player)               → fitness / outcome dict

    Backend TODO:
        - Maintain a session store: { game_id: Game }
        - Route POST /game/{id}/place  → game.place_ship(...)
        - Route POST /game/{id}/fire   → game.fire(...)
        - Route GET  /game/{id}/state  → game.get_state(player)
        - Attach the pre-trained AI model and call ai.choose_shot(state) / ai.place_ships(board)
    """

    def __init__(self) -> None:
        self.boards: dict[int, Board] = {1: Board(), 2: Board()}
        self.phase:        str            = GamePhase.PLACEMENT
        self.current_turn: int            = 1
        self.winner:       Optional[int]  = None
        self.turn_count:   int            = 0

    # ---------------------------------------------------------------- placement

    def place_ship(
        self,
        player:      int,
        ship_name:   str,
        row:         int,
        col:         int,
        orientation, # Orientation | int (0/1) | str ('H'/'V')
    ) -> dict:
        """
        Place a ship during the placement phase.

        Returns:
            {'success': bool, 'error': str | None}
        """
        if self.phase != GamePhase.PLACEMENT:
            return {'success': False, 'error': 'Not in placement phase'}
        if player not in (1, 2):
            return {'success': False, 'error': 'Invalid player number'}

        orientation = _parse_orientation(orientation)
        if orientation is None:
            return {'success': False, 'error': 'Invalid orientation (use Orientation enum, 0/1, or "H"/"V")'}

        ok = self.boards[player].place_ship(ship_name, row, col, orientation)
        if not ok:
            return {'success': False, 'error': f'Cannot place {ship_name} at ({row}, {col})'}

        # Advance to battle phase once both players have placed all ships
        if all(self.boards[p].all_ships_placed() for p in (1, 2)):
            self.phase = GamePhase.BATTLE

        return {'success': True, 'error': None}

    # ------------------------------------------------------------------ battle

    def fire(self, player: int, row: int, col: int) -> dict:
        """
        Fire a shot during the battle phase.

        Returns:
            success:        bool
            result:         'hit' | 'miss'
            sunk_ship_name: str | None
            game_over:      bool
            winner:         int | None   (1 or 2)
            error:          str | None
        """
        if self.phase != GamePhase.BATTLE:
            return _fire_error('Not in battle phase')
        if player != self.current_turn:
            return _fire_error("Not this player's turn")
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
            return _fire_error('Coordinates out of bounds')

        opponent    = 3 - player
        shot_result = self.boards[opponent].receive_shot(row, col)

        if shot_result['result'] == 'already_shot':
            return _fire_error('Cell has already been targeted')

        self.boards[player].record_shot_result(
            row, col, shot_result['result'], shot_result['sunk_ship']
        )

        sunk_name = shot_result['sunk_ship'].name if shot_result['sunk_ship'] else None
        game_over = self.boards[opponent].all_ships_sunk()

        if game_over:
            self.phase  = GamePhase.OVER
            self.winner = player
        else:
            self.current_turn = opponent

        self.turn_count += 1

        return {
            'success':        True,
            'result':         shot_result['result'],
            'sunk_ship_name': sunk_name,
            'game_over':      game_over,
            'winner':         self.winner,
            'error':          None,
        }

    # --------------------------------------------------------------- state / AI

    def get_state(self, player: int) -> dict:
        """
        Full game state as seen by one player.
        Intended for HTTP API responses.

        Backend TODO: return this as JSON from GET /game/{id}/state?player={player}
        """
        opponent = 3 - player
        return {
            'phase':          self.phase,
            'current_turn':   self.current_turn,
            'winner':         self.winner,
            'turn_count':     self.turn_count,
            'your_board':     self.boards[player].to_dict(reveal=True),
            'opponent_board': self.boards[opponent].to_dict(reveal=False),
        }

    def get_ai_state(self, player: int) -> dict:
        """
        Compact state for the neural network (targeting phase).

        Returns:
            shot_tracker   np.ndarray shape (10, 10), dtype int8
                           Values: UNKNOWN=0, MISS=-1, HIT=1, SUNK=2
            enemy_sunk     list[bool] length 5 — which opponent ships are sunk,
                           ordered by SHIP_DEFINITIONS
            own_ships_alive list[bool] length 5 — which of this player's ships
                           are still afloat
        """
        board    = self.boards[player]
        opp      = self.boards[3 - player]
        return {
            'shot_tracker':    board.shot_tracker.copy(),
            'enemy_sunk':      [s.is_sunk() for s in opp.ships],
            'own_ships_alive': [not s.is_sunk() for s in board.ships],
        }

    def get_stats(self, player: int) -> dict:
        """
        Per-player outcome statistics for the genetic algorithm fitness function.

        won:          True if this player won
        shots_fired:  total shots taken
        hits_made:    shots that were hits
        times_hit:    how many times this player's own ships were hit
        ships_sunk:   how many opponent ships this player sank
        turns:        total turns in the game
        """
        b = self.boards[player]
        return {
            'won':         self.winner == player,
            'shots_fired': b.shots_fired,
            'hits_made':   b.hits_made,
            'times_hit':   b.times_hit,
            'ships_sunk':  b.ships_sunk_by_me,
            'turns':       self.turn_count,
        }

    def is_over(self) -> bool:
        return self.phase == GamePhase.OVER

    def reset(self) -> None:
        """Reset to a fresh game (reuses the object)."""
        self.__init__()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _parse_orientation(value) -> Optional[Orientation]:
    """Accept Orientation enum, int (0/1), or string ('H'/'V'/'HORIZONTAL'/'VERTICAL')."""
    if isinstance(value, Orientation):
        return value
    if isinstance(value, int):
        try:
            return Orientation(value)
        except ValueError:
            return None
    if isinstance(value, str):
        v = value.strip().upper()
        if v in ('H', 'HORIZONTAL'):
            return Orientation.HORIZONTAL
        if v in ('V', 'VERTICAL'):
            return Orientation.VERTICAL
    return None


def _fire_error(msg: str) -> dict:
    return {
        'success':        False,
        'result':         None,
        'sunk_ship_name': None,
        'game_over':      False,
        'winner':         None,
        'error':          msg,
    }


def random_place_all_ships(
    board: Board, rng: Optional[np.random.Generator] = None
) -> bool:
    """
    Randomly and validly place all ships on a board.
    Useful for testing and for seeding early training generations.
    Returns True on success, False if a valid placement couldn't be found
    within the attempt limit (should never happen on a standard board).
    """
    if rng is None:
        rng = np.random.default_rng()
    for ship in board.ships:
        placed   = False
        attempts = 0
        while not placed and attempts < 1000:
            row         = int(rng.integers(0, BOARD_SIZE))
            col         = int(rng.integers(0, BOARD_SIZE))
            orientation = Orientation(int(rng.integers(0, 2)))
            placed      = board.place_ship(ship.name, row, col, orientation)
            attempts   += 1
        if not placed:
            return False
    return True


# ---------------------------------------------------------------------------
# Terminal display helpers
# ---------------------------------------------------------------------------

_GRID_SYMBOLS = {
    int(GridState.EMPTY): '.',
    int(GridState.SHIP):  'S',
    int(GridState.HIT):   'X',
    int(GridState.MISS):  'O',
}

_SHOT_SYMBOLS = {
    int(ShotState.UNKNOWN): '.',
    int(ShotState.MISS):    'O',
    int(ShotState.HIT):     'X',
    int(ShotState.SUNK):    '#',
}


def print_board(board: Board, reveal: bool = False, label: str = '') -> None:
    """
    Print a board to stdout.

    reveal=True:  show full grid (ship positions visible) — owner's view.
    reveal=False: show shot_tracker (what this player knows of the opponent).
    """
    if label:
        print(f'\n=== {label} ===')
    header = '   ' + ' '.join(f'{i:1}' for i in range(BOARD_SIZE))
    print(header)
    if reveal:
        for r in range(BOARD_SIZE):
            row_str = ' '.join(_GRID_SYMBOLS.get(int(board.grid[r, c]), '?') for c in range(BOARD_SIZE))
            print(f'{r:2} {row_str}')
    else:
        for r in range(BOARD_SIZE):
            row_str = ' '.join(_SHOT_SYMBOLS.get(int(board.shot_tracker[r, c]), '?') for c in range(BOARD_SIZE))
            print(f'{r:2} {row_str}')


def print_game_state(game: Game, player: int) -> None:
    """Print both boards from one player's perspective."""
    print_board(game.boards[player], reveal=True,  label=f'Player {player} — Your Board')
    print_board(game.boards[player], reveal=False, label=f'Player {player} — Opponent (your shots)')


# ---------------------------------------------------------------------------
# Quick demo (run: python game.py)
# ---------------------------------------------------------------------------

def _run_random_demo() -> None:
    """Simulate a full random-vs-random game and print results."""
    rng  = np.random.default_rng(seed=42)
    game = Game()

    # Place ships randomly for both players
    for player in (1, 2):
        ok = random_place_all_ships(game.boards[player], rng)
        if not ok:
            print(f'Ship placement failed for player {player}')
            return

    game.phase = GamePhase.BATTLE  # skip placement API, boards already populated

    print('Starting random vs random demo...\n')

    while not game.is_over():
        p          = game.current_turn
        unshot     = game.boards[p].get_unshot_cells()
        row, col   = unshot[int(rng.integers(0, len(unshot)))]
        result     = game.fire(p, row, col)
        turn_label = f'Turn {game.turn_count:3d} | P{p} fires ({row},{col})'
        outcome    = result['result'].upper()
        extra      = f' — sunk {result["sunk_ship_name"]}!' if result['sunk_ship_name'] else ''
        print(f'{turn_label} → {outcome}{extra}')

    print(f'\nGame over! Player {game.winner} wins in {game.turn_count} turns.')
    for p in (1, 2):
        s = game.get_stats(p)
        print(
            f'  P{p}: shots={s["shots_fired"]}  hits={s["hits_made"]}  '
            f'times_hit={s["times_hit"]}  ships_sunk={s["ships_sunk"]}'
        )
    print()
    print_game_state(game, 1)


if __name__ == '__main__':
    _run_random_demo()
