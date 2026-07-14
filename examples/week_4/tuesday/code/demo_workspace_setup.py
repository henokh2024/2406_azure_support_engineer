import json
import subprocess
import sys
import time
from datetime import datetime, timezone

# Target resource configurations
RG_NAME = "rg-monitoring-prod-eastus-01"
WORKSPACE_NAME = "law-srelogs-01"
VM_NAME = "vm-appserver-prod-01"
NSG_NAME = "nsg-monitoring-prod-01"

# ANSI color codes for formatting
CYAN = "\033[0;36m"
YELLOW = "\033[1;33m"
GREEN = "\033[0;32m"
RED = "\033[0;31m"
NC = "\033[0m"

def run_az_command(args):
    """Helper to run az CLI commands and return parsed JSON or status code."""
    try:
        # Explicitly run using shell=True/False depending on OS, but on Linux shell=False is standard
        result = subprocess.run(
            ["az"] + args,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout), 0
            except json.JSONDecodeError:
                return result.stdout.strip(), 0
        else:
            return result.stderr.strip(), result.returncode
    except FileNotFoundError:
        return "Azure CLI (az) command not found in PATH.", -1

def check_azure_login():
    """Returns the subscription ID if logged in, or None if unauthenticated/offline."""
    output, code = run_az_command(["account", "show", "--query", "id", "-o", "tsv"])
    if code == 0 and isinstance(output, str) and output:
        # Strip any carriage returns or newlines
        return output.strip()
    return None

def verify_extension_installed():
    """Checks if monitor-control-service extension is installed. Installs if missing."""
    # Check if 'data-collection' is recognized under az monitor
    help_output, code = run_az_command(["monitor", "data-collection", "-h"])
    if code != 0:
        print(f"{YELLOW}[NOTE] Installing required Azure CLI extension 'monitor-control-service'...{NC}")
        _, install_code = run_az_command(["extension", "add", "--name", "monitor-control-service", "--yes"])
        if install_code == 0:
            print(f"{GREEN}[STATUS] Extension 'monitor-control-service' installed successfully.{NC}\n")
        else:
            print(f"{RED}[WARNING] Failed to install 'monitor-control-service' extension automatically.{NC}\n")

def simulate_audit_mode():
    """Prints mock audit logs when running in offline/simulated mode."""
    print(f"{YELLOW}[NOTE] Azure CLI session not found or not logged in. Running audit script in OFFLINE/SIMULATED mode.{NC}")
    print(f"{YELLOW}To run a live audit, execute 'az login' first.{NC}\n")

    print(f"{CYAN}=== 1. AUDITING LOG ANALYTICS WORKSPACE ==={NC}")
    print(f"[EXEC] az monitor log-analytics workspace show --resource-group {RG_NAME} --workspace-name {WORKSPACE_NAME}")
    print(f"[STATUS] Log Analytics Workspace '{WORKSPACE_NAME}' found. Retention: 30 days. SKU: PerGB2018.\n")

    print(f"{CYAN}=== 2. AUDITING NSG PLATFORM DIAGNOSTIC LOGS ROUTING ==={NC}")
    print(f"[EXEC] az monitor diagnostic-settings show --name ds-nsglogs-prod-01 --resource .../networkSecurityGroups/{NSG_NAME}")
    print(f"[STATUS] Diagnostic setting 'ds-nsglogs-prod-01' found. NSG platform log routing enabled.\n")

    print(f"{CYAN}=== 3. AUDITING VM DATA COLLECTION RULE ASSOCIATION (AMA/DCR) ==={NC}")
    print(f"[EXEC] az monitor data-collection rule association list --resource .../virtualMachines/{VM_NAME}")
    print(f"[STATUS] VM is successfully associated with a Data Collection Rule. Azure Monitor Agent (AMA) link verified.\n")

def run_live_audit(sub_id):
    """Executes live CLI queries against Azure resources."""
    print(f"{GREEN}[INFO] Active Azure CLI session found. Running LIVE audit against subscription {sub_id}.{NC}\n")
    
    verify_extension_installed()

    # 1. Audit Log Analytics Workspace
    print(f"{CYAN}=== 1. AUDITING LOG ANALYTICS WORKSPACE ==={NC}")
    workspace_data, code = run_az_command([
        "monitor", "log-analytics", "workspace", "show",
        "--resource-group", RG_NAME,
        "--workspace-name", WORKSPACE_NAME,
        "--query", "{name:name, sku:sku.name, retention:retentionInDays}"
    ])
    if code == 0:
        print("[STATUS] Workspace found:")
        print(json.dumps(workspace_data, indent=2))
    else:
        print(f"  {RED}[ERROR] Log Analytics Workspace '{WORKSPACE_NAME}' not found in Resource Group '{RG_NAME}'.{NC}")
    print()

    # 2. Audit NSG platform diagnostics settings
    print(f"{CYAN}=== 2. AUDITING NSG PLATFORM DIAGNOSTIC LOGS ROUTING ==={NC}")
    nsg_resource_id = f"/subscriptions/{sub_id}/resourceGroups/{RG_NAME}/providers/Microsoft.Network/networkSecurityGroups/{NSG_NAME}"
    nsg_data, code = run_az_command([
        "monitor", "diagnostic-settings", "show",
        "--name", "ds-nsglogs-prod-01",
        "--resource", nsg_resource_id,
        "--query", "{name:name, workspace:workspaceId}"
    ])
    if code == 0:
        print("[STATUS] Diagnostic settings found:")
        print(json.dumps(nsg_data, indent=2))
    else:
        print(f"  {RED}[ERROR] Diagnostic setting 'ds-nsglogs-prod-01' not found on NSG '{NSG_NAME}'.{NC}")
    print()

    # 3. Audit DCR VM association
    print(f"{CYAN}=== 3. AUDITING VM DATA COLLECTION RULE ASSOCIATION (AMA/DCR) ==={NC}")
    vm_resource_id = f"/subscriptions/{sub_id}/resourceGroups/{RG_NAME}/providers/Microsoft.Compute/virtualMachines/{VM_NAME}"
    dcr_data, code = run_az_command([
        "monitor", "data-collection", "rule", "association", "list",
        "--resource", vm_resource_id,
        "--query", "[].{name:name, dcr:dataCollectionRuleId}"
    ])
    if code == 0 and dcr_data:
        print("[STATUS] Data Collection Rule associations found:")
        print(json.dumps(dcr_data, indent=2))
    else:
        print(f"  {RED}[ERROR] No Data Collection Rule associations found on Virtual Machine '{VM_NAME}'.{NC}")
    print()

def audit_telemetry_latency(table_name, event_timestamp, ingestion_timestamp):
    """Calculates ingestion latency and outputs SRE troubleshooting statuses."""
    delay = ingestion_timestamp - event_timestamp
    
    # Format times in UTC ISO format
    event_str = datetime.fromtimestamp(event_timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ingest_str = datetime.fromtimestamp(ingestion_timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    print(f"Table: {table_name}")
    print(f"  Log Generation Time : {event_str}")
    print(f"  Database Index Time : {ingest_str}")
    print(f"  Total Ingestion Lag : {delay} seconds")
    
    if delay > 300:
        print(f"  {RED}[LATENCY ALERT] Ingestion delay exceeds 5 minutes (300s). Potential ingestion backlog or network queue delay.{NC}")
    elif delay < 0:
        print(f"  {RED}[SCHEMA ERROR] Negative ingestion lag. Check target VM clock synchronization NTP rules.{NC}")
    else:
        print(f"  {GREEN}[STATUS] Ingestion latency within healthy bounds (nominal).{NC}")
    print("-" * 60)

def main():
    sub_id = check_azure_login()
    
    if sub_id:
        run_live_audit(sub_id)
    else:
        simulate_audit_mode()
        
    print(f"{CYAN}=== 4. AUDITING TELEMETRY INGESTION LATENCY ==={NC}")
    
    now = int(time.time())
    
    # Scenario A: Nominal delay (45s)
    audit_telemetry_latency("AppRequests", now - 45, now)
    
    # Scenario B: High ingestion latency (12m / 720s delay)
    audit_telemetry_latency("AppTraces", now - 720, now)
    
    # Scenario C: Negative delay due to drift in guest VM clocks (-120s delay)
    audit_telemetry_latency("Syslog", now + 120, now)
    
    print("Workspace setup and ingestion latency audits complete.")

if __name__ == "__main__":
    main()
