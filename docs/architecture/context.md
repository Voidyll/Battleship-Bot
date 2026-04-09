``` mermaid
    C4Context
        title System Context diagram for Battleship Bot System
        
        Person(user, "Gaming User", "User playing game")

        System(game, "Frontend Game", "The actual game the user plays")
        System(backend, "Backend Logic", "The logic that handles any changes or such")
        System(ai, "AI Model", "The AI model the user can play against")

        Rel(user, game, "Plays")
        Rel(game, backend, "Accesses")
        Rel(backend, ai, "Prompts")
```