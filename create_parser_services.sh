#!/bin/bash

# This script automates the creation of csv-parser systemd services
# based on existing checking_stream_quality services.
# It should be run with sudo privileges.

SYSTEMD_PATH="/etc/systemd/system"
BASE_SERVICE_PREFIX="checking_stream_quality_"
NEW_SERVICE_PREFIX="csv-parser_"
PYTHON_SCRIPT_PATH="/root/process-monitor/csv_parser_service.py"
CSV_PATH="/root/aios-checking-stream-quality-services/csvs"
LOG_PATH="/root/process-monitor/logs"
PYTHON_EXECUTABLE="/usr/bin/python3"
WORKING_DIRECTORY="/root"

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Please use sudo."
   exit 1
fi

if [ ! -d "$SYSTEMD_PATH" ]; then
    echo "Error: Systemd directory not found at $SYSTEMD_PATH"
    exit 1
fi

cd "$SYSTEMD_PATH" || { echo "Failed to navigate to $SYSTEMD_PATH"; exit 1; }

echo "Searching for stream quality services in $SYSTEMD_PATH..."

for service_file in ${BASE_SERVICE_PREFIX}stream*.service; do
    if [ ! -f "$service_file" ]; then
        echo "No services found matching the pattern '${BASE_SERVICE_PREFIX}stream*.service'."
        exit 0
    fi

    temp_name=${service_file#${BASE_SERVICE_PREFIX}}
    stream_id=${temp_name%.service}

    echo "Found base service for: $stream_id"

    new_service_file="${NEW_SERVICE_PREFIX}${stream_id}.service"

    echo "Generating new service file: $new_service_file"

    cat << EOF > "$new_service_file"
[Unit]
Description=CSV to JSONL Parser Service for $stream_id
After=${BASE_SERVICE_PREFIX}${stream_id}.service
BindsTo=${BASE_SERVICE_PREFIX}${stream_id}.service

[Service]
Type=simple
ExecStart=${PYTHON_EXECUTABLE} ${PYTHON_SCRIPT_PATH} ${CSV_PATH}/${stream_id}_ilhasprod.csv ${CSV_PATH}/${stream_id}_ilhasprod.jsonl --log-file ${LOG_PATH}/csv_parser_${stream_id}.log
User=root
WorkingDirectory=${WORKING_DIRECTORY}
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=${BASE_SERVICE_PREFIX}${stream_id}.service
EOF

    echo "Successfully created $new_service_file."
    echo "---"
done

echo "Reloading systemd daemon to apply changes..."
systemctl daemon-reload

echo "Script finished successfully."
echo "The systemd daemon has been reloaded."
echo "You may now enable and start the new services as needed. For example:"
echo "sudo systemctl enable --now ${NEW_SERVICE_PREFIX}stream701.service"

