import functools
import os
import sys
from dotenv import load_dotenv
from . import logger
from flask import Flask, request, jsonify, make_response, send_from_directory, abort, render_template, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

RESOURCE_PREFIX = "resources"
ADMIN_PREFIX = "admin_pages"
ERROR_TEMPLATE = "error.html"

INDEX_FILE = "LMGGC.html"
LOGS_TEMPLATE = "logs.html.jinja"
ERROR_TEMPLATE = "error.html.jinja"

# .env vars
load_dotenv()
USERNAME = os.getenv("ADMIN_USER")
PASSWORD = os.getenv("ADMIN_PASS")

# --- Flask App Initialization ---
app = Flask(__name__, 
            static_folder=os.path.join(PROJECT_ROOT, "site/public"),
            template_folder=os.path.join(PROJECT_ROOT, ADMIN_PREFIX))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

@app.before_request
def setup_logs():
    """Ensure log directories exist before the first request."""
    os.makedirs(os.path.join(PROJECT_ROOT, "logs"), exist_ok=True)
    log_files = [logger.LOG_FILE, logger.ERROR_LOG_FILE]
    for file_path in log_files:
        if not os.path.exists(file_path):
            with open(file_path, 'a'):
                pass

# --- Helper Functions ---

def check_auth():
    """Checks for Basic Auth headers. Returns True if authorized."""
    auth = request.authorization
    if auth and auth.username == USERNAME and auth.password == PASSWORD:
        return True
    return False

def requires_auth(f):
    """Decorator to enforce Basic Authentication."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            return make_response('Access denied: Authentication required.', 401, 
                                 {'WWW-Authenticate': 'Basic realm="Restricted Logs"'})
        return f(*args, **kwargs)
    return decorated

# --- Route Definitions ---

# Static Files
@app.route('/')
def index():
    return send_from_directory(str(app.static_folder), INDEX_FILE)

@app.route('/<path:filename>')
def serve_public_files(filename):
    return send_from_directory(str(app.static_folder), filename)

# Resources (CSS/JS/Images from PROJECT_ROOT/resources/)
@app.route(f'/{RESOURCE_PREFIX}/<path:filename>')
def serve_resources(filename):
    """Serves files from the project root's resources/ directory."""
    try:
        resource_path = os.path.join(PROJECT_ROOT, RESOURCE_PREFIX)
        return send_from_directory(resource_path, filename)
    except FileNotFoundError:
        abort(404)

# Favicon
@app.route('/favicon.ico')
def favicon():

    return serve_resources('favicon.png')

# Logs Page (Requires Auth)
@app.route('/logs')
@requires_auth
def logs_page():
    return render_template(LOGS_TEMPLATE)

# API Endpoints (Requires Auth)
@app.route('/api/logs/<log_file>')
@requires_auth
def api_log_file(log_file):
    """Serves requests.log or errors.log."""
    if log_file not in ['requests.log', 'errors.log']:
        abort(404)
    
    # Serve the file directly from the logs/ directory
    log_path = os.path.join(PROJECT_ROOT, 'logs')
    return send_from_directory(log_path, log_file, mimetype='text/plain')

@app.route('/api/logs/stats')
@requires_auth
def api_log_stats():
    log_type = request.args.get('type', 'requests')
    try:
        current_size = logger.get_log_size(log_type)
        return jsonify({
            'size': current_size, 
            'max_size': logger.MAX_LOG_SIZE
        })
    except Exception as e:
        app.logger.error(f"Failed to fetch log stats: {e}")
        return jsonify({'error': f"Failed to fetch log stats: {e}", 'code': 500}), 500

@app.route('/api/logs/search')
@requires_auth
def api_log_search():
    log_type = request.args.get('type', 'requests')
    search_term = request.args.get('q', '')
    try: 
        results = logger.search_logs(search_term, log_type)
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"Log search failed: {e}")
        return jsonify({'error': f"Log search failed due to an internal error: {e}", 'code': 500}), 500

@app.route('/api/logs/archive', methods=['GET'])
@requires_auth
def api_log_archive():
    log_type = request.args.get('type', 'requests')
    
    try:
        # Get the path to the renamed file
        archive_path, filename = logger.archive_logs(log_type)
        
        if archive_path is None:
             return jsonify({'error': 'Log file not found.'}), 404
        
        return send_file(archive_path, as_attachment=True, download_name=filename)
        
    except Exception as e:
        app.logger.error(f"Log archive failed: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.after_request
def log_all_requests(response):
    """Logs details of every request after it has been processed by the app."""
    try:
        logger.log_flask_request(request, response)
    except Exception as e:
        # Log error but do not crash the request itself
        print(f"CRITICAL: Failed to log request: {e}", file=sys.stderr)
        
    return response

# --- Error Handling ---

# Custom 404 handler
@app.errorhandler(404)
def page_not_found(error):
    logger.log_error_to_file(f"HTTP Error 404 (Not Found): {request.path}")
    try:
        return make_response(app.jinja_env.get_template(ERROR_TEMPLATE).render(
            code=404, message="Not Found"), 404)
    except Exception:
        return make_response("<h1>404 Not Found</h1>", 404)

# Custom 500 handler
@app.errorhandler(500)
def internal_server_error(error):
    logger.log_error_to_file(f"HTTP Error 500 (Internal Server Error): {request.path}")
    try:
        return make_response(app.jinja_env.get_template(ERROR_TEMPLATE).render(
            code=500, message="Internal Server Error"), 500)
    except Exception:
        return make_response("<h1>500 Internal Server Error</h1>", 500)

# --- Main Execution ---

if __name__ == "__main__":
    # Only run locally
    import sys
    try:
        PORT = int(sys.argv[1])
    except (IndexError, ValueError):
        PORT = 1500

    app.run(port=PORT, debug=True)