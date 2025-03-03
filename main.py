import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import time
import uuid
import logging
import random
import os

# Minimal logging to reduce CPU/memory overhead
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret!')
# Use provided free Redis URL from Render, fallback for local testing
redis_url = os.getenv('REDIS_URL', 'redis://red-cv2qp25umphs739tuhrg:6379')
socketio = SocketIO(app, cors_allowed_origins="*", message_queue=redis_url)

@@ -53,13 +53,15 @@
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

@@ -147,50 +149,49 @@
emit('error', {"message": "Invalid ingredient type"}, room=request.sid)
return
prepared_id = str(uuid.uuid4())[:8]
    # Trimmed prepared_item to save memory
    prepared_item = {"id": prepared_id, "type": ingredient_type}
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
