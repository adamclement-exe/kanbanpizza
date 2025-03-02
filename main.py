import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import time
import uuid
import logging
import random

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

group_games = {}
player_group = {}

def new_game_state():
    return {
        "players": {},
        "prepared_ingredients": [],
        "built_pizzas": [],
        "oven": [],
        "completed_pizzas": [],
        "wasted_pizzas": [],
        "round": 1,
        "max_rounds": 3,
        "current_phase": "waiting",
        "max_pizzas_in_oven": 3,
        "round_duration": 420,
        "oven_on": False,
        "oven_timer_start": None,
        "round_start_time": None,
        "debrief_duration": 180,
        "customer_orders": [],
        "pending_orders": []
    }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def on_connect():
    logging.info("Client connected: %s", request.sid)

@socketio.on('join')
def on_join(data):
    room = data.get("room", "default")
    if room not in group_games:
        group_games[room] = new_game_state()
    game_state = group_games[room]
    player_group[request.sid] = room
    if request.sid not in game_state["players"]:
        game_state["players"][request.sid] = {"builder_ingredients": []}
    join_room(room)
    socketio.emit('game_state', game_state, room=room)
    logging.info("Client %s joined room %s", request.sid, room)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    room = player_group.get(sid)
    if room:
        game_state = group_games.get(room)
        if game_state and sid in game_state["players"]:
            del game_state["players"][sid]
        del player_group[sid]
        socketio.emit('game_state', game_state, room=room)
        logging.info("Client disconnected: %s", sid)

@socketio.on('time_request')
def on_time_request():
    sid = request.sid
    room = player_group.get(sid, "default")
    game_state = group_games.get(room)
    if not game_state:
        emit('time_response', {"roundTimeRemaining": 0, "ovenTime": 0})
        return

    roundTimeRemaining = 0
    if game_state["current_phase"] == "round" and game_state["round_start_time"]:
        elapsed = time.time() - game_state["round_start_time"]
        left = game_state["round_duration"] - elapsed
        roundTimeRemaining = max(0, int(left))

        if game_state["round"] == 3 and game_state["pending_orders"]:
            current_time = elapsed
            pending_orders = game_state["pending_orders"]
            orders_to_deliver = []
            for order in pending_orders[:]:  # Copy to avoid modifying during iteration
                if order["arrival_time"] <= current_time:
                    orders_to_deliver.append(order)
                if len(orders_to_deliver) >= 10:  # Batch size
                    game_state["customer_orders"].extend(orders_to_deliver)
                    for order in orders_to_deliver:
                        game_state["pending_orders"].remove(order)
                        socketio.emit('new_order', order, room=room)
                        logging.info("Delivered order %s to room %s at %.2f seconds", order['id'], room, current_time)
                    socketio.emit('game_state', game_state, room=room)
                    orders_to_deliver = []
                    eventlet.sleep(0)  # Yield to event loop
            if orders_to_deliver:  # Handle remaining
                game_state["customer_orders"].extend(orders_to_deliver)
                for order in orders_to_deliver:
                    game_state["pending_orders"].remove(order)
                    socketio.emit('new_order', order, room=room)
                    logging.info("Delivered order %s to room %s at %.2f seconds", order['id'], room, current_time)
                socketio.emit('game_state', game_state, room=room)

    elif game_state["current_phase"] == "debrief" and game_state["debrief_start_time"]:
        elapsed = time.time() - game_state["debrief_start_time"]
        left = game_state["debrief_duration"] - elapsed
        roundTimeRemaining = max(0, int(left))

    ovenTime = 0
    if game_state["oven_on"] and game_state["oven_timer_start"]:
        ovenTime = int(time.time() - game_state["oven_timer_start"])

    emit('time_response', {
        "roundTimeRemaining": roundTimeRemaining,
        "ovenTime": ovenTime,
        "phase": game_state["current_phase"]
    })

@socketio.on('prepare_ingredient')
def on_prepare_ingredient(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    if game_state["current_phase"] != "round":
        return
    ingredient_type = data.get("ingredient_type")
    if ingredient_type not in ["base", "sauce", "ham", "pineapple"]:
        emit('error', {"message": "Invalid ingredient type"}, room=request.sid)
        return
    prepared_id = str(uuid.uuid4())[:8]
    prepared_item = {"id": prepared_id, "type": ingredient_type, "prepared_by": room}
    game_state["prepared_ingredients"].append(prepared_item)
    socketio.emit('ingredient_prepared', prepared_item, room=room)
    socketio.emit('game_state', game_state, room=room)

@socketio.on('take_ingredient')
def on_take_ingredient(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    if game_state["current_phase"] != "round":
        return
    ingredient_id = data.get("ingredient_id")
    target_sid = data.get("target_sid")
    taken = next((ing for ing in game_state["prepared_ingredients"] if ing["id"] == ingredient_id), None)
    if taken:
        game_state["prepared_ingredients"].remove(taken)
        if game_state["round"] > 1 and target_sid and target_sid in game_state["players"]:
            game_state["players"][target_sid]["builder_ingredients"].append(taken)
        socketio.emit('ingredient_removed', {"ingredient_id": ingredient_id}, room=room)
        socketio.emit('game_state', game_state, room=room)
    else:
        emit('error', {"message": "Ingredient not available."}, room=request.sid)

@socketio.on('build_pizza')
def on_build_pizza(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    if game_state["current_phase"] != "round":
        return

    if "ingredients" in data:
        builder_ingredients = data.get("ingredients", [])
    else:
        target_sid = data.get("player_sid", request.sid)
        if target_sid not in game_state["players"]:
            emit('build_error', {"message": "Target player not found."}, room=request.sid)
            return
        builder_ingredients = game_state["players"][target_sid]["builder_ingredients"]
        if not builder_ingredients:
            emit('build_error', {"message": "No ingredients in target builder."}, room=request.sid)
            return

    if not builder_ingredients:
        emit('build_error', {"message": "No ingredients provided."}, room=request.sid)
        return

    counts = {"base": 0, "sauce": 0, "ham": 0, "pineapple": 0}
    for ing in builder_ingredients:
        ing_type = ing.get("type", "")
        if ing_type in counts:
            counts[ing_type] += 1

    pizza_id = str(uuid.uuid4())[:8]
    pizza = {
        "pizza_id": pizza_id,
        "team": room,
        "built_at": time.time(),
        "baking_time": 0,
        "ingredients": counts
    }

    if game_state["round"] < 3:
        valid = counts["base"] == 1 and counts["sauce"] == 1 and (
            (counts["ham"] == 4 and counts["pineapple"] == 0) or
            (counts["ham"] == 2 and counts["pineapple"] == 2)
        )
        if not valid:
            pizza["status"] = "invalid"
            pizza["emoji"] = '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🚫</span></div>'
            game_state["wasted_pizzas"].append(pizza)
            socketio.emit('build_error', {"message": "Invalid combo: Wasted as incomplete."}, room=request.sid)
        else:
            pizza_type = "bacon" if counts["ham"] == 4 else "pineapple"
            pizza["type"] = pizza_type
            pizza["emoji"] = (
                '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓</span></div>'
                if pizza_type == "bacon" else
                '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🍍</span></div>'
            )
            game_state["built_pizzas"].append(pizza)
            socketio.emit('pizza_built', pizza, room=room)
    else:
        matched_order = next(
            (order for order in game_state["customer_orders"]
             if order["ingredients"]["base"] == counts["base"] and
                order["ingredients"]["sauce"] == counts["sauce"] and
                order["ingredients"]["ham"] == counts["ham"] and
                order["ingredients"]["pineapple"] == counts["pineapple"]),
            None
        )
        if matched_order:
            pizza["type"] = matched_order["type"]
            pizza["order_id"] = matched_order["id"]
            pizza["emoji"] = {
                "ham": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓</span></div>',
                "pineapple": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🍍</span></div>',
                "ham & pineapple": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓🍍</span></div>',
                "light ham": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓¹</span></div>',
                "light pineapple": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🍍¹</span></div>',
                "plain": '<div class="emoji-wrapper"><span class="emoji">🍕</span></div>',
                "heavy ham": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓⁶</span></div>',
                "heavy pineapple": '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🍍⁶</span></div>'
            }[matched_order["type"]]
            game_state["customer_orders"].remove(matched_order)
            game_state["built_pizzas"].append(pizza)
            socketio.emit('order_fulfilled', {"order_id": matched_order["id"]}, room=room)
            socketio.emit('pizza_built', pizza, room=room)
        else:
            pizza["status"] = "unmatched"
            pizza["emoji"] = '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">❓</span></div>'
            game_state["wasted_pizzas"].append(pizza)
            socketio.emit('build_error', {"message": "Pizza doesn't match any current order."}, room=request.sid)

    if game_state["round"] > 1 and "ingredients" not in data:
        game_state["players"][target_sid]["builder_ingredients"] = []
        socketio.emit('clear_shared_builder', {"player_sid": target_sid}, room=room)

    socketio.emit('game_state', game_state, room=room)

@socketio.on('move_to_oven')
def on_move_to_oven(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    if game_state["current_phase"] != "round":
        return
    if game_state["oven_on"]:
        emit('oven_error', {"message": "Oven is on; cannot add pizzas while on."}, room=request.sid)
        return
    pizza_id = data.get("pizza_id")
    pizza = next((p for p in game_state["built_pizzas"] if p["pizza_id"] == pizza_id), None)
    if not pizza or len(game_state["oven"]) >= game_state["max_pizzas_in_oven"]:
        emit('oven_error', {"message": "Oven issue: Pizza not found or full!"}, room=request.sid)
        return
    game_state["built_pizzas"].remove(pizza)
    pizza["oven_start"] = time.time()
    game_state["oven"].append(pizza)
    socketio.emit('pizza_moved_to_oven', pizza, room=room)
    socketio.emit('game_state', game_state, room=room)

@socketio.on('toggle_oven')
def toggle_oven(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    if game_state["current_phase"] != "round":
        return
    desired_state = data.get("state")
    if desired_state == "on" and not game_state["oven_on"]:
        game_state["oven_on"] = True
        game_state["oven_timer_start"] = time.time()
        socketio.emit('oven_toggled', {"state": "on"}, room=room)
    elif desired_state == "off" and game_state["oven_on"]:
        elapsed = time.time() - game_state["oven_timer_start"]
        for pizza in game_state["oven"]:
            pizza["baking_time"] += elapsed
            total_baking = pizza["baking_time"]
            if total_baking < 30:
                pizza["status"] = "undercooked"
                game_state["wasted_pizzas"].append(pizza)
            elif 30 <= total_baking <= 45:
                pizza["status"] = "cooked"
                game_state["completed_pizzas"].append(pizza)
            else:
                pizza["status"] = "burnt"
                game_state["wasted_pizzas"].append(pizza)
        game_state["oven"] = []
        game_state["oven_on"] = False
        game_state["oven_timer_start"] = None
        socketio.emit('oven_toggled', {"state": "off"}, room=room)
    socketio.emit('game_state', game_state, room=room)

@socketio.on('start_round')
def on_start_round(data):
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    if game_state["current_phase"] != "waiting":
        return
    game_state["current_phase"] = "round"
    game_state["round_start_time"] = time.time()
    game_state["prepared_ingredients"] = []
    game_state["built_pizzas"] = []
    game_state["oven"] = []
    game_state["completed_pizzas"] = []
    game_state["wasted_pizzas"] = []
    game_state["oven_on"] = False
    game_state["oven_timer_start"] = None
    game_state["customer_orders"] = []
    game_state["pending_orders"] = []
    for sid in game_state["players"]:
        game_state["players"][sid]["builder_ingredients"] = []

    if game_state["round"] == 3:
        def set_orders():
            game_state["pending_orders"] = generate_customer_orders(game_state["round_duration"])
            socketio.emit('game_state', game_state, room=room)
        eventlet.spawn(set_orders)
    else:
        socketio.emit('game_state', game_state, room=room)

    socketio.emit('round_started', {
        "round": game_state["round"],
        "duration": game_state["round_duration"],
        "customer_orders": game_state["customer_orders"]
    }, room=room)
    eventlet.spawn(round_timer, game_state["round_duration"], room)

def generate_customer_orders(round_duration):
    order_types = [
        {"type": "ham", "ingredients": {"base": 1, "sauce": 1, "ham": 4, "pineapple": 0}},
        {"type": "pineapple", "ingredients": {"base": 1, "sauce": 1, "ham": 0, "pineapple": 4}},
        {"type": "ham & pineapple", "ingredients": {"base": 1, "sauce": 1, "ham": 2, "pineapple": 2}},
        {"type": "light ham", "ingredients": {"base": 1, "sauce": 1, "ham": 1, "pineapple": 0}},
        {"type": "light pineapple", "ingredients": {"base": 1, "sauce": 1, "ham": 0, "pineapple": 1}},
        {"type": "plain", "ingredients": {"base": 1, "sauce": 1, "ham": 0, "pineapple": 0}},
        {"type": "heavy ham", "ingredients": {"base": 1, "sauce": 1, "ham": 6, "pineapple": 0}},
        {"type": "heavy pineapple", "ingredients": {"base": 1, "sauce": 1, "ham": 0, "pineapple": 6}}
    ]
    orders = []
    max_order_time = round_duration - 45
    for i in range(50):
        order = {"id": str(uuid.uuid4())[:8], **random.choice(order_types)}
        order["arrival_time"] = (i * (max_order_time / 49))
        orders.append(order)
    return orders

def round_timer(duration, room):
    eventlet.sleep(duration)
    end_round(room)

def end_round(room):
    try:
        game_state = group_games.get(room)
        if not game_state or game_state["current_phase"] != "round":
            return
        game_state["current_phase"] = "debrief"
        game_state["debrief_start_time"] = time.time()
        leftover_ingredients = len(game_state["prepared_ingredients"])
        unsold_pizzas = game_state["built_pizzas"] + game_state["oven"]
        unsold_count = len(unsold_pizzas)
        completed_count = len(game_state["completed_pizzas"])
        wasted_count = len(game_state["wasted_pizzas"])

        if game_state["round"] == 3:
            fulfilled_orders = sum(1 for pizza in game_state["completed_pizzas"] if "order_id" in pizza)
            unmatched_pizzas = sum(1 for pizza in game_state["completed_pizzas"] if "order_id" not in pizza)
            remaining_orders = len(game_state["customer_orders"]) + len(game_state["pending_orders"])
            score = (
                fulfilled_orders * 20
                - unmatched_pizzas * 10
                - wasted_count * 10
                - unsold_count * 5
                - leftover_ingredients
                - remaining_orders * 15
            )
            result = {
                "completed_pizzas_count": completed_count,
                "wasted_pizzas_count": wasted_count,
                "unsold_pizzas_count": unsold_count,
                "ingredients_left_count": leftover_ingredients,
                "fulfilled_orders_count": fulfilled_orders,
                "remaining_orders_count": remaining_orders,
                "unmatched_pizzas_count": unmatched_pizzas,
                "score": score
            }
        else:
            score = (
                completed_count * 10
                - wasted_count * 10
                - unsold_count * 5
                - leftover_ingredients
            )
            result = {
                "completed_pizzas_count": completed_count,
                "wasted_pizzas_count": wasted_count,
                "unsold_pizzas_count": unsold_count,
                "ingredients_left_count": leftover_ingredients,
                "score": score
            }

        socketio.emit('round_ended', result, room=room)
        if game_state["round"] < game_state["max_rounds"]:
            game_state["round"] += 1
            eventlet.spawn(debrief_timer, game_state["debrief_duration"], room)
        else:
            eventlet.spawn(final_debrief_timer, game_state["debrief_duration"], room)
    except Exception as e:
        logging.error("Error in end_round: %s", e)

def debrief_timer(duration, room):
    eventlet.sleep(duration)
    game_state = group_games.get(room)
    if not game_state:
        return
    game_state["current_phase"] = "round"
    game_state["round_start_time"] = time.time()
    game_state["debrief_start_time"] = None
    game_state["prepared_ingredients"] = []
    game_state["built_pizzas"] = []
    game_state["oven"] = []
    game_state["completed_pizzas"] = []
    game_state["wasted_pizzas"] = []
    game_state["oven_on"] = False
    game_state["oven_timer_start"] = None
    game_state["customer_orders"] = []
    game_state["pending_orders"] = []
    for sid in game_state["players"]:
        game_state["players"][sid]["builder_ingredients"] = []

    if game_state["round"] == 3:
        game_state["pending_orders"] = generate_customer_orders(game_state["round_duration"])

    socketio.emit('game_state', game_state, room=room)
    socketio.emit('round_started', {
        "round": game_state["round"],
        "duration": game_state["round_duration"],
        "customer_orders": game_state["customer_orders"]
    }, room=room)
    eventlet.spawn(round_timer, game_state["round_duration"], room)

def final_debrief_timer(duration, room):
    eventlet.sleep(duration)
    game_state = group_games.get(room)
    if not game_state:
        return
    game_state["current_phase"] = "waiting"
    game_state["round"] = 1
    game_state["prepared_ingredients"] = []
    game_state["built_pizzas"] = []
    game_state["oven"] = []
    game_state["completed_pizzas"] = []
    game_state["wasted_pizzas"] = []
    game_state["oven_on"] = False
    game_state["oven_timer_start"] = None
    game_state["round_start_time"] = None
    game_state["debrief_start_time"] = None
    game_state["customer_orders"] = []
    game_state["pending_orders"] = []
    for sid in game_state["players"]:
        game_state["players"][sid]["builder_ingredients"] = []
    socketio.emit('game_reset', game_state, room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
