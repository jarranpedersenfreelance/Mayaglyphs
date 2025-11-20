import http.server
import socketserver
import sys

# --- Configuration ---
DIRECTORY = "site/public/"

class Handler(http.server.SimpleHTTPRequestHandler):
    """A request handler that serves files from a specific directory."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def run_server(port):
    """Sets up and runs the web server"""
    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            httpd.serve_forever()
    except PermissionError:
        print(f"Error: Permission denied. Cannot bind to port {port}. Use a non-privileged port (>1024) or check root permissions.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    try:
        PORT = int(sys.argv[1])
    except IndexError:
        PORT = 1500 # Default port for local run
    except ValueError:
        print("Error: Port must be an integer.")
        sys.exit(1)
        
    run_server(PORT)