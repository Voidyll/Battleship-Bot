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

class Game:
    @property
    def battleship(self) -> Ship:
        return self._battleship
    
    @property
    def carrier(self) -> Ship:
        return self._carrier
    
    @property
    def cruiser(self) -> Ship:
        return self._cruiser
    
    @property
    def destroyer(self) -> Ship:
        return self._destroyer
    
    @property
    def submarine(self) -> Ship:
        return self._submarine
    
    def Game(self):
        self._error = False