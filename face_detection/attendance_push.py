import json
import requests
from datetime import date
import logging

def push_attendance():
    with open('attendance_cache.json', 'r') as f:
        attendance_cache = json.load(f)
    with open('config.json', 'r') as f:
        config = json.load(f)
    today = str(date.today())
    headers = {
        "Authorization": f"token {config['service_account']['api_key']}:{config['service_account']['api_secret']}",
        "Content-Type": "application/json"
    }
    erp_url = config['erp_url']
    for emp, times in attendance_cache.get(today, {}).items():
        payload = {
            "employee": emp,
            "attendance_date": today,
            "in_time": times["in_time"],
            "out_time": times["out_time"],
            "status": "Present"
        }
        try:
            resp = requests.post(f"{erp_url}/api/resource/Attendance", json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            print(f"Attendance pushed for {emp}: {payload}")
        except Exception as e:
            print(f"Failed to push attendance for {emp}: {e}")
    # Clear cache for today
    attendance_cache[today] = {}
    with open('attendance_cache.json', 'w') as f:
        json.dump(attendance_cache, f)

if __name__ == "__main__":
    push_attendance() 