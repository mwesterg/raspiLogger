#!/usr/bin/env python3
# main.py

import os
import csv
import re
import sqlite3
import threading
import time
import sys
import tempfile
from datetime import datetime

import serial
import serial.tools.list_ports
from flask import Flask, render_template, jsonify, send_file

import subprocess

# Conditional import for pyudev (Linux only)
if sys.platform.startswith('linux'):
    import pyudev

# --- Configuration ---
DATABASE_FILE = 'esp32_logs.db'
MAX_LOG_ENTRIES = 1000  # Max entries per log level table
SERIAL_BAUDRATE = 115200

# Supported device Vendor and Product IDs
SUPPORTED_DEVICES = [
    {"vendor_id": "10c4", "product_id": "ea60"},  # CP2102 USB to UART Bridge
    {"vendor_id": "303a", "product_id": "1001"},  # ESP32-S2 in normal mode
    {"vendor_id": "303a", "product_id": "0002"}   # ESP32-S3/C3 with TinyUSB
]

# --- Global State ---
esp32_connection_status = {
    "connected": False,
    "port": None,
    "device_info": {
        "chip_type": None,
        "features": None,
        "mac_address": None,
        "app_version": None,
        "project_name": None,
        "reset_reason": None,
        "compile_time": None,
        "esp_idf_version": None
    },
    "boot_logs": [],
    "boot_timestamp": None
}

# --- Flask Web App ---
app = Flask(__name__, template_folder='templates', static_folder='static')

# --- Database Setup ---
def init_db():
    """Initializes the database and creates tables if they don't exist."""
    # Connect with check_same_thread=False to allow access from multiple threads
    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn:
        cursor = conn.cursor()
        log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
        for level in log_levels:
            cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {level} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                tag TEXT,
                message TEXT,
                received_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''')
        # Table for general statistics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            key TEXT PRIMARY KEY,
            value INTEGER
        )
        ''')
        # Initialize stats
        stats_keys = ['total_messages', 'info_messages', 'debug_messages', 'warning_messages', 'error_messages', 'other_messages']
        for key in stats_keys:
            cursor.execute('INSERT OR IGNORE INTO stats (key, value) VALUES (?, 0)', (key,))
        conn.commit()

def add_log_entry(level, timestamp, tag, message):
    """Adds a log entry to the database, enforcing MAX_LOG_ENTRIES."""
    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn:
        cursor = conn.cursor()
        
        # Add the new log
        cursor.execute(f'INSERT INTO {level} (timestamp, tag, message) VALUES (?, ?, ?)', (timestamp, tag, message))
        
        # Check table size and trim if necessary (circular buffer behavior)
        cursor.execute(f'SELECT COUNT(*) FROM {level}')
        count = cursor.fetchone()[0]
        
        if count > MAX_LOG_ENTRIES:
            # Find the oldest entry's id and delete it
            cursor.execute(f'DELETE FROM {level} WHERE id IN (SELECT id FROM {level} ORDER BY id ASC LIMIT ?)', (count - MAX_LOG_ENTRIES,))

        # Update statistics
        cursor.execute('UPDATE stats SET value = value + 1 WHERE key = ?', (f'{level.lower()}_messages',))
        cursor.execute('UPDATE stats SET value = value + 1 WHERE key = ?', ('total_messages',))
        conn.commit()

def update_other_messages_stat():
    """Increments the count of non-logging messages."""
    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE stats SET value = value + 1 WHERE key = ?', ('other_messages',))
        conn.commit()

# --- ESP-IDF Log Parsing ---
# Regex to strip ANSI color codes
ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-9;]*m')
# Regex to parse ESP-IDF log format: e.g., "I (1234) TAG: message"
LOG_PATTERN = re.compile(r"^(D|I|W|E) \(([\d:.]+)\) ([\w.-]+): (.*)$")

def parse_log_message(line):
    """Parses a line and returns a dictionary or None."""
    # Strip ANSI color codes from the line
    cleaned_line = ANSI_ESCAPE_PATTERN.sub('', line)
    match = LOG_PATTERN.match(cleaned_line)
    if not match:
        return None
    
    level_char, timestamp, tag, message = match.groups()
    level_map = {'D': 'DEBUG', 'I': 'INFO', 'W': 'WARNING', 'E': 'ERROR'}
    
    return {
        'level': level_map.get(level_char),
        'timestamp': timestamp,
        'tag': tag,
        'message': message.strip()
    }

# --- Serial Port Monitoring ---
def reset_esp32(port):
    """Resets the ESP32 device using esptool and gets device info."""
    global esp32_connection_status
    try:
        print(f"Getting device info from {port} using esptool...")
        result = subprocess.run(["esptool", "--port", port, "flash_id"], capture_output=True, text=True, check=True)
        
        # Extracting information from esptool output
        chip_type_match = re.search(r"Detecting chip type... (.+)", result.stdout)
        if chip_type_match:
            esp32_connection_status["device_info"]["chip_type"] = chip_type_match.group(1).strip()

        features_match = re.search(r"Features: (.+)", result.stdout)
        if features_match:
            esp32_connection_status["device_info"]["features"] = features_match.group(1).strip()

        mac_address_match = re.search(r"MAC: (.+)", result.stdout)
        if mac_address_match:
            esp32_connection_status["device_info"]["mac_address"] = mac_address_match.group(1).strip()

        print(f"Resetting ESP32 at {port} using esptool...")
        subprocess.run(["esptool", "--port", port, "run"], check=True)
        print(f"ESP32 at {port} reset successfully.")

    except subprocess.CalledProcessError as e:
        print(f"Error interacting with ESP32 at {port}: {e}")
    except FileNotFoundError:
        print("esptool not found. Please ensure it is installed and in your PATH.")

def monitor_serial_port(device_path):
    """Reads from a serial port and logs the messages."""
    global esp32_connection_status
    print(f"Attempting to monitor serial port: {device_path}")
    try:
        print(f"Opening serial port {device_path} with baudrate {SERIAL_BAUDRATE}...")
        with serial.Serial(device_path, SERIAL_BAUDRATE, timeout=1) as ser:
            esp32_connection_status["connected"] = True
            esp32_connection_status["port"] = device_path
            esp32_connection_status["boot_logs"] = [] # Clear previous boot logs on new connection
            esp32_connection_status["boot_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Capture boot time
            print(f"Successfully opened {device_path}. Waiting for messages...")
            reset_esp32(device_path)
            time.sleep(2) # Wait for the device to boot
            
            is_booting = True
            while True:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"Received line: {line}")
                        
                        if is_booting:
                            esp32_connection_status["boot_logs"].append(line)
                            if "main_task: Calling app_main()" in line:
                                is_booting = False
                                print("App main started. Switching to normal logging.")

                        app_version_match = re.search(r"App version: (.*?)\x1b", line)
                        if app_version_match:
                            esp32_connection_status["device_info"]["app_version"] = app_version_match.group(1).strip()

                        project_name_match = re.search(r"Project name: (.*?)\x1b", line)
                        if project_name_match:
                            esp32_connection_status["device_info"]["project_name"] = project_name_match.group(1).strip()

                        reset_reason_match = re.search(r"rst:0x[0-9a-f]+ \(([^)]+)\)", line)
                        if reset_reason_match:
                            esp32_connection_status["device_info"]["reset_reason"] = reset_reason_match.group(1).strip()

                        compile_time_match = re.search(r"Compile time: (.*?)\x1b", line)
                        if compile_time_match:
                            esp32_connection_status["device_info"]["compile_time"] = compile_time_match.group(1).strip()

                        esp_idf_version_match = re.search(r"ESP-IDF version: (.*?)\x1b", line)
                        if esp_idf_version_match:
                            esp32_connection_status["device_info"]["esp_idf_version"] = esp_idf_version_match.group(1).strip()

                        if not is_booting: # Only add to info logs if not in boot sequence
                            parsed_log = parse_log_message(line)
                            if parsed_log:
                                print(f"Logged: {parsed_log['level']} - {parsed_log['message']}")
                                add_log_entry(
                                    parsed_log['level'],
                                    parsed_log['timestamp'],
                                    parsed_log['tag'],
                                    parsed_log['message']
                                )
                            else:
                                # This is not a standard log message
                                update_other_messages_stat()
                                print(f"Non-log message: {line}")
                except serial.SerialException:
                    print(f"Device {device_path} disconnected. Stopping monitor.")
                    esp32_connection_status["connected"] = False
                    esp32_connection_status["port"] = None
                    esp32_connection_status["device_info"] = {
                        "chip_type": None,
                        "features": None,
                        "mac_address": None,
                        "usb_mode": None,
                        "app_version": None,
                        "project_name": None,
                        "reset_reason": None,
                        "compile_time": None,
                        "esp_idf_version": None
                    }
                    
                    esp32_connection_status["boot_logs"] = []
                    esp32_connection_status["boot_timestamp"] = None
                    break
                except Exception as e:
                    print(f"An error occurred while reading from serial port: {e}")
                    time.sleep(1)

    except serial.SerialException as e:
        print(f"Could not open serial port {device_path}: {e}")

# --- udev Device Detection ---
def device_event_handler():
    """Monitors for USB device connections and disconnections (Linux) or periodically scans (Windows)."""
    if sys.platform.startswith('linux'):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='tty')
        
        print("Starting USB device monitor (Linux udev)...")
        
        # Check for already connected devices on startup
        for device in context.list_devices(subsystem='tty'):
            for supported_device in SUPPORTED_DEVICES:
                if device.get('ID_VENDOR_ID') == supported_device["vendor_id"] and device.get('ID_MODEL_ID') == supported_device["product_id"]:
                    print(f"Found pre-existing ESP32 at {device.device_node}")
                    threading.Thread(target=monitor_serial_port, args=(device.device_node,), daemon=True).start()
                    break  # Move to the next device

        # Monitor for new connections
        for action, device in monitor:
            print(f"New device detected: {device.device_node}")
            if action == 'add' and 'ID_VENDOR_ID' in device and 'ID_MODEL_ID' in device:
                for supported_device in SUPPORTED_DEVICES:
                    if device['ID_VENDOR_ID'] == supported_device["vendor_id"] and device['ID_MODEL_ID'] == supported_device["product_id"]:
                        print(f"ESP32 connected at {device.device_node}")
                        # Give the system a moment to stabilize the device node
                        time.sleep(1)
                        threading.Thread(target=monitor_serial_port, args=(device.device_node,), daemon=True).start()
                        break # Move to the next device
            elif action == 'remove':
                if device.device_node == esp32_connection_status["port"]:
                    print(f"ESP32 disconnected from {device.device_node}")
                    esp32_connection_status["connected"] = False
                    esp32_connection_status["port"] = None
                    esp32_connection_status["device_info"] = {
                        "chip_type": None,
                        "features": None,
                        "mac_address": None,
                        "usb_mode": None,
                        "app_version": None,
                        "project_name": None,
                        "reset_reason": None,
                        "compile_time": None,
                        "esp_idf_version": None
                    }
                    esp32_connection_status["boot_logs"] = []
                    esp32_connection_status["boot_timestamp"] = None
            
            # Note: Handling disconnection is implicitly managed by the serial reader thread exiting.
    else: # Windows or other non-Linux OS
        print("Starting USB device monitor (Windows/Generic)...")
        connected_ports = {}

        def scan_ports():
            nonlocal connected_ports
            while True:
                current_ports = {}
                for p in serial.tools.list_ports.comports():
                    for supported_device in SUPPORTED_DEVICES:
                        if p.vid and p.pid and f'{p.vid:04x}' == supported_device["vendor_id"] and f'{p.pid:04x}' == supported_device["product_id"]:
                            if p.device not in connected_ports:
                                print(f"Found ESP32 at {p.device}")
                                threading.Thread(target=monitor_serial_port, args=(p.device,), daemon=True).start()
                                connected_ports[p.device] = True
                            current_ports[p.device] = True
                
                # Remove disconnected ports
                disconnected_ports = [port for port in connected_ports if port not in current_ports]
                for port in disconnected_ports:
                    print(f"ESP32 disconnected from {port}")
                    if port == esp32_connection_status["port"]:
                        esp32_connection_status["connected"] = False
                        esp32_connection_status["port"] = None
                        esp32_connection_status["device_info"] = {
                            "chip_type": None,
                            "features": None,
                            "mac_address": None,
                            "usb_mode": None,
                            "app_version": None,
                            "project_name": None,
                            "reset_reason": None,
                            "compile_time": None,
                            "esp_idf_version": None
                        }
                        esp32_connection_status["boot_logs"] = []
                        esp32_connection_status["boot_timestamp"] = None
                    del connected_ports[port]

                time.sleep(3) # Scan every 3 seconds

        threading.Thread(target=scan_ports, daemon=True).start()

# --- Flask Web Routes ---
@app.route('/')
def index():
    """Serves the main dashboard page."""
    html_template = """
    return render_template('index.html')
    """
    return render_template_string(html_template)

@app.route('/tags')
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

@app.route('/filtered_logs/<tag>')
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

@app.route('/restart_device', methods=['POST'])
def restart_device():
    """Restarts the connected ESP32 device."""
    global esp32_connection_status
    if esp32_connection_status["connected"] and esp32_connection_status["port"]:
        try:
            # This will trigger a new boot sequence and log capture
            reset_esp32(esp32_connection_status["port"])
            return jsonify(success=True, message="Device restart initiated.")
        except Exception as e:
            return jsonify(success=False, message=f"Error restarting device: {e}"), 500
    else:
        return jsonify(success=False, message="No ESP32 device connected."), 400

@app.route('/boot_logs')
def get_boot_logs():
    """Returns the latest boot logs."""
    return jsonify(boot_logs=esp32_connection_status["boot_logs"], boot_timestamp=esp32_connection_status["boot_timestamp"])

@app.route('/connection_status')
def get_connection_status():
    """Returns the current ESP32 connection status."""
    return jsonify(esp32_connection_status)

@app.route('/stats')
def get_stats():
    """Returns the current logging statistics as JSON."""
    with sqlite3.connect(DATABASE_FILE, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM stats')
        stats = {row[0]: row[1] for row in cursor.fetchall()}
    return jsonify(stats)

@app.route('/latest_logs/<level>')
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


@app.route('/download/<level>')
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

@app.route('/reset', methods=['POST'])
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
        print("Database has been reset successfully.")
        return jsonify(success=True, message="All logs and statistics have been reset.")
    except Exception as e:
        print(f"Error resetting database: {e}")
        return jsonify(success=False, message="An error occurred during reset."), 500

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
