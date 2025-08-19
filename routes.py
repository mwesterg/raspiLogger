# routes.py

import os
import csv
import tempfile
from datetime import datetime
import sqlite3
import logging # Import logging

from flask import Blueprint, render_template, jsonify, send_file, request, current_app

from database import init_db, add_log_entry, update_other_messages_stat
from config import DATABASE_FILE

routes_bp = Blueprint('routes', __name__)

@routes_bp.route('/')
def index():
    """Serves the main dashboard page."""
    return render_template('index.html')

@routes_bp.route('/tags')
def get_unique_tags():
    """Returns all unique tags from the database."""
    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn: 
        cursor = conn.cursor()
        # Get unique tags from all log level tables
        tags = set()
        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            cursor.execute(f'SELECT DISTINCT tag FROM {level}')
            for row in cursor.fetchall():
                tags.add(row[0])
    return jsonify(list(tags))

@routes_bp.route('/filtered_logs/<tag>')
def get_filtered_logs(tag):
    """Returns the last 10 log messages for a specific tag across all levels."""
    all_logs = []
    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn: 
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            # Fetch all logs for the given tag from each table
            query = f"SELECT timestamp, tag, message, received_at FROM {level} WHERE tag = ?"
            cursor.execute(query, (tag,))
            all_logs.extend([dict(row) for row in cursor.fetchall()])

    # Sort all collected logs by received_at (newest first)
    # Convert received_at strings to datetime objects for accurate sorting
    all_logs.sort(key=lambda x: datetime.strptime(x['received_at'], '%Y-%m-%d %H:%M:%S'), reverse=True)

    # Take the latest 10 logs
    latest_10_logs = all_logs[:10]

    # Sort these 10 logs by received_at (oldest first) for display in the UI
    latest_10_logs.sort(key=lambda x: datetime.strptime(x['received_at'], '%Y-%m-%d %H:%M:%S'))

    return jsonify(latest_10_logs)

@routes_bp.route('/restart_device', methods=['POST'])
def restart_device():
    """Restarts the connected ESP32 device."""
    esp_manager = current_app.esp_manager
    if esp_manager.esp32_connection_status["connected"] and esp_manager.esp32_connection_status["port"]:
        try:
            # This will trigger a new boot sequence and log capture
            esp_manager.reset_esp32(esp_manager.esp32_connection_status["port"])
            return jsonify(success=True, message="Device restart initiated.")
        except Exception as e:
            return jsonify(success=False, message=f"Error restarting device: {e}"), 500
    else:
        return jsonify(success=False, message="No ESP32 device connected."), 400

@routes_bp.route('/boot_logs')
def get_boot_logs():
    """Returns the latest boot logs."""
    esp_manager = current_app.esp_manager
    return jsonify(boot_logs=esp_manager.esp32_connection_status["boot_logs"], boot_timestamp=esp_manager.esp32_connection_status["boot_timestamp"])

@routes_bp.route('/connection_status')
def get_connection_status():
    """Returns the current ESP32 connection status."""
    esp_manager = current_app.esp_manager
    return jsonify(esp_manager.esp32_connection_status)

@routes_bp.route('/stats')
def get_stats():
    """Returns the current logging statistics as JSON."""
    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn: 
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM stats')
        stats = {row[0]: row[1] for row in cursor.fetchall()}
    return jsonify(stats)

@routes_bp.route('/latest_logs/<level>')
def get_latest_logs(level):
    """Returns the last 10 log messages for a specific level."""
    level = level.upper()
    allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    if level not in allowed_levels:
        return jsonify(error="Invalid log level"), 404

    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn: 
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        cursor = conn.cursor()
        
        query = f"SELECT timestamp, tag, message FROM (SELECT * FROM {level} ORDER BY received_at DESC LIMIT 10) AS subquery ORDER BY received_at ASC"
        cursor.execute(query)
        logs = [dict(row) for row in cursor.fetchall()]
    return jsonify(logs)


@routes_bp.route('/download/<level>')
def download_logs(level):
    """Generates and serves a CSV file for a specific log level."""
    level = level.upper()
    allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    if level not in allowed_levels:
        return "Invalid log level", 404

    filename = os.path.join(tempfile.gettempdir(), f"esp32_{level.lower()}_logs.csv")
    
    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn: 
        cursor = conn.cursor()
        cursor.execute(f'SELECT received_at, timestamp, tag, message FROM {level} ORDER BY id ASC')
        rows = cursor.fetchall()

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ReceivedAt', 'LogTimestamp', 'Tag', 'Message'])
        writer.writerows(rows)
        
    return send_file(filename, as_attachment=True, download_name=f'esp32_{level.lower()}_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

@routes_bp.route('/reset', methods=['POST'])
def reset_database():
    """Clears all logs and resets statistics in the database."""
    try:
        with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn: 
            cursor = conn.cursor()
            log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
            # Clear all log entries from each table
            for level in log_levels:
                cursor.execute(f'DELETE FROM {level}')
            # Reset all statistic counters to 0
            cursor.execute('UPDATE stats SET value = 0')
            conn.commit()
        logging.info("Database has been reset successfully.")
        return jsonify(success=True, message="All logs and statistics have been reset.")
    except Exception as e:
        logging.error(f"Error resetting database: {e}")
        return jsonify(success=False, message="An error occurred during reset."), 500

@routes_bp.route('/flash_device', methods=['POST'])
def flash_device():
    """Flashes a binary to the ESP32 device."""
    esp_manager = current_app.esp_manager
    if 'firmware' not in request.files:
        return jsonify(success=False, message="No firmware file provided."), 400

    firmware_file = request.files['firmware']
    if firmware_file.filename == '':
        return jsonify(success=False, message="No selected file."), 400

    if esp_manager.esp32_connection_status["connected"] and esp_manager.esp32_connection_status["port"]:
        try:
            # Save the uploaded file temporarily
            temp_dir = tempfile.gettempdir()
            firmware_path = os.path.join(temp_dir, firmware_file.filename)
            firmware_file.save(firmware_path)

            # Call the flashing function in esp_handler
            output = esp_manager.flash_firmware(esp_manager.esp32_connection_status["port"], firmware_path, "factory_app")
            
            # Clean up the temporary file
            os.remove(firmware_path)

            return jsonify(success=True, message="Flashing initiated.", output=output)
        except Exception as e:
            return jsonify(success=False, message=f"Error flashing device: {e}", output=str(e)), 500
    else:
        return jsonify(success=False, message="No ESP32 device connected."), 400

@routes_bp.route('/all_logs/<level>')
def get_all_logs(level):
    """Returns all log messages for a specific level."""
    level = level.upper()
    allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    if level not in allowed_levels:
        return jsonify(error="Invalid log level"), 404

    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn: 
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        cursor = conn.cursor()
        
        query = f"SELECT timestamp, tag, message FROM {level} ORDER BY received_at ASC"
        cursor.execute(query)
        logs = [dict(row) for row in cursor.fetchall()]
    return jsonify(logs)

@routes_bp.route('/app_logs')
def get_app_logs():
    """Returns the content of the application log file."""
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.log')
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r', encoding='utf-8') as f:
            logs = f.read()
        return jsonify(logs=logs)
    else:
        return jsonify(logs="No application logs found."), 404
