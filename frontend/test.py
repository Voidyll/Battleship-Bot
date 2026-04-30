import services.api_client as api
import sys
import services.game as g

ships = ["Cruiser", "Carrier", "Battleship", "Destroyer", "Submarine"]

def main():
    print("Test cases running...")

    data: dict = api.create_game()

    game = placeShips(data)

    gameData = g.Game(data=game.get('snapshot'))

    data = {
        'snapshot':game.get("snapshot"),
        'autoResolveAiTurn':True,
        'player':1,
        'ai_player':2,
        'col':0,
        'row':0
    }

    gameData = g.Game(data=api.fire(data).get('snapshot'))

    print(f"Game: {gameData.stats.hits}")
    

def placeShips(data: dict) -> dict:
    i = 0
    for ship in ships:
        place_ship = {
            "snapshot": data['snapshot'],
            "player": 1,
            "col": i,
            "row": 0,
            "orientation": 1,
            "ship": ship
        }
        data = api.place_ship(place_ship)
        i += 1

        if data.get("error") is not None:
            print(data)
            sys.exit()
    
    return data

if __name__ == '__main__':
    main()