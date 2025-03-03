import eventlet

eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import redis
import time
import uuid
import logging
import random
import os
import json

# Minimal logging to save resources
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret!')
redis_url = os.getenv('REDIS_URL', 'redis://red-cv2qp25umphs739tuhrg:6379')
socketio = SocketIO(app, cors_allowed_origins="*", message_queue=redis_url)

# Redis client for key-value and Pub/Sub
redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
pubsub = redis_client.pubsub()

# In-memory tracking (fallback if Redis resets, since no persistence)
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


def get_game_state(room):
    state = redis_client.get(f"game:{room}")
    if state:
        return json.loads(state)
    return new_game_state()


def set_game_state(room, state):
    redis_client.set(f"game:{room}", json.dumps(state))


def publish_event(room, event_type, data):
    event = json.dumps({"type": event_type, "data": data})
    redis_client.publish(f"room:{room}", event)


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def on_connect():
    logging.info("Client connected: %s", request.sid)


@socketio.on('join')
def on_join(data):
    room = data.get("room", "default")
    player_group[request.sid] = room
    game_state = get_game_state(room)
    if request.sid not in game_state["players"]:
        game_state["players"][request.sid] = {"builder_ingredients": []}
    set_game_state(room, game_state)
    join_room(room)
    pubsub.subscribe(f"room:{room}")
    emit('game_state', game_state)  # Initial full state
    logging.info("Client %s joined room %s", request.sid, room)


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    room = player_group.get(sid)
    if room:
        game_state = get_game_state(room)
        if sid in game_state["players"]:
            del game_state["players"][sid]
        set_game_state(room, game_state)
        publish_event(room, "game_state_update", {"players": game_state["players"]})
        del player_group[sid]
    logging.info("Client disconnected: %s", sid)


@socketio.on('time_request')
def on_time_request():
    room = player_group.get(request.sid, "default")
    game_state = get_game_state(room)

    def process_time_request():
        round_time_remaining = 0
        if game_state["current_phase"] == "round" and game_state["round_start_time"]:
            elapsed = time.time() - game_state["round_start_time"]
            round_time_remaining = max(0, int(game_state["round_duration"] - elapsed))
            if game_state["round"] == 3 and game_state["pending_orders"]:
                current_time = elapsed
                pending_orders = game_state["pending_orders"]
                orders_to_deliver = []
                for order in pending_orders[:]:
                    if order["arrival_time"] <= current_time:
                        orders_to_deliver.append(order)
                        game_state["pending_orders"].remove(order)
                    if len(orders_to_deliver) >= 10:
                        game_state["customer_orders"].extend(orders_to_deliver)
                        publish_event(room, "new_orders", orders_to_deliver)
                        orders_to_deliver = []
                if orders_to_deliver:
                    game_state["customer_orders"].extend(orders_to_deliver)
                    publish_event(room, "new_orders", orders_to_deliver)
                set_game_state(room, game_state)
        elif game_state["current_phase"] == "debrief" and game_state["debrief_start_time"]:
            elapsed = time.time() - game_state["debrief_start_time"]
            round_time_remaining = max(0, int(game_state["debrief_duration"] - elapsed))

        oven_time = 0
        if game_state["oven_on"] and game_state["oven_timer_start"]:
            oven_time = int(time.time() - game_state["oven_timer_start"])

        emit('time_response', {
            "roundTimeRemaining": round_time_remaining,
            "ovenTime": oven_time,
            "phase": game_state["current_phase"]
        })

    eventlet.spawn(process_time_request)


@socketio.on('prepare_ingredient')
def on_prepare_ingredient(data):
    room = player_group.get(request.sid, "default")
    game_state = get_game_state(room)
    if game_state["current_phase"] != "round":
        return
    ingredient_type = data.get("ingredient_type")
    if ingredient_type not in ["base", "sauce", "ham", "pineapple"]:
        emit('error', {"message": "Invalid ingredient type"})
        return
    prepared_id = str(uuid.uuid4())[:8]
    item = {"id": prepared_id, "type": ingredient_type}
    game_state["prepared_ingredients"].append(item)
    set_game_state(room, game_state)
    publish_event(room, "ingredient_prepared", item)


@socketio.on('take_ingredient')
def on_take_ingredient(data):
    room = player_group.get(request.sid, "default")
    game_state = get_game_state(room)
    if game_state["current_phase"] != "round":
        return
    ingredient_id = data.get("ingredient_id")
    target_sid = data.get("target_sid")
    taken = next((ing for ing in game_state["prepared_ingredients"] if ing["id"] == ingredient_id), None)
    if taken:
        game_state["prepared_ingredients"].remove(taken)
        if game_state["round"] > 1 and target_sid in game_state["players"]:
            game_state["players"][target_sid]["builder_ingredients"].append(taken)
        set_game_state(room, game_state)
        publish_event(room, "ingredient_removed", {"ingredient_id": ingredient_id})
    else:
        emit('error', {"message": "Ingredient not available."})


@socketio.on('build_pizza')
def on_build_pizza(data):
    room = player_group.get(request.sid, "default")
    game_state = get_game_state(room)
    if game_state["current_phase"] != "round":
        return

    if "ingredients" in data:
        builder_ingredients = data.get("ingredients", [])
    else:
        target_sid = data.get("player_sid", request.sid)
        if target_sid not in game_state["players"]:
            emit('build_error', {"message": "Target player not found."})
            return
        builder_ingredients = game_state["players"][target_sid]["builder_ingredients"]

    if not builder_ingredients:
        emit('build_error', {"message": "No ingredients provided."})
        return

    counts = {"base": 0, "sauce": 0, "ham": 0, "pineapple": 0}
    for ing in builder_ingredients:
        counts[ing["type"]] += 1

    pizza_id = str(uuid.uuid4())[:8]
    pizza = {"pizza_id": pizza_id, "ingredients": counts, "built_at": time.time(), "baking_time": 0}

    if game_state["round"] < 3:
        valid = counts["base"] == 1 and counts["sauce"] == 1 and (
                (counts["ham"] == 4 and counts["pineapple"] == 0) or
                (counts["ham"] == 2 and counts["pineapple"] == 2)
        )
        if not valid:
            pizza["status"] = "invalid"
            pizza[
                "emoji"] = '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🚫</span></div>'
            game_state["wasted_pizzas"].append(pizza)
            set_game_state(room, game_state)
            publish_event(room, "build_error", {"message": "Invalid combo: Wasted."})
        else:
            pizza_type = "bacon" if counts["ham"] == 4 else "pineapple"
            pizza["type"] = pizza_type
            pizza["emoji"] = (
                '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🥓</span></div>'
                if pizza_type == "bacon" else
                '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🍍</span></div>'
            )
            game_state["built_pizzas"].append(pizza)
            set_game_state(room, game_state)
            publish_event(room, "pizza_built", pizza)
    else:
        matched_order = next(
            (order for order in game_state["customer_orders"] if order["ingredients"] == counts),
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
            set_game_state(room, game_state)
            publish_event(room, "order_fulfilled", {"order_id": matched_order["id"]})
            publish_event(room, "pizza_built", pizza)
        else:
            pizza["status"] = "unmatched"
            pizza[
                "emoji"] = '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">❓</span></div>'
            game_state["wasted_pizzas"].append(pizza)
            set_game_state(room, game_state)
            publish_event(room, "build_error", {"message": "No matching order."})

    if game_state["round"] > 1 and "ingredients" not in data:
        game_state["players"][target_sid]["builder_ingredients"] = []
        set_game_state(room, game_state)
        publish_event(room, "clear_shared_builder", {"player_sid": target_sid})


@socketio.on('move_to_oven')
def on_move_to_oven(data):
    room = player_group.get(request.sid, "default")
    game_state = get_game_state(room)
    if game_state["current_phase"] != "round" or game_state["oven_on"]:
        emit('oven_error', {"message": "Oven is on or not in round."})
        return
    pizza_id = data.get("pizza_id")
    pizza = next((p for p in game_state["built_pizzas"] if p["pizza_id"] == pizza_id), None)
    if not pizza or len(game_state["oven"]) >= game_state["max_pizzas_in_oven"]:
        emit('oven_error', {"message": "Oven full or pizza not found."})
        return
    game_state["built_pizzas"].remove(pizza)
    pizza["oven_start"] = time.time()
    game_state["oven"].append(pizza)
    set_game_state(room, game_state)
    publish_event(room, "pizza_moved_to_oven", pizza)


@socketio.on('toggle_oven')
def toggle_oven(data):
    room = player_group.get(request.sid, "default")
    game_state = get_game_state(room)
    if game_state["current_phase"] != "round":
        return
    desired_state = data.get("state")
    if desired_state == "on" and not game_state["oven_on"]:
        game_state["oven_on"] = True
        game_state["oven_timer_start"] = time.time()
        set_game_state(room, game_state)
        publish_event(room, "oven_toggled", {"state": "on"})
    elif desired_state == "off" and game_state["oven_on"]:
        elapsed = time.time() - game_state["oven_timer_start"]
        for pizza in game_state["oven"]:
            pizza["baking_time"] += elapsed
            if pizza["baking_time"] < 30:
                pizza["status"] = "undercooked"
                game_state["wasted_pizzas"].append(pizza)
            elif 30 <= pizza["baking_time"] <= 45:
                pizza["status"] = "cooked"
                game_state["completed_pizzas"].append(pizza)
            else:
                pizza["status"] = "burnt"
                game_state["wasted_pizzas"].append(pizza)
        game_state["oven"] = []
        game_state["oven_on"] = False
        game_state["oven_timer_start"] = None
        set_game_state(room, game_state)
        publish_event(room, "oven_toggled", {"state": "off"})


@socketio.on('start_round')
def on_start_round(data):
    room = player_group.get(request.sid, "default")
    game_state = get_game_state(room)
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
    set_game_state(room, game_state)
    if game_state["round"] == 3:
        game_state["pending_orders"] = generate_customer_orders(game_state["round_duration"])
        set_game_state(room, game_state)
    publish_event(room, "round_started", {
        "round": game_state["round"],
        "duration": game_state["round_duration"],
        "customer_orders": game_state["customer_orders"]
    })
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
        order["arrival_time"] = i * (max_order_time / 49)
        orders.append(order)
    return orders


def round_timer(duration, room):
    eventlet.sleep(duration)
    end_round(room)


def end_round(room):
    game_state = get_game_state(room)
    if game_state["current_phase"] != "round":
        return
    game_state["current_phase"] = "debrief"
    game_state["debrief_start_time"] = time.time()
    result = compute_round_result(game_state)
    set_game_state(room, game_state)
    publish_event(room, "round_ended", result)
    if game_state["round"] < game_state["max_rounds"]:
        game_state["round"] += 1
        eventlet.spawn(debrief_timer, game_state["debrief_duration"], room)
    else:
        eventlet.spawn(final_debrief_timer, game_state["debrief_duration"], room)


def compute_round_result(game_state):
    leftover_ingredients = len(game_state["prepared_ingredients"])
    unsold_pizzas = len(game_state["built_pizzas"]) + len(game_state["oven"])
    completed_count = len(game_state["completed_pizzas"])
    wasted_count = len(game_state["wasted_pizzas"])
    if game_state["round"] == 3:
        fulfilled_orders = sum(1 for pizza in game_state["completed_pizzas"] if "order_id" in pizza)
        unmatched_pizzas = sum(1 for pizza in game_state["completed_pizzas"] if "order_id" not in pizza)
        remaining_orders = len(game_state["customer_orders"]) + len(game_state["pending_orders"])
        score = fulfilled_orders * 20 - unmatched_pizzas * 10 - wasted_count * 10 - unsold_pizzas * 5 - leftover_ingredients - remaining_orders * 15
        return {
            "completed_pizzas_count": completed_count,
            "wasted_pizzas_count": wasted_count,
            "unsold_pizzas_count": unsold_pizzas,
            "ingredients_left_count": leftover_ingredients,
            "fulfilled_orders_count": fulfilled_orders,
            "remaining_orders_count": remaining_orders,
            "unmatched_pizzas_count": unmatched_pizzas,
            "score": score
        }
    score = completed_count * 10 - wasted_count * 10 - unsold_pizzas * 5 - leftover_ingredients
    return {
        "completed_pizzas_count": completed_count,
        "wasted_pizzas_count": wasted_count,
        "unsold_pizzas_count": unsold_pizzas,
        "ingredients_left_count": leftover_ingredients,
        "score": score
    }


def debrief_timer(duration, room):
    eventlet.sleep(duration)
    game_state = get_game_state(room)
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
    set_game_state(room, game_state)
    publish_event(room, "round_started", {
        "round": game_state["round"],
        "duration": game_state["round_duration"],
        "customer_orders": game_state["customer_orders"]
    })
    eventlet.spawn(round_timer, game_state["round_duration"], room)


def final_debrief_timer(duration, room):
    eventlet.sleep(duration)
    game_state = get_game_state(room)
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
    set_game_state(room, game_state)
    publish_event(room, "game_reset", game_state)

def start_pubsub_listener():
    def listen():
        pubsub = redis_client.pubsub()
        subscribed_rooms = set()
        while True:
            # Update subscriptions based on active rooms
            current_rooms = set(player_group.values())
            new_rooms = current_rooms - subscribed_rooms
            old_rooms = subscribed_rooms - current_rooms
            for room in new_rooms:
                pubsub.subscribe(f"room:{room}")
            for room in old_rooms:
                pubsub.unsubscribe(f"room:{room}")
            subscribed_rooms = current_rooms

            # Listen for messages
            message = pubsub.get_message(timeout=1.0)
            if message and message['type'] == 'message':
                room = message['channel'].split(':')[1]
                event_data = json.loads(message['data'])
                socketio.emit(event_data['type'], event_data['data'], room=room)
            eventlet.sleep(0.1)  # Yield to other green threads

    eventlet.spawn(listen)

# Start the listener when the app initializes
start_pubsub_listener()
if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
