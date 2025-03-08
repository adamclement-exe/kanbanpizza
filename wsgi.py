import eventlet
eventlet.monkey_patch()

from main import app

if __name__ == "__main__":
    app.run()
