``` mermaid
    C4Container
        title Container Diagram for Battleship Bot System

        Person(user, "Gamer", "The one who plays the game.")

        Container_Boundary(battlship_system, "Battleship Bot System"){
            Container(static, "Static Content")
            Container(ui, "UI")
            Container(backend, "Backend")
            Container(ai, "AI Battleship Bot")
        }

        Rel(user, static, "Loads Page")
        Rel(user, ui, "Plays Battleship Via")
        Rel(ui, backend, "Makes API reqests to [JSON/HTTP]")
        Rel(backend, ai, "Prompts AI for game moves")
```