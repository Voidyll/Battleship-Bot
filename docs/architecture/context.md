``` mermaid
    C4Context
        title System Context diagram for Battleship Bot System
        
        Person(user, "User", "User playing game")

        System(game, "Battleship Game System", "The Battleship game")

        Rel(user, game, "Plays")

        UpdateRelStyle(user, game, $textColor="white", $offsetX="-15", $offsetY="-10")
```