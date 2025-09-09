This stack uses uses Prometheus for metrics, Loki for logs, and an EC2 instance with Nginx as a gateway to expose the local data sources to the internet for Grafana to access.

# Components

Local stack (managed by Docker Compose)
- Prometheus: A time-series database that scrapes and stores metrics.
- Loki: A log aggregation system designed to be cost-effective and easy to operate.
- Process Exporter: Scrapes metrics from specified processes and exposes them for Prometheus.
- Promtail: The log collection agent that tails log files and pushes them to Loki.

# External components

- Grafana (Remote): The visualization platform.
- AWS EC2 Instance: A public-facing server with a static IP that acts as a gateway.
- Nginx: A reverse proxy running on the EC2 instance to forward traffic.
- Tailscale: A secure VPN connecting the EC2 instance to the AIBOX.

# Recommended standards

Following these standards will make the setup easier.

- **One Log File per Service Instance**: For clear log separation, each distinct service should write to its own uniquely named log file (e.g., `service_A.log`, `service_B.log`). This allows Promtail to easily assign a specific and accurate label to each log stream.
- **Descriptive Process Commands**: Launch the applications with descriptive command-line arguments. Including unique identifiers (like a service name or stream ID) is crucial for process-exporter's regex to dynamically group and label the metrics.
- **Consistent Labeling**: Aim for consistent labels between the metrics and logs. For instance, the groupname in Prometheus should correspond to the service label in Loki where possible.

# Setup

## 1. Configuration
### Clone the repository:

```
git clone https://github.com/gnogueira04/process-monitor
cd process-monitor
```

### Target a process:
Open `process-exporter/config.yml` and add entries for the processes you want to monitor. The following example targets Python services run with uvicorn.

```
process_names:
  - name: '{{.Matches.script_base}}-stream{{.Matches.stream_id}}'
    comm:
      - uvicorn
      - python3.9
    cmdline:
      - '.*uvicorn\s+(?P<script_base>[\w_]+?)_stream(?P<stream_id>\d+).*'
```

### Target a log file:
Open `promtail/promtail.yml` and update the `scrape_configs` to point to your log files. This example targets two different services based on their filenames.

```
scrape_configs:
- job_name: ppl_detection
  static_configs:
  - targets:
      - localhost
    labels:
      service: ppl_detection_double_check
      __path__: /path/to/your/logs/ppl_detection_double_check.log

- job_name: checkdoor
  static_configs:
  - targets:
      - localhost
    labels:
      service: checkdoor_ai_agent_stream05
      __path__: /path/to/your/logs/checkdoor_ai_agent_stream05.log
```

Update the volume mount in `docker-compose.yml` so Promtail can access the log directory.

```
promtail:
  image: grafana/promtail:latest
  container_name: promtail
  command: ["-config.file=/etc/promtail/promtail.yml"]
  ports: 
    - "9080:9080"
  volumes:
    - ./promtail:/etc/promtail
    - /path/to/your/logs:/path/to/your/logs # Update this
  networks:
    - lgtm-net
  restart: unless-stopped
```

### Configuration Explained

This section details how the example configurations for process-exporter and promtail work and how they directly relate to the queries you'll use in Grafana.

#### Process Monitoring (`process-exporter/config.yml`)

The goal of this configuration is to find your running services and group their metrics under a single, meaningful name.

```
process_names:
  - name: '{{.Matches.script_base}}-stream{{.Matches.stream_id}}'
    comm:
      - uvicorn
    cmdline:
      - '.*uvicorn\s+(?P<script_base>[\w_]+?)_stream(?P<stream_id>\d+).*'
```

- The exporter first finds processes whose command name (`comm`) is `uvicorn`. Then, it applies the regular expression to the full command line.
- The expression `(?P<script_base>...)` and `(?P<stream_id>...)` are named capture groups. They find and "capture" the base name of the script and its stream number
- The name template uses the captured parts to build a final name. For a process running as `... uvicorn ppl_detection_double_check_stream02 ...`, the exporter generates the name `ppl_detection_double_check-stream02`. This name becomes the value for the groupname label in Prometheus. This is why the example query works:
  ```
  rate(namedprocess_namegroup_cpu_seconds_total{groupname="ppl_detection_double_check-stream02"}[5m])
  ```

#### Log Collection (`promtail/promtail.yml`)

The goal here is to find all log files for a given service and assign a consistent label to them.

```
scrape_configs:
- job_name: ppl_detection
  static_configs:
  - targets:
      - localhost
    labels:
      service: ppl_detection_double_check
      __path__: /path/to/your/logs/ppl_detection_double_check.log
```

- This configuration uses a simple method of creating one `scrape_configs` block for each service you want to monitor.
- The `__path__` directive tells Promtail where to find the log file.
- The `labels` section statically assigns a `service` label with the value `ppl_detection_double_check` to every single log line that comes from any of the files matched by the path. This makes querying in Grafana extremely simple:
  ```
  {service="ppl_detection_double_check"}
  ```


## 2. Running the stack
### Start the Local Services:
Launch the Prometheus, Loki, Promtail, and process exporter containers.

```
docker compose up -d
```

### Configure the EC2 Gateway:

  1. **Launch EC2 Instance**: In AWS, launch a `t3.micro` instance with an Ubuntu Server 22.04 LTS image.
  2. **Configure Security Group**: Create a security group and add inbound rules to allow traffic on ports `22` (SSH from your IP), `9090` (Prometheus), and `3100` (Loki).
  3. **Assign Elastic IP**: Allocate an Elastic IP and associate it with your EC2 instance. This is your permanent static IP.
  4. **Install Tailscale on EC2**: SSH into your instance and run the following, then authenticate:
     ```
     curl -fsSL https://tailscale.com/install.sh | sh
     sudo tailscale up
     ```
   5. **Verify Connection**: Run tailscale status to get your local machine's Tailscale IP.
   6. **Install Nginx on EC2**:
      ```
      sudo apt update && sudo apt install nginx -y
      ```
   7. **Configure Nginx**: Create a config file sudo nano `/etc/nginx/sites-available/monitoring-proxy` and paste the following, replacing the placeholders:
      ```
      # Forward traffic for Prometheus
      server {
          listen 9090;
          server_name <EC2_ELASTIC_IP>;
      
          location / {
              proxy_pass http://<LOCAL_TAILSCALE_IP>:9090;
          }
      }
      
      # Forward traffic for Loki
      server {
          listen 3100;
          server_name <EC2_ELASTIC_IP>;
      
          location / {
              proxy_pass http://<LOCAL_TAILSCALE_IP>:3100;
          }
      }
      ```
   8. **Enable and Restart Nginx**:
      ```
      sudo ln -s /etc/nginx/sites-available/monitoring-proxy /etc/nginx/sites-enabled/
      sudo systemctl restart nginx
      ```

### Adding a second AIBOX to an existing EC2 gateway

This guide covers the steps to add a second, third, etc.. AIBOX to the existing EC2 reverse proxy setup. 

#### Open new ports in AWS

Your new AIBOX will have services running on the same default ports (9090 for Prometheus, 3100 for Loki). Since the EC2 instance is already using these ports for the first AIBOX (odk04), you must map the new services to different public ports.

In this example, we'll map public port `9091` to AIBOX-2's Prometheus and `3101` to AIBOX-2's Loki.

  1. Navigate to the EC2 Security Group in the AWS Console.
  2. Add the following new inbound rules:
    - Custom TCP (Port `9091`): Source `Anywhere (0.0.0.0/0)` for AIBOX-2's Prometheus.
    - Custom TCP (Port `3101`): Source `Anywhere (0.0.0.0/0)` for AIBOX-2's Loki.

#### Update the nginx configuration

Now, add new rules to the Nginx configuration on the EC2 instance to proxy traffic to the new AIBOX.

  1. SSH into the EC2 instance.
  2. Edit the existing Nginx config file:
     ```
     sudo nano /etc/nginx/sites-available/monitoring-proxy
     ```
  3. Add the following new `server` blocks to the end of the file. Replace the placeholders with your IPs.
     ```
    # --- New services on AIBOX-2 ---
    
    # Forward public port 9091 to AIBOX-2's Prometheus
    server {
        listen 9091;
        server_name <EC2_ELASTIC_IP>;
    
        location / {
            proxy_pass http://<AIBOX_2_TAILSCALE_IP>:9090;
        }
    }
    
    # Forward public port 3101 to AIBOX-2's Loki
    server {
        listen 3101;
        server_name <EC2_ELASTIC_IP>;
    
        location / {
            proxy_pass http://<AIBOX_2_TAILSCALE_IP>:3100;
        }
    }
     ```
  4. Test and restart Nginx:
     ```
     sudo nginx -t
     sudo systemctl restart nginx
     ```

#### Add new data sources in Grafana

Finally, add the new services as separate data sources in the remote Grafana instance.

##### Prometheus (for AIBOX-2):
  1. Navigate to **Connections > Data Sources** and add a new Prometheus source.
  2. For the URL, use the EC2 static IP with the new port: `http://<EC2_ELASTIC_IP>:9091`.
  3. Click Save & Test.

##### Loki (for AIBOX-2)
  1. Add a new Loki data source.
  2. For the URL, use the EC2 static IP with the new port: `http://<EC2_ELASTIC_IP>:3101`.
  3. Click Save & Test.

## 3. Configure Grafana
Log in to the remote Grafana instance.

Navigate to **Connections > Data Sources**.

### Add Prometheus:

1. Select Prometheus.
2. For the URL, use the EC2 static IP: `http://<EC2_ELASTIC_IP>:9090`.
3. Click Save & Test.

### Add Loki:

1. Select Loki.
2. For the URL, use the EC2 static IP: `http://<EC2_ELASTIC_IP>:3100`.
3. Click Save & Test.

## 4. Query the data

### Loki query (Logs):
Use the service label you defined in promtail.yml.

```
{service="ppl_detection_double_check"}
```

### Prometheus query (Metrics):
Query for metrics from the process exporter using the group name you defined. For example, to get CPU usage:

```
rate(namedprocess_namegroup_cpu_seconds_total{groupname="ppl_detection_double_check-stream02"}[5m])
```

## Project structure
```
.
├── docker-compose.yml     # Defines the local services (Prometheus, Loki, etc.)
├── loki/
│   └── loki.yml           # Loki configuration
├── populate_log.sh        # Helper script to generate sample logs
├── process-exporter/
│   └── config.yml         # Defines which processes to monitor for metrics
├── prometheus/
│   └── prometheus.yml     # Prometheus configuration (scrape targets)
└── promtail/
    └── promtail.yml       # Promtail configuration (log file locations)
```
