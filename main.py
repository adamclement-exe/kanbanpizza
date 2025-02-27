import time
import threading
import uuid
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
async_mode = None
socketio = SocketIO(app, async_mode=async_mode, cors_allowed_origins="*")

# Global dictionaries for room game states and mapping player session IDs to their room
group_games = {}
player_group = {}

def new_game_state():
    state = {
        "players": {},
        "prepared_ingredients": [],
        "built_pizzas": [],
        "oven": [],
        "completed_pizzas": [],
        "wasted_pizzas": [],
        "round": 1,
        "max_rounds": 1,
        "current_phase": "waiting",
        "max_pizzas_in_oven": 3,
        "round_duration": 420,  # Your desired value
        "oven_on": False,
        "oven_timer_start": None,
        "round_start_time": None
    }
    logging.debug(f"New game state created with round_duration: {state['round_duration']}")
    return state


@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    print("Client connected:", request.sid)
    # Wait for join with room info before sending game state.

@socketio.on('join')
def on_join(data):
    room = data.get("room", "default")
    if room not in group_games:
        group_games[room] = new_game_state()
    game_state = group_games[room]
    player_group[request.sid] = room
    game_state["players"][request.sid] = {"room": room}
    join_room(room)
    socketio.emit('player_joined', {"sid": request.sid, "room": room}, room=room)
    socketio.emit('game_state', game_state, room=room)
    print(f"Client {request.sid} joined room {room}")

@socketio.on('disconnect')
def on_disconnect():
    room = player_group.get(request.sid)
    if room:
        game_state = group_games.get(room)
        if game_state and request.sid in game_state["players"]:
            del game_state["players"][request.sid]
        del player_group[request.sid]
        socketio.emit('game_state', game_state, room=room)
        print("Client disconnected:", request.sid)

@socketio.on('prepare_ingredient')
def on_prepare_ingredient(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    ingredient_type = data.get("ingredient_type")
    if ingredient_type not in ["base", "sauce", "ham", "pineapple"]:
        emit('error', {"message": "Invalid ingredient type"}, room=request.sid)
        return
    prepared_id = str(uuid.uuid4())[:8]
    # Use the room as the identifier for who prepared the ingredient.
    prepared_item = {
        "id": prepared_id,
        "type": ingredient_type,
        "prepared_by": room
    }
    game_state["prepared_ingredients"].append(prepared_item)
    socketio.emit('ingredient_prepared', prepared_item, room=room)
    socketio.emit('game_state', game_state, room=room)

@socketio.on('take_ingredient')
def on_take_ingredient(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    ingredient_id = data.get("ingredient_id")
    taken = None
    for ing in game_state["prepared_ingredients"]:
        if ing["id"] == ingredient_id:
            taken = ing
            break
    if taken:
        game_state["prepared_ingredients"].remove(taken)
        socketio.emit('ingredient_removed', {"ingredient_id": ingredient_id}, room=room)
        socketio.emit('game_state', game_state, room=room)
    else:
        emit('error', {"message": "Ingredient not available."}, room=request.sid)

@socketio.on('build_pizza')
def on_build_pizza(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
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
    pizza = {
        "pizza_id": pizza_id,
        "team": room,  # use room as the team identifier
        "built_at": time.time(),
        "baking_time": 0
    }
    game_state["built_pizzas"].append(pizza)
    socketio.emit('pizza_built', pizza, room=room)
    socketio.emit('game_state', game_state, room=room)

@socketio.on('move_to_oven')
def on_move_to_oven(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
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
    game_state["built_pizzas"] = [p for p in game_state["built_pizzas"] if p["pizza_id"] != pizza_id]
    pizza["oven_start"] = time.time()
    pizza["baking_time"] = 0
    game_state["oven"].append(pizza)
    socketio.emit('pizza_moved_to_oven', pizza, room=room)
    socketio.emit('game_state', game_state, room=room)

@socketio.on('toggle_oven')
def toggle_oven(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    desired_state = data.get("state")
    if desired_state == "on":
        if game_state["oven_on"]:
            emit('oven_error', {"message": "Oven is already on."}, room=request.sid)
            return
        game_state["oven_on"] = True
        game_state["oven_timer_start"] = time.time()
        socketio.emit('oven_toggled', {"state": "on", "oven_timer": 0}, room=room)
    elif desired_state == "off":
        if not game_state["oven_on"]:
            emit('oven_error', {"message": "Oven is already off."}, room=request.sid)
            return
        elapsed = time.time() - game_state["oven_timer_start"]
        for pizza in game_state["oven"]:
            pizza["baking_time"] += elapsed
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
        socketio.emit('oven_toggled', {"state": "off", "oven_timer": 0}, room=room)
        socketio.emit('game_state', game_state, room=room)
    else:
        emit('oven_error', {"message": "Invalid oven state requested."}, room=request.sid)

@socketio.on('start_round')
def on_start_round(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    logging.debug(f"Room {room} on_start_round: current round_duration = {game_state['round_duration']}")
    if game_state["current_phase"] != "waiting":
        return
    game_state["current_phase"] = "round"
    game_state["round_start_time"] = time.time()
    logging.debug(f"Round started at {game_state['round_start_time']} with duration {game_state['round_duration']}")
    # Clear previous round state
    game_state["prepared_ingredients"] = []
    game_state["built_pizzas"] = []
    game_state["oven"] = []
    game_state["completed_pizzas"] = []
    game_state["wasted_pizzas"] = []
    game_state["oven_on"] = False
    game_state["oven_timer_start"] = None
    socketio.emit('round_started', {
        "round": game_state["round"],
        "duration": 400,
        "start_time": game_state["round_start_time"]
    }, room=room)
    threading.Thread(target=round_timer, args=(game_state["round_duration"], room)).start()

def round_timer(duration, room):
    time.sleep(duration)
    end_round(room)

def end_round(room):
    game_state = group_games[room]
    game_state["current_phase"] = "debrief"
    # Compute the overall score for the room
    score = len(game_state["completed_pizzas"]) * 10 - len(game_state["wasted_pizzas"]) * 10 - len(game_state["prepared_ingredients"]) * 1
    result = {
        "completed_pizzas_count": len(game_state["completed_pizzas"]),
        "wasted_pizzas_count": len(game_state["wasted_pizzas"]),
        "score": score
    }
    socketio.emit('round_ended', result, room=room)
    threading.Thread(target=debrief_timer, args=(60, room)).start()

def debrief_timer(duration, room):
    time.sleep(duration)
    game_state = group_games[room]
    game_state["current_phase"] = "waiting"
    game_state["prepared_ingredients"] = []
    game_state["built_pizzas"] = []
    game_state["oven"] = []
    game_state["completed_pizzas"] = []
    game_state["wasted_pizzas"] = []
    game_state["oven_on"] = False
    game_state["oven_timer_start"] = None
    game_state["round_start_time"] = None
    socketio.emit('game_reset', game_state, room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
