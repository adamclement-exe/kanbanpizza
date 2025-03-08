import eventlet
eventlet.monkey_patch()

# Import the app after monkey-patching
from main import app

if __name__ == "__main__":
    # For local testing (optional)
    app.run()
