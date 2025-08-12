

def flash_firmware(port, firmware_path, partition_name):
    """Flashes firmware to the ESP32 device using esptool."""
    global esp_global
    try:
        if esp_global is None:
            print(f"Detecting chip for flashing at {port}...")
            esp_global = detect_chip(port=port)
        
        print(f"Flashing {firmware_path} to {partition_name} on {port}...")
        # esptool.write_flash expects a list of (address, filename) tuples
        # It also expects the file to be open in binary mode.
        with open(firmware_path, 'rb') as f:
            # write_flash returns a tuple (bytes_written, output_string)
            bytes_written, output_string = write_flash(esp_global, [(0x10000, f)])
        
        print(f"Flashing complete. Bytes written: {bytes_written}")
        return output_string
    except Exception as e:
        print(f"Error during flashing: {e}")
        raise # Re-raise the exception to be caught by the route