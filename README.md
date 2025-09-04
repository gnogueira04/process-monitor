This project uses uses Prometheus for metrics, Loki for logs, and ngrok to expose the local data sources to the internet for Grafana to access.

# Components

Local stack (Managed by Docker Compose)
- Prometheus: A time-series database that scrapes and stores metrics.
- Loki: A log aggregation system designed to be cost-effective and easy to operate.
- Process Exporter: Scrapes metrics from specified processes (by name) and exposes them for Prometheus.
- Promtail: The log collection agent that tails log files and pushes them to Loki.

# External components

- Grafana (Remote): The visualization platform.
- ngrok: A reverse proxy service that creates a secure tunnel from your local machine to the public internet.

# Setup

## Prerequisites
- Docker & Docker Compose: To run the local services.
- An ngrok account: Sign up at ngrok.com to get an authtoken.
- A remote Grafana instance: A Grafana Cloud account or a self-hosted Grafana.

## 1. Configuration
### Clone the repository:

```
git clone https://github.com/gnogueira04/process-monitor
cd process-monitor
```

### Target a process:
Open `process-exporter/config.yml` and change chrome to the name of the process you want to monitor.

```
process_names:
  - comm:
    - your_process_name # e.g., node, python, etc.

Target a Log File (Logs):
Open promtail/promtail.yml and update the __path__ to point to the log file of your target process. Also, update the job label to something descriptive.

scrape_configs:
- job_name: my_app_logs # Change this
  static_configs:
  - targets:
      - localhost
    labels:
      job: my_app # This label will be used in Grafana
      __path__: /path/to/your/app.log # IMPORTANT: Update this path
```

### Configure ngrok:

Open ngrok.yml and ensure the ports for prometheus (9090) and loki (3100) are correct.

Add your ngrok authtoken. You can either paste it into the ngrok.yml file or add it globally with the command:

```
ngrok config add-authtoken <YOUR_AUTHTOKEN>
```

## 2. Running the stack
### Start the Local Services:
Launch the Prometheus, Loki, Promtail, and process exporter containers.

```
docker compose up -d
```

### Start ngrok tunnel:
In a separate terminal, run ngrok to create the public URLs for Prometheus and Loki.

```
ngrok start --all
```

ngrok will display the forwarding URLs. Keep this terminal open.

## 3. Configure Grafana
Log in to your remote Grafana instance.

Navigate to Connections > Data Sources.

### Add Prometheus:

1. Select Prometheus.

2. For the URL, use the `https-` forwarding URL for Prometheus from your ngrok terminal.

3. Click Save & Test.

### Add Loki:

1. Select Loki.

2. For the URL, use the `https-` forwarding URL for Loki from your ngrok terminal.

3. Click Save & Test.

## 4. Query the data

### Loki query (Logs):
Use the job label you defined in `promtail.yml`.

```
{job="my_app"}
```

### Prometheus query (Metrics):
Query for metrics from the process exporter. For example, to get CPU usage:

```
rate(namedprocess_namegroup_cpu_seconds_total{groupname="your_process_name"}[5m])
```

## Project structure
```
.
├── docker-compose.yml     # Defines the local services (Prometheus, Loki, etc.)
├── loki/
│   └── loki.yml           # Loki configuration
├── ngrok/
│   └── ngrok.yml          # ngrok configuration to define the tunnels
├── populate_log.sh        # Helper script to generate sample logs
├── process-exporter/
│   └── config.yml         # Defines which processes to monitor for metrics
├── prometheus/
│   └── prometheus.yml     # Prometheus configuration (scrape targets)
└── promtail/
    └── promtail.yml       # Promtail configuration (log file locations)
```
