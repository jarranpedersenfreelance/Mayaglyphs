import http.server
import socketserver
import sys
import os
import base64
import json
import datetime
import urllib.parse
from dotenv import load_dotenv
import logger

# Site files and Webserver files
DIRECTORY = "site/public/"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
RESOURCE_PREFIX = "resources/"
ADMIN_PREFIX = "admin_pages/"
ERROR_TEMPLATE = "error.html"

# .env vars
load_dotenv()
USERNAME = os.getenv("ADMIN_USER")
PASSWORD = os.getenv("ADMIN_PASS")

# resource file types
MIME_TYPES = {
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.png': 'image/png'
}

class Handler(http.server.SimpleHTTPRequestHandler):
    """A request handler that serves files from a specific directory."""
    
    def __init__(self, *args, **kwargs):
        # Initialize the standard handler pointing to site files
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def send_error(self, code, message=None, explain=None):
        """Overrides base method to send a custom error"""
        is_api_request = self.path.startswith('/api/')

        if message is None:
            # Get the standard HTTP message if none is provided
            message = self.responses[code][0] 

        # Log the error internally using the logs module
        logger.log_error_to_file(f"HTTP Error {code} ({message}): {self.path}")
        
        if is_api_request:
            # API Response: Send a simple JSON error
            response_data = {'error': explain if explain else message, 'code': code}
            response = json.dumps(response_data).encode('utf-8')
            
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            
        else:
            # Send the custom HTML error page
            display_message = explain if explain else message
            template_path = os.path.join(ADMIN_PREFIX, ERROR_TEMPLATE)
            with open(template_path, 'rt') as f:
                template = f.read()
            html_content = template.format(code=code, message=display_message).encode('utf-8')
            
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Connection", "close")
            self.send_header("Content-Length", str(len(html_content)))
            self.end_headers()
            self.wfile.write(html_content)

    def log_request(self, code='-', size='-'):
        """Overrides the base class method to write logs to custom file"""
        logger.log_request_to_file(self) 

    def do_GET(self):
        """Intercept specific routes before checking the static directory."""
        resource_path = f"/{RESOURCE_PREFIX}"
        parsed_path = urllib.parse.urlparse(self.path)
        path_only = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        log_type = query_params.get('type', ['requests'])[0]

        if path_only.startswith(resource_path):
            filepath = path_only[1:]
            file_extension = os.path.splitext(filepath)[1].lower()
            content_type = MIME_TYPES.get(file_extension, 'application/octet-stream')

            self.serve_file_from_root(filepath, content_type=content_type)
        
        elif path_only == '/favicon.ico':
            self.serve_file_from_root(f"{RESOURCE_PREFIX}favicon.png", "image/png")
            
        elif path_only == '/logs':
            if self.check_auth(True):
                self.serve_file_from_root(f"{ADMIN_PREFIX}logs.html", "text/html; charset=utf-8")

        elif path_only == '/api/logs/requests.log':
            if self.check_auth():
                self.serve_file_from_root("logs/requests.log", "text/plain; charset=utf-8")

        elif path_only == '/api/logs/errors.log':
            if self.check_auth():
                self.serve_file_from_root("logs/errors.log", "text/plain; charset=utf-8")

        elif path_only == '/api/logs/stats':
            if self.check_auth():
                try:
                    self.send_json({'size': logger.get_log_size(log_type)})
                except Exception as e:
                    self.send_error(500, explain=f"Failed to fetch log stats: {e}")

        elif path_only == '/api/logs/search':
            if self.check_auth():
                try: 
                    search_term = query_params.get('q', [''])[0] 
                    results = logger.search_logs(search_term, log_type)
                    self.send_json(results)
                except Exception as e:
                    self.send_error(500, explain=f"Log search failed due to an internal error: {e}")

        elif path_only == '/api/logs/archive':
            if self.check_auth():
                try:
                    logger.archive_logs(self, log_type)
                except Exception as e:
                    self.send_error(500, explain=f"Log archive failed due to an internal error: {e}")
            
        else:
            super().do_GET()

    def send_json(self, data):
        """Helper to send JSON response"""
        response = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def check_auth(self, is_initial_page=False):
        """Checks for Basic Auth headers. Returns True if authorized."""
        auth_header = self.headers.get('Authorization')

        # Basic auth sends credentials as "Basic base64(username:password)"
        credentials = f"{USERNAME}:{PASSWORD}"
        expected_signature = base64.b64encode(credentials.encode()).decode()
        expected_header = f"Basic {expected_signature}"

        if auth_header == expected_header:
            return True
        else:
            self.send_response(401)
            if is_initial_page:
                self.send_header('WWW-Authenticate', 'Basic realm="Restricted Logs"')
            
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Access denied: Authentication required.")
            return False

    def serve_file_from_root(self, filename, content_type):
        """Helper to serve a file from the PROJECT_ROOT instead of DIRECTORY"""
        file_path = os.path.join(PROJECT_ROOT, filename)
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, explain=f"Internal Server Error while reading file: {e}")
        else:
            self.send_error(404, explain=f"The requested file '{filename}' could not be found.")

def run_server(port):
    """Sets up and runs the web server"""
    print(f"Serving HTTP on port {port} ...")
    try:
        socketserver.TCPServer.allow_reuse_address = True 
        with socketserver.TCPServer(("", port), Handler) as httpd:
            httpd.serve_forever()
    except PermissionError:
        print(f"Error: Permission denied. Cannot bind to port {port}.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    try:
        PORT = int(sys.argv[1])
    except IndexError:
        PORT = 1500 
    except ValueError:
        print("Error: Port must be an integer.")
        sys.exit(1)
        
    run_server(PORT)