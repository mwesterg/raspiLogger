#!/usr/bin/env python3
# main.py

import os
import csv
import re
import sqlite3
import threading
import time
from datetime import datetime

import serial
import pyudev
from flask import Flask, render_template_string, jsonify, send_file

import subprocess

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
app = Flask(__name__)

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
    """Monitors for USB device connections and disconnections."""
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='tty')
    
    print("Starting USB device monitor...")
    
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
        
        # Note: Handling disconnection is implicitly managed by the serial reader thread exiting.

# --- Flask Web Routes ---
@app.route('/')
def index():
    """Serves the main dashboard page."""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TurboMon</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; }
        </style>
    </head>
    <body class="bg-gray-100 text-gray-800">
        <div class="container mx-auto p-4 md:p-8">
            <div class="flex justify-between items-center mb-6">
                <h1 class="text-3xl font-bold text-gray-900">TurboMonitor</h1>
                <div id="connection-status" class="flex items-center">
                    <div id="connection-indicator" class="h-4 w-4 rounded-full mr-2"></div>
                    <span id="connection-text"></span>
                    <div id="device-info" class="ml-4 text-sm text-gray-500"></div>
                </div>
            </div>
            
            <div id="stats-container" class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
                <!-- Stats will be loaded here by JavaScript -->
            </div>

            <h2 class="text-2xl font-semibold mb-4 text-gray-900">Live Log Feeds</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
                <!-- Debug Column -->
                <div>
                    <h3 class="text-lg font-medium mb-2 text-blue-600">Debug</h3>
                    <div id="debug-log-feed" class="h-64 overflow-y-auto font-mono text-sm bg-gray-900 text-white p-4 rounded shadow-inner">
                        <p class="text-gray-500">Waiting for logs...</p>
                    </div>
                </div>
                <!-- Info Column -->
                <div>
                    <h3 class="text-lg font-medium mb-2 text-green-600">Info</h3>
                    <div id="info-log-feed" class="h-64 overflow-y-auto font-mono text-sm bg-gray-900 text-white p-4 rounded shadow-inner">
                         <p class="text-gray-500">Waiting for logs...</p>
                    </div>
                </div>
                <!-- Warning Column -->
                <div>
                    <h3 class="text-lg font-medium mb-2 text-yellow-600">Warning</h3>
                    <div id="warning-log-feed" class="h-64 overflow-y-auto font-mono text-sm bg-gray-900 text-white p-4 rounded shadow-inner">
                         <p class="text-gray-500">Waiting for logs...</p>
                    </div>
                </div>
                <!-- Error Column -->
                <div>
                    <h3 class="text-lg font-medium mb-2 text-red-600">Error</h3>
                    <div id="error-log-feed" class="h-64 overflow-y-auto font-mono text-sm bg-gray-900 text-white p-4 rounded shadow-inner">
                         <p class="text-gray-500">Waiting for logs...</p>
                    </div>
                </div>
            </div>

            <h2 class="text-2xl font-semibold mb-4 text-gray-900">Download Logs</h2>
            <div class="bg-white p-6 rounded-lg shadow-md">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <a href="/download/DEBUG" class="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded text-center transition duration-300">Download DEBUG</a>
                    <a href="/download/INFO" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded text-center transition duration-300">Download INFO</a>
                    <a href="/download/WARNING" class="bg-yellow-500 hover:bg-yellow-600 text-white font-bold py-2 px-4 rounded text-center transition duration-300">Download WARNING</a>
                    <a href="/download/ERROR" class="bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded text-center transition duration-300">Download ERROR</a>
                </div>
            </div>

            <h2 class="text-2xl font-semibold mb-4 mt-8 text-gray-900">Maintenance</h2>
            <div class="bg-white p-6 rounded-lg shadow-md">
                <div class="flex flex-wrap gap-4">
                    <button id="reset-database-button" class="bg-red-700 hover:bg-red-800 text-white font-bold py-2 px-4 rounded transition duration-300">Reset Database</button>
                    <button id="show-boot-logs-button" class="bg-blue-700 hover:bg-blue-800 text-white font-bold py-2 px-4 rounded transition duration-300">Show Boot Logs</button>
                    <button id="restart-device-button" class="bg-purple-700 hover:bg-purple-800 text-white font-bold py-2 px-4 rounded transition duration-300">Restart Device</button>
                    <button id="filter-logs-button" class="bg-green-700 hover:bg-green-800 text-white font-bold py-2 px-4 rounded transition duration-300">Filter Logs by Tag</button>
                </div>
                <p class="text-sm text-gray-600 mt-2">This will permanently delete all stored logs and reset all counters.</p>
            </div>
        </div>

        <!-- Modal for confirmation -->
        <div id="reset-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full hidden z-50">
            <div class="relative top-20 mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
                <div class="mt-3 text-center">
                    <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                        <svg class="h-6 w-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                    </div>
                    <h3 class="text-lg leading-6 font-medium text-gray-900">Reset Database?</h3>
                    <div class="mt-2 px-7 py-3">
                        <p class="text-sm text-gray-500">
                            Are you sure? All stored logs and statistics will be permanently deleted. This action cannot be undone.
                        </p>
                    </div>
                    <div class="items-center px-4 py-3 space-y-2 md:space-y-0 md:flex md:items-center md:justify-center md:space-x-4">
                        <button id="confirm-reset-btn" class="w-full md:w-auto px-4 py-2 bg-red-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500">
                            Yes, Reset Database
                        </button>
                        <button id="cancel-reset-btn" class="w-full md:w-auto px-4 py-2 bg-gray-200 text-gray-900 text-base font-medium rounded-md shadow-sm hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-300">
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal for Boot Logs -->
        <div id="boot-logs-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full hidden z-50">
            <div class="relative top-20 mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
                <div class="mt-3 text-center">
                    <h3 class="text-lg leading-6 font-medium text-gray-900">Latest Boot Logs</h3>
                    <p id="boot-log-date" class="text-sm text-gray-500 mb-2"></p>
                    <div class="mt-2 px-7 py-3">
                        <div id="boot-logs-content" class="h-64 overflow-y-auto font-mono text-sm bg-gray-900 text-white p-4 rounded shadow-inner text-left">
                            <!-- Boot logs will be loaded here -->
                        </div>
                    </div>
                    <div class="items-center px-4 py-3">
                        <button id="close-boot-logs-btn" class="w-full px-4 py-2 bg-blue-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal for Filtered Logs -->
        <div id="filter-logs-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full hidden z-50">
            <div class="relative top-20 mx-auto p-5 border w-full max-w-md shadow-lg rounded-md bg-white">
                <div class="mt-3 text-center">
                    <h3 class="text-lg leading-6 font-medium text-gray-900">Filter Logs by Tag</h3>
                    <div class="mt-4">
                        <select id="tag-dropdown" class="block w-full p-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm">
                            <option value="">Select a Tag</option>
                        </select>
                    </div>
                    <div class="mt-4 px-7 py-3">
                        <div id="filtered-logs-content" class="h-64 overflow-y-auto font-mono text-sm bg-gray-900 text-white p-4 rounded shadow-inner text-left">
                            <!-- Filtered logs will be loaded here -->
                        </div>
                    </div>
                    <div class="items-center px-4 py-3">
                        <button id="close-filter-logs-btn" class="w-full px-4 py-2 bg-blue-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            const logLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

            function fetchConnectionStatus() {
                fetch('/connection_status')
                    .then(response => response.json())
                    .then(data => {
                        const indicator = document.getElementById('connection-indicator');
                        const text = document.getElementById('connection-text');
                        const deviceInfo = document.getElementById('device-info');
                        if (data.connected) {
                            indicator.classList.remove('bg-red-500');
                            indicator.classList.add('bg-green-500');
                            text.textContent = `Connected at ${data.port}`;
                            let deviceInfoHTML = '';
                            if(data.device_info) {
                                deviceInfoHTML += `<div class="grid grid-cols-2 gap-x-4">`;
                                if (data.device_info.chip_type) {
                                    deviceInfoHTML += `<div><span class="font-semibold">Chip Type:</span> ${data.device_info.chip_type}</div>`;
                                }
                                if (data.device_info.features) {
                                    deviceInfoHTML += `<div><span class="font-semibold">Features:</span> ${data.device_info.features}</div>`;
                                }
                                if (data.device_info.mac_address) {
                                    deviceInfoHTML += `<div><span class="font-semibold">MAC Address:</span> ${data.device_info.mac_address}</div>`;
                                }
                                if (data.device_info.app_version) {
                                    deviceInfoHTML += `<div><span class="font-semibold">App Version:</span> ${data.device_info.app_version}</div>`;
                                }
                                if (data.device_info.project_name) {
                                    deviceInfoHTML += `<div><span class="font-semibold">Project Name:</span> ${data.device_info.project_name}</div>`;
                                }
                                if (data.device_info.reset_reason) {
                                    deviceInfoHTML += `<div><span class="font-semibold">Reset Reason:</span> ${data.device_info.reset_reason}</div>`;
                                }
                                if (data.device_info.compile_time) {
                                    deviceInfoHTML += `<div><span class="font-semibold">Compile Time:</span> ${data.device_info.compile_time}</div>`;
                                }
                                if (data.device_info.esp_idf_version) {
                                    deviceInfoHTML += `<div><span class="font-semibold">ESP-IDF Version:</span> ${data.device_info.esp_idf_version}</div>`;
                                }
                                deviceInfoHTML += `</div>`;
                            }
                            deviceInfo.innerHTML = deviceInfoHTML;
                        } else {
                            indicator.classList.remove('bg-green-500');
                            indicator.classList.add('bg-red-500');
                            text.textContent = 'Disconnected';
                            deviceInfo.innerHTML = '';
                        }
                    });
            }

            function fetchStats() {
                fetch('/stats')
                    .then(response => response.json())
                    .then(data => {
                        const container = document.getElementById('stats-container');
                        container.innerHTML = `
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-gray-500">Total Msgs</p><p class="text-2xl font-bold">${data.total_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-blue-500">Debug</p><p class="text-2xl font-bold">${data.debug_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-green-500">Info</p><p class="text-2xl font-bold">${data.info_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-yellow-500">Warning</p><p class="text-2xl font-bold">${data.warning_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-red-500">Error</p><p class="text-2xl font-bold">${data.error_messages || 0}</p></div>
                            <div class="bg-white p-4 rounded-lg shadow-md text-center"><p class="text-sm text-gray-500">Other</p><p class="text-2xl font-bold">${data.other_messages || 0}</p></div>
                        `;
                    });
            }
            
            function fetchLogsForLevel(level) {
                fetch(`/latest_logs/${level}`)
                    .then(response => response.json())
                    .then(logs => {
                        const feed = document.getElementById(`${level.toLowerCase()}-log-feed`);
                        if (logs.length === 0) {
                            feed.innerHTML = `<p class="text-gray-500">No ${level.toLowerCase()} logs.</p>`;
                            return;
                        }
                        
                        let logHTML = '';
                        logs.forEach(log => {
                            logHTML += `<div class="log-entry whitespace-nowrap overflow-hidden text-ellipsis">(${log.timestamp}) ${log.tag}: ${log.message}</div>`;
                        });
                        feed.innerHTML = logHTML;
                    });
            }

            // Fetch initial data on page load
            fetchConnectionStatus();
            fetchStats();
            logLevels.forEach(level => fetchLogsForLevel(level));
            
            // Set intervals to fetch data periodically
            setInterval(fetchConnectionStatus, 5000);
            setInterval(fetchStats, 5000);
            logLevels.forEach(level => {
                setInterval(() => fetchLogsForLevel(level), 3000);
            });

            // --- Reset Logic ---
            const resetDatabaseButton = document.getElementById('reset-database-button');
            console.log('resetDatabaseButton:', resetDatabaseButton);
            const modal = document.getElementById('reset-modal');
            console.log('modal:', modal);
            const confirmBtn = document.getElementById('confirm-reset-btn');
            console.log('confirmBtn:', confirmBtn);
            const cancelBtn = document.getElementById('cancel-reset-btn');
            console.log('cancelBtn:', cancelBtn);

            const showBootLogsButton = document.getElementById('show-boot-logs-button');
            console.log('showBootLogsButton:', showBootLogsButton);
            const bootLogsModal = document.getElementById('boot-logs-modal');
            console.log('bootLogsModal:', bootLogsModal);
            const closeBootLogsBtn = document.getElementById('close-boot-logs-btn');
            console.log('closeBootLogsBtn:', closeBootLogsBtn);
            const bootLogsContent = document.getElementById('boot-logs-content');
            console.log('bootLogsContent:', bootLogsContent);
            const bootLogDate = document.getElementById('boot-log-date');
            console.log('bootLogDate:', bootLogDate);

            const restartDeviceButton = document.getElementById('restart-device-button');
            console.log('restartDeviceButton:', restartDeviceButton);

            const filterLogsButton = document.getElementById('filter-logs-button');
            console.log('filterLogsButton:', filterLogsButton);
            const filterLogsModal = document.getElementById('filter-logs-modal');
            console.log('filterLogsModal:', filterLogsModal);
            const closeFilterLogsBtn = document.getElementById('close-filter-logs-btn');
            console.log('closeFilterLogsBtn:', closeFilterLogsBtn);
            const tagDropdown = document.getElementById('tag-dropdown');
            console.log('tagDropdown:', tagDropdown);
            const filteredLogsContent = document.getElementById('filtered-logs-content');
            console.log('filteredLogsContent:', filteredLogsContent);

            if (resetDatabaseButton) {
                resetDatabaseButton.addEventListener('click', () => {
                    console.log('Reset Database button clicked');
                    modal.classList.remove('hidden');
                });
            } else {
                console.error('resetDatabaseButton not found!');
            }

            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    console.log('Cancel button clicked');
                    modal.classList.add('hidden');
                });
            } else {
                console.error('cancelBtn not found!');
            }

            if (confirmBtn) {
                confirmBtn.addEventListener('click', () => {
                    console.log('Confirm Reset button clicked');
                    fetch('/reset', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        modal.classList.add('hidden');
                        if(data.success) {
                            console.log('Reset successful');
                            fetchStats(); // Immediately update the stats on the page
                            logLevels.forEach(level => {
                                 const feed = document.getElementById(`${level.toLowerCase()}-log-feed`);
                                 feed.innerHTML = `<p class="text-gray-500">No ${level.toLowerCase()} logs.</p>`;
                            });
                        } else {
                            console.error('An error occurred during reset: ' + data.message);
                        }
                    })
                    .catch(error => {
                        modal.classList.add('hidden');
                        console.error('Error:', error);
                    });
                });
            } else {
                console.error('confirmBtn not found!');
            }

            if (showBootLogsButton) {
                showBootLogsButton.addEventListener('click', () => {
                    console.log('Show Boot Logs button clicked');
                    fetch('/boot_logs')
                        .then(response => response.json())
                        .then(data => {
                            bootLogsContent.innerHTML = '';
                            if (data.boot_logs && data.boot_logs.length > 0) {
                                data.boot_logs.forEach(log => {
                                    bootLogsContent.innerHTML += `<div>${log}</div>`;
                                });
                            } else {
                                bootLogsContent.innerHTML = '<p class="text-gray-500">No boot logs available.</p>';
                            }
                            if (data.boot_timestamp) {
                                bootLogDate.textContent = `Boot Time: ${data.boot_timestamp}`;
                            } else {
                                bootLogDate.textContent = '';
                            }
                            bootLogsModal.classList.remove('hidden');
                        })
                        .catch(error => {
                            console.error('Error fetching boot logs:', error);
                            bootLogsContent.innerHTML = '<p class="text-red-500">Error loading boot logs.</p>';
                            bootLogsModal.classList.remove('hidden');
                        });
                });
            } else {
                console.error('showBootLogsButton not found!');
            }

            if (closeBootLogsBtn) {
                closeBootLogsBtn.addEventListener('click', () => {
                    console.log('Close Boot Logs button clicked');
                    bootLogsModal.classList.add('hidden');
                });
            } else {
                console.error('closeBootLogsBtn not found!');
            }

            if (restartDeviceButton) {
                restartDeviceButton.addEventListener('click', () => {
                    console.log('Restart Device button clicked');
                    fetch('/restart_device', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if(data.success) {
                            console.log('Device restart initiated.');
                        } else {
                            console.error('Error initiating device restart: ' + data.message);
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                    });
                });
            } else {
                console.error('restartDeviceButton not found!');
            }

            if (filterLogsButton) {
                filterLogsButton.addEventListener('click', () => {
                    console.log('Filter Logs button clicked');
                    filterLogsModal.classList.remove('hidden');
                    fetch('/tags')
                        .then(response => response.json())
                        .then(tags => {
                            tagDropdown.innerHTML = '<option value="">Select a Tag</option>';
                            tags.forEach(tag => {
                                tagDropdown.innerHTML += `<option value="${tag}">${tag}</option>`;
                            });
                        })
                        .catch(error => {
                            console.error('Error fetching tags:', error);
                        });
                });
            } else {
                console.error('filterLogsButton not found!');
            }

            if (closeFilterLogsBtn) {
                closeFilterLogsBtn.addEventListener('click', () => {
                    console.log('Close Filter Logs button clicked');
                    filterLogsModal.classList.add('hidden');
                    filteredLogsContent.innerHTML = ''; // Clear content when closing
                    tagDropdown.value = ''; // Reset dropdown
                });
            } else {
                console.error('closeFilterLogsBtn not found!');
            }

            if (tagDropdown) {
                tagDropdown.addEventListener('change', (event) => {
                    const selectedTag = event.target.value;
                    if (selectedTag) {
                        console.log(`Tag selected: ${selectedTag}`);
                        fetch(`/filtered_logs/${selectedTag}`)
                            .then(response => response.json())
                            .then(logs => {
                                filteredLogsContent.innerHTML = '';
                                if (logs.length > 0) {
                                    logs.forEach(log => {
                                        filteredLogsContent.innerHTML += `<div>(${log.timestamp}) ${log.tag}: ${log.message}</div>`;
                                    });
                                } else {
                                    filteredLogsContent.innerHTML = '<p class="text-gray-500">No logs found for this tag.</p>';
                                }
                            })
                            .catch(error => {
                                console.error('Error fetching filtered logs:', error);
                                filteredLogsContent.innerHTML = '<p class="text-red-500">Error loading filtered logs.</p>';
                            });
                    } else {
                        filteredLogsContent.innerHTML = ''; // Clear if no tag selected
                    }
                });
            } else {
                console.error('tagDropdown not found!');
            }
        </script>
    </body>
    </html>
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

    filename = f"/tmp/esp32_{level.lower()}_logs.csv"
    
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
