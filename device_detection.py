# This file handles the detection and monitoring of USB devices,
# specifically ESP32 devices, across different operating systems.

import sys
import threading
import time
import serial.tools.list_ports
import logging # Import logging

# Conditional import for pyudev (Linux only)
if sys.platform.startswith('linux'):
    import pyudev

from config import SUPPORTED_DEVICES

def device_event_handler(esp_manager):
    """Monitors for USB device connections and disconnections (Linux) or periodically scans (Windows)."""
    if sys.platform.startswith('linux'):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='tty')
        
        logging.info("Starting USB device monitor (Linux udev)...")
        
        # Check for already connected devices on startup
        for device in context.list_devices(subsystem='tty'):
            for supported_device in SUPPORTED_DEVICES:
                if device.get('ID_VENDOR_ID') == supported_device["vendor_id"] and device.get('ID_MODEL_ID') == supported_device["product_id"]:
                    logging.info(f"Found pre-existing ESP32 at {device.device_node}")
                    threading.Thread(target=esp_manager.monitor_serial_port, args=(device.device_node,), daemon=True).start()
                    break  # Move to the next device

        # Monitor for new connections
        for action, device in monitor:
            logging.info(f"New device detected: {device.device_node}")
            if action == 'add' and 'ID_VENDOR_ID' in device and 'ID_MODEL_ID' in device:
                for supported_device in SUPPORTED_DEVICES:
                    if device['ID_VENDOR_ID'] == supported_device["vendor_id"] and device['ID_MODEL_ID'] == supported_device["product_id"]:
                        logging.info(f"ESP32 connected at {device.device_node}")
                        # Give the system a moment to stabilize the device node
                        time.sleep(1)
                        threading.Thread(target=esp_manager.monitor_serial_port, args=(device.device_node,), daemon=True).start()
                        break # Move to the next device
            elif action == 'remove':
                if device.device_node == esp_manager.esp32_connection_status["port"]:
                    logging.info(f"ESP32 disconnected from {device.device_node}")
                    with esp_manager.lock:
                        esp_manager.esp32_connection_status["connected"] = False
                        esp_manager.esp32_connection_status["port"] = None
                        esp_manager.esp32_connection_status["device_info"] = {
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
                        esp_manager.esp32_connection_status["boot_logs"] = []
                        esp_manager.esp32_connection_status["boot_timestamp"] = None
                        esp_manager.esp32_connection_status["is_booting"] = False
                        esp_manager.esp32_connection_status["cpu_start_count"] = 0 # Reset counter
                        esp_manager.esp_global = None # Reset global esp object on disconnect
            
            # Note: Handling disconnection is implicitly managed by the serial reader thread exiting.
    else: # Windows or other non-Linux OS
        logging.info("Starting USB device monitor (Windows/Generic)...")
        connected_ports = {}

        def scan_ports():
            nonlocal connected_ports
            while True:
                current_ports = {}
                for p in serial.tools.list_ports.comports():
                    for supported_device in SUPPORTED_DEVICES:
                        if p.vid and p.pid and f'{p.vid:04x}' == supported_device["vendor_id"] and f'{p.pid:04x}' == supported_device["product_id"]:
                            if p.device not in connected_ports:
                                logging.info(f"Found ESP32 at {p.device}")
                                threading.Thread(target=esp_manager.monitor_serial_port, args=(p.device,), daemon=True).start()
                                connected_ports[p.device] = True
                            current_ports[p.device] = True
                
                # Remove disconnected ports
                disconnected_ports = [port for port in connected_ports if port not in current_ports]
                for port in disconnected_ports:
                    logging.info(f"ESP32 disconnected from {port}")
                    with esp_manager.lock:
                        if port == esp_manager.esp32_connection_status["port"]:
                            esp_manager.esp32_connection_status["connected"] = False
                            esp_manager.esp32_connection_status["port"] = None
                            esp_manager.esp32_connection_status["device_info"] = {
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
                            esp_manager.esp32_connection_status["boot_logs"] = []
                            esp_manager.esp32_connection_status["boot_timestamp"] = None
                            esp_manager.esp32_connection_status["is_booting"] = False
                            esp_manager.esp32_connection_status["cpu_start_count"] = 0 # Reset counter
                            esp_manager.esp_global = None # Reset global esp object on disconnect
                    del connected_ports[port]

                time.sleep(3) # Scan every 3 seconds

        threading.Thread(target=scan_ports, daemon=True).start()