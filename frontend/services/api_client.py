import requests
import sys

BASE_URL = "http://localhost:5000/api/game"

def create_game() -> dict:
    response = requests.post(url=f"{BASE_URL}/new")

    return response.json()

def place_ship(data: dict) -> dict:
    response = requests.post(url=f"{BASE_URL}/place-ship", json=data)

    if response.status_code == 500:
        print("Server error!")
        sys.exit()

    return response.json()