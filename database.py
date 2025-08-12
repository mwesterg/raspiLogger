# database.py

import sqlite3
from config import DATABASE_FILE, MAX_LOG_ENTRIES

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