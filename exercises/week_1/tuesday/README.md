# Lab: Log Processing with Python Collections

## Objectives
- Read and parse a structured text file in Python.
- Apply Python collections (**Lists**, **Sets**, and **Dictionaries**) to aggregate data.
- Implement conditional control flow loops (`for`, `if`) to filter raw events.
- Output aggregated system logs metrics in a structured terminal report.

---

## Scenario
As an SRE on call, you are investigating an application outage. You need to analyze the application's access log (`logs.txt`) to determine the volume of requests, unique client IPs hitting the system, HTTP status code frequencies (especially errors like HTTP 500), and find the endpoints that are experiencing slow latency response times (exceeding 100ms).

---

## Tasks

### Task 1: Complete the Line Parser
1. Navigate to the directory:
2. Open `log_processor.py`.
3. Complete the function `parse_log_line(line)`. It should split the space-separated fields of the Common Log Format line and extract:
   - Client IP (`ip`) -> standard index 0.
   - HTTP Method (`method`) -> index 5 (removing quotes `"`).
   - Target path (`path`) -> index 6.
   - HTTP Status Code (`status`) -> index 8 (cast to `int`).
   - Latency (`latency`) -> index 9 (cast to `int`).

### Task 2: Implement Log File Aggregation
1. Implement the logic in `analyze_logs(file_path)` to read the file line by line.
2. For each line, parse it and aggregate:
   - Add the parsed request dictionary to `all_requests` (list).
   - Add the client IP to `unique_ips` (set) to keep track of unique clients.
   - Count the HTTP status codes in `status_counts` (dictionary where keys are status codes and values are counts).
   - If the request latency exceeds `100`ms, append the request dictionary to `slow_requests` (list).

### Task 3: Output Formatting
1. Complete the code to sort and print all unique client IPs.
2. Complete the code to loop over all `slow_requests` and print their HTTP method, path, latency, and status codes.

---

## Verification
Run your script:
```bash
python log_processor.py
```

Expected output metrics:
- Total Requests Processed: 10
- Unique Client IPs: 5
- HTTP Status Code Breakdown: `{200: 5, 401: 1, 500: 3, 404: 1}`
- Slow Requests count: 3

