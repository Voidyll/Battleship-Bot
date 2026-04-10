``` mermaid
    C4Container
        title Container Diagram for Battleship Bot System

        Person(user, "User", "The one who plays the game.")

        Container_Boundary(battlship_system, "Battleship Bot System"){
            Container(static, "Static Content")
            Container(ui, "UI", "Displays the gameboard <br> and any changes to it")
            Container(backend, "Backend", "Handles game actions <br> from the ai and <br> sends it to the frontend")
            Container(ai, "AI Battleship Bot")
        }

        Rel(user, static, "Loads Page")
        Rel(user, ui, "Plays Battleship Via")
        Rel(ui, backend, "Makes API <br> reqests to <br> [JSON/HTTP]")
        Rel(backend, ai, "Prompts AI for <br> game moves")
        Rel(static, ui, "Delivers")

        UpdateRelStyle(static, ui, $textColor="white", $offsetX="-30", $offsetY="-20")
        UpdateRelStyle(ui, backend, $textColor="white", $offsetX="-40", $offsetY="-20")
        UpdateRelStyle(backend, ai, $textColor="white", $offsetX="-40", $offsetY="-20")
        UpdateRelStyle(user, static, $textColor="white")
        UpdateRelStyle(user, ui, $textColor="white")
```
