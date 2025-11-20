import http.server
import socketserver
import sys
import os
import base64
from dotenv import load_dotenv

# Site files and Webserver files
DIRECTORY = "site/public/"
SYSTEM_ROOT = "." 

load_dotenv()
USERNAME = os.getenv("ADMIN_USER")
PASSWORD = os.getenv("ADMIN_PASS")

class Handler(http.server.SimpleHTTPRequestHandler):
    """A request handler that serves files from a specific directory."""
    
    def __init__(self, *args, **kwargs):
        # Initialize the standard handler pointing to site files
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        """Intercept specific routes before checking the static directory."""
        
        if self.path == '/favicon.ico':
            self.serve_file_from_root("favicon.png", "image/png")
            
        elif self.path == '/logs':
            if self.check_auth():
                self.serve_file_from_root("logpage/logs.html", "text/plain; charset=utf-8")
            
        else:
            super().do_GET()

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
        file_path = os.path.join(SYSTEM_ROOT, filename)
        
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