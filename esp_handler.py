# This file handles interactions with the ESP32 device, including serial communication,
# boot log detection, device information retrieval, and firmware flashing.
import sys
import time
from datetime import datetime
import serial
import serial.tools.list_ports 
from esptool import detect_chip, run, write_flash, reset_chip
import re
import logging # Impor
import threading

from config import SUPPORTED_DEVICES, SERIAL_BAUDRATE
from database import add_log_entry, update_other_messages_stat
from log_parser import parse_log_message

sys.path.append("esptools")
import parttool

class ESPManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.esp_global = None
        self.esp32_connection_status = {
            "connected": False,
            "port": None,
            "device_info": {
                "chip_type": None,
                "features": None,
                "mac_address": None,
                "app_version": None,
                "project_name": None,
                "reset_reason": [],
                "compile_time": None,
                "esp_idf_version": None
            },
            "boot_logs": [],
            "boot_timestamp": None,
            "is_booting": False,
            "cpu_start_count": 0 # New field
        }

    def reset_esp32(self, port, get_info=False):
        """Resets the ESP32 device using esptool. Optionally gets device info."""
        with self.lock:
            try:
                if get_info or self.esp_global is None: # If it's a new connection or esp_global is not set
                    logging.info(f"Detecting chip at {port}...")
                    self.esp_global = detect_chip(port=port)
                    logging.info("Getting device info...")
                    self.esp32_connection_status["device_info"]["chip_type"] = self.esp_global.CHIP_NAME
                    self.esp32_connection_status["device_info"]["features"] = ", ".join(self.esp_global.get_chip_features())
                    self.esp32_connection_status["device_info"]["mac_address"] = ":".join(f"{b:02x}" for b in self.esp_global.read_mac())
                else:
                    logging.info(f"Using existing ESP object for {port}...")

                logging.info(f"Resetting ESP32 at {port} using esptool...")
                reset_chip(self.esp_global, reset_mode="hard-reset")
                # Boot log capture will now be triggered by "rst:0x" message
                logging.info(f"ESP32 at {port} reset successfully.")

            except Exception as e:
                logging.error(f"Error interacting with ESP32 at {port}: {e}")
                self.esp_global = None # Reset global esp object on error

    def monitor_serial_port(self, device_path):
        """Reads from a serial port and logs the messages."""
        logging.info(f"Attempting to monitor serial port: {device_path}")
        try:
            logging.info(f"Opening serial port {device_path} with baudrate {SERIAL_BAUDRATE}...")
            with serial.Serial(device_path, SERIAL_BAUDRATE, timeout=1) as ser:
                with self.lock:
                    self.esp32_connection_status["connected"] = True
                    self.esp32_connection_status["port"] = device_path
                    self.esp32_connection_status["is_booting"] = False # Ensure it's false initially
                logging.info(f"Successfully opened {device_path}. Waiting for messages...")
                self.reset_esp32(device_path, get_info=True)
                time.sleep(2) # Wait for the device to boot
                
                while True:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            with self.lock:
                                logging.debug(f"Received line: {line}")
                                
                                # Check for reset reason to start boot logging
                                if not self.esp32_connection_status["is_booting"] and "rst:0x" in line:
                                    self.esp32_connection_status["is_booting"] = True
                                    self.esp32_connection_status["boot_logs"] = [] # Clear previous boot logs
                                    self.esp32_connection_status["boot_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Capture boot time
                                    self.esp32_connection_status["cpu_start_count"] = 0 # Reset counter
                                    logging.info("Detected reset reason (rst:0x). Starting boot log capture.")

                                if self.esp32_connection_status["is_booting"]:
                                    logging.debug(f"is_booting is True. Appending line to boot_logs. Current boot_logs length: {len(self.esp32_connection_status['boot_logs'])}")
                                    self.esp32_connection_status["boot_logs"].append(line)
                                    logging.debug(f"After append. New boot_logs length: {len(self.esp32_connection_status['boot_logs'])}")
                                    
                                    # Parse the log to get the tag for boot detection
                                    parsed_log_for_boot_check = parse_log_message(line)
                                    if parsed_log_for_boot_check:
                                        if parsed_log_for_boot_check['tag'] == 'cpu_start':
                                            self.esp32_connection_status["cpu_start_count"] += 1
                                        elif self.esp32_connection_status["cpu_start_count"] > 0: # If we've seen at least one cpu_start message
                                            self.esp32_connection_status["is_booting"] = False
                                            logging.info("App main started (cpu_start transition). Switching to normal logging.")
                                            # Reset cpu_start_count for next boot
                                            self.esp32_connection_status["cpu_start_count"] = 0

                                # These regex matches should probably be moved to log_parser or a new device_info_parser
                                # For now, keeping them here as they directly update esp32_connection_status
                                app_version_match = re.search(r"App version: (.*?)\x1b", line)
                                if app_version_match:
                                    self.esp32_connection_status["device_info"]["app_version"] = app_version_match.group(1).strip()

                                project_name_match = re.search(r"Project name: (.*?)\x1b", line)
                                if project_name_match:
                                    self.esp32_connection_status["device_info"]["project_name"] = project_name_match.group(1).strip()

                                reset_reason_match = re.search(r"rst:0x[0-9a-f]+ \(([^)]+)\)", line)
                                if reset_reason_match:
                                    self.esp32_connection_status["device_info"]["reset_reason"].append(reset_reason_match.group(1).strip())

                                compile_time_match = re.search(r"Compile time: (.*?)\x1b", line)
                                if compile_time_match:
                                    self.esp32_connection_status["device_info"]["compile_time"] = compile_time_match.group(1).strip()

                                esp_idf_version_match = re.search(r"ESP-IDF version: (.*?)\x1b", line)
                                if esp_idf_version_match:
                                    self.esp32_connection_status["device_info"]["esp_idf_version"] = esp_idf_version_match.group(1).strip()

                                logging.debug(f"is_booting: {self.esp32_connection_status['is_booting']}")
                                if not self.esp32_connection_status["is_booting"]: # Only add to info logs if not in boot sequence
                                    parsed_log = parse_log_message(line)
                                    logging.debug(f"Parsed log: {parsed_log}")
                                    if parsed_log:
                                        logging.info(f"Logged: {parsed_log['level']} - {parsed_log['message']}")
                                        logging.debug(f"Adding log entry: {parsed_log['level']}, {parsed_log['timestamp']}, {parsed_log['tag']}, {parsed_log['message']}")
                                        add_log_entry(
                                            parsed_log['level'],
                                            parsed_log['timestamp'],
                                            parsed_log['tag'],
                                            parsed_log['message']
                                        )
                                    else:
                                        # This is not a standard log message
                                        update_other_messages_stat()
                                        logging.debug(f"Non-log message, updating other stats: {line}")
                                        logging.info(f"Non-log message: {line}")
                    except serial.SerialException:
                        logging.error(f"Device {device_path} disconnected. Stopping monitor.")
                        with self.lock:
                            self.esp32_connection_status["connected"] = False
                            self.esp32_connection_status["port"] = None
                            self.esp32_connection_status["device_info"] = {
                                "chip_type": None,
                                "features": None,
                                "mac_address": None,
                                "usb_mode": None,
                                "app_version": None,
                                "project_name": None,
                                "reset_reason": [],
                                "compile_time": None,
                                "esp_idf_version": None
                            }
                            
                            self.esp32_connection_status["boot_logs"] = []
                            self.esp32_connection_status["boot_timestamp"] = None
                            self.esp32_connection_status["is_booting"] = False
                            self.esp32_connection_status["cpu_start_count"] = 0 # Reset counter
                            self.esp_global = None # Reset global esp object on disconnect
                        break
                    except Exception as e:
                        logging.error(f"An error occurred while reading from serial port: {e}")
                        time.sleep(1)

        except serial.SerialException as e:
            logging.error(f"Could not open serial port {device_path}: {e}")

    def flash_firmware(self, port, firmware_path, partition_name):
        """Flashes firmware to the ESP32 device using esptool."""
        with self.lock:
            try:
                logging.info(f"Connecting to ESP device at {port}...")

                esp = self.esp_global.run_stub()
                target_offset = 0x10000

                logging.info(f"Flashing {firmware_path} to partition '{partition_name}' at offset 0x{target_offset:x} on {port}...")
                
                write_flash(
                esp=esp,
                args=None,   # CLI args object is optional here
                address_filename=[(target_offset, firmware_path)],
                flash_size="detect",
                no_progress=False,
                encrypt=False
                )
                    
                logging.info(f"Flashing complete.")
                return "Flashing successful."
            except Exception as e:
                logging.error(f"Error during flashing: {e}")
                raise # Re-raise the exception to be caught by the route
 