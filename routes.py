
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