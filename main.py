import eventlet
from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, emit, join_room
import time
import uuid
import random
import sqlite3
from flask_compress import Compress

app = Flask(__name__)
Compress(app)

app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', ping_timeout=60, ping_interval=25)

group_games = {}
player_group = {}

ROOM_TIMEOUT = 1800  # Room inactive timeout (seconds)
PLAYER_TIMEOUT = 300  # Player inactivity timeout (seconds)
MAX_ROOMS = 10
MAX_PLAYERS = 5  # Maximum players per room

shutdown_flag = False

# SQLite database setup
DB_FILE = "high_scores.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Drop the old table if it exists to reset with new schema (for this update)
    #c.execute("DROP TABLE IF EXISTS high_scores")
    c.execute('''CREATE TABLE IF NOT EXISTS high_scores
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  room_name TEXT NOT NULL,
                  round_number INTEGER NOT NULL,
                  score INTEGER NOT NULL,
                  ranking INTEGER NOT NULL,  -- 1 for 1st, 2 for 2nd, 3 for 3rd
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(round_number, ranking))''')
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

@app.route('/download-db')
def download_db():
    token = request.args.get('token')
    if token != "swansea":  # Replace with a secure token
        return "Unauthorized", 401
    try:
        return send_file(DB_FILE, as_attachment=True, download_name="high_scores.db")
    except FileNotFoundError:
        return "Database file not found", 404

def new_game_state(password=None):
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
        "round_duration": 180,
        "oven_on": False,
        "oven_timer_start": None,
        "round_start_time": None,
        "debrief_duration": 120,
        "customer_orders": [],
        "pending_orders": [],
        "last_updated": time.time(),
        "password": password  # Add password to game state
    }


def save_high_score(room, round_number, score):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Fetch current top 3 for this round
    c.execute("SELECT room_name, score, ranking FROM high_scores WHERE round_number = ? ORDER BY ranking",
              (round_number,))
    current_scores = c.fetchall()

    # Convert to a list of [room_name, score, ranking]
    scores_list = [(row[0], row[1], row[2]) for row in current_scores]

    # Add new score to the list
    scores_list.append((room, score, 0))  # 0 as temporary ranking

    # Sort by score descending and take top 3
    scores_list.sort(key=lambda x: x[1], reverse=True)
    top_three = scores_list[:3]

    # Assign rankings and update database
    for i, (room_name, score_val, _) in enumerate(top_three, 1):
        c.execute("""
            INSERT OR REPLACE INTO high_scores (room_name, round_number, score, ranking, timestamp)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (room_name, round_number, score_val, i))

    conn.commit()
    conn.close()


def get_high_scores():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT round_number, ranking, room_name, score, timestamp 
        FROM high_scores 
        WHERE round_number IN (1, 2, 3) 
        ORDER BY round_number, ranking
    """)
    scores = [
        {"round_number": row[0], "ranking": row[1], "room_name": row[2], "score": row[3], "timestamp": row[4]}
        for row in c.fetchall()
    ]
    conn.close()

    # Structure as { round: { 1: {...}, 2: {...}, 3: {...} } }
    result = {1: {}, 2: {}, 3: {}}
    for score in scores:
        result[score["round_number"]][score["ranking"]] = {
            "room_name": score["room_name"],
            "score": score["score"],
            "timestamp": score["timestamp"]
        }
    return result

def update_player_activity(sid):
    room = player_group.get(sid)
    if room and room in group_games:
        player = group_games[room]["players"].get(sid)
        if player is not None:
            player["last_activity"] = time.time()


def check_inactive_rooms():
    while not shutdown_flag:
        current_time = time.time()
        rooms_to_remove = []
        for room, game_state in list(group_games.items()):
            players_to_remove = []
            for sid, player in list(game_state["players"].items()):
                if current_time - player.get("last_activity", game_state["last_updated"]) >= PLAYER_TIMEOUT:
                    print(f"Removing inactive player {sid} from room {room}")
                    players_to_remove.append(sid)
            for sid in players_to_remove:
                if sid in player_group:
                    socketio.emit('player_timeout',
                                  {"message": "You have been inactive and are removed from the room."}, room=sid)
                    del player_group[sid]
                del game_state["players"][sid]
            if current_time - game_state["last_updated"] >= ROOM_TIMEOUT or not game_state["players"]:
                print(f"Removing inactive room {room}")
                rooms_to_remove.append(room)
        for room in rooms_to_remove:
            if room in group_games:
                for sid in list(group_games[room]["players"]):
                    if sid in player_group:
                        socketio.emit('room_expired', {"message": "Room inactive for a long time, please reconnect."},
                                      room=sid)
                        del player_group[sid]
                del group_games[room]
                update_room_list()
        eventlet.sleep(60)


eventlet.spawn(check_inactive_rooms)


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}")
    update_player_activity(request.sid)
    update_room_list()


@socketio.on('join')
def on_join(data):
    if shutdown_flag:
        return

    room = data.get("room")
    password = data.get("password")  # Expect password from client

    if not room or not password:
        emit('join_error', {"message": "Room name and password are required."}, room=request.sid)
        return

    if room not in group_games and len(group_games) >= MAX_ROOMS:
        emit('join_error', {"message": "Maximum room limit (10) reached."}, room=request.sid)
        return

    if room in group_games:
        if group_games[room]["password"] != password:
            emit('join_error', {"message": "Incorrect password."}, room=request.sid)
            return
    else:
        group_games[room] = new_game_state(password)

    game_state = group_games[room]
    if len(game_state["players"]) >= MAX_PLAYERS:
        emit('join_error', {"message": "Room is full. Maximum 5 players allowed."}, room=request.sid)
        return

    player_group[request.sid] = room
    if request.sid not in game_state["players"]:
        game_state["players"][request.sid] = {"builder_ingredients": [], "last_activity": time.time()}
    else:
        game_state["players"][request.sid]["last_activity"] = time.time()

    game_state["last_updated"] = time.time()
    join_room(room)
    socketio.emit('game_state', game_state, room=room)
    update_room_list()
    print(f"Client {request.sid} joined room {room}")


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    room = player_group.get(sid)
    print(f"Client disconnected: {sid} from room {room}")
    if room and room in group_games:
        game_state = group_games[room]
        if sid in game_state["players"]:
            del game_state["players"][sid]
            game_state["last_updated"] = time.time()
        if sid in player_group:
            del player_group[sid]
        socketio.emit('game_state', game_state, room=room)
        if len(game_state["players"]) == 0:
            del group_games[room]
        update_room_list()


@socketio.on('time_request')
def on_time_request():
    if shutdown_flag:
        return
    update_player_activity(request.sid)
    sid = request.sid
    room = player_group.get(sid, "default")
    game_state = group_games.get(room)
    if not game_state:
        emit('time_response', {"roundTimeRemaining": 0, "ovenTime": 0})
        return

    current_time = time.time()
    roundTimeRemaining = 0
    if game_state["current_phase"] == "round" and game_state["round_start_time"]:
        elapsed = current_time - game_state["round_start_time"]
        roundTimeRemaining = max(0, int(game_state["round_duration"] - elapsed))
        if game_state["round"] == 3 and game_state["pending_orders"]:
            orders_to_deliver = [order for order in game_state["pending_orders"] if order["arrival_time"] <= elapsed][
                                :10]
            if orders_to_deliver:
                game_state["customer_orders"].extend(orders_to_deliver)
                for order in orders_to_deliver:
                    game_state["pending_orders"].remove(order)
                    socketio.emit('new_order', order, room=room)
                socketio.emit('game_state_update', {
                    "customer_orders": game_state["customer_orders"],
                    "pending_orders": game_state["pending_orders"]
                }, room=room)
                game_state["last_updated"] = current_time
    elif game_state["current_phase"] == "debrief" and game_state.get("debrief_start_time"):
        elapsed = current_time - game_state["debrief_start_time"]
        roundTimeRemaining = max(0, int(game_state["debrief_duration"] - elapsed))

    ovenTime = 0
    if game_state["oven_on"] and game_state["oven_timer_start"]:
        ovenTime = int(current_time - game_state["oven_timer_start"])

    socketio.emit('time_response', {
        "roundTimeRemaining": roundTimeRemaining,
        "ovenTime": ovenTime,
        "phase": game_state["current_phase"]
    }, room=room)


@socketio.on('prepare_ingredient')
def on_prepare_ingredient(data):
    if shutdown_flag:
        return
    update_player_activity(request.sid)
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
    game_state["last_updated"] = time.time()
    socketio.emit('ingredient_prepared', prepared_item, room=room)
    socketio.emit('game_state', game_state, room=room)


@socketio.on('take_ingredient')
def on_take_ingredient(data):
    if shutdown_flag:
        return
    update_player_activity(request.sid)
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
        game_state["last_updated"] = time.time()
        socketio.emit('ingredient_removed', {"ingredient_id": ingredient_id}, room=room)
        socketio.emit('game_state', game_state, room=room)
    else:
        emit('error', {"message": "Ingredient not available."}, room=request.sid)


@socketio.on('build_pizza')
def on_build_pizza(data):
    if shutdown_flag:
        return
    update_player_activity(request.sid)
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
            pizza[
                "emoji"] = '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">🚫</span></div>'
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
            pizza[
                "emoji"] = '<div class="emoji-wrapper"><span class="emoji">🍕</span><span class="emoji">❓</span></div>'
            game_state["wasted_pizzas"].append(pizza)
            socketio.emit('build_error', {"message": "Pizza doesn't match any current order."}, room=request.sid)

    if game_state["round"] > 1 and "ingredients" not in data:
        target_sid = data.get("player_sid", request.sid)
        game_state["players"][target_sid]["builder_ingredients"] = []
        socketio.emit('clear_shared_builder', {"player_sid": target_sid}, room=room)

    game_state["last_updated"] = time.time()
    socketio.emit('game_state', game_state, room=room)


@socketio.on('move_to_oven')
def on_move_to_oven(data):
    if shutdown_flag:
        return
    update_player_activity(request.sid)
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
    game_state["last_updated"] = time.time()
    socketio.emit('pizza_moved_to_oven', pizza, room=room)
    socketio.emit('game_state', game_state, room=room)


@socketio.on('toggle_oven')
def toggle_oven(data):
    if shutdown_flag:
        return
    update_player_activity(request.sid)
    room = player_group.get(request.sid, "default")
    game_state = group_games.get(room, new_game_state())
    if game_state["current_phase"] != "round":
        return
    desired_state = data.get("state")
    if desired_state == "on" and not game_state["oven_on"]:
        game_state["oven_on"] = True
        game_state["oven_timer_start"] = time.time()
        game_state["last_updated"] = time.time()
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
        game_state["last_updated"] = time.time()
        socketio.emit('oven_toggled', {"state": "off"}, room=room)
    socketio.emit('game_state', game_state, room=room)


@socketio.on('request_room_list')
def on_request_room_list():
    if shutdown_flag:
        return
    update_player_activity(request.sid)
    update_room_list()


def update_room_list():
    room_list = {r: len(group_games[r]["players"]) for r in group_games if len(group_games[r]["players"]) > 0}
    socketio.emit('room_list', {"rooms": room_list, "high_scores": get_high_scores()})


@socketio.on('start_round')
def on_start_round(data):
    if shutdown_flag:
        return
    update_player_activity(request.sid)
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
    game_state["last_updated"] = time.time()
    if game_state["round"] == 3:
        game_state["pending_orders"] = generate_customer_orders(game_state["round_duration"])
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
    for i in range(20):
        order = {"id": str(uuid.uuid4())[:8], **random.choice(order_types)}
        order["arrival_time"] = (i * (max_order_time / 19))
        orders.append(order)
    return orders


def round_timer(duration, room):
    eventlet.sleep(duration)
    if not shutdown_flag:
        end_round(room)


def end_round(room):
    if shutdown_flag:
        return
    game_state = group_games.get(room)
    if not game_state or game_state["current_phase"] != "round":
        return
    game_state["current_phase"] = "debrief"
    game_state["debrief_start_time"] = time.time()
    leftover_ingredients = len(game_state["prepared_ingredients"])
    unsold_pizzas = game_state["built_pizzas"] + game_state["oven"]
    unsold_count = len(unsold_pizzas)

    # Calculate score based on your scoring rules
    completed_count = len(game_state["completed_pizzas"])
    wasted_count = len(game_state["wasted_pizzas"])
    if game_state["round"] < 3:
        score = (completed_count * 10) - (wasted_count * 10) - (unsold_count * 5) - leftover_ingredients
    else:
        fulfilled_orders = sum(1 for pizza in game_state["completed_pizzas"] if "order_id" in pizza)
        unmatched_count = sum(1 for pizza in game_state["completed_pizzas"] if "order_id" not in pizza)
        remaining_orders = len(game_state["customer_orders"])
        score = (fulfilled_orders * 20) - (unmatched_count * 10) - (wasted_count * 10) - (
                    unsold_count * 5) - leftover_ingredients - (remaining_orders * 15)

    result = {
        "completed_pizzas_count": completed_count,
        "wasted_pizzas_count": wasted_count,
        "unsold_pizzas_count": unsold_count,
        "ingredients_left_count": leftover_ingredients,
        "score": score
    }
    if game_state["round"] == 3:
        result["fulfilled_orders_count"] = fulfilled_orders
        result["remaining_orders_count"] = remaining_orders
        result["unmatched_pizzas_count"] = unmatched_count

    save_high_score(room, game_state["round"], score)
    game_state["last_updated"] = time.time()
    socketio.emit('game_state', game_state, room=room)
    socketio.emit('round_ended', result, room=room)
    eventlet.spawn(debrief_timer, game_state["debrief_duration"], room)


def debrief_timer(duration, room):
    eventlet.sleep(duration)
    if not shutdown_flag:
        reset_round(room)


def reset_round(room):
    game_state = group_games.get(room)
    if not game_state or game_state["current_phase"] != "debrief":
        return
    game_state["current_phase"] = "waiting"
    game_state["round"] += 1
    if game_state["round"] > game_state["max_rounds"]:
        game_state["round"] = 1  # Reset to Round 1 after Round 3
    game_state["debrief_start_time"] = None
    game_state["last_updated"] = time.time()
    socketio.emit('game_reset', game_state, room=room)


# List of known search engine User-Agent substrings
SEARCH_ENGINE_AGENTS = [
    # Google
    "Googlebot", "Googlebot-Image", "Googlebot-News", "Googlebot-Video", 
    "Mediapartners-Google", "AdsBot-Google", "Google-InspectionTool",

    # Bing
    "Bingbot", "BingPreview", "MSNBot",

    # Other search engines
    "Slurp", "DuckDuckBot", "Baiduspider", "YandexBot", 
    "Sogou", "Exabot", "facebot", "ia_archiver"
]

@app.route('/search-engine-info')
def search_engine_info():
    # Get the User-Agent header from the request
    user_agent = request.headers.get('User-Agent', '')

    # Check if the User-Agent matches any known search engine bots
    is_search_engine = any(agent in user_agent for agent in SEARCH_ENGINE_AGENTS)

    if not is_search_engine:
        # Return a 403 Forbidden response for non-search-engine users
        return "Access Denied: This page is for search engines only.", 403

    # Instructions and metadata for search engines
    info = {
        "title": "Kanban Pizza - Game Instructions and Information",
        "description": "Kanban Pizza is an interactive online game to learn Agile and Kanban principles through a pizza-making simulation.",
        "instructions": """
            <h2>How to Play Kanban Pizza</h2>
            <p><strong>Objective:</strong> Build and bake pizzas to score points across three rounds.</p>
            <h3>Getting Started</h3>
            <p>Gather 3-5 players, enter a room name and shared password, then click 'Enter Room'. Start the game with the 'Start Round' button.</p>
            <h3>Round 1: Basic Pizza Making</h3>
            <p>- Prepare ingredients (Base, Sauce, Ham, Pineapple) and drag them to your Pizza Builder.<br>
            - Valid pizzas: Ham (1 Base, 1 Sauce, 4 Ham) or Ham & Pineapple (1 Base, 1 Sauce, 2 Ham, 2 Pineapple).<br>
            - Submit pizzas, move them to the oven (max 3 at a time), and bake for 30-45 seconds.<br>
            - Scoring: +10 per completed pizza, -10 per wasted, -5 per unsold, -1 per leftover ingredient.</p>
            <h3>Round 2: Collaboration</h3>
            <p>- Use Shared Pizza Builders to collaborate.<br>
            - Same pizza rules and scoring as Round 1.</p>
            <h3>Round 3: Customer Orders</h3>
            <p>- Match 20 customer orders (e.g., Plain: 1 Base, 1 Sauce; Heavy Ham: 1 Base, 1 Sauce, 6 Ham).<br>
            - Scoring: +20 per fulfilled order, -10 per unmatched/wasted, -5 per unsold, -1 per leftover, -15 per unfulfilled order.</p>
            <p><em>Learn Agile principles like collaboration and continuous improvement!</em></p>
        """,
        "keywords": "Kanban, Agile, pizza game, workflow simulation, team collaboration, online game",
        "author": "Adam Clement 2025",
        "url": "https://kanbanpizza.onrender.com/"
    }

    # Render as simple HTML for crawlers
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="description" content="{info['description']}">
        <meta name="keywords" content="{info['keywords']}">
        <meta name="author" content="{info['author']}">
        <meta name="robots" content="index, nofollow">
        <title>{info['title']}</title>
    </head>
    <body>
        <h1>{info['title']}</h1>
        {info['instructions']}
        <p>For more, visit: <a href="{info['url']}">{info['url']}</a></p>
    </body>
    </html>
    """
    return html_content

if __name__ == '__main__':
    socketio.run(app, debug=True)
