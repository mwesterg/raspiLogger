
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