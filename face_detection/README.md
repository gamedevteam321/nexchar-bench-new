# Face Detection Attendance System

This system automatically detects employee faces and marks attendance in ERPNext using a dedicated service account.

## Prerequisites

- Python 3.7 or higher
- Webcam or IP camera
- ERPNext instance with API access
- Service account in ERPNext with appropriate permissions

## Service Account Setup

1. Create a service account in ERPNext:
   - Create a new user (e.g., face.attendance@nexchar.com)
   - Assign minimal permissions:
     - Read + Create on Employee Checkin
     - Optional: Read on Employee
   - Generate API key and secret for this user
   - Note: This single service account will be used by all face detection devices

2. Configure the system:
   - Update `config.json` with the service account credentials
   - Set the correct ERP URL
   - Adjust camera settings if needed

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Add employee faces:
   - Create a `faces` directory
   - Add employee face images in the format: `employee_code.jpg`
   - Each employee should have a clear, front-facing photo

## Usage

1. Start the face detection system:
```bash
python main.py
```

2. The system will:
   - Access your webcam
   - Detect faces in real-time
   - Match faces to employee records
   - Send check-in/out data to ERPNext using the service account
   - Display detection status on screen

3. Press 'q' to quit the application

## Security Notes

- The service account should have minimal required permissions
- Keep API credentials secure and never commit them to version control
- Regularly rotate the service account API key
- Monitor system logs for any unauthorized access attempts
- Use HTTPS for ERPNext communication in production

## Troubleshooting

1. Camera not detected:
   - Check camera connection
   - Verify camera permissions
   - Update camera_id in config.json

2. Face detection issues:
   - Ensure good lighting
   - Check camera focus
   - Update face images if needed

3. API connection errors:
   - Verify service account credentials
   - Check network connection
   - Confirm ERPNext server is running
   - Verify service account permissions

## Support

For issues or questions, please contact your system administrator. 