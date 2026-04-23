import backend.app.validate as validate
import game.game as g;
import AI.agent as ai

def placeShip(data: dict):
    validHeaders = {"snapshot", "player", "ship", "row", "col", "orientation"}
    valid = validate.validateInput(data, validHeaders)
    if not valid.success:
        return {'error': 'Did not include all headers...', 'missing-headers': list(valid.missingHeaders)}, 400, {'Content-Type': 'application/json'}

    snapshot = data['snapshot']

    player = validate.validateInt("player", data['player'])
    shipName = data['ship']
    row = validate.validateInt("row", data['row'])
    col = validate.validateInt("col", data['col'])
    orientation = validate.validateInt("orientation", data['orientation'])

    game = g.Game().from_snapshot(snapshot)

    error = game.place_ship(player, shipName, row, col, orientation)

    if (error.get('success') == False):
        return error, 400, {'Content-Type': 'application/json'}
    
    state = game.get_state(player)

    return {"snapshot": game.to_snapshot(), "player-state": state}, 200, {'Content-Type': 'application/json'}

def fire(data: dict, agent: ai.Agent):
    validHeaders = {"snapshot", "player", "row", "col", "ai_player", "autoResolveAiTurn"}

    valid = validate.validateInput(data, validHeaders)
    if not valid.success:
        return {'error': 'Did not include all headers...', 'missing-headers': list(valid.missingHeaders)}, 400, {'Content-Type': 'application/json'}

    snapshot = data['snapshot']
    player = validate.validateInt("player", data['player'])
    row = validate.validateInt("player", data['row'])
    col = validate.validateInt("col", data['col'])
    ai_player = validate.validateInt("ai_player", data['ai_player'])
    autoResolveAiTurn = validate.validateBool("autoResolveAiTurn", data['autoResolveAiTurn'])

    game = g.Game().from_snapshot(snapshot)

    aiState = game.get_ai_state(player)

    status = game.fire_with_auto_ai_turn(player, row, col, ai_player, agent.choose_shot(ai_state=aiState), autoResolveAiTurn)

    state = game.get_state(player)

    return {"snapshot": game.to_snapshot, "status": status, "player-state": state}