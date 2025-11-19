#!/bin/bash

# ps -ef | grep 'server.py' | grep -v grep

# constants
LOCAL_PORT=1500
SERVER_PORT=1500

# lightsail details
REMOTE_USER="ec2-user"
REMOTE_HOST="3.129.121.42"
KEY_PATH="PersonalServerKey.pem"
REMOTE_DIR="/home/${REMOTE_USER}/webserver/"

# Local files/directories to deploy (don't use / on dirs)
LOCAL_FILES=(
    "server.py"
    "site"
)

function local_start() {
    echo "Running server locally at localhost:${PORT}"
    python3 server.py ${LOCAL_PORT}
}

function remote_execute() {
    # The -f flag tells ssh to go to the background just before command execution.
    # The -n flag tells ssh to redirect stdin from /dev/null, preventing it from waiting for input.

    if [[ "$1" == *nohup* ]]; then
        # Use -f and -n only for the background start command
        ssh -i "${KEY_PATH}" -f -n "${REMOTE_USER}@${REMOTE_HOST}" "$1"
    else
        # Use standard execution for kill, status, mkdir, etc.
        ssh -i "${KEY_PATH}" "${REMOTE_USER}@${REMOTE_HOST}" "$1"
    fi
}

function server_start() {
    echo "--- Starting Remote Server Deployment ---"    
    # 1. Ensure remote directory exists
    echo "1. Ensuring remote directory exists..."
    remote_execute "mkdir -p ${REMOTE_DIR}"

    # 2. Sync local files to the remote directory
    echo "2. Transferring files with rsync..."
    for FILE in "${LOCAL_FILES[@]}"; do
        # -r: recursive, -a: archive mode, -z: compress, -e: specify remote shell
        rsync -r -a -z -e "ssh -i ${KEY_PATH}" "${FILE}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"
        if [ $? -ne 0 ]; then
            echo "Error: rsync failed for ${FILE}. Aborting."
            exit 1
        fi
    done
    echo "File transfer complete."
    
    # Use pkill on the remote server to stop any running instances of webserver.
    REMOTE_KILL_COMMAND="pkill -f server.py"
    
    # Start the server detached
    # nohup: runs command even if the controlling terminal is closed
    # > /dev/null 2>&1: redirects stdout and stderr to /dev/null (silences output)
    # &: runs the command in the background
    REMOTE_START_COMMAND="cd ${REMOTE_DIR} && nohup python3 server.py ${SERVER_PORT} > /dev/null 2>&1 &"

    echo "Stopping old server and starting new detached server on port ${SERVER_PORT}"
    remote_execute "${REMOTE_KILL_COMMAND}"
    remote_execute "${REMOTE_START_COMMAND}"
    
    echo "--- Remote Server Started! ---"
    echo "Access the site at: http://${REMOTE_HOST}"
}

function server_kill() {
    remote_execute "pkill -f server.py"
}

case "$1" in
    local)
        local_start
        ;;
    server)
        server_start
        ;;
    kill)
        server_kill
        ;;
    *)
        echo "Usage: $0 {local | server | kill }"
        exit 1
esac