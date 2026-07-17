#!/usr/bin/env bash

set -euo pipefail

# Force UTF-8 encoding and unbuffered output for Python sub-processes
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

log_header() {
    echo "======================================================================"
    echo "  $1"
    echo "======================================================================"
}

log_info() {
    echo "[INFO] $1"
}

# Target file paths
PROM_CONFIG="prometheus.yml"
GRAFANA_DS_PAYLOAD="grafana_datasource.json"

log_header "1. WRITING PROMETHEUS SCRAPE CONFIGURATION"
log_info "Creating $PROM_CONFIG target mappings..."

cat << 'EOF' > "$PROM_CONFIG"
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'sre-fastapi-app'
    metrics_path: '/metrics'
    scrape_interval: 10s
    static_configs:
      - targets: ['localhost:8000']
EOF

log_info "Config created successfully. Contents of $PROM_CONFIG:"
cat "$PROM_CONFIG"
echo ""

log_header "2. SIMULATING CONTAINER INITIALIZATION"
log_info "Docker commands to deploy the monitoring containers:"
echo "  [DOCKER] docker run -d --name prometheus-srv --network=\"host\" -v \$(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus"
echo "  [DOCKER] docker run -d --name grafana-srv -p 3000:3000 grafana/grafana"
echo ""

log_header "3. CONFIGURING GRAFANA DATASOURCE VIA REST API"
log_info "Preparing datasource JSON payload: $GRAFANA_DS_PAYLOAD"

cat << 'EOF' > "$GRAFANA_DS_PAYLOAD"
{
  "name": "prometheus-prod-01",
  "type": "prometheus",
  "url": "http://prometheus-srv:9090",
  "access": "proxy",
  "basicAuth": false,
  "isDefault": true
}
EOF

log_info "Payload created. Simulating REST call to Grafana Admin API..."
echo "  [API] curl -X POST -H 'Content-Type: application/json' -d @$GRAFANA_DS_PAYLOAD http://admin:admin@localhost:3000/api/datasources"
log_info "Response: 200 OK | Message: Datasource 'prometheus-prod-01' added successfully (ID: 1)."
echo ""

log_header "4. LAUNCHING COMBINED OBSERVABILITY SIMULATOR CLI"
log_info "Executing Python interactive simulation..."

# Find the python executable
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "[ERROR] Python 3 was not found in PATH. Cannot run simulation."
        exit 1
    fi
fi

# Run the python script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$PYTHON_CMD" "$SCRIPT_DIR/demo_combined_observability.py"

# Clean up configuration files
log_header "5. POST-DEMO ENVIRONMENT CLEANUP"
log_info "Cleaning up temporary configurations..."
rm -f "$PROM_CONFIG" "$GRAFANA_DS_PAYLOAD"
log_info "Demo simulation complete."
