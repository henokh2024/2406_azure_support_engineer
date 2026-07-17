import time
import requests
from fastapi import FastAPI, BackgroundTasks, Response
import uvicorn

app = FastAPI(title="SRE Metric Alerts & Action Group Demo App")

# SRE Thresholds (baselines)
DYNAMIC_UPPER_LIMIT = 80.0
DYNAMIC_LOWER_LIMIT = 5.0
ACTION_GROUP_WEBHOOK_URL = "http://localhost:8000/webhook"

# Simulated active system state
current_cpu_load = 15.0  # normal baseline

def run_cpu_evaluation():
    """Simulates Azure Monitor checking VM CPU metrics and calling the Action Group webhook if anomalous."""
    global current_cpu_load
    print(f"\n[AZURE MONITOR] Evaluating CPU Metric: {current_cpu_load}% (Normal range: {DYNAMIC_LOWER_LIMIT}% - {DYNAMIC_UPPER_LIMIT}%)")
    
    if current_cpu_load > DYNAMIC_UPPER_LIMIT:
        print(f"[AZURE MONITOR] [ALERT FIRED] CPU load {current_cpu_load}% exceeds upper dynamic limit {DYNAMIC_UPPER_LIMIT}%")
        # Trigger Action Group Webhook
        payload = {
            "alertName": "alert-cpu-dynamic-01",
            "status": "Fired",
            "metricName": "Percentage CPU",
            "currentValue": current_cpu_load,
            "threshold": DYNAMIC_UPPER_LIMIT,
            "actionGroup": "ag-sreoncall-01",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        try:
            requests.post(ACTION_GROUP_WEBHOOK_URL, json=payload)
        except Exception as e:
            print(f"[AZURE MONITOR] Failed to route alert notification: {e}")
            
    elif current_cpu_load < DYNAMIC_LOWER_LIMIT:
        print(f"[AZURE MONITOR] [ALERT FIRED] CPU load {current_cpu_load}% is below lower dynamic limit {DYNAMIC_LOWER_LIMIT}%")
        payload = {
            "alertName": "alert-cpu-dynamic-01",
            "status": "Fired",
            "metricName": "Percentage CPU",
            "currentValue": current_cpu_load,
            "threshold": DYNAMIC_LOWER_LIMIT,
            "actionGroup": "ag-sreoncall-01",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        try:
            requests.post(ACTION_GROUP_WEBHOOK_URL, json=payload)
        except Exception as e:
            print(f"[AZURE MONITOR] Failed to route alert notification: {e}")
    else:
        print("[AZURE MONITOR] CPU load is within normal operating limits. Alert status: Resolved")

@app.get("/")
def read_root():
    return {"status": "healthy", "current_cpu_load": current_cpu_load}

@app.get("/metrics")
def get_metrics():
    content = f"""# HELP vm_cpu_utilization Percentage CPU utilization of the host virtual machine.
# TYPE vm_cpu_utilization gauge
vm_cpu_utilization {current_cpu_load}
"""
    return Response(content=content, media_type="text/plain")

@app.get("/spike")
def trigger_spike(background_tasks: BackgroundTasks):
    """Triggers an artificial CPU load spike and runs alert evaluation."""
    global current_cpu_load
    current_cpu_load = 94.5
    print("\n[APP] Received heavy request load! Simulating CPU spike...")
    background_tasks.add_task(run_cpu_evaluation)
    return {"message": "CPU load spike triggered", "new_cpu_load": current_cpu_load}

@app.get("/drop")
def trigger_drop(background_tasks: BackgroundTasks):
    """Triggers an artificial CPU drop (e.g. idle server) and runs alert evaluation."""
    global current_cpu_load
    current_cpu_load = 1.5
    print("\n[APP] Server entered deep idle state...")
    background_tasks.add_task(run_cpu_evaluation)
    return {"message": "CPU load drop triggered", "new_cpu_load": current_cpu_load}

@app.get("/reset")
def trigger_reset(background_tasks: BackgroundTasks):
    """Resets CPU load to baseline."""
    global current_cpu_load
    current_cpu_load = 15.0
    print("\n[APP] Restoring baseline load...")
    background_tasks.add_task(run_cpu_evaluation)
    return {"message": "CPU load reset to baseline", "new_cpu_load": current_cpu_load}

@app.post("/webhook")
def action_group_webhook(payload: dict):
    """Mock Action Group Webhook receiver."""
    print("\n================== ACTION GROUP NOTIFICATION ==================")
    print(f"ALERT SIGNAL : {payload['alertName']} is {payload['status'].upper()}!")
    print(f"RESOURCE     : vm-appserver-prod-01")
    print(f"METRIC       : {payload['metricName']} = {payload['currentValue']}% (Threshold: {payload['threshold']}%)")
    print(f"ACTION GROUP : {payload['actionGroup']} dispatched notification to: sre-oncall@company.com")
    print("===============================================================")
    return {"status": "Notification routed"}

if __name__ == "__main__":
    print("Starting SRE Metric Alerts & Action Group App...")
    uvicorn.run(app, host="0.0.0.0", port=8000)