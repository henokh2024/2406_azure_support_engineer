import subprocess
import random
import sys

def run_az_command(command_list):
    """Utility function to safely execute an Azure CLI command array"""
    print(f"Executing: {' '.join(command_list)}")
    try:
        # run() executes the command and waits or it to complete
        result = subprocess.run(command_list, check=True, text=True, capture_output=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\n Error executing command!", file=sys.stderr)
        print(f"Error Code: {e.returncode}", file=sys.stderr)
        print(f"Details: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def main():
    print("=== Azure CLI and Resource Governance Demo ===")
    # 1. Capture dynamic input from the CLI user
    rg_name = input("Enter Resource Group Name [rg-governance-demo-01]: ").strip() or "rg-governance-demo-01"
    location = input("Enter Azure Region [eastus]: ").strip() or "eastus"

    # Generate uique storage account name
    random_number = random.randint(1000, 9999)
    storage_name = f"stgovdemo{random_number}"

    print(f"\nConfiguration set:")
    print(f"- Resource Group: {rg_name}")
    print(f"- Location: {location}")
    print(f"- Storage Name: {storage_name}\n")

    # 2. Create the Resource Group
    print("=== 2. Resource Group Management ===")
    create_rg_cmd = ["az", "group", "create", "--name", rg_name, "--location", location, "--output", "json"]
    run_az_command(create_rg_cmd)

    # 3. Create the Storage Account
    print("=== 3. Resource Creation ===")
    create_storage_cmd = [
        "az", "storage", "account", "create",
        "--name", storage_name,
        "--resource-group", rg_name,
        "--location", location,
        "--sku", "Standard_LRS",
        "--kind", "StorageV2",
        "--output", "table"
    ]
    run_az_command(create_storage_cmd)

    # 4. Tag the Storage Account
    print("=== 4. Resource Tagging ===")
    tag_storage_cmd = [
        "az", "storage", "account", "update",
        "--name", storage_name,
        "--resource-group", rg_name,
        "--tags", "Environment=Dev", "Owner=SRE",
        "--output", "table"
    ]
    run_az_command(tag_storage_cmd)

    # 5. Query the resources
    print("=== 5. Query Resources ===")
    query_cmd = ["az", "resource", "list", "--tag", "Environment=Dev", "--output", "table"]
    run_az_command(query_cmd)

    # 6. Output cleanup instructions
    print("=== 6. Resource Group Cleanup ===")
    print("To delete everything created by this app, run: ")
    print(f"az group delete --name {rg_name} --no-wait --yes")

if __name__ == "__main__":
    main()
