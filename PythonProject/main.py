import time
import threading
import uuid
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
#socketio = SocketIO(app)
async_mode = None
socketio = SocketIO(app, async_mode=async_mode, cors_allowed_origins="*")
# Global game state for Round 1 with updated oven logic
game_state = {
    "players": {},  # key: sid, value: {username, team}
    "prepared_ingredients": [],  # list of prepared ingredient objects {id, type, prepared_by}
    "built_pizzas": [],  # pizzas assembled but not yet in the oven
    "oven": [],  # pizzas currently in the oven
    "completed_pizzas": [],  # pizzas that are cooked correctly
    "wasted_pizzas": [],  # pizzas that are undercooked or burnt
    "round": 1,
    "max_rounds": 1,  # only Round 1 for now
    "current_phase": "waiting",  # waiting, round, debrief, finished
    "max_pizzas_in_oven": 3,
    "round_duration": 300,  # 5 minutes per round
    "oven_on": False,  # oven state: on or off
    "oven_timer_start": None,  # timestamp when oven was turned on
}


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def on_connect():
    print("Client connected:", request.sid)
    emit('game_state', game_state)


@socketio.on('disconnect')
def on_disconnect():
    print("Client disconnected:", request.sid)
    if request.sid in game_state["players"]:
        del game_state["players"][request.sid]
    socketio.emit('game_state', game_state, broadcast=True)


@socketio.on('join')
def on_join(data):
    username = data.get("username", f"Player_{request.sid[:5]}")
    team = data.get("team", username)
    game_state["players"][request.sid] = {"username": username, "team": team}
    join_room("game")
    socketio.emit('player_joined', {"sid": request.sid, "username": username, "team": team}, room="game")
    socketio.emit('game_state', game_state, room="game")
    print(f"{username} joined as team {team}")


# ========= INGREDIENT PREPARATION =========
@socketio.on('prepare_ingredient')
def on_prepare_ingredient(data):
    """
    data: { "ingredient_type": one of "base", "sauce", "ham", "pineapple" }
    """
    ingredient_type = data.get("ingredient_type")
    if ingredient_type not in ["base", "sauce", "ham", "pineapple"]:
        emit('error', {"message": "Invalid ingredient type"}, room=request.sid)
        return
    prepared_id = str(uuid.uuid4())[:8]
    player = game_state["players"].get(request.sid, {})
    team = player.get("team", "unknown")
    prepared_item = {
        "id": prepared_id,
        "type": ingredient_type,
        "prepared_by": team
    }
    game_state["prepared_ingredients"].append(prepared_item)
    socketio.emit('ingredient_prepared', prepared_item, room="game")
    socketio.emit('game_state', game_state, room="game")


# ========= TAKE INGREDIENT FROM THE POOL =========
@socketio.on('take_ingredient')
def on_take_ingredient(data):
    """
    data: { "ingredient_id": <id> }
    Immediately removes the ingredient from the shared pool.
    """
    ingredient_id = data.get("ingredient_id")
    taken = None
    for ing in game_state["prepared_ingredients"]:
        if ing["id"] == ingredient_id:
            taken = ing
            break
    if taken:
        game_state["prepared_ingredients"].remove(taken)
        socketio.emit('ingredient_removed', {"ingredient_id": ingredient_id}, room="game")
        socketio.emit('game_state', game_state, room="game")
    else:
        emit('error', {"message": "Ingredient not available."}, room=request.sid)


# ========= BUILDING THE PIZZA =========
@socketio.on('build_pizza')
def on_build_pizza(data):
    """
    data: { "ingredients": [ {id, type}, ... ] }

    Valid combination:
      - 1 "base"
      - 1 "sauce"
      - And either 4 "ham" OR (2 "ham" and 2 "pineapple")
    """
    builder_ingredients = data.get("ingredients", [])
    if not builder_ingredients:
        emit('build_error', {"message": "No ingredients provided."}, room=request.sid)
        return

    counts = {"base": 0, "sauce": 0, "ham": 0, "pineapple": 0}
    for ing in builder_ingredients:
        counts[ing.get("type", "")] += 1

    valid = False
    if counts["base"] == 1 and counts["sauce"] == 1:
        if counts["ham"] == 4 and counts["pineapple"] == 0:
            valid = True
        elif counts["ham"] == 2 and counts["pineapple"] == 2:
            valid = True

    if not valid:
        emit('build_error',
             {"message": "Invalid combination: 1 base, 1 sauce and either 4 ham OR 2 ham and 2 pineapple required."},
             room=request.sid)
        return

    pizza_id = str(uuid.uuid4())[:8]
    player = game_state["players"].get(request.sid, {})
    team = player.get("team", "unknown")
    pizza = {
        "pizza_id": pizza_id,
        "team": team,
        "built_at": time.time(),
        "baking_time": 0  # cumulative baking time
    }
    game_state["built_pizzas"].append(pizza)
    socketio.emit('pizza_built', pizza, room="game")
    socketio.emit('game_state', game_state, room="game")


# ========= MOVING A BUILT PIZZA TO THE OVEN =========
@socketio.on('move_to_oven')
def on_move_to_oven(data):
    """
    data: { "pizza_id": <id> }
    Moves a built pizza into the oven.
    Pizzas can only be added when the oven is off.
    Enforces a limit of 3 pizzas.
    """
    if game_state["oven_on"]:
        emit('oven_error', {"message": "Oven is on; cannot add pizzas."}, room=request.sid)
        return

    pizza_id = data.get("pizza_id")
    pizza = None
    for p in game_state["built_pizzas"]:
        if p["pizza_id"] == pizza_id:
            pizza = p
            break
    if not pizza:
        emit('oven_error', {"message": "Pizza not found among built pizzas."}, room=request.sid)
        return
    if len(game_state["oven"]) >= game_state["max_pizzas_in_oven"]:
        emit('oven_error', {"message": "Oven is full!"}, room=request.sid)
        return

    # Remove from built pizzas and add to oven
    game_state["built_pizzas"] = [p for p in game_state["built_pizzas"] if p["pizza_id"] != pizza_id]
    pizza["oven_start"] = time.time()
    pizza["baking_time"] = 0  # start at 0 for new pizza
    game_state["oven"].append(pizza)
    socketio.emit('pizza_moved_to_oven', pizza, room="game")
    socketio.emit('game_state', game_state, room="game")


# ========= TOGGLE OVEN =========
@socketio.on('toggle_oven')
def toggle_oven(data):
    """
    data: { "state": "on" or "off" }
    When turning the oven on, start its timer.
    When turning it off, update the baking time for each pizza,
    then evaluate them:
      - <30 sec: undercooked (wasted)
      - 30-45 sec: cooked (completed)
      - >45 sec: burnt (wasted)
    """
    desired_state = data.get("state")
    if desired_state == "on":
        if game_state["oven_on"]:
            emit('oven_error', {"message": "Oven is already on."}, room=request.sid)
            return
        game_state["oven_on"] = True
        game_state["oven_timer_start"] = time.time()
        socketio.emit('oven_toggled', {"state": "on", "oven_timer": 0}, room="game")
    elif desired_state == "off":
        if not game_state["oven_on"]:
            emit('oven_error', {"message": "Oven is already off."}, room=request.sid)
            return
        elapsed = time.time() - game_state["oven_timer_start"]
        # Update baking time for each pizza in the oven
        for pizza in game_state["oven"]:
            pizza["baking_time"] += elapsed
        # Evaluate each pizza
        pizzas_to_remove = []
        for pizza in game_state["oven"]:
            total_baking = pizza["baking_time"]
            if total_baking < 30:
                pizza["status"] = "undercooked"
                game_state["wasted_pizzas"].append(pizza)
                pizzas_to_remove.append(pizza)
            elif 30 <= total_baking <= 45:
                pizza["status"] = "cooked"
                game_state["completed_pizzas"].append(pizza)
                pizzas_to_remove.append(pizza)
            elif total_baking > 45:
                pizza["status"] = "burnt"
                game_state["wasted_pizzas"].append(pizza)
                pizzas_to_remove.append(pizza)
        for pizza in pizzas_to_remove:
            if pizza in game_state["oven"]:
                game_state["oven"].remove(pizza)
        game_state["oven_on"] = False
        game_state["oven_timer_start"] = None
        socketio.emit('oven_toggled', {"state": "off", "oven_timer": 0}, room="game")
        socketio.emit('game_state', game_state, room="game")
    else:
        emit('oven_error', {"message": "Invalid oven state requested."}, room=request.sid)


# ========= ROUND CONTROL =========
@socketio.on('start_round')
def on_start_round(data):
    if game_state["current_phase"] != "waiting":
        return
    game_state["current_phase"] = "round"
    # Clear previous round state
    game_state["prepared_ingredients"] = []
    game_state["built_pizzas"] = []
    game_state["oven"] = []
    game_state["completed_pizzas"] = []
    game_state["wasted_pizzas"] = []
    game_state["oven_on"] = False
    game_state["oven_timer_start"] = None
    socketio.emit('round_started', {"round": game_state["round"], "duration": game_state["round_duration"]},
                  room="game")
    threading.Thread(target=round_timer, args=(game_state["round_duration"],)).start()


def round_timer(duration):
    time.sleep(duration)
    end_round()


def end_round():
    game_state["current_phase"] = "debrief"
    result = {
        "completed_pizzas_count": len(game_state["completed_pizzas"]),
        "wasted_pizzas_count": len(game_state["wasted_pizzas"])
    }
    socketio.emit('round_ended', result, room="game")
    threading.Thread(target=debrief_timer, args=(60,)).start()


def debrief_timer(duration):
    time.sleep(duration)
    game_state["current_phase"] = "finished"
    socketio.emit('game_over', game_state, room="game")


if __name__ == '__main__':
    socketio.run(app, debug=True,allow_unsafe_werkzeug=True)
