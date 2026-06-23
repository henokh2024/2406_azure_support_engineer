"""
Python Script: log_processor.py (Starter Code)
Instructions:
Complete the functions below to parse the 'logs.txt' file, categorize requests,
filter slow requests, and display unique client IP statistics using Python collections.
"""

def parse_log_line(line):
    """
    Parses a single log line in Common Log Format.
    Example line:
    192.168.1.10 - - [10/Jun/2026:10:15:30 +0000] "GET /api/v1/users HTTP/1.1" 200 45

    Returns a dictionary of parsed parts:
    {
        "ip": "192.168.1.10",
        "method": "GET",
        "path": "/api/v1/users",
        "status": 200,
        "latency": 45
    }
    """
    # TODO: Split the log line and extract the IP, Method, Path, Status Code, and Latency (last element).
    # Tip: Use line.split() and string slicing. Remember to cast status and latency to integers!
    pass

def analyze_logs(file_path):
    """
    Reads the logs file, parses each line, and aggregates metrics using lists, sets, and dicts.
    """
    all_requests = []
    unique_ips = set()
    status_counts = {}
    slow_requests = []

    # TODO: Open the file and process it line by line
    # For each line:
    # 1. Parse it using parse_log_line()
    # 2. Add the parsed request to all_requests (list)
    # 3. Add the client IP to unique_ips (set)
    # 4. Increment the status code counts in status_counts (dict)
    # 5. If latency is greater than 100ms, add to slow_requests (list)

    print("=========================================")
    print("SRE LOG ANALYSIS SUMMARY REPORT")
    print("=========================================")
    print(f"Total Requests Processed: {len(all_requests)}")
    print(f"Unique Client IPs: {len(unique_ips)}")
    print(f"HTTP Status Code Breakdown: {status_counts}")
    print(f"Slow Requests (>100ms) Count: {len(slow_requests)}")
    print("-----------------------------------------")
    print("Detailed List of Unique Client IPs:")
    # TODO: Print sorted list of unique client IPs
    
    print("\nDetailed List of Slow Requests:")
    # TODO: Print the path and latency of each slow request

if __name__ == "__main__":
    import os
    # Find logs.txt relative to this script
    logs_file = os.path.join(os.path.dirname(__file__), "logs.txt")
    if os.path.exists(logs_file):
        analyze_logs(logs_file)
    else:
        print(f"Error: {logs_file} not found. Please run this script in its local folder.")

