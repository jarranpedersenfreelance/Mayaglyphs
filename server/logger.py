import datetime
import sys
import requests
import os
from typing import Dict, Any
from urllib.parse import urlparse
from user_agents import parse

# --- Configuration ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
LOG_FILE = os.path.join(PROJECT_ROOT, "logs/requests.log")
ERROR_LOG_FILE = os.path.join(PROJECT_ROOT, "logs/errors.log")
GEO_IP_API = "http://ip-api.com/json/{ip}?fields=country,regionName,city"
LOG_FORMAT = "[{timestamp}] [{ip}] [{country}/{region}/{city}] [Referrer: {referrer}] [{method}] {url} | Agent: {user_agent}"
MAX_RETURN = 1000

STATIC_ASSET_EXTENSIONS = (
    '.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', 
    '.woff', '.woff2', '.ttf', '.otf', '.eot', '.map', '.json', '.txt'
)

IGNORED_ROUTES = [
    '/logs'
]

def get_log_size():
    """Returns the size of requests.log in bytes"""
    if os.path.exists(LOG_FILE):
        return os.path.getsize(LOG_FILE)
    return 0

def search_logs(term) -> Dict[str, Any]:
    """Filters log lines containing the term and returns JSON."""
    results = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Iterate in reverse to show newest logs first
            for line in reversed(lines): 
                if term.lower() in line.lower():
                    results.append(line.strip())
                    # Limit results to avoid massive response payload
                    if len(results) >= MAX_RETURN: 
                        break
    return {'results': results, 'count': len(results)}


def log_error_to_file(message):
    """Writes a timestamped message to the dedicated error log file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    with open(ERROR_LOG_FILE, 'a') as f:
        f.write(log_entry + "\n")

def is_static_asset(url_path):
    """Checks if a request is for a static asset based on the file extension."""
    path = urlparse(url_path).path
    
    # Check if the path ends with one of the defined static asset extensions
    if path.lower().endswith(STATIC_ASSET_EXTENSIONS):
        return True
    
    # Also check for common routes that don't serve full pages but aren't files (e.g., favicon)
    if path in IGNORED_ROUTES:
        return True
        
    return False

def is_bot(user_agent_string):
    """Checks if a request is likely from a bot/crawler based on the User-Agent header."""
    if not user_agent_string:
        return False

    # Use the ua-parser library to intelligently check
    user_agent = parse(user_agent_string)
    
    # Check for common flags
    if user_agent.is_bot:
        return True

    # Can add more specific checks here
    # e.g. filtering out specific known bot names from user_agent.device.family
        
    return False

def get_geolocation(ip_address):
    """
    Attempts to get location data for a given IP address.
    NOTE: Currently rate limited to 45/min, do batch lookup to increase
    """
    if ip_address in ('127.0.0.1', 'localhost'):
        return "N/A", "N/A", "N/A" # localhost/testing
        
    try:
        response = requests.get(GEO_IP_API.format(ip=ip_address), timeout=0.5)
        response.raise_for_status()
        data = response.json()
        
        country = data.get('country', 'Unknown')
        region = data.get('regionName', 'Unknown')
        city = data.get('city', 'Unknown')
        
        return country, region, city
        
    except requests.RequestException as e:
        log_error_to_file(f"GeoIP failed for {ip_address}: {e}")
        return "GeoIP-Failed", "GeoIP-Failed", "GeoIP-Failed"

def log_request_to_file(handler):
    """Logs the details of the incoming HTTP request to the LOG_FILE."""

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    method = handler.command
    url = handler.path
    referrer = handler.headers.get('Referer', 'N/A')
    user_agent = handler.headers.get('User-Agent', 'N/A')

    # Get proxy ip for server, regular for local
    ip = handler.headers.get('X-Real-IP')
    if not ip:
        ip = handler.client_address[0]

    if is_static_asset(url):
        return

    if is_bot(user_agent):
        return

    # Fetch Geolocation (comment out if performance needed)
    country, region, city = get_geolocation(ip)
    
    log_entry = LOG_FORMAT.format(
        timestamp=timestamp,
        ip=ip,
        country=country,
        region=region,
        city=city,
        referrer=referrer,
        method=method,
        url=url,
        user_agent=user_agent
    )
    
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_entry + "\n")
    except IOError as e:
        print(f"Error writing to log file {LOG_FILE}: {e}", file=sys.stderr)

def archive_logs(handler):
    """Reads current log, sends it as download, then clears file."""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'rb') as f:
            content = f.read()
        
        handler.send_response(200)
        handler.send_header("Content-Type", "text/plain")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"requests_archive_{timestamp}.log"
        handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        handler.send_header("Content-Length", str(len(content)))
        handler.end_headers()
        handler.wfile.write(content)

        with open(LOG_FILE, 'w'):
            pass