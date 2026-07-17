#!/usr/bin/env python3
# This script operates in HYBRID mode:
# 1. If Azure CLI is logged in and a local Prometheus server is running, it queries
#    real Azure Activity Logs, Resource Health, and live PromQL metrics.
# 2. Otherwise, it falls back to a realistic local simulation.

import json
import sys
import subprocess
import urllib.request
import urllib.parse
import os
import platform
from datetime import datetime, timedelta, timezone

# Enable VT100 virtual terminal processing and UTF-8 encoding on Windows shells
if platform.system() == "Windows":
    os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# ANSI color codes for rich formatting
CYAN = "\033[0;36m"
YELLOW = "\033[1;33m"
GREEN = "\033[0;32m"
RED = "\033[0;31m"
MAGENTA = "\033[0;35m"
NC = "\033[0m"

RG_NAME = "rg-monitoring-prod-eastus-01"
VM_NAME = "vm-appserver-prod-01"
PROM_URL = "http://localhost:9090"

# --- 1. Simulated Telemetry Database (Offline Fallback) ---
TIME_BASELINE = datetime(2026, 6, 8, 12, 0, 0)

MOCK_ACTIVITY_LOGS = [
    {
        "eventTimestamp": "2026-06-08T12:00:00Z",
        "operationName": "Microsoft.Network/networkSecurityGroups/write",
        "status": "Succeeded",
        "caller": "net-admin@company.com",
        "description": "Updated NSG rules, added Rule Priority 150: Deny Inbound TCP Port 8000 (FastAPI Service) from Any"
    },
    {
        "eventTimestamp": "2026-06-08T12:10:00Z",
        "operationName": "Microsoft.Compute/virtualMachines/restart/action",
        "status": "Started",
        "caller": "sre-oncall@company.com",
        "description": "Initiated guest reboot as containment mitigation step."
    },
    {
        "eventTimestamp": "2026-06-08T12:15:00Z",
        "operationName": "Microsoft.Network/networkSecurityGroups/write",
        "status": "Succeeded",
        "caller": "sre-oncall@company.com",
        "description": "Reverted Rule Priority 150 (Removed Deny Inbound TCP Port 8000)."
    }
]

MOCK_RESOURCE_HEALTH = [
    {"timestamp": "2026-06-08T11:50:00Z", "status": "Available", "summary": "Resource is healthy and responding to management heartbeats."},
    {"timestamp": "2026-06-08T12:05:00Z", "status": "Unavailable", "summary": "VM is not responding to connection requests. Hypervisor heartbeat lost."},
    {"timestamp": "2026-06-08T12:18:00Z", "status": "Available", "summary": "Resource health recovered."}
]

MOCK_METRICS_TIMELINE = {
    "2026-06-08T12:00:00Z": {"up": 1.0, "http_requests_rate_5m": 45.8, "vm_cpu_utilization": 14.2},
    "2026-06-08T12:05:00Z": {"up": 0.0, "http_requests_rate_5m": 0.0, "vm_cpu_utilization": 95.8},
    "2026-06-08T12:10:00Z": {"up": 0.0, "http_requests_rate_5m": 0.0, "vm_cpu_utilization": 0.0},
    "2026-06-08T12:15:00Z": {"up": 0.0, "http_requests_rate_5m": 0.0, "vm_cpu_utilization": 15.0},
    "2026-06-08T12:20:00Z": {"up": 1.0, "http_requests_rate_5m": 48.2, "vm_cpu_utilization": 18.5},
    "2026-06-08T12:25:00Z": {"up": 1.0, "http_requests_rate_5m": 45.9, "vm_cpu_utilization": 13.8}
}

# --- 2. Hybrid Environment Checks ---
def is_azure_logged_in():
    try:
        res = subprocess.run(["az", "account", "show", "--query", "id", "-o", "tsv"], capture_output=True, text=True, check=False, timeout=5)
        return res.returncode == 0 and bool(res.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def is_prometheus_running():
    try:
        url = f"{PROM_URL}/api/v1/query?query=up"
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False

def print_banner(title):
    print(f"\n{CYAN}======================================================================{NC}")
    print(f"{YELLOW}  {title}{NC}")
    print(f"{CYAN}======================================================================{NC}")

def render_ascii_chart(label, times_and_vals, is_binary=False):
    print(f"\n{MAGENTA}[VISUALIZATION] Metric Panel: {label}{NC}")
    print("-" * 65)
    
    values = [val for _, val in times_and_vals]
    max_val = max(values) if values else 1
    
    for t_str, v in times_and_vals:
        # Format time to HH:MM:SS
        if "T" in t_str:
            time_display = t_str.split("T")[1][:8]
        else:
            time_display = t_str
            
        if is_binary:
            bar = "====================" if v == 1.0 else ""
            status_text = "UP (1)" if v == 1.0 else f"{RED}DOWN (0){NC}"
            print(f"  {time_display} | {status_text:<15} {bar}")
        else:
            bar_len = int((v / max_val) * 25) if max_val > 0 else 0
            bar = "#" * bar_len
            print(f"  {time_display} | {v:>8.1f} | {bar}")
    print("-" * 65)

# --- 3. Option 1: View Raw Metrics Scrape (Friday) ---
def view_raw_metrics():
    print_banner("OPTION 1: PROMETHEUS /METRICS PLAIN-TEXT SCRAPE ENDPOINT")
    
    # Try fetching metrics directly from a running local endpoint first
    fetched_live = False
    for port in [8000, 9090]:
        try:
            url = f"http://localhost:{port}/metrics"
            with urllib.request.urlopen(url, timeout=1) as response:
                content = response.read().decode("utf-8")
                print(f"{GREEN}[LIVE SCRAPE] Successfully retrieved live metrics from: {url}{NC}\n")
                # Print first 25 lines of the live scrape for classroom display
                lines = content.splitlines()
                for line in lines[:25]:
                    print(line)
                if len(lines) > 25:
                    print("... (truncated)")
                fetched_live = True
                break
        except Exception:
            continue
            
    if not fetched_live:
        print(f"{YELLOW}[OFFLINE SIMULATION] Showing template Prometheus plain-text scrape payload:{NC}\n")
        print(f"{GREEN}# HELP up Status of the target scrape. 1 = reachable, 0 = unreachable.{NC}")
        print(f"{GREEN}# TYPE up gauge{NC}")
        print('up{instance="vm-appserver-prod-01:8000",job="sre-fastapi-app"} 1.0\n')
        print(f"{GREEN}# HELP http_requests_total Total number of HTTP requests processed by the application.{NC}")
        print(f"{GREEN}# TYPE http_requests_total counter{NC}")
        print('http_requests_total{instance="vm-appserver-prod-01:8000",job="sre-fastapi-app",method="GET",status="200"} 1515.0')
        print('http_requests_total{instance="vm-appserver-prod-01:8000",job="sre-fastapi-app",method="POST",status="201"} 112.0')
        print('http_requests_total{instance="vm-appserver-prod-01:8000",job="sre-fastapi-app",method="GET",status="500"} 24.0\n')
        print(f"{GREEN}# HELP vm_cpu_utilization Percentage CPU utilization of the host virtual machine.{NC}")
        print(f"{GREEN}# TYPE vm_cpu_utilization gauge{NC}")
        print('vm_cpu_utilization{instance="vm-appserver-prod-01:8000",job="sre-fastapi-app"} 13.8\n')
        print(f"{GREEN}# HELP vm_memory_active_bytes Active memory on the VM in bytes.{NC}")
        print(f"{GREEN}# TYPE vm_memory_active_bytes gauge{NC}")
        print('vm_memory_active_bytes{instance="vm-appserver-prod-01:8000",job="sre-fastapi-app"} 3459114240.0')

# --- 4. Option 2: PromQL Query Engine (Friday) ---
def run_promql_query():
    print_banner("OPTION 2: PROMQL QUERY ENGINE")
    print("Available PromQL queries:")
    print("  1. up{job=\"sre-fastapi-app\"}")
    print("  2. rate(http_requests_total[5m])")
    print("  3. vm_cpu_utilization")
    
    choice = input("\nSelect PromQL expression (1-3): ").strip()
    
    query_map = {
        "1": ("up{job=\"sre-fastapi-app\"}", True),
        "2": ("rate(http_requests_total[5m])", False),
        "3": ("vm_cpu_utilization", False)
    }
    
    if choice not in query_map:
        print(f"{RED}Invalid selection.{NC}")
        return
        
    query_expr, is_binary = query_map[choice]
    
    if is_prometheus_running():
        print(f"\n{GREEN}[LIVE PROMQL] Connecting to local Prometheus server at: {PROM_URL}{NC}")
        print(f"{CYAN}[PROMQL] Executing: {query_expr}{NC}")
        
        # Query a 25-minute range dynamically from Prometheus TSDB
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        start_epoch = now_epoch - 1500  # 25 minutes ago
        
        url = f"{PROM_URL}/api/v1/query_range?query={urllib.parse.quote(query_expr)}&start={start_epoch}&end={now_epoch}&step=300s"
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
                results = payload.get("data", {}).get("result", [])
                
                if not results:
                    print(f"{YELLOW}[INFO] Query returned no active timeseries. Target VM might be stopped.{NC}")
                    return
                    
                times_and_vals = []
                # Collect timestamps and values from range vectors
                for val_pair in results[0]["values"]:
                    epoch_time = float(val_pair[0])
                    val = float(val_pair[1])
                    dt = datetime.fromtimestamp(epoch_time).strftime("%H:%M:%S")
                    times_and_vals.append((dt, val))
                    
                render_ascii_chart(query_expr, times_and_vals, is_binary=is_binary)
        except Exception as e:
            print(f"{RED}[ERROR] Failed to fetch range metrics from Prometheus API: {e}{NC}")
    else:
        # Fall back to offline simulation
        print(f"\n{YELLOW}[OFFLINE SIMULATION] Simulating PromQL evaluation for: {query_expr}{NC}")
        timestamps = sorted(MOCK_METRICS_TIMELINE.keys())
        
        metric_key = {
            "1": "up",
            "2": "http_requests_rate_5m",
            "3": "vm_cpu_utilization"
        }[choice]
        
        times_and_vals = [(t, MOCK_METRICS_TIMELINE[t][metric_key]) for t in timestamps]
        render_ascii_chart(query_expr, times_and_vals, is_binary=is_binary)

# --- 5. Option 3: Audit Azure Activity Logs & Resource Health (Thursday) ---
def get_azure_logs_live():
    print(f"{GREEN}[LIVE AZURE] Querying Azure Resource Provider APIs...{NC}")
    
    # 1. Fetch Activity Logs
    activity_cmd = [
        "az", "monitor", "activity-log", "list",
        "--resource-group", RG_NAME,
        "--offset", "4h",
        "--query", "[].{eventTimestamp:eventTimestamp, caller:caller, operationName:operationName.value, status:status.value, description:description}",
        "-o", "json"
    ]
    activity_logs = []
    try:
        res = subprocess.run(activity_cmd, capture_output=True, text=True, check=False, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            activity_logs = json.loads(res.stdout)
        else:
            print(f"{YELLOW}[WARNING] Could not retrieve Activity Logs. Resource Group '{RG_NAME}' may not exist yet.{NC}")
    except subprocess.TimeoutExpired:
        print(f"{RED}[ERROR] Activity Logs query timed out (Azure API connection took too long).{NC}")
    except Exception as e:
         print(f"{RED}[ERROR] Activity Logs query failed: {e}{NC}")

    # 2. Fetch Resource Health via REST API (No extensions required)
    vm_id_cmd = [
        "az", "vm", "show",
        "-g", RG_NAME,
        "-n", VM_NAME,
        "--query", "id",
        "-o", "tsv"
    ]
    health_info = None
    try:
        vm_res = subprocess.run(vm_id_cmd, capture_output=True, text=True, check=False, timeout=5)
        if vm_res.returncode == 0 and vm_res.stdout.strip():
            vm_id = vm_res.stdout.strip().replace("\r", "")
            health_uri = f"{vm_id}/providers/Microsoft.ResourceHealth/availabilityStatuses/current?api-version=2020-05-01"
            health_cmd = [
                "az", "rest",
                "--method", "get",
                "--uri", health_uri,
                "--query", "{status:properties.availabilityState, summary:properties.summary}",
                "-o", "json"
            ]
            res = subprocess.run(health_cmd, capture_output=True, text=True, check=False, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                health_info = json.loads(res.stdout)
    except subprocess.TimeoutExpired:
        print(f"{RED}[ERROR] Resource Health query timed out.{NC}")
    except Exception:
        pass

    return activity_logs, health_info

def audit_azure_logs():
    print_banner("OPTION 3: AUDITING AZURE ACTIVITY LOGS & RESOURCE HEALTH")
    
    if is_azure_logged_in():
        activity_logs, health_info = get_azure_logs_live()
        
        print(f"\n{YELLOW}--- Live Azure Activity Logs (Last 4 Hours) ---{NC}")
        if activity_logs:
            for log in activity_logs[:10]: # Print latest 10 logs
                ts = log.get("eventTimestamp", "UNKNOWN")
                caller = log.get("caller", "SYSTEM")
                op = log.get("operationName", "UNKNOWN")
                status = log.get("status", "UNKNOWN")
                desc = log.get("description", "No details provided.")
                print(f"[{ts}] | {caller} | {op} - Status: {status}")
                print(f"    Details : {desc}\n")
        else:
            print("  (No logs returned. Ensure infrastructure has been deployed.)")

        print(f"{YELLOW}--- Live Azure Resource Health Event ---{NC}")
        if health_info:
            status = health_info.get("status", "Unknown")
            color = GREEN if status == "Available" else RED
            print(f"Target Resource : {VM_NAME}")
            print(f"Current Health  : {color}{status}{NC}")
            print(f"Summary Details : {health_info.get('summary', 'No summary details.')}")
        else:
            print("  (Unable to retrieve Resource Health status.)")
    else:
        print(f"{YELLOW}[OFFLINE SIMULATION] Showing simulated incident logs database:{NC}")
        
        print(f"\n{YELLOW}--- Simulated Azure Activity Logs (Control-Plane Operations) ---{NC}")
        for log in MOCK_ACTIVITY_LOGS:
            print(f"[{log['eventTimestamp']}] | {log['caller']} | {log['operationName']} - Status: {log['status']}")
            print(f"    Details : {log['description']}\n")

        print(f"{YELLOW}--- Simulated Azure Resource Health Events (Platform Status) ---{NC}")
        for health in MOCK_RESOURCE_HEALTH:
            color = GREEN if health["status"] == "Available" else RED
            print(f"[{health['timestamp']}] | Status: {color}{health['status']:<12}{NC} | {health['summary']}")

# --- 6. Option 4: E2E Telemetry Correlation & Automated RCA ---
def run_telemetry_rca():
    print_banner("OPTION 4: AUTOMATED CROSS-TELEMETRY CORRELATION & RCA")
    
    # 1. Fetch data based on environment
    live_active = False
    if is_azure_logged_in() and is_prometheus_running():
        # Attempt live correlation
        try:
            activity_logs, health_info = get_azure_logs_live()
            # Fetch target UP vector from Prometheus API
            now_epoch = int(datetime.now(timezone.utc).timestamp())
            start_epoch = now_epoch - 1800 # last 30 minutes
            url = f"{PROM_URL}/api/v1/query_range?query=up{{job=\"sre-fastapi-app\"}}&start={start_epoch}&end={now_epoch}&step=60s"
            
            with urllib.request.urlopen(url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
                results = payload.get("data", {}).get("result", [])
                
                if results and activity_logs:
                    print(f"\n{GREEN}[CORRELATION ENGINE] Running live cross-telemetry analyzer...{NC}")
                    live_active = True
                    
                    # Scan for when target status went down
                    outage_onset_epoch = None
                    for val_pair in results[0]["values"]:
                        if float(val_pair[1]) == 0.0:
                            outage_onset_epoch = float(val_pair[0])
                            break
                            
                    if not outage_onset_epoch:
                        print(f"{GREEN}[SUCCESS] Live Prometheus metrics confirm all targets are currently healthy.{NC}")
                        return
                        
                    outage_onset_dt = datetime.fromtimestamp(outage_onset_epoch)
                    outage_onset_str = outage_onset_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    print(f"{RED}[ANOMALY] Live metrics scrape failure (up=0) detected starting at: {outage_onset_str}{NC}")
                    
                    # Corelate with resource health status
                    if health_info:
                        print(f"{RED}[CORRELATION] Resource Health is currently reporting: '{health_info.get('status')}'{NC}")
                        print(f"              Details: {health_info.get('summary')}")
                        
                    # Find Activity logs preceding the metric drop
                    print(f"\n{CYAN}[RCA SEARCH] Auditing Activity Log writes preceding: {outage_onset_str}...{NC}")
                    triggering_event = None
                    for log in activity_logs:
                        log_time_str = log.get("eventTimestamp")
                        if not log_time_str:
                            continue
                        try:
                            # Strip milliseconds and Z for parsing
                            parsed_ts = log_time_str.split(".")[0].replace("Z", "")
                            log_dt = datetime.strptime(parsed_ts, "%Y-%m-%dT%H:%M:%S")
                            if log_dt <= outage_onset_dt and "/write" in log.get("operationName", "").lower():
                                triggering_event = log
                                break
                        except Exception:
                            continue
                            
                    if triggering_event:
                        print(f"{YELLOW}[ROOT CAUSE] Correlating control-plane edit isolated:{NC}")
                        print(f"  Time of Action : {triggering_event['eventTimestamp']}")
                        print(f"  Caller Identity: {triggering_event['caller']}")
                        print(f"  API Operation  : {triggering_event['operationName']}")
                        print(f"  Action Details : {triggering_event['description']}")
                    else:
                        print(f"{YELLOW}[INFO] No preceding control-plane updates found. Check for OS-level crashes.{NC}")
                    
                    print(f"\n{CYAN}[MITIGATION AUDIT] Evaluating SRE triage operations...{NC}")
                    for log in activity_logs:
                        log_time_str = log.get("eventTimestamp")
                        if not log_time_str:
                            continue
                        try:
                            parsed_ts = log_time_str.split(".")[0].replace("Z", "")
                            log_dt = datetime.strptime(parsed_ts, "%Y-%m-%dT%H:%M:%S")
                            if log_dt > outage_onset_dt:
                                op_name = log.get("operationName", "").lower()
                                desc = log.get("description", "")
                                if "restart" in op_name:
                                    print(f"  - {log_time_str}: VM Reboot triggered -> {RED}INEFFECTIVEMITIGATION{NC}")
                                    print("    (Reason: VM reboots do not override hypervisor-level network security blocks.)")
                                elif "write" in op_name and ("revert" in desc.lower() or "delete" in desc.lower() or "remove" in desc.lower()):
                                    print(f"  - {log_time_str}: NSG rule reverted/removed -> {GREEN}EFFECTIVE MITIGATION{NC}")
                                    print("    (Reason: Restores inbound routing paths on TCP Port 8000.)")
                        except Exception:
                            continue
                    return
        except Exception as e:
            print(f"{RED}[ERROR] Live correlation failed: {e}. Falling back to simulated logs.{NC}")

    if not live_active:
        # Simulated Correlation output
        print(f"{YELLOW}[OFFLINE SIMULATION] Performing correlation on simulated dataset...{NC}")
        print(f"{CYAN}[STEP 1] Scanning Prometheus Metrics telemetry for anomalies...{NC}")
        timestamps = sorted(MOCK_METRICS_TIMELINE.keys())
        outage_onset = None
        
        for t in timestamps:
            if MOCK_METRICS_TIMELINE[t]["up"] == 0.0:
                outage_onset = t
                break
                
        if not outage_onset:
            print(f"{GREEN}[SUCCESS] No metric anomalies detected. All targets are UP.{NC}")
            return
            
        print(f"{RED}[ANOMALY] Prometheus target scrape failure (up=0) detected starting at: {outage_onset}{NC}")

        print(f"\n{CYAN}[STEP 2] Correlating with Azure Resource Health status...{NC}")
        matching_health = None
        for health in MOCK_RESOURCE_HEALTH:
            if health["timestamp"] == outage_onset:
                matching_health = health
                break
        
        if matching_health:
            print(f"{RED}[CORRELATION] Resource Health transitions to '{matching_health['status']}' at {matching_health['timestamp']}{NC}")
            print(f"              Details: {matching_health['summary']}")

        print(f"\n{CYAN}[STEP 3] Auditing Azure Activity Logs for preceding control-plane edits...{NC}")
        onset_dt = datetime.strptime(outage_onset, "%Y-%m-%dT%H:%M:%SZ")
        
        triggering_event = None
        for log in MOCK_ACTIVITY_LOGS:
            log_dt = datetime.strptime(log["eventTimestamp"], "%Y-%m-%dT%H:%M:%SZ")
            if log_dt <= onset_dt and log["operationName"].endswith("/write"):
                triggering_event = log
                
        if triggering_event:
            print(f"{YELLOW}[CORRELATION] Triggering event identified within preceding window:{NC}")
            print(f"  Timestamp    : {triggering_event['eventTimestamp']}")
            print(f"  Caller       : {triggering_event['caller']}")
            print(f"  Action       : {triggering_event['operationName']}")
            print(f"  Description  : {triggering_event['description']}")

        print(f"\n{CYAN}[STEP 4] Analyzing Mitigations & Resolution Timeline...{NC}")
        for log in MOCK_ACTIVITY_LOGS:
            log_dt = datetime.strptime(log["eventTimestamp"], "%Y-%m-%dT%H:%M:%SZ")
            if log_dt > onset_dt:
                if "restart" in log["operationName"]:
                    print(f"  - {log['eventTimestamp']}: VM Reboot started by {log['caller']} -> {RED}INEFFECTIVE MITIGATION{NC}")
                    print("    (Reason: VM reboots do not override hypervisor-level network security blocks.)")
                elif "write" in log["operationName"] and "Reverted" in log["description"]:
                    print(f"  - {log['eventTimestamp']}: NSG Rule reverted by {log['caller']} -> {GREEN}EFFECTIVE MITIGATION{NC}")
                    print("    (Reason: Restores inbound routing paths on TCP Port 8000.)")

        recovery_time = "2026-06-08T12:20:00Z"
        print(f"\n{GREEN}[RESULT] Metrics recovery confirmed at {recovery_time} (up=1, throughput restored to 48.2 req/sec).{NC}")
        
        print(f"\n{YELLOW}================== ROOT CAUSE ANALYSIS (RCA) SUMMARY =================={NC}")
        print("1. OUTAGE TRIGGER  : NSG rule edit (Port 8000 blocked) by network administrator.")
        print("2. IMPACTED LAYER  : Data-plane application inaccessible. Prometheus target scrape fails.")
        print("3. FALSE LEAD      : VM reboot was attempted but did not mitigate the network block.")
        print("4. CORRECTION      : Reverting the NSG rule restored network connectivity.")
        print("5. LESSON LEARNED  : Cross-correlate Prometheus application telemetry (scraping 'up'")
        print("                     status) with Azure Resource Health and Activity Logs to prevent")
        print("                     needless host reboots during routing disruptions.")
        print(f"{YELLOW}======================================================================={NC}")

# --- 7. Option 5: Prometheus & Grafana Configurations (Friday) ---
def view_configs():
    print_banner("OPTION 5: PROMETHEUS & GRAFANA CONFIGURATIONS")
    
    print(f"\n{YELLOW}1. Prometheus Target Scrape Configuration (prometheus.yml){NC}")
    print("Defines scrape intervals and maps target API endpoints for ingestion:")
    print("-" * 65)
    prometheus_yml = """global:
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
      - targets: ['localhost:8000']"""
    print(prometheus_yml)
    print("-" * 65)
    
    print(f"\n{YELLOW}2. Registering Prometheus Datasource (Grafana REST API Payload){NC}")
    print("To hook Prometheus up to Grafana, submit a POST request to Grafana's API:")
    print("HTTP POST /api/datasources")
    print("Payload:")
    datasource_json = {
        "name": "prometheus-prod-01",
        "type": "prometheus",
        "url": "http://prometheus-srv:9090",
        "access": "proxy",
        "basicAuth": False,
        "isDefault": True
    }
    print(json.dumps(datasource_json, indent=2))
    
    print(f"\n{YELLOW}3. Grafana Dashboard Variables & Panel Snippet{NC}")
    print("Using dynamic variables like '$instance' lets operators filter dashboards dynamically.")
    print("Below is the JSON structure defining the PromQL query panel in Grafana:")
    panel_json = {
        "title": "Application Request Rate",
        "type": "timeseries",
        "datasource": {
            "type": "prometheus",
            "uid": "prometheus-prod-01"
        },
        "targets": [
            {
                "expr": "rate(http_requests_total{instance=\"$instance\"}[5m])",
                "legendFormat": "{{method}} - {{status}}",
                "refId": "A"
            }
        ]
    }
    print(json.dumps(panel_json, indent=2))

# --- Main Menu loop ---
def main():
    # Detect running environment
    az_status = f"{GREEN}Connected (LIVE DATA ACTIVE){NC}" if is_azure_logged_in() else f"{YELLOW}Offline (SIMULATED DATA ACTIVE){NC}"
    prom_status = f"{GREEN}Connected (LIVE METRICS ACTIVE){NC}" if is_prometheus_running() else f"{YELLOW}Offline (SIMULATED METRICS ACTIVE){NC}"
    
    print(f"\n{CYAN}Observability Agent Environment Status:{NC}")
    print(f"  - Azure CLI Connection : {az_status}")
    print(f"  - Prometheus Server API: {prom_status}")

    while True:
        print(f"\n{CYAN}--- SRE Observability Simulation CLI (Combined Thursday/Friday Demo) ---{NC}")
        print("1. View Raw Prometheus Scrape Endpoint (/metrics)")
        print("2. Query PromQL Metric Engine")
        print("3. Audit Azure Activity Logs & Resource Health")
        print("4. Execute Telemetry Correlation & Automated RCA")
        print("5. View Prometheus & Grafana Configs")
        print("6. Exit")
        
        choice = input("\nSelect Option (1-6): ").strip()
        
        if choice == "1":
            view_raw_metrics()
        elif choice == "2":
            run_promql_query()
        elif choice == "3":
            audit_azure_logs()
        elif choice == "4":
            run_telemetry_rca()
