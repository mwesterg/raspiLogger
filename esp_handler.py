# esp_handler.py

import time
from datetime import datetime
import serial
import serial.tools.list_ports 
from esptool import detect_chip, reset_chip, write_flash
import re

from config import SUPPORTED_DEVICES, SERIAL_BAUDRATE
from database import add_log_entry, update_other_messages_stat
from log_parser import parse_log_message

esp_global = None

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
    "boot_timestamp": None,
    "is_booting": False
}

def reset_esp32(port, get_info=False):
    """Resets the ESP32 device using esptool. Optionally gets device info."""
    global esp32_connection_status, esp_global
    try:
        if get_info or esp_global is None: # If it's a new connection or esp_global is not set
            print(f"Detecting chip at {port}...")
            esp_global = detect_chip(port=port)
            print("Getting device info...")
            esp32_connection_status["device_info"]["chip_type"] = esp_global.CHIP_NAME
            esp32_connection_status["device_info"]["features"] = ", ".join(esp_global.get_chip_features())
            esp32_connection_status["device_info"]["mac_address"] = ":".join(f"{b:02x}" for b in esp_global.read_mac())
        else:
            print(f"Using existing ESP object for {port}...")

        print(f"Resetting ESP32 at {port} using esptool...")
        reset_chip(esp_global, reset_mode="hard-reset")
        esp32_connection_status["is_booting"] = True # Start expecting boot logs
        esp32_connection_status["boot_logs"] = [] # Clear previous boot logs
        esp32_connection_status["boot_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Capture boot time
        print(f"ESP32 at {port} reset successfully.")

    except Exception as e:
        print(f"Error interacting with ESP32 at {port}: {e}")
        esp_global = None # Reset global esp object on error

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
            esp32_connection_status["is_booting"] = True # Start expecting boot logs
            print(f"Successfully opened {device_path}. Waiting for messages...")
            reset_esp32(device_path, get_info=True)
            time.sleep(2) # Wait for the device to boot
            
            # is_booting = True # This is now global
            while True:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"Received line: {line}")
                        
                        if esp32_connection_status["is_booting"]:
                            esp32_connection_status["boot_logs"].append(line)
                            if "main_task: Calling app_main()" in line:
                                esp32_connection_status["is_booting"] = False
                                print("App main started. Switching to normal logging.")

                        # These regex matches should probably be moved to log_parser or a new device_info_parser
                        # For now, keeping them here as they directly update esp32_connection_status
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

                        if not esp32_connection_status["is_booting"]: # Only add to info logs if not in boot sequence
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
                    esp32_connection_status["is_booting"] = False
                    esp_global = None # Reset global esp object on disconnect
                    break
                except Exception as e:
                    print(f"An error occurred while reading from serial port: {e}")
                    time.sleep(1)

    except serial.SerialException as e:
        print(f"Could not open serial port {device_path}: {e}")

def flash_firmware(port, firmware_path, partition_name):
    """Flashes firmware to the ESP32 device using esptool."""
    global esp_global
    try:
        if esp_global is None:
            print(f"Detecting chip for flashing at {port}...")
            esp_global = detect_chip(port=port)
        
        # Read partition table
        print("Reading partition table...")
        partitions = esp_global.read_partition_table()
        
        target_offset = None
        for p in partitions:
            if p.name == partition_name:
                target_offset = p.offset
                break
        
        if target_offset is None:
            raise ValueError(f"Partition '{partition_name}' not found in device's partition table.")

        print(f"Flashing {firmware_path} to partition '{partition_name}' at offset 0x{target_offset:x} on {port}...")
        
        with open(firmware_path, 'rb') as f:
            bytes_written, output_string = write_flash(esp_global, [(target_offset, f)])
        
        print(f"Flashing complete. Bytes written: {bytes_written}")
        return output_string
    except Exception as e:
        print(f"Error during flashing: {e}")
        raise # Re-raise the exception to be caught by the route