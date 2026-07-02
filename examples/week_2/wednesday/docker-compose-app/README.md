# README

## VNET Setup

### Step 1: Create a Resource Group

1. In the search box at the top of the portal, search for **Resource groups** and select it.
2. Click **+ Create**.
3. Select your subscription, enter Resource group name: `rg-portal-demo-eastus`, and select Region: **(US) East US**.
4. Click **Review + create**, then click **Create**.

#### Step 2: Create and Configure the Shared NSG

1. Search for **Network security groups** and click **+ Create**.
2. Select Resource Group: `rg-portal-demo-eastus`. Enter Name: `nsg-shared-portal`.
3. Click **Review + create**, then click **Create**.
4. Once deployed, open `nsg-shared-portal`, go to **Inbound security rules** -> **+ Add** to define the ruleset for both tiers:
    - **SSH (admin access)**: Source: **Any**, Destination port: `22`, Protocol: **TCP**, Action: **Allow**, Priority: `100`, Name: `Allow_SSH_Public`. Click **Add**.
    - **FastAPI (web app)**: Source: **Any**, Destination port: `8080`, Protocol: **TCP**, Action: **Allow**, Priority: `110`, Name: `Allow_8080_Public`. Click **Add**.
    - **PostgreSQL (app-to-db)**: Source: **IP Addresses**, Source IP: `10.0.1.0/24` (App Subnet), Destination port: `5432`, Protocol: **TCP**, Action: **Allow**, Priority: `120`, Name: `Allow_Postgres_From_AppSubnet`. Click **Add**.
    - **PostgreSQL Deny (security boundary)**: Source: **Any**, Destination port: `5432`, Protocol: **TCP**, Action: **Deny**, Priority: `200`, Name: `Deny_All_Other_Db_Inbound`. Click **Add**.

### Step 3: Create a Custom VNet and Subnets (With Shared NSG Association)

1. Search for **Virtual networks** and click **+ Create**.
2. Select Resource Group: `rg-portal-demo-eastus`. Enter Name: `vnet-portal-demo`.
3. Under the **IP Addresses** tab:
    - Keep the default IPv4 address space `10.0.0.0/16`.
    - Remove the default subnet and click **+ Add subnet**.
    - **App Subnet**: Enter Name: `subnet-app`, Address range: `10.0.1.0/24`.
        - In the **Network security group** dropdown, select `nsg-shared-portal`. Click **Add**.
    - **Db Subnet**: Click **+ Add subnet** again. Enter Name: `subnet-db`, Address range: `10.0.2.0/24`.
        - In the **Network security group** dropdown, select `nsg-shared-portal`. Click **Add**.
4. Click **Review + create**, then click **Create**.

### Step 4: Create a NAT Gateway (For Private Subnet Outbound Egress)

1. Search for **NAT gateways** and click **+ Create**.
2. Select Resource Group: `rg-portal-demo-eastus`. Enter Name: `nat-gateway-demo`.
3. Select Region: **(US) East US**.
4. Under the **Outbound IP** tab:
    - Click **Create a new public IP address** (e.g. `pip-nat-gw`).
5. Under the **Subnet** tab:
    - Select Virtual network: `vnet-portal-demo`.
    - Check the boxes to associate it with **both** `subnet-app` and `subnet-db`.
6. Click **Review + create**, then click **Create**.

### Step 5: Deploy the Database VM (Private-Only)

1. Search for **Virtual machines** and click **Create** -> **Azure virtual machine**.
2. Select Resource Group: `rg-portal-demo-eastus`. Enter Name: `vm-db-portal`.
3. Select Image: **Ubuntu Server 22.04 LTS**.
4. Size: Select **Standard_B1s** (Cost Control!).
5. Administrator account: Choose **SSH public key**, username `azureuser`, and generate a new key pair.
6. Under the **Networking** tab:
    - Select Virtual network: `vnet-portal-demo`.
    - Select Subnet: `subnet-db (10.0.2.0/24)`. (It will automatically inherit `nsg-shared-portal` and route outbound through the NAT Gateway).
    - Public IP: Select **None** (Strict Security Boundary!).
    - NIC network security group: Select **None** (since the NSG is already associated at the subnet level).
7. Under the **Management** tab: Keep default settings.
8. Click **Review + create**, then click **Create**.

### Step 6: Deploy the App VM (With Managed Identity)

1. Repeat the VM creation process. Name: `vm-app-portal`.
2. Subnet: Choose `subnet-app (10.0.1.0/24)`. (It will automatically inherit `nsg-shared-portal` and route outbound through the NAT Gateway).
3. Public IP: Create a standard public IP (so we can SSH in for the demo).
4. Under the **Networking** tab:
    - NIC network security group: Select **None**.
5. Under the **Management** tab:
    - Under **Identity**, check **Enable system-assigned managed identity** (Crucial for Azure AD token auth!).
6. Review and Create the VM.



## VM Setup

### 1. Provision VMs

If provisioning via the Portal, download both private key files:

- `vm-app-portal_key` (for the Application VM)
- `vm-db-portal_key` (for the Database VM)

Place these key files in your local project directory. Note the **Public IP of the App VM**, and the **Private IPs** of both VMs.

### 2. Configure the Database VM

Since the Database VM has no public IP, we transit (tunnel) through the App VM.

1. Copy the `db-vm/` directory and the DB private key to the App VM using the App VM key:
    
    ```bash
    scp -i vm-app-portal_key -r ./db-vm azureuser@<APP_VM_PUBLIC_IP>:/home/azureuser/
    scp -i vm-app-portal_key vm-db-portal_key azureuser@<APP_VM_PUBLIC_IP>:/home/azureuser/
    ```
    
2. SSH into the App VM:
    
    ```bash
    ssh -i vm-app-portal_key azureuser@<APP_VM_PUBLIC_IP>
    ```
    
3. On the App VM, restrict permissions on the DB private key (essential for SSH client execution):
    
    ```bash
    chmod 400 /home/azureuser/vm-db-portal_key
    ```
    
4. Copy the database compose directory from the App VM to the DB VM using its private IP and key:
    
    ```bash
    scp -i /home/azureuser/vm-db-portal_key -r /home/azureuser/db-vm azureuser@<DB_VM_PRIVATE_IP>:/home/azureuser/
    ```
    
5. SSH from the App VM into the DB VM:
    
    ```bash
    ssh -i /home/azureuser/vm-db-portal_key azureuser@<DB_VM_PRIVATE_IP>
    ```
    
6. Install Docker and Docker Compose on the DB VM:
    
    ```bash
    sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
    sudo usermod -aG docker $USER && newgrp docker
    ```
    
7. Start the PostgreSQL database:
    
    ```bash
    cd ~/db-vm
    docker compose up -d
    ```
    

### 3. Configure the Application VM

1. Open a new local terminal session and copy the `app-vm/` directory to the App VM:
    
    ```bash
    scp -i vm-app-portal_key -r ./app-vm azureuser@<APP_VM_PUBLIC_IP>:/home/azureuser/
    ```
    
2. SSH back into the App VM:
    
    ```bash
    ssh -i vm-app-portal_key azureuser@<APP_VM_PUBLIC_IP>
    ```
    
3. Install Docker and Docker Compose on the App VM:
    
    ```bash
    sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
    sudo usermod -aG docker $USER && newgrp docker
    ```
    
4. Update `app-vm/docker-compose.yml` to specify the private IP of the Database VM:
    
    ```bash
    cd ~/app-vm
    nano docker-compose.yml
    # Change DB_HOST to the private IP of the DB VM (e.g., 10.0.2.4)
    ```
    
5. Run the FastAPI Web Application:
    
    ```bash
    docker compose up -d --build
    ```