import http.server
import socketserver
import sys
import os
import base64
import json
import datetime
import urllib.parse
from dotenv import load_dotenv
import logs

# Site files and Webserver files
DIRECTORY = "site/public/"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
RESOURCE_PREFIX = "resources/"
ADMIN_PREFIX = "admin_pages/"

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

    def log_request(self, code='-', size='-'):
        """Overrides the base class method to write logs to custom file"""
        logs.log_request_to_file(self) 

    def do_GET(self):
        """Intercept specific routes before checking the static directory."""
        resource_path = f"/{RESOURCE_PREFIX}"
        parsed_path = urllib.parse.urlparse(self.path)
        path_only = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)

        if path_only.startswith(resource_path):
            filepath = path_only[1:]
            file_extension = os.path.splitext(filepath)[1].lower()
            content_type = MIME_TYPES.get(file_extension, 'application/octet-stream')

            self.serve_file_from_root(filepath, content_type=content_type)
        
        elif path_only == '/favicon.ico':
            self.serve_file_from_root(f"{RESOURCE_PREFIX}favicon.png", "image/png")

        elif path_only == '/requests.log':
            if self.check_auth():
                self.serve_file_from_root("server/requests.log", "text/plain; charset=utf-8")
            
        elif path_only == '/logs':
            if self.check_auth():
                self.serve_file_from_root(f"{ADMIN_PREFIX}logs.html", "text/html; charset=utf-8")

        elif path_only == '/api/logs/stats':
            if self.check_auth():
                self.send_json({'size': logs.get_log_size()})

        elif path_only == '/api/logs/search':
            if self.check_auth():
                search_term = query_params.get('q', [''])[0] 
                results = logs.search_logs(search_term)
                self.send_json(results)

        elif path_only == '/api/logs/archive':
            if self.check_auth():
                self.archive_logs()
            
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

    def check_auth(self):
        """Checks for Basic Auth headers. Returns True if authorized."""
        auth_header = self.headers.get('Authorization')

        # Basic auth sends credentials as "Basic base64(username:password)"
        credentials = f"{USERNAME}:{PASSWORD}"
        expected_signature = base64.b64encode(credentials.encode()).decode()
        expected_header = f"Basic {expected_signature}"

        if auth_header == expected_header:
            return True
        else:
            # If no header or wrong password, send 401 to trigger browser popup
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="Restricted Logs"')
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Access denied: Authentication required.")
            return False

    def serve_file_from_root(self, filename, content_type):
        """Helper to serve a file from the SYSTEM_ROOT instead of DIRECTORY"""
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
                self.send_error(500, f"Internal Server Error: {e}")
        else:
            self.send_error(404, "File not found")

    def archive_logs(self):
        """Reads current log, sends it as download, then clears file."""
        if os.path.exists(logs.LOG_FILE):
            with open(logs.LOG_FILE, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"requests_archive_{timestamp}.log"
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

            with open(logs.LOG_FILE, 'w'):
                pass

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