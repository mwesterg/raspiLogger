
@routes_bp.route('/flash_device', methods=['POST'])
def flash_device():
    """Flashes a binary to the ESP32 device."""
    if 'firmware' not in request.files:
        return jsonify(success=False, message="No firmware file provided."), 400

    firmware_file = request.files['firmware']
    if firmware_file.filename == '':
        return jsonify(success=False, message="No selected file."), 400

    if esp32_connection_status["connected"] and esp32_connection_status["port"]:
        try:
            # Save the uploaded file temporarily
            temp_dir = tempfile.gettempdir()
            firmware_path = os.path.join(temp_dir, firmware_file.filename)
            firmware_file.save(firmware_path)

            # Call the flashing function in esp_handler
            output = flash_firmware(esp32_connection_status["port"], firmware_path, "factory_app")
            
            # Clean up the temporary file
            os.remove(firmware_path)

            return jsonify(success=True, message="Flashing initiated.", output=output)
        except Exception as e:
            return jsonify(success=False, message=f"Error flashing device: {e}", output=str(e)), 500
    else:
        return jsonify(success=False, message="No ESP32 device connected."), 400
