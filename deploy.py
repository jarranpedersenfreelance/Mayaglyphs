import subprocess
import sys
import argparse
import time
import signal
import zipfile
import os
import shutil
from dotenv import load_dotenv
import urllib.request
import urllib.error

# --- Configuration Constants ---
LOCAL_PORT = 1500
SERVER_PORT = 1500
ACCESS_PORT = 80

REMOTE_USER = "ec2-user"
REMOTE_HOST = "3.129.121.42"
KEY_PATH = "PersonalServerKey.pem"
REMOTE_DIR = f"/home/{REMOTE_USER}/"
REMOTE_SITE_DIR = f"/home/{REMOTE_USER}/site/"
LOCAL_SITE_DIR = "site"

# Webserver Files/Folders to sync
LOCAL_FILES = [
    "requirements.txt", 
    "server",
    "resources",
    "admin_pages"
]

load_dotenv()
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

# --- Helper Functions ---

def run_command(command, shell=False, suppress_output=False):
    """Runs a subprocess command."""
    try:
        subprocess.run(command, check=True, shell=shell, 
                       stdout=subprocess.DEVNULL if suppress_output else None)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        sys.exit(1)

def get_ssh_base_cmd():
    """Returns the base SSH command list with key."""
    return ["ssh", "-i", KEY_PATH, f"{REMOTE_USER}@{REMOTE_HOST}"]

def sigint_handler(signal, frame):
    """Handles the SIGINT signal (Ctrl-C) gracefully."""
    print("\n\nCaught Ctrl-C. Shutting down...")
    local_kill()
    sys.exit(0)

def check_health():
    """Tries to connect to the server. """
    url = f"http://{REMOTE_HOST}:{ACCESS_PORT}"
    print(f"Ping check: {url} ...")
    
    attempts = 2
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    print("Server is up and responding!")
                    return True
        except (urllib.error.URLError, ConnectionResetError):
            print(f"   Attempt {i+1}/{attempts}: Server not ready yet...")
            time.sleep(2)
            
    return False

def ensure_local_venv():
    """Checks if local venv exists, creates if not."""
    if not os.path.exists(".venv"):
        print("Creating local virtual environment (.venv)...")
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
    return os.path.join(".venv", "bin", "python"), os.path.join(".venv", "bin", "pip")

def install_requirements(remote=False, venv_pip=None):
    """Installs dependencies from requirements.txt locally or remotely."""
    print("Installing dependencies from requirements.txt")
    
    if remote:
        ssh_cmd = get_ssh_base_cmd()
        remote_cmds = (
            "if [ ! -d '.venv' ]; then python3 -m venv .venv; fi && "
            ".venv/bin/pip install -r requirements.txt"
        )
        ssh_cmd.append(remote_cmds)
        run_command(ssh_cmd)
        print("Remote requirements installed.")
    else:
        if not venv_pip:
            _, venv_pip = ensure_local_venv()
            
        command = [venv_pip, "install", "-r", "requirements.txt"]
        subprocess.run(command, check=False)
        print("Local requirements installed.")

# --- Command Functions ---

def local_start():
    """Starts the server locally."""
    print(f"--- Running server locally at localhost:{LOCAL_PORT} ---")
    signal.signal(signal.SIGINT, sigint_handler)
    venv_python, venv_pip = ensure_local_venv()
    install_requirements(remote=False, venv_pip=venv_pip)
    local_kill()
    print("Starting local server...")
    run_command([venv_python, "server/server.py", str(LOCAL_PORT)])

def server_kill():
    print("Stopping old server...")
    ssh_cmd = get_ssh_base_cmd()
    ssh_cmd.append("pkill -f server.py")
    subprocess.run(ssh_cmd, stderr=subprocess.DEVNULL)

def local_kill():
    print("Stopping old server...")
    ssh_cmd = get_ssh_base_cmd()
    subprocess.run(['pkill', '-f', 'server.py'], stderr=subprocess.DEVNULL)

def server_deploy():
    """Syncs files and restarts the remote server."""
    print("--- Starting Remote Server Deployment ---")

    # Ensure remote directory exists
    print("Ensuring remote directory exists...")
    ssh_cmd = get_ssh_base_cmd()
    ssh_cmd.append(f"mkdir -p {REMOTE_DIR}")
    run_command(ssh_cmd)

    # Sync local files via rsync
    print("Transferring files with rsync...")
    for file_name in LOCAL_FILES:
        # Construct rsync command
        # -e specifies the ssh command to use (with key)
        # Add --delete to delete files on server that are delete locally (will also delete other files)
        rsync_cmd = [
            "rsync", "-r", "-a", "-z",
            "-e", f"ssh -i {KEY_PATH}",
            file_name,
            f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}"
        ]
        run_command(rsync_cmd)
    
    print("File transfer complete.")

    install_requirements(remote=True)
    server_kill()
    print(f"Starting server...")

    remote_execution = (
        f"cd {REMOTE_DIR} && "
        f"ADMIN_USER='{ADMIN_USER}' ADMIN_PASS='{ADMIN_PASS}' "
        f"nohup .venv/bin/python server/server.py {SERVER_PORT} > /dev/null 2>&1 &"
    )
    
    final_ssh_cmd = ["ssh", "-i", KEY_PATH, "-f", "-n", 
                     f"{REMOTE_USER}@{REMOTE_HOST}", remote_execution]
    
    run_command(final_ssh_cmd)

    print("--- Remote Server Started! ---")
    print(f"Access the site at: http://{REMOTE_HOST}")

def deploy_site_local(zip_file_path):
    """Extracts the contents of a specified zip file into the local site/ directory."""
    if not os.path.exists(zip_file_path):
        print(f"Error: Zip file not found at {zip_file_path}")
        sys.exit(1)
        
    print(f"Extracting {zip_file_path} contents to local '{LOCAL_SITE_DIR}' directory")

    # Delete current contents
    if os.path.exists(LOCAL_SITE_DIR):
        print(f"Deleting existing local '{LOCAL_SITE_DIR}' directory...")
        shutil.rmtree(LOCAL_SITE_DIR)
    os.makedirs(LOCAL_SITE_DIR, exist_ok=False)
    
    try:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(LOCAL_SITE_DIR)
        print("Extraction successful.")
    except Exception as e:
        print(f"Error during local extraction: {e}")
        sys.exit(1)

def deploy_site_remote(zip_file_path):
    """Transfers the specified zip file to the remote server and extracts its contents into site/"""
    if not os.path.exists(zip_file_path):
        print(f"Error: Zip file not found at {zip_file_path}")
        sys.exit(1)

    remote_temp_path = os.path.join(REMOTE_DIR, os.path.basename(zip_file_path))
    
    print(f"Deploying {zip_file_path} to remote server and extracting to {REMOTE_SITE_DIR}")

    # Transfer the ZIP file using rsync
    print("Transferring zip file...")
    rsync_cmd = [
        "rsync", "-a", "-z",
        "-e", f"ssh -i {KEY_PATH}",
        zip_file_path,
        f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}"
    ]
    run_command(rsync_cmd)
    
    # Execute remote commands
    print("Extracting contents remotely...")
    remote_commands = (
        # Delete current contents
        f"rm -rf {REMOTE_SITE_DIR} && "
        # Ensure the 'site' extraction directory exists
        f"mkdir -p {REMOTE_SITE_DIR} && "
        # Unzip the temporary file into the 'site' directory, overwriting existing files
        f"unzip -o {remote_temp_path} -d {REMOTE_SITE_DIR} && "
        # Clean up the temporary zip file
        f"rm {remote_temp_path}"
    )
    ssh_cmd = get_ssh_base_cmd()
    ssh_cmd.append(remote_commands)
    run_command(ssh_cmd)

    print("Remote site deployment complete.")

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Deployment Script")
    
    # Use subparser for complex command handling
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Standard Commands (no extra arguments)
    subparsers.add_parser("local", help="Run server locally.")
    subparsers.add_parser("server", help="Deploy and restart remote server.")
    subparsers.add_parser("kill", help="Stop remote server.")
    
    # local-site
    parser_local_site = subparsers.add_parser("local-site", help="Extract specified ZIP file contents into local 'site' directory.")
    parser_local_site.add_argument("zip_file_path", help="Path to the ZIP file.")

    # server-site
    parser_server_site = subparsers.add_parser("server-site", help="Transfer specified ZIP file to remote and extract into remote 'site' directory.")
    parser_server_site.add_argument("zip_file_path", help="Path to the ZIP file.")


    args = parser.parse_args()

    # Execution logic based on action
    if args.action == "local":
        local_start()
    elif args.action == "server":
        server_deploy()
    elif args.action == "kill":
        server_kill()
    elif args.action == "local-site":
        deploy_site_local(args.zip_file_path)
    elif args.action == "server-site":
        deploy_site_remote(args.zip_file_path)

if __name__ == "__main__":
    main()