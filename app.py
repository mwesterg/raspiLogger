# This file is the main entry point for the Flask web application.
# It sets up the Flask app, a new esp_manager instance, configures logging, registers blueprints, and starts the server.

import threading
from flask import Flask
import logging # Import logging
from logging.handlers import RotatingFileHandler # Import RotatingFileHandler
import os # Import os for path operations

# Configure the root logger to only show ERROR and higher messages
# logging.basicConfig(level=logging.ERROR) # This sets up console logging

# Configure file logging
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
file_handler = RotatingFileHandler(log_file_path, maxBytes=1024 * 1024 * 10, backupCount=5) # 10 MB per file, 5 backups
file_handler.setLevel(logging.INFO) # Set file handler level to INFO
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Get the root logger and add the file handler
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.INFO) # Set root logger level to INFO

from database import init_db
from device_detection import device_event_handler
from esp_handler import ESPManager
from routes import routes_bp

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

# Create an instance of ESPManager
esp_manager = ESPManager()

app.register_blueprint(routes_bp)

# Suppress Werkzeug access logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) # Or logging.CRITICAL, or logging.WARNING

# --- Main Execution ---
if __name__ == '__main__':
    # Initialize the database
    init_db()

    # Start the device monitor in a background thread
    udev_thread = threading.Thread(target=device_event_handler, args=(esp_manager,), daemon=True)
    udev_thread.start()

    # Start the Flask web server
    # Running on 0.0.0.0 makes it accessible on your network
    print("Starting Flask web server on http:raspitest.local:5000")
    app.run(host='0.0.0.0', port=5000)