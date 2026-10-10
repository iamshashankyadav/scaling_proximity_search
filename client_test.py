import time
import requests
import json
import sys

# change this URL whenever you deploy to cloud / other port
BASE_URL = "http://10.1.75.79:5203"

# agar command line se URL pass kre to wo use kr lo
if len(sys.argv) > 1:
    BASE_URL = sys.argv[1].rstrip("/")

print(f"Testing API at: {BASE_URL}\n" + "="*50)

# Sample test cases to run
test_cases = [
    {
        "name": "Center Grid Query (Pharmacy)",
        "params": {"lat": 0.5, "long": 0.5, "cat": "pharmacy", "rad": 0.2, "link": "link.txt"}
    },
    {
        "name": "Corner Query (Bank at 0,0)",
        "params": {"lat": 0.05, "long": 0.05, "cat": "bank", "rad": 0.3}
    },
    {
        "name": "Hospital Search (North-East quadrant)",
        "params": {"lat": 0.75, "long": 0.85, "cat": "hospital", "rad": 0.25}
    },
    {
        "name": "School Search (Small radius)",
        "params": {"lat": 0.33, "long": 0.44, "cat": "school", "rad": 0.15}
    },
    {
        "name": "Cafe Search (POST request test)",
        "params": {"lat": 0.6, "long": 0.2, "cat": "cafe", "rad": 0.3},
        "method": "POST"
    }
]

# 1. Health check
try:
    t0 = time.time()
    res = requests.get(f"{BASE_URL}/health", timeout=3)
    elapsed = (time.time() - t0) * 1000
    print(f"[*] Health Check: Status {res.status_code} ({elapsed:.1f}ms) -> {res.json()}\n")
except Exception as e:
    print(f"[!] Server connect nhi ho pa rha {BASE_URL}: {e}")
    print("[!] Make sure 'python main.py' is running in another terminal!\n")
    sys.exit(1)

# 2. Running test queries
print("Running Sample Queries:\n" + "-"*50)
for idx, tc in enumerate(test_cases, 1):
    method = tc.get("method", "GET")
    name = tc["name"]
    params = tc["params"]
    
    t0 = time.time()
    try:
        if method == "POST":
            resp = requests.post(f"{BASE_URL}/search/", json=params, timeout=5)
        else:
            resp = requests.get(f"{BASE_URL}/search/", params=params, timeout=5)
            
        latency = (time.time() - t0) * 1000
        
        if resp.status_code == 200:
            result_ids = resp.json()
            print(f"[Pass] Test {idx}: {name}")
            print(f"       Method: {method} | Latency: {latency:.2f}ms")
            print(f"       Input:  {params}")
            print(f"       Top 10 IDs: {result_ids}\n")
        else:
            print(f"[Fail] Test {idx}: {name} - Status {resp.status_code}")
            print(f"       Response: {resp.text}\n")
            
    except Exception as err:
        print(f"[Error] Test {idx}: {name} -> {err}\n")

print("="*50)
print("Testing completed!")
