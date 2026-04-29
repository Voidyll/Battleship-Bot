import services.api_client as api
import sys

ships = ["Cruiser", "Carrier", "Battleship", "Destroyer", "Submarine"]

def main():
    print("Test cases running...")

    data: dict = api.create_game()
    
    print(f"Game created:\n{data}")

    game = placeShips(data)

    print(f"Placed ships:\n{game}")
    

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