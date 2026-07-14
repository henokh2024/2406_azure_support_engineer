# Guide

This guide walks you step-by-step through provisioning an Azure Log Analytics Workspace, establishing diagnostic logs routing, troubleshooting guest agent endpoints, and auditing ingestion latency.

---

## 1. Architectural Topology Overview

Here is the logging topology we will build/verify in this lab:

- **Virtual Machine:** `vm-appserver-prod-01` (source VM forwarding logs).
- **Central Logs Database:** `law-srelogs-01` (Log Analytics Workspace receiving the telemetry).
- **Diagnostic Logs Routing:** VM diagnostic rules that capture and direct metrics and system logs to the workspace.

---

## 2. Core Concepts Reference

### Centralized Log Analytics

By consolidating application and VM platform logs in a single central **Log Analytics Workspace**, SREs can run complex correlation queries across multiple resources using Kusto Query Language (KQL) to locate root causes during outages.

### Ingestion Latency Boundaries

Logs are not instantly visible in workspaces. There is a processing lag determined by three boundaries:

1. **Collection Latency:** The time taken by the VM agent (Azure Monitor Agent) to write and batch event logs locally.
2. **Transmission Latency:** Delays routing logs over HTTPS (requires port 443 open to the `AzureMonitor` service tag).
3. **Processing Latency:** Time taken by Azure's indexing engines to parse and index records into database tables.
4. **Clock Drift Anomaly:** If a VM's guest OS clock is out of sync (failed NTP updates), the query engine compares incorrect local timestamps against Azure system times, resulting in negative ingestion lag warnings.

---

## 3. Step-by-Step Lab Execution

### Step 1: Provision Prerequisite VM & Resource Group (Skip if continuing from Monday)

If you are starting this lab fresh without the resources from Monday's lab, configure the prerequisite group, firewall (NSG), and VM:

1. Open the Azure Portal.
2. Search for **Resource groups** in the top search bar -> select it -> click **+ Create**. Resource Group: `rg-monitoring-prod-eastus-01`, Region: `East US`. Click **Create**.
3. Search for **Network security groups** -> click **+ Create**. Resource Group: `rg-monitoring-prod-eastus-01`, Name: `nsg-monitoring-prod-01`, Region: `East US`. Click **Create**.
    - Open `nsg-monitoring-prod-01` -> select **Inbound security rules** -> click **+ Add**:
        - **SSH Admin:** Source: `Any`, Destination port: `22`, Protocol: `TCP`, Action: `Allow`, Priority: `100`, Name: `Allow-SSH-Inbound`.
        - **FastAPI Web Service:** Source: `Any`, Destination port: `8000`, Protocol: `TCP`, Action: `Allow`, Priority: `110`, Name: `Allow-FastAPI-8000`.
4. Search for **Virtual machines** -> click **+ Create** -> **Azure virtual machine**.
5. **Basics Tab:**
    - Resource Group: `rg-monitoring-prod-eastus-01`
    - VM Name: `vm-appserver-prod-01`
    - Region: `East US`
    - Image: `Ubuntu Server 22.04 LTS`
    - Size: `Standard_B1s` (Cost Control)
    - Authentication type: `SSH public key`, Username: `azureuser`. Key pair: `vm-appserver-key` (Download and save the private key PEM file).
6. **Networking Tab:** Allow default Virtual network and Subnet generation.
    - **Public IP:** Select **Create new** (assign standard public IP).
    - **NIC network security group:** Select **Advanced** -> select `nsg-monitoring-prod-01`.
7. **Management Tab:** Check **Enable auto-shutdown** (7:00 PM local) to maintain cost control.
8. Click **Review + create** -> **Create**.

---

### Step 2: Provision the Log Analytics Workspace

1. Open the Azure Portal.
2. Search for **Log Analytics workspaces** in the top portal search bar and select it.
3. Click **+ Create**.
4. **Basics Tab:**
    - **Subscription:** Select your subscription.
    - **Resource Group:** `rg-monitoring-prod-eastus-01` (Reusing the resource group)
    - **Name:** `law-srelogs-01`
    - **Region:** `East US`
5. Click **Review + create** -> **Create**.
6. Once deployed, navigate to `law-srelogs-01` -> click **Usage and estimated costs** under the General section -> select **Data Retention**. Confirm it is set to **30 days** to ensure free tier cost compliance.

---

### Step 3: Configure Network Security Group (NSG) Diagnostic Logs Routing

> [!CAUTION]
**Virtual Machines do NOT support Diagnostic Settings:**
If you search for Virtual Machines in the Diagnostic Settings resource list, they will not appear. VMs do not support platform-level Diagnostic Settings. To send VM guest OS logs or performance counters to a workspace, you **must** configure **Data Collection Rules (DCR)** and the **Azure Monitor Agent (AMA)** (see Step 4). However, other supporting resources¿such as **Network Security Groups (NSGs)**, Public IPs, and Load Balancers¿*do* support Diagnostic Settings. In this step, we configure NSG logging to capture network events.
> 

To route NSG platform event logs to the workspace:

1. Search for **Monitor** in the top search bar -> select it.
2. In the Monitor left sidebar under **Settings**, click **Diagnostic settings**.
3. Under Resource type, filter by/select **Network security groups**.
4. Select `nsg-monitoring-prod-01` in the resources list.
5. Click **+ Add diagnostic setting**.
6. Configure settings:
    - **Diagnostic setting name:** `ds-nsglogs-prod-01`
    - **Categories:** Under Logs, check **allLogs**.
    - **Destination details:** Check **Send to Log Analytics workspace**.
    - **Workspace:** Select `law-srelogs-01`.
7. Click **Save**.
*(Note: This captures platform-level logs from the Network Security Group. This is supported and does not require storage accounts or agents).*

---

### Step 4: Configure Guest OS Telemetry via Data Collection Rules (AMA/DCR)

> [!IMPORTANT]
**Diagnostics Extension Deprecation:**
The legacy guest-level Azure Diagnostics Extension (LAD/WAD) was deprecated on March 31, 2026. Microsoft no longer supports it. All guest OS metrics, events, and syslog diagnostics must now be configured using **Data Collection Rules (DCR)** and the modern **Azure Monitor Agent (AMA)**.
> 

To install the AMA agent and pull Syslog logs into your workspace:

1. Search for **Data Collection Rules** in the top search bar -> select it.
2. Click **+ Create**.
3. **Basics Tab:**
    - **Rule Name:** `dcr-vmlogs-prod-01`
    - **Resource Group:** `rg-monitoring-prod-eastus-01`
    - **Platform Type:** `Linux`
4. **Resources Tab:**
    - Click **+ Add resources** -> check the box next to `vm-appserver-prod-01` -> click **Apply**.
5. **Collect and deliver Tab:**
    - Click **+ Add data source**.
    - **Data source type:** Select **Linux Syslog**.
    - **Syslog facilities configuration:** In the grid, select **LOG_INFO** (or **LOG_DEBUG** to capture all verbosity) from the dropdown next to each facility. You can check the checkbox in the table header to apply this to all facilities at once.
    - Select **Destination** sub-tab:
        - **Destination type:** Select **Azure Monitor Logs** (or **Log Analytics Workspaces** depending on portal version).
        - **Workspace (or Account or Namespace):** Select `law-srelogs-01`.
    - Click **Add data source**.
6. Click **Review + create** -> **Create**.
*(Note: This automatically provisions the AMA guest VM extension and links the log routing rule).*

---

## 4. Verification and Troubleshooting

### Step 1: Connect to the Virtual Machine

1. SSH into the VM:
    
    ```bash
    ssh -i path/to/vm-appserver-key.pem azureuser@<vm-public-ip>
    ```
    

### Step 2: Verify Azure Monitor Agent (AMA) Daemon Status

1. Check if the AMA service is running on the host machine:
    
    ```bash
    systemctl status azuremonitoragent
    ```
    
2. If the daemon status is `inactive (dead)`, restart it:
    
    ```bash
    sudo systemctl restart azuremonitoragent
    ```
    

### Step 3: Diagnose Outbound Endpoints Connectivity

1. Test network connectivity to the Azure Monitor handler endpoint to verify no firewalls are blocking TCP port 443:
    
    ```bash
    curl -v <https://global.handler.control.monitor.azure.com/ping>
    ```
    
2. A successful SSL handshake and connection status confirms outbound network rules allow traffic. If the connection hangs or returns a timeout, check the NSG outbound rules.

### Step 4: Check Guest OS Clock Synchronization (NTP)

1. Verify if the system clock is synchronized:
    
    ```bash
    chronyc tracking
    ```
    
2. If NTP sync is broken, force synchronization:*(On Windows hosts, use `w32tm /resync` to force sync).*
    
    ```bash
    sudo systemctl restart chrony
    ```
    

### Step 5: Run the Ingestion Delay Audit

This script acts as a validation checker. It automatically detects if you are logged into the Azure CLI (if not, it falls back to a simulated offline run). When logged in, it queries the status of the workspace, the NSG diagnostic setting, and the VM DCR association to verify they are properly configured. Then, it runs the simulated ingestion delay checks:

1. Navigate to the Tuesday demo folder in your terminal:
    
    ```bash
    cd weeklytechrepo/Monitoring-Observability/demo/2-Tuesday/
    ```
    
2. Run the audit script in WSL Ubuntu:
    
    ```bash
    python3 code/demo_workspace_setup.py
    ```
    
3. **Analyze Ingestion Scenarios:**
    - **Scenario A (Nominal):** Normal data plane delays of under 60 seconds are healthy.
    - **Scenario B (Backlog Queue):** Delay spikes exceeding 5 minutes (300 seconds) indicate network blocks or transmission queues.
    - **Scenario C (Negative Delay):** Negative duration traces warn that the guest VM clock is drifting and NTP time sync services must be rebooted.
