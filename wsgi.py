# wsgi.py
import eventlet
eventlet.monkey_patch(os=False, select=True, socket=True, time=True)

# Import the app after monkey-patching
from main import app

if __name__ == "__main__":
    # For local testing (optional)
    app.run()
