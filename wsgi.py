# run.py
import eventlet
#eventlet.monkey_patch()

from main import app, socketio

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)  # Match Render.com's expected port
