import cv2
import requests
import json
from datetime import datetime, timedelta, date
import os
from pathlib import Path
import logging
from typing import Optional, Dict, Any
import time
from face_recognizer_module import FaceRecognizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('face_detection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FaceDetectionSystem:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.face_recognizer = FaceRecognizer()
        self.check_interval = self.config.get('check_interval_seconds', 5)
        self.attendance_cache_file = "attendance_cache.json"
        self.attendance_cache = self._load_attendance_cache()
        self.last_checkin_times = {}  # Track last check-in time per employee
        self.last_log_type = {}       # Track last IN/OUT per employee
        self.shift_info = {}          # employee_code -> {start, end}
        self.present_employees = set()
        self.last_seen_times = {}     # employee_code -> last seen timestamp
        self.shift_type_name = "morning"  # You can make this dynamic if needed
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Validate required configuration
            required_fields = ['service_account', 'erp_url']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required configuration field: {field}")
                    
            if 'api_key' not in config['service_account'] or 'api_secret' not in config['service_account']:
                raise ValueError("Missing API credentials in service_account configuration")
                
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {config_path} not found!")
            raise

    def _load_attendance_cache(self):
        try:
            with open(self.attendance_cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_attendance_cache(self):
        with open(self.attendance_cache_file, 'w') as f:
            json.dump(self.attendance_cache, f)
        print("attendance_cache.json saved!")

    def update_attendance(self, employee_code):
        today = str(date.today())
        now = datetime.now().strftime("%H:%M:%S")
        if today not in self.attendance_cache:
            self.attendance_cache[today] = {}
        if employee_code not in self.attendance_cache[today]:
            # First detection: create IN and OUT checkin
            self.attendance_cache[today][employee_code] = {"in_time": now, "out_time": now, "in_id": None, "out_id": None}
            self._save_attendance_cache()
            # Create IN checkin in ERPNext
            in_id = self.create_employee_checkin(employee_code, now, "IN")
            # Create OUT checkin in ERPNext (initially same as IN)
            out_id = self.create_employee_checkin(employee_code, now, "OUT")
            self.attendance_cache[today][employee_code]["in_id"] = in_id
            self.attendance_cache[today][employee_code]["out_id"] = out_id
        else:
            # Update OUT time and OUT checkin in ERPNext
            self.attendance_cache[today][employee_code]["out_time"] = now
            out_id = self.attendance_cache[today][employee_code].get("out_id")
            if not out_id:
                # If missing, create a new OUT checkin and store its ID
                out_id = self.create_employee_checkin(employee_code, now, "OUT")
                self.attendance_cache[today][employee_code]["out_id"] = out_id
            else:
                self.update_employee_checkin(employee_code, now, "OUT", out_id)
        self._save_attendance_cache()

    def create_employee_checkin(self, employee_code, check_time, log_type):
        headers = {
            "Authorization": f"token {self.config['service_account']['api_key']}:{self.config['service_account']['api_secret']}",
            "Content-Type": "application/json"
        }
        payload = {
            "employee": employee_code,
            "log_type": log_type,
            "time": f"{date.today()} {check_time}"
        }
        try:
            resp = requests.post(f"{self.config['erp_url']}/api/resource/Employee Checkin", json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get('data', {}).get('name')
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to create {log_type} checkin for {employee_code}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
                print("ERPNext error response:", e.response.text)
            return None
        except Exception as e:
            logger.error(f"Failed to create {log_type} checkin for {employee_code}: {e}")
            return None

    def update_employee_checkin(self, employee_code, check_time, log_type, checkin_id):
        if not checkin_id:
            # If no ID, create a new OUT checkin
            return self.create_employee_checkin(employee_code, check_time, log_type)
        headers = {
            "Authorization": f"token {self.config['service_account']['api_key']}:{self.config['service_account']['api_secret']}",
            "Content-Type": "application/json"
        }
        payload = {
            "time": f"{date.today()} {check_time}"
        }
        try:
            resp = requests.put(f"{self.config['erp_url']}/api/resource/Employee Checkin/{checkin_id}", json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            return checkin_id
        except requests.exceptions.HTTPError as e:
            # Fallback: if 404, create a new OUT checkin and update cache
            if e.response is not None and e.response.status_code == 404:
                logger.error(f"OUT checkin ID {checkin_id} not found for {employee_code}, creating new OUT checkin.")
                new_id = self.create_employee_checkin(employee_code, check_time, log_type)
                # Update cache with new OUT checkin ID
                today = str(date.today())
                if today in self.attendance_cache and employee_code in self.attendance_cache[today]:
                    self.attendance_cache[today][employee_code]["out_id"] = new_id
                    self._save_attendance_cache()
                return new_id
            else:
                logger.error(f"Failed to update OUT checkin for {employee_code}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response content: {e.response.text}")
                return None
        except Exception as e:
            logger.error(f"Failed to update OUT checkin for {employee_code}: {e}")
            return None

    def can_check_in(self, employee_code: str) -> bool:
        """Check if enough time has passed since last check-in."""
        current_time = time.time()
        last_checkin = self.last_checkin_times.get(employee_code, 0)
        return (current_time - last_checkin) >= self.check_interval

    def get_next_log_type(self, employee_code: str) -> str:
        last_type = self.last_log_type.get(employee_code, "OUT")
        return "IN" if last_type == "OUT" else "OUT"

    def send_to_erp(self, employee_code: str, log_type: str = "IN") -> bool:
        """Send check-in/out data to ERPNext."""
        if not self.can_check_in(employee_code):
            logger.info(f"Skipping check-in for {employee_code} - too soon since last check-in")
            return False

        checkin_payload = {
            "employee": employee_code,
            "log_type": log_type,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        headers = {
            "Authorization": f"token {self.config['service_account']['api_key']}:{self.config['service_account']['api_secret']}",
            "Content-Type": "application/json"
        }

        try:
            # Create Employee Checkin
            logger.info(f"Attempting to create check-in record for employee {employee_code}")
            checkin_response = requests.post(
                f"{self.config['erp_url']}/api/resource/Employee Checkin",
                json=checkin_payload,
                headers=headers,
                timeout=10
            )
            checkin_response.raise_for_status()
            logger.info(f"Successfully created check-in record: {checkin_response.json()}")

            # Update last check-in time
            self.last_checkin_times[employee_code] = time.time()
            self.last_log_type[employee_code] = log_type
            logger.info(f"Successfully recorded check-in for employee {employee_code}")
            return True

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to ERPNext server at {self.config['erp_url']}: {str(e)}")
            logger.error("Please check if the ERPNext server is running and accessible")
            return False
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timed out while connecting to ERPNext: {str(e)}")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response content: {e.response.text}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to record check-in: {str(e)}")
            return False

    def fetch_shift_info(self, employee_code: str) -> Optional[Dict[str, str]]:
        """Fetch shift start and end time for the employee from ERPNext."""
        headers = {
            "Authorization": f"token {self.config['service_account']['api_key']}:{self.config['service_account']['api_secret']}",
            "Content-Type": "application/json"
        }
        try:
            # Fetch employee doc
            emp_url = f"{self.config['erp_url']}/api/resource/Employee/{employee_code}"
            emp_resp = requests.get(emp_url, headers=headers, timeout=10)
            emp_resp.raise_for_status()
            emp_data = emp_resp.json()
            shift_type = emp_data['data'].get('shift_type') or emp_data['data'].get('default_shift')
            if not shift_type:
                logger.warning(f"No shift type assigned for {employee_code}")
                return None
            # Fetch shift type doc
            shift_url = f"{self.config['erp_url']}/api/resource/Shift Type/{shift_type}"
            shift_resp = requests.get(shift_url, headers=headers, timeout=10)
            shift_resp.raise_for_status()
            shift_data = shift_resp.json()
            start = shift_data['data'].get('start_time')
            end = shift_data['data'].get('end_time')
            if start and end:
                return {"start": start, "end": end}
            else:
                logger.warning(f"Shift times not found for {employee_code} shift {shift_type}")
                return None
        except Exception as e:
            logger.error(f"Error fetching shift info for {employee_code}: {str(e)}")
            return None

    def run(self):
        """Main loop for face detection and check-in processing."""
        cap = cv2.VideoCapture(self.config.get('camera_id', 0))
        
        try:
            while True:
                now = datetime.now()
                ret, frame = cap.read()
                if not ret:
                    logger.error("Failed to grab frame")
                    break

                # Recognize faces in the frame
                employee_code = self.face_recognizer.recognize_faces(frame)
                detected_now = set()
                if employee_code:
                    detected_now.add(employee_code)
                    self.update_attendance(employee_code)  # Always update cache on detection
                    # Fetch shift info if not already cached
                    if employee_code not in self.shift_info:
                        shift = self.fetch_shift_info(employee_code)
                        if shift:
                            self.shift_info[employee_code] = shift
                    # Update last seen time
                    self.last_seen_times[employee_code] = now
                    # Display status message on frame
                    status_color = (0, 255, 0)
                    status_text = f"Detected {employee_code}"
                    cv2.putText(frame, f"Employee {employee_code} - {status_text}", 
                              (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
                # Check for employees to mark OUT at shift end
                for emp in list(self.present_employees):
                    shift = self.shift_info.get(emp)
                    if not shift:
                        continue
                    shift_end = datetime.combine(now.date(), datetime.strptime(shift['end'], "%H:%M:%S").time())
                    grace_end = shift_end + timedelta(hours=2)
                    if now >= grace_end:
                        # Only mark OUT if not already OUT
                        if self.last_log_type.get(emp) != "OUT":
                            success = self.send_to_erp(emp, log_type="OUT")
                            if success:
                                self.last_log_type[emp] = "OUT"
                                self.present_employees.remove(emp)
                                logger.info(f"Marked OUT for {emp} at shift end with grace period {grace_end}")
                # Draw face boxes and names
                self.face_recognizer.draw_face_boxes(frame)
                
                # Display the frame
                cv2.imshow('Face Detection', frame)
                
                # Break loop on 'q' press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        finally:
            cap.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        face_system = FaceDetectionSystem()
        face_system.run()
    except Exception as e:
        logger.error(f"System error: {str(e)}") 