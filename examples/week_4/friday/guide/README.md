# Guide

This guide walks you step-by-step through deploying a containerized monitoring stack from a **completely clean environment**, configuring Prometheus scraping, and using dynamic querying and Azure Activity log correlation to solve a simulated routing outage.

---

## 1. Step-by-Step Lab Setup (Clean Azure Environment)

Run these commands inside your local SRE terminal (such as WSL, Git Bash, or Azure Cloud Shell).

### Step 1.1: Deploy Cloud Infrastructure

Create the Resource Group, virtual network filtering rules, and VM hosting.

```bash
# 1. Create a Resource Group
az group create --name rg-monitoring-prod-eastus-01 --location eastus

# 2. Create the Network Security Group (NSG)
az network nsg create --resource-group rg-monitoring-prod-eastus-01 --name nsg-monitoring-prod-01

# 3. Create NSG Rules to open TCP ports 22, 8000, 9090, and 3000
az network nsg rule create -g rg-monitoring-prod-eastus-01 --nsg-name nsg-monitoring-prod-01 -n Allow-SSH-Inbound --priority 100 --destination-port-ranges 22 --access Allow --protocol Tcp
az network nsg rule create -g rg-monitoring-prod-eastus-01 --nsg-name nsg-monitoring-prod-01 -n Allow-FastAPI-8000 --priority 110 --destination-port-ranges 8000 --access Allow --protocol Tcp
az network nsg rule create -g rg-monitoring-prod-eastus-01 --nsg-name nsg-monitoring-prod-01 -n Allow-Prometheus-9090 --priority 120 --destination-port-ranges 9090 --access Allow --protocol Tcp
az network nsg rule create -g rg-monitoring-prod-eastus-01 --nsg-name nsg-monitoring-prod-01 -n Allow-Grafana-3000 --priority 130 --destination-port-ranges 3000 --access Allow --protocol Tcp

# 4. Deploy SRE Host VM (Ubuntu 22.04, size Standard_B1s for cost control)
az vm create \
  --resource-group rg-monitoring-prod-eastus-01 \
  --name vm-appserver-prod-01 \
  --image Ubuntu2204 \
  --size Standard_B1s \
  --admin-username azureuser \
  --nsg nsg-monitoring-prod-01 \
  --generate-ssh-keys \
  --assign-identity
```

---

### Step 1.2: Configure VM Host Environment & Azure CLI

Connect to the VM to install Docker and the Azure CLI. You will also authorize the VM using Azure's Managed Identity (RBAC) to allow the CLI simulation to query Azure platform APIs.

```bash
# 1. SSH into the VM (replace with your VM Public IP)
ssh azureuser@<VM-PUBLIC-IP>

# 2. Install Docker on the VM
sudo apt-get update && sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker

# Configure user permissions
sudo usermod -aG docker azureuser
newgrp docker

# 3. Install the Azure CLI on the VM guest OS
curl -sL <https://aka.ms/InstallAzureCLIDeb> | sudo bash
```

#### Step 1.2.5: Configure Managed Identity Permissions (RBAC Setup)

To query Activity Logs and Resource Health, the VM's identity must be granted access.

**From your local management workstation terminal (not inside the VM), run:**

```bash
# 1. Get the Resource Group ID directly (stripping Windows carriage returns)
rgId=$(az group show --name rg-monitoring-prod-eastus-01 --query id -o tsv | tr -d '\r')

# 2. Get the VM System-Assigned Identity Principal ID (stripping carriage returns)
vmPrincipalId=$(az vm show -g rg-monitoring-prod-eastus-01 -n vm-appserver-prod-01 --query identity.principalId -o tsv | tr -d '\r')

# 3. Assign the Reader role to the VM principal
# Note: On Windows Git Bash/MSYS, prefix with MSYS_NO_PATHCONV=1 to stop the terminal
# from converting the Azure scope ID (/subscriptions/...) into a local Windows filepath.
MSYS_NO_PATHCONV=1 az role assignment create \
  --assignee-object-id "$vmPrincipalId" \
  --assignee-principal-type ServicePrincipal \
  --role Reader \
  --scope "$rgId"
```

**Back inside the VM terminal session, log in using the managed identity:**

```bash
az login --identity
```

---

### Step 1.3: Deploy Containerized Services

Deploy the SRE target application, the Prometheus query engine, and the Grafana visualization service on the VM host.

1. **Build and launch the FastAPI application from source:**
    
    ```bash
    # Create code directory and Dockerfile
    mkdir -p ~/code && cd ~/code
    cat << 'EOF' > Dockerfile
    FROM python:3.10-slim
    WORKDIR /app
    RUN pip install --no-cache-dir fastapi uvicorn requests
    COPY demo_alerts_config.py .
    EXPOSE 8000
    CMD ["python", "demo_alerts_config.py"]
    EOF
    
    # Copy Monday's script content into demo_alerts_config.py (or transfer it)
    # Then build the docker image:
    docker build -t alert-demo-app .
    
    # Run the container from the built image:
    docker run -d --name alert-demo-service -p 8000:8000 alert-demo-app
    ```
    
2. **Configure Prometheus scrape targets:**
To demonstrate the Network Security Group (NSG) firewall block later, Prometheus must scrape the VM's **Private IP** instead of `localhost`. (Traffic to `localhost` stays entirely inside the guest OS loopback interface and bypasses Azure NSG firewall rules).
    
    Get the VM's Private IP (e.g. `10.0.1.4`):
    
    ```bash
    hostname -I
    ```
    
    Create a file named `prometheus.yml` in the current directory, replacing `<VM-PRIVATE-IP>` with the IP returned above:
    
    ```yaml
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    scrape_configs:
      - job_name: 'sre-fastapi-app'
        metrics_path: '/metrics'
        scrape_interval: 10s
        static_configs:
          - targets: ['<VM-PRIVATE-IP>:8000']
    ```
    
3. **Launch the Prometheus container:**
    
    ```bash
    docker run -d --name prometheus-srv --network="host" -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus
    ```
    
    *(Note: Using network type `host` allows the container to easily resolve and poll the VM's private IP on port 8000).*
    
4. **Launch the Grafana container:**
    
    ```bash
    docker run -d --name grafana-srv -p 3000:3000 grafana/grafana
    ```
    

---

## 2. Interactive Telemetry Auditing & Correlation

Execute the Friday runner script on your local SRE shell to start the interactive dashboard:

```bash
bash code/demo_prometheus_grafana.sh
```

*(On native Windows environments, run: `python code/demo_combined_observability.py`)*

The script checks for active connections to Azure and local Prometheus servers. If active, it fetches live data. If offline, it falls back to a simulated scenario.

### Step 2.1: View Raw Metrics Scrapes

1. Select Option **`1`** (`View Raw Prometheus Scrape Endpoint`).
2. Note the plaintext syntax structure. Verify how dimensional labels map requests.

### Step 2.2: Verify Baseline Healthy Metrics

1. Select Option **`2`** (`Query PromQL Metric Engine`).
2. Query **`1`** (`up{job="sre-fastapi-app"}`).
3. Observe that target status is `UP (1)`.

---

## 3. Incident Triggering & Outage Analysis

We will now block access to the application in real-time.

### Step 3.1: Trigger the Outage

From a separate SRE management shell, inject a Deny rule on port 8000 to simulate a routing failure:

```bash
az network nsg rule create \
  --resource-group rg-monitoring-prod-eastus-01 \
  --nsg-name nsg-monitoring-prod-01 \
  -n Deny-FastAPI-8000 \
  --priority 105 \
  --destination-port-ranges 8000 \
  --access Deny \
  --protocol Tcp
```

### Step 3.2: Inspect Outage Metrics (PromQL)

1. In the CLI simulator menu, select Option **`2`** -> Query **`1`** (`up`).
2. Observe the timeline dip. The target status has dropped to `DOWN (0)`.
*(Note: If Prometheus was configured to scrape `localhost` instead of the Private IP, the loopback traffic stays inside the VM guest OS and bypasses the NSG rule. In this case, you can simulate a data-plane crash by stopping the container: `docker stop alert-demo-service` on the VM host).*

### Step 3.3: Audit Platform Health Logs

1. In the CLI simulator, select Option **`3`** (`Audit Azure Activity Logs & Resource Health`).
2. Observe the platform state. Note that if you stopped the container, Resource Health correctly remains `Available` (since the VM hardware is healthy). To simulate a full platform outage where Resource Health becomes `Unavailable`, stop/deallocate the VM itself via `az vm stop` from your workstation.

### Step 3.4: Automate Cross-Telemetry Correlation & RCA

1. In the CLI simulator, select Option **`4`** (`Execute Telemetry Correlation & Automated RCA`).
2. Trace the timeline. Review the RCA summary highlighting how the NSG block triggered the outage and why reboots are false leads during firewall incidents.

---

## 4. Mitigation & Cleanups

### Step 4.1: Revert the Network Block

Remove the blocking Deny rule to restore the routing path:

```bash
az network nsg rule delete \
  --resource-group rg-monitoring-prod-eastus-01 \
  --nsg-name nsg-monitoring-prod-01 \
  -n Deny-FastAPI-8000
```

### Step 4.2: Verify Recovery

1. Re-run Option **`2`** -> Query **`1`** (`up`). Verify that the target has returned to `UP (1)`.
2. Re-run Option **`3`** to confirm Resource Health is `Available`.

### Step 4.3: Delete Cloud Resources (Cost Control)

Ensure all resources are deleted when the lab is complete to prevent billing:

```bash
az group delete --name rg-monitoring-prod-eastus-01 --yes --no-wait
```