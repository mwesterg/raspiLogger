# app.py

import threading
from flask import Flask

from database import init_db
from device_detection import device_event_handler
from routes import routes_bp

app = Flask(__name__, template_folder='templates', static_folder='static')
app.register_blueprint(routes_bp)

# --- Main Execution ---
if __name__ == '__main__':
    # Initialize the database
    init_db()

    # Start the device monitor in a background thread
    udev_thread = threading.Thread(target=device_event_handler, daemon=True)
    udev_thread.start()

    # Start the Flask web server
    # Running on 0.0.0.0 makes it accessible on your network
    print("Starting Flask web server on http:raspitest.local:5000")
    app.run(host='0.0.0.0', port=5000)