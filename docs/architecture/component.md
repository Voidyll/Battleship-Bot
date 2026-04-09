``` mermaid
    C4Component

        Container_Boundary(battleship, "Battleship Game System"){
            Container(ui, "UI", "Displays gameboard and info")

            Container_Boundary(backend, "Backend"){
                Container_Boundary(endpoints, "Endpoints"){
                    Component(start, "Start Game API", "API endpoint to have the AI set its ships and store it")
                    Component(hit_ship, "Ship Location Check API", "API endpoint to check if the user's coordinates hit the AI's ship")
                    Component(location, "Attack Coordinate API", "API endpoint to get the AI's coordinates to try and hit")
                    Component(hit_or_miss, "AI Hit Ship API", "API endpoint to return whether the AI's coordinates hit one of the user's ships")
                }

                Container_Boundary(ship_info, "Ship Info"){
                    Component(ship_comp, "Ship Component", "Handles reads and writes for the AI's ships")
                    Component(miss_comp, "Missed Component", "Handles reads and writes for the AI's and user's misses")
                    Component(hit_comp, "Hit Component", "Handles reads and writes for the AI's and user's hits")
                }

                Container_Boundary(ai_info, "AI Info"){
                    Component(ai_logic_validator, "AI Logic Validator", "Validates the AI's game logic")
                    Component(ai_prompt_comp, "AI Prompt Component", "Handles prompting the AI and parsing output")
                }
            }

            Container(ai, "Battleship AI")
        }

        Rel(ui, start, "Start Game", "JSON/HTTP")
        Rel(ui, hit_ship, "Check Ship Hit", "JSON/HTTP")
        Rel(ui, location, "Get AI Attack Location", "JSON/HTTP")
        Rel(ui, hit_or_miss, "Returns status of hit check", "JSON/HTTP")

        Rel(start, ai_prompt_comp, "Requests new ship locations from the AI")
        Rel(start, ai_logic_validator, "Validates ai output compared to game logic")
        Rel(start, ship_comp, "Saves ship locations")

        Rel(hit_ship, ship_comp, "Compares user's input coordinates to all of the AI's coordinates to check for hits")
        Rel(hit_ship, miss_comp, "If misses, save missed location")
        Rel(hit_ship, hit_comp, "If hit, save hit location")

        Rel(location, ai_prompt_comp, "Requests location for the AI to attack")
        Rel(location, ai_logic_validator, "Validates ai output compared to game logic")
        
        Rel(hit_or_miss, hit_comp, "If hit, save hit location")
        Rel(hit_or_miss, miss_comp, "If miss, save miss location")

        Rel(ai_prompt_comp, ai, "Prompt AI for output")


        UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")

        UpdateRelStyle(ui, hit_or_miss, $offsetX="150", $offsetY="50")
```