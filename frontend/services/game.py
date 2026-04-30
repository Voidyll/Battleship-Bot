# Create a game class to handle the deserialization of the dictionaries.
"""
We can create a class for each ship and give them their own info, then store each ship object in the game object.
We can then create a "stats" class to keep track of each hit the player has made
We need a phase variable to keep track of what phase we are in
We need a current_turn variable to keep track of the turn count
We really just need the above info to create a decent game class for sending to the frontend...
"""
class Ship:
    @property
    def placed(self) -> bool:
        return self._placed
    
    @property
    def hits(self) -> list:
        return self._hits
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def positions(self) -> list[list[int]]:
        return self._positions
    
    @property 
    def sunk(self) -> bool:
        return self._sunk
    
    @property
    def size(self) -> int:
        return self._size
    
    def __init__(self, data: dict):
        self._hits = data.get('hits')
        self._name = data.get('name')
        self._placed = bool(data.get('placed'))
        self._positions = data.get('positions')
        self._size = int(data.get('size'))
        self._sunk = bool(data.get('sunk'))

    def createShips(data: list[dict]):
        ships: list[Ship] = []

        for d in data:
            newShip = Ship(data=d)
            ships.append(newShip)

        return ships

class Stats:
    @property 
    def shipsSunk(self) -> int:
        return self._shipsSunk

    @property
    def shotsFired(self) -> int:
        return self._shotsFired
    
    @property
    def hits(self) -> int:
        return self._hits
    
    @property
    def hitsMade(self) -> int:
        return self._hitsMade

    def __init__(self, data: dict):
        self._shipsSunk = int(data.get('ships_sunk_by_me'))
        self._shotsFired = int(data.get('shots_fired'))
        self._hits = int(data.get('times_hit'))
        self._hitsMade = int(data.get('hits_made'))

HUMAN_PLAYER: str = "1"

class Game:
    @property
    def ships(self) -> list[Ship]:
        return self._ships

    @property
    def currentTurn(self) -> int:
        return self._currentTurn

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def turnCount(self) -> int:
        return self._turnCount
    
    @property
    def winner(self) -> int:
        return self._winner

    @property
    def error(self) -> bool:
        return self._error

    @property
    def shots(self) -> list[list[int]]:
        return self._shots

    @property 
    def stats(self) -> Stats:
        return self._stats

    @property
    def placed(self) -> list[str]:
        return self._placed

    @property
    def grid(self) -> list[list[int]]:
        return self._grid

    def __init__(self, data: dict):
        self._currentTurn = int(data.get('current_turn'))
        self._phase = data.get('phase')
        self._turnCount = int(data.get('turn_count'))
        self._winner = data.get('winner')
        self._ships = Ship.createShips(data=data.get('boards').get(HUMAN_PLAYER).get('ships'))
        self._shots = data.get('boards').get(HUMAN_PLAYER).get('shot_tracker')
        self._stats = Stats(data=data.get('boards').get(HUMAN_PLAYER).get('stats'))
        self._placed = data.get('boards').get(HUMAN_PLAYER).get('placed')
        self._grid = data.get('boards').get(HUMAN_PLAYER).get('grid')

        self._error = False