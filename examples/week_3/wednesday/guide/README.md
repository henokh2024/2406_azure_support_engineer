# Guide

This guide is designed to walk you step-by-step through configuring Azure virtual network routing, custom Route Tables, User-Defined Routes (UDR), Network Security Groups (NSGs), and auditing active route tables.

You will build a secure, isolated three-tier subnet topology where all backend traffic is inspected by a Network Virtual Appliance (NVA) firewall.

---

## 1. Architectural Topology Overview

Here is the network layout we will build:

- **Virtual Network:** `vnet-core-prod-01` (IP space: `10.0.0.0/16`)
- **Subnet 1 (Frontend):** `snet-frontend-01` (`10.0.1.0/24`) ¿ Public-facing web servers.
- **Subnet 2 (Backend):** `snet-backend-01` (`10.0.2.0/24`) ¿ Isolated database and internal API services.
- **Subnet 3 (DMZ/Transit):** `snet-dmz-01` (`10.0.3.0/24`) ¿ Hosts the firewall Network Virtual Appliance (NVA).

### Key Routing Policies We Will Enforce:

1. All traffic from the **Frontend Subnet** to the **Backend Subnet** must route through the **NVA** (`10.0.3.4`).
2. All outbound egress traffic from the **Backend Subnet** to the public internet must route through the **NVA**.
3. Outbound requests from the **Backend Subnet** to a specific external high-performance API (`198.51.100.50`) must bypass the firewall and go directly to the Internet.
4. Outbound traffic from the **Backend Subnet** to a known malicious range (`203.0.113.0/24`) must be dropped immediately (**black-holed**).

---

## 2. Core Concepts Reference

### Public vs. Private Subnets in Azure

Unlike AWS, where a subnet is flagged as "public" or "private" at the route table level (depending on an Internet Gateway rule), **all subnets in Azure have direct outbound internet access by default** via `0.0.0.0/0 -> Internet`.
In Azure, a subnet is classified as public-facing or private based on:

1. **Public IP Addresses:** Whether resources (like VMs or load balancers) are assigned public IP addresses.
2. **Network Security Groups (NSGs):** Rules that block inbound internet traffic.
3. **User-Defined Routes (UDRs):** Rules that override the default internet egress route and send traffic to a firewall or drop it entirely.

### Propagate Gateway Routes (BGP Propagation)

When you create an Azure Route Table, you will see a setting called **Propagate gateway routes**:

- **Yes (Default):** Select this if you want the subnet to automatically learn and use routes advertised by your Azure virtual network gateways (like VPN or ExpressRoute) via Border Gateway Protocol (BGP).
- **No:** Select this to block BGP-learned routes. In enterprise hub-and-spoke topologies with central firewalls, this is set to **No** to prevent on-premises traffic from bypassing the firewall routes. For our lab, we will keep it as **Yes**.

### Stateful Firewalls and Source NAT (SNAT)

Azure Network Security Groups (NSGs) are **stateful**. This means if you allow an inbound request, the return path is automatically allowed.
However, if you route traffic through an NVA, the NVA must rewrite the packet's source IP address using **Source NAT (SNAT / Masquerading)** to match its own IP (`10.0.3.4`). Without SNAT, return packets would bypass the NVA directly via local VNet routing, causing stateful connection drops (**asymmetric routing**).

- Because SNAT changes the source IP of incoming traffic at the backend VM to `10.0.3.4`, you must explicitly configure the backend NSG to allow port `22` (SSH) and `5000` (API) from the **DMZ subnet (`10.0.3.0/24`)**, rather than just the frontend subnet.

---

## 3. Step-by-Step Lab Execution

### Step 1: Provision the Virtual Network and Subnets

1. In the Portal Search bar, type **Virtual networks** and select it.
2. Click **+ Create**.
3. On the **Basics** tab, configure:
    - **Resource Group:** `rg-network-prod-eastus-01` (Create a new resource group if it does not exist)
    - **Name:** `vnet-core-prod-01`
    - **Region:** `East US`
4. On the **IP Addresses** tab:
    - Set the IPv4 address space to `10.0.0.0/16`.
    - Remove the default subnet if present, and click **+ Add subnet** to create the following three subnets:
        - **Frontend Subnet:**
            - Name: `snet-frontend-01`
            - Address range: `10.0.1.0/24`
        - **Backend Subnet:**
            - Name: `snet-backend-01`
            - Address range: `10.0.2.0/24`
        - **DMZ Subnet:**
            - Name: `snet-dmz-01`
            - Address range: `10.0.3.0/24`
5. Click **Review + create**, then click **Create**.

---

### Step 2: Provision Network Security Groups (NSGs)

You must configure the security boundaries to permit SSH administration and HTTP routing:

1. **Create `nsg-frontend-01`:**
    - Search for **Network security groups** in the Portal search bar and select it.
    - Click **+ Create**. Select Resource Group `rg-network-prod-eastus-01`, name it `nsg-frontend-01`, and select region `East US`.
    - Once deployed, open `nsg-frontend-01` -> Select **Inbound security rules** -> Click **+ Add**:
        - **SSH Rule:** Source: `Any`, Destination port: `22`, Protocol: `TCP`, Action: `Allow`, Priority: `100`, Name: `Allow-SSH-Inbound`.
        - **HTTP Rule:** Source: `Any`, Destination port: `80`, Protocol: `TCP`, Action: `Allow`, Priority: `110`, Name: `Allow-HTTP-Inbound`.
    - Select **Subnets** in the left menu -> Click **+ Associate**:
        - Virtual network: `vnet-core-prod-01`
        - Subnet: `snet-frontend-01`
2. **Create `nsg-backend-01`:**
    - Create another NSG named `nsg-backend-01` in the same resource group and region.
    - Select **Inbound security rules** -> Click **+ Add**:
        - **SSH from Frontend:** Source: `IP Addresses`, Source IP: `10.0.1.0/24`, Port: `22`, Protocol: `TCP`, Action: `Allow`, Priority: `100`, Name: `Allow-SSH-From-Frontend`.
        - **SSH from DMZ (NVA SNAT):** Source: `IP Addresses`, Source IP: `10.0.3.0/24`, Port: `22`, Protocol: `TCP`, Action: `Allow`, Priority: `105`, Name: `Allow-SSH-From-DMZ`. *(Required to allow forwarded management traffic from NVA)*.
        - **FastAPI from Frontend:** Source: `IP Addresses`, Source IP: `10.0.1.0/24`, Port: `5000`, Protocol: `TCP`, Action: `Allow`, Priority: `110`, Name: `Allow-Port5000-From-Frontend`.
        - **FastAPI from DMZ (NVA SNAT):** Source: `IP Addresses`, Source IP: `10.0.3.0/24`, Port: `5000`, Protocol: `TCP`, Action: `Allow`, Priority: `115`, Name: `Allow-Port5000-From-DMZ`. *(Required to allow forwarded API traffic)*.
        - **Deny Inbound from Internet:** Source: `Internet`, Port: , Protocol: , Action: `Deny`, Priority: `200`, Name: `Deny-Direct-Internet-Inbound`.
    - Select **Subnets** -> Click **+ Associate**:
        - Virtual network: `vnet-core-prod-01`
        - Subnet: `snet-backend-01`
3. **Create `nsg-dmz-01`:**
    - Create another NSG named `nsg-dmz-01` in the same resource group and region.
    - Select **Inbound security rules** -> Click **+ Add**:
        - **SSH Rule:** Source: `Any`, Destination port: `22`, Protocol: `TCP`, Action: `Allow`, Priority: `100`, Name: `Allow-SSH-Inbound`.
        - **Allow Transit Traffic:** Source: `VirtualNetwork`, Destination port: , Protocol: , Action: `Allow`, Priority: `110`, Name: `Allow-Internal-Transit`.
    - Select **Subnets** -> Click **+ Associate**:
        - Virtual network: `vnet-core-prod-01`
        - Subnet: `snet-dmz-01`

---

### Step 3: Provision Route Tables in the Azure Portal

1. **Create the Route Tables:**
    - Search for **Route tables** in the Portal search bar and select it.
    - Click **+ Create**:
        - Resource Group: `rg-network-prod-eastus-01`
        - Name: `rt-frontend-prod-01`
        - Region: `East US`
        - Propagate gateway routes: **Yes**
    - Click **Review + create** -> **Create**.
    - Repeat the process to create the second route table named `rt-backend-prod-01` using the same configuration.
2. **Add Custom Routes to `rt-frontend-prod-01`:**
    - Open `rt-frontend-prod-01` -> Select **Routes** in the left menu -> Click **+ Add**:
        - Route name: `RouteToBackendViaNVA`
        - Destination IP addresses: `10.0.2.0/24`
        - Next hop type: `Virtual appliance`
        - Next hop address: `10.0.3.4` (IP of `vm-nva-01`)
3. **Add Custom Routes to `rt-backend-prod-01`:**
    - Open `rt-backend-prod-01` -> Select **Routes** -> Click **+ Add**:
        - **Force Egress through NVA (Default Route):**
            - Route name: `RouteToFirewallDefault`
            - Destination IP addresses: `0.0.0.0/0`
            - Next hop type: `Virtual appliance`
            - Next hop address: `10.0.3.4`
        - **Bypass NVA for External API (Internet Next-Hop):**
            - Route name: `BypassNVAForExtAPI`
            - Destination IP addresses: `198.51.100.50/32`
            - Next hop type: `Internet`
        - **Drop Malicious Traffic (None Next-Hop / Black-Hole):**
            - Route name: `DropMaliciousTraffic`
            - Destination IP addresses: `203.0.113.0/24`
            - Next hop type: `None`
        - **Route to On-Premises (Gateway Next-Hop):**
            - Route name: `RouteToOnPrem`
            - Destination IP addresses: `172.16.0.0/12`
            - Next hop type: `Virtual network gateway`
        - **Direct Local Override (VnetLocal Next-Hop):**
            - Route name: `LocalVNetDirectOverride`
            - Destination IP addresses: `10.0.99.0/24`
            - Next hop type: `Virtual network`
4. **Associate Route Tables with Subnets:**
    - In both route table screens, select **Subnets** -> Click **+ Associate**:
        - Select VNet `vnet-core-prod-01`.
        - Associate `rt-frontend-prod-01` to `snet-frontend-01`.
        - Associate `rt-backend-prod-01` to `snet-backend-01`.

---

### Step 4: Deploy the Virtual Machines

1. **Deploy the Private Backend VM (`vm-backend-01`):**
    - Search for **Virtual machines** -> Click **+ Create** -> **Azure virtual machine**.
    - **Basics Tab:**
        - Resource Group: `rg-network-prod-eastus-01`
        - VM Name: `vm-backend-01`
        - Region: `East US`
        - Image: `Ubuntu Server 22.04 LTS - Gen2`
        - Size: `Standard_B1s` (Cost Control)
        - Authentication: `SSH public key`, Username: `azureuser`
        - Key pair name: `vm-backend-01-key`
        - Public inbound ports: **None**
    - **Networking Tab:**
        - Virtual network: `vnet-core-prod-01`
        - Subnet: `snet-backend-01 (10.0.2.0/24)`
        - Public IP: **None** *(Strict Isolation)*
        - NIC network security group: **None** *(Subnet NSG is already associated)*
    - **Management Tab:**
        - Auto-shutdown: **Enable auto-shutdown** (e.g. 7:00 PM) to control idle VM billing.
    - Click **Review + create** -> **Create** (Download the private key `.pem` file).
2. **Deploy the Frontend VM (`vm-frontend-01`):**
    - Repeat the VM creation steps with the following modifications:
        - VM Name: `vm-frontend-01`
        - Subnet: `snet-frontend-01 (10.0.1.0/24)`
        - Public IP: **Yes** (Create standard Public IP so you can SSH in)
    - Note down the public IP address of `vm-frontend-01` for testing.
3. **Deploy the NVA Firewall VM (`vm-nva-01`):**
    - Repeat the VM creation steps with the following modifications:
        - VM Name: `vm-nva-01`
        - Subnet: `snet-dmz-01 (10.0.3.0/24)`
        - Public IP: **Yes** (Standard Public IP)
    - **Enable IP Forwarding on the NIC:**
        - Once `vm-nva-01` is deployed, navigate to its resource page.
        - Click **Networking** -> select the active **Network Interface** (NIC).
        - In the NIC left menu, click **IP configurations**.
        - Under **IP forwarding**, set it to **Enabled** and click **Save/Apply** *(Azure drops transit packets not destined for the VM's own IP unless IP forwarding is enabled)*.

---

### Step 5: Configure the NVA Guest OS

Even with Azure IP forwarding enabled, the Linux guest operating system must be configured to act as a router and NAT gateway:

1. SSH into `vm-nva-01` using its public IP:
    
    ```bash
    ssh -i path/to/vm-nva-01-key.pem azureuser@<nva-public-ip>
    ```
    
2. Enable IP forwarding in the Linux kernel:*(To make this change permanent, edit `/etc/sysctl.conf` and uncomment `net.ipv4.ip_forward=1`)*
    
    ```bash
    sudo sysctl -w net.ipv4.ip_forward=1
    ```
    
3. Configure Source NAT (SNAT) and forwarding policies in `iptables`:
    
    ```bash
    sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    sudo iptables -A FORWARD -j ACCEPT
    ```
    
4. Disable UFW to prevent local OS firewall rules from dropping forwarded traffic:
    
    ```bash
    sudo ufw disable
    ```
    

---

### Step 6: VM Environment Setup and Code Transfer

1. **Install Docker on both `vm-frontend-01` and `vm-backend-01`:**
SSH into each VM and run:
    
    ```bash
    sudo apt-get update
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker azureuser
    newgrp docker
    ```
    
2. **Upload Lab Code to `vm-frontend-01`:**
From your local machine's terminal, upload the codebase:
    
    ```bash
    scp -r -i path/to/vm-frontend-01-key.pem path/to/azure-support-sre/weeklytechrepo/Networking/demo/3-Wednesday/code/ azureuser@<frontend-public-ip>:~/
    ```
    
3. **Copy the Backend Code to the Private VM (`vm-backend-01`):**
Because `vm-backend-01` is private, we must copy the files from the frontend jump box.
    - **Key Copying (Lab Shortcut)**
    Upload the backend key to the frontend host, then run:
        
        ```bash
        scp -i ~/vm-backend-01-key.pem -r ~/code/backend azureuser@10.0.2.4:~/
        ```
        

---

### Step 7: Build and Run Application Containers

1. **On `vm-backend-01` (10.0.2.4):**
SSH into the backend VM and run:
    
    ```bash
    # Build the Docker image
    docker build -t backend-api ./backend
    
    # Run the backend API container
    docker run -d --name backend-service -p 5000:5000 backend-api
    ```
    
2. **On `vm-frontend-01` (10.0.1.4):**
SSH into the frontend VM and run:
    
    ```bash
    # Navigate to the uploaded code folder
    cd ~/code
    
    # Build the Docker image
    docker build -t frontend-web ./frontend
    
    # Run the frontend web app container
    docker run -d --name frontend-service -p 80:80 frontend-web
    ```
    

---

### Step 8: Run Diagnostics and Verify Effective Routes

1. **Auditing Effective Routes:**
    - In the Azure Portal, go to **Virtual Machines** -> Select `vm-backend-01`.
    - Go to **Networking** -> Click your active **Network Interface** (NIC).
    - In the NIC screen left menu, click **Effective routes**.
    - Observe that the default system route `0.0.0.0/0 -> Internet` is marked as **Invalidated**, and the custom `0.0.0.0/0 -> VirtualAppliance` route is active.
2. **Execute Diagnostic Tests in Web UI:**
    - Open a browser and navigate to the public IP of `vm-frontend-01` (e.g., `http://<frontend-public-ip>`).
    - Click **Run All Diagnostics** and review the logs:
        - **Backend API Service:** returns **Success** (Traffic is routed through NVA, NAT'ed, and allowed by the backend NSG on port 5000).
        - **Backend SSH Management:** returns **Success** (permitted by the `Allow-SSH-From-DMZ` rule).
        - **High-Performance External API:** returns **Timeout** (Expected behavior on a live public cloud because `198.51.100.50` is a reserved documentation IP, but proves the UDR bypassed the NVA).
        - **Known Malicious Range:** returns **Timeout** (Discarded by Next Hop: `None`).
        - **On-Premises Database Server:** returns **Timeout** (Routed to virtual gateway; gateway is inactive).

---

## 4. Troubleshooting Guide

### Why is my SSH connection from Frontend VM to Backend VM hanging?

1. **NVA Forwarding is Missing:** Check if you enabled IP forwarding on `vm-nva-01`'s NIC in the Portal and ran the `sysctl` and `iptables` commands inside the guest OS.
2. **Stateful NSG Mismatch:** Since the NVA rewrites the source IP using masquerade, traffic arrives at `vm-backend-01` from the NVA IP (`10.0.3.4`). Ensure you have an inbound rule in `nsg-backend-01` allowing port `22` from `10.0.3.0/24`.
3. **Local Linux Firewall:** If UFW is enabled on the NVA VM, it may drop forwarded traffic by default. Run `sudo ufw disable` on the NVA.
