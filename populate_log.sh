#!/bin/sh

LOG_FILE="/root/process-monitor/app.log"
LOG_DIR=$(dirname "$LOG_FILE")

if [ "$(id -u)" -ne 0 ]; then
  echo "Error: This script needs to be run with sudo to write to $LOG_DIR"
  echo "Please run it like this: sudo ./log_generator.sh"
  exit 1
fi

if [ ! -d "$LOG_DIR" ]; then
    echo "Directory $LOG_DIR does not exist. Creating it..."
    mkdir -p "$LOG_DIR"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create directory. Aborting."
        exit 1
    fi
    echo "Directory created."
fi

echo "Starting log generator..."
echo "Writing logs to: $LOG_FILE"
echo "Press [Ctrl+C] to stop."

while true; do
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    RAND_SEED=$(date +%N)

    case $((RAND_SEED % 6)) in
        0|1|2) LOG_LEVEL="INFO";;
        3) LOG_LEVEL="WARN";;
        4) LOG_LEVEL="ERROR";;
        5) LOG_LEVEL="DEBUG";;
    esac

    case $((RAND_SEED % 9)) in
        0) MESSAGE="User authenticated successfully";;
        1) MESSAGE="Page loaded in 250ms";;
        2) MESSAGE="Configuration saved to profile";;
        3) MESSAGE="Ad-blocker detected and disabled feature X";;
        4) MESSAGE="Failed to fetch resource: /api/v2/user/settings";;
        5) MESSAGE="GPU process crashed, restarting.";;
        6) MESSAGE="High memory usage detected: 1.5GB";;
        7) MESSAGE="Processing user input for form field 'username'";;
        8) MESSAGE="Cache cleared for site: example.com";;
    esac

    LOG_LINE="$TIMESTAMP [$LOG_LEVEL] - chrome_process[$$]: $MESSAGE"

    echo "$LOG_LINE" >> "$LOG_FILE"
    echo "   Appended: $LOG_LINE"

    sleep $((RAND_SEED % 5 + 1))
done

