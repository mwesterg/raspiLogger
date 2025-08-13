# log_parser.py

import re
import logging # Import logging

# Regex to strip ANSI color codes
ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-9;]*m')
# Regex to parse ESP-IDF log format: e.g., "I (1234) TAG: message"
LOG_PATTERN = re.compile(r"^(D|I|W|E) \(([\d:.]+)\) ([\w.-]+): (.*)$")

def parse_log_message(line):
    """Parses a line and returns a dictionary or None."""
    # Strip ANSI color codes from the line
    cleaned_line = ANSI_ESCAPE_PATTERN.sub('', line)
    logging.debug(f"Cleaned line: {cleaned_line}") # DEBUG: Print cleaned line
    match = LOG_PATTERN.match(cleaned_line)
    logging.debug(f"Regex match: {match}") # DEBUG: Print regex match
    if not match:
        return None
    
    level_char, timestamp, tag, message = match.groups()
    logging.debug(f"Matched groups: Level={level_char}, Timestamp={timestamp}, Tag={tag}, Message={message}") # DEBUG: Print matched groups
    level_map = {'D': 'DEBUG', 'I': 'INFO', 'W': 'WARNING', 'E': 'ERROR'}
    
    return {
        'level': level_map.get(level_char),
        'timestamp': timestamp,
        'tag': tag,
        'message': message.strip()
    }