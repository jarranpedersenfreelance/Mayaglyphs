import subprocess
import sys
import argparse
import time
import signal
import urllib.request
import urllib.error

# --- Configuration Constants ---
LOCAL_PORT = 1500
SERVER_PORT = 1500
ACCESS_PORT = 80

REMOTE_USER = "ec2-user"
REMOTE_HOST = "3.129.121.42"
KEY_PATH = "PersonalServerKey.pem"
REMOTE_DIR = f"/home/{REMOTE_USER}/webserver/"

# Files/Folders to sync
LOCAL_FILES = ["server.py", "site"]

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

def print_remote_logs():
    """Reads the server.log file from the remote machine."""
    print("\nFETCHING REMOTE SERVER LOGS (Last 20 lines)")
    ssh_cmd = get_ssh_base_cmd()
    ssh_cmd.append(f"tail -n 20 {REMOTE_DIR}server.log")
    subprocess.run(ssh_cmd)

def local_start():
    """Starts the server locally."""
    print(f"--- Running server locally at localhost:{LOCAL_PORT} ---")
    signal.signal(signal.SIGINT, sigint_handler)
    # using sys.executable ensures we use the same python env running this script
    run_command([sys.executable, "server.py", str(LOCAL_PORT)])

def server_kill():
    print("Stopping old server...")
    ssh_cmd = get_ssh_base_cmd()
    ssh_cmd.append("pkill -f server.py")
    subprocess.run(ssh_cmd, stderr=subprocess.DEVNULL)

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

    # Stop old server
    server_kill()

    print(f"Starting server...")
    # Use nohup and redirects to ensure it runs in background 
    remote_execution = f"cd {REMOTE_DIR} && nohup python3 server.py {SERVER_PORT} > server.log 2>&1 &"
    
    # Use -f -n flags for SSH to tell it to go to background instantly
    final_ssh_cmd = ["ssh", "-i", KEY_PATH, "-f", "-n", 
                     f"{REMOTE_USER}@{REMOTE_HOST}", remote_execution]
    
    run_command(final_ssh_cmd)

    print("--- Remote Server Started! ---")
    print(f"Access the site at: http://{REMOTE_HOST}")

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Deployment Script")
    parser.add_argument("action", choices=["local", "server", "kill"], 
                        help="Action to perform: local (run locally), server (deploy), or kill (stop remote)")

    args = parser.parse_args()

    if args.action == "local":
        local_start()
    elif args.action == "server":
        server_deploy()
    elif args.action == "kill":
        server_kill()

if __name__ == "__main__":
    main()