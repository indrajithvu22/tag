import gspread
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os

app = Flask(__name__)

# --- Google Sheets Configuration ---
# IMPORTANT: Replace this with your actual Google Sheet ID
SPREADSHEET_ID = '10Ij202XqY_j2YiIqGx4XLnrjMLrm5HTWCVPKMkGQ52k' 
CREDENTIALS_FILE = 'credentials.json'

# Global variables to hold sheet objects
registration_worksheet = None
attendance_worksheet = None

try:
    # Authenticate with the service account
    gc = gspread.service_account(filename=CREDENTIALS_FILE)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    
    # 1. Registration Sheet (for web form and lookup)
    registration_worksheet = spreadsheet.sheet1
    if not registration_worksheet.row_values(1):
        registration_worksheet.append_row(['Name', 'Registration Number', 'RFID Tag ID', 'Web Timestamp'])

    # 2. Attendance Sheet (for ESP32 check-ins and IN/OUT status)
    ATTENDANCE_SHEET_NAME = 'Attendance'
    try:
        attendance_worksheet = spreadsheet.worksheet(ATTENDANCE_SHEET_NAME)
    except gspread.WorksheetNotFound:
        # Create the attendance sheet if it doesn't exist
        attendance_worksheet = spreadsheet.add_worksheet(title=ATTENDANCE_SHEET_NAME, rows=100, cols=5)
        
    if not attendance_worksheet.row_values(1):
        # Header for the full IN/OUT attendance log
        attendance_worksheet.append_row(['Date & Time', 'Name', 'Registration Number', 'RFID Tag ID', 'Status (IN/OUT)']) 

except Exception as e:
    print(f"FATAL ERROR: Failed to connect to Google Sheets. Check your SPREADSHEET_ID, credentials.json, and sharing settings. Details: {e}")
    registration_worksheet = None
    attendance_worksheet = None

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the attractive main registration form."""
    return render_template('index.html')

# 1. Route for Web Form Registration (Prevents Duplicates by Reg. Number)
@app.route('/register', methods=['POST'])
def register():
    """Handles web form submission, checks for duplicates, and writes to Registration sheet."""
    if registration_worksheet is None:
        return jsonify({"message": "Server error: Database connection failed."}), 500

    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        reg_number = data.get('regNumber', '').strip().upper() 
        
        if not name or not reg_number:
            return jsonify({"message": "Name and Registration Number are required."}), 400

        # Check for Duplicate Registration Number (Column B, index 2)
        reg_numbers_list = registration_worksheet.col_values(2)[1:] # [1:] skips the header
        
        if reg_number in reg_numbers_list:
            print(f"DUPLICATE FOUND: Registration Number {reg_number} already exists.")
            return jsonify({"message": f"Registration Number {reg_number} is already registered. Avoid duplicate registration."}), 409

        # Append New Data: Name, Reg. Number, (Blank RFID Tag ID), Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [name, reg_number, '', timestamp]

        registration_worksheet.append_row(new_row)
        
        print(f"SUCCESS: New web registration for {name} ({reg_number}) recorded.")
        return jsonify({
            "message": "Registration successful! Your tag can now be assigned.",
            "name": name,
            "regNumber": reg_number
        }), 200

    except Exception as e:
        print(f"An error occurred during registration: {e}")
        return jsonify({"message": "An unexpected server error occurred during registration."}), 500

# 2. Route for ESP32 Attendance System (IN/OUT Logic)
@app.route('/attendance', methods=['POST'])
def record_attendance():
    """
    Handles RFID scans from the ESP32, determines IN or OUT status based on the last recorded action, 
    and records the full attendance entry.
    """
    if registration_worksheet is None or attendance_worksheet is None:
        return jsonify({"status": "error", "message": "Server database setup failed."}), 500

    try:
        data = request.get_json()
        rfid_tag_id = data.get('rfid_tag', '').strip().upper() 

        if not rfid_tag_id:
            return jsonify({"status": "error", "message": "No RFID Tag ID provided."}), 400
        
        # --- 1. Look up Registration Info (Name and Reg. Number) ---
        
        # Assuming RFID Tag ID is in column C (index 3) of the Registration sheet
        tag_ids = registration_worksheet.col_values(3)
        
        try:
            # Find the row index where the RFID Tag ID matches
            row_index = tag_ids.index(rfid_tag_id) + 1 
        except ValueError:
            print(f"ATTENDANCE FAIL: Unknown RFID Tag ID: {rfid_tag_id}")
            return jsonify({"status": "failure", "message": "Unregistered tag."}), 404

        # Retrieve Name (Col A) and Registration Number (Col B)
        row_data = registration_worksheet.row_values(row_index)
        name = row_data[0]       
        reg_number = row_data[1] 
        
        # --- 2. Determine IN or OUT Status ---
        
        # Fetch all attendance records to check the last action for this user
        attendance_data = attendance_worksheet.get_all_records()
        
        # Filter records for the current user (Reg Number is in column 'Registration Number')
        user_records = [
            record for record in attendance_data 
            if record.get('Registration Number') == reg_number
        ]
        
        new_status = 'IN' # Default status
        if user_records:
            # Check the status of the *most recent* record
            last_status = user_records[-1].get('Status (IN/OUT)')
            
            if last_status == 'IN':
                new_status = 'OUT'
            # If last_status was 'OUT', the new status remains 'IN'

        # --- 3. Record Attendance ---
        
        datetime_now = datetime.now()
        date_time_str = datetime_now.strftime("%Y-%m-%d %H:%M:%S")
        
        attendance_row = [
            date_time_str,      # Date & Time
            name,               # Name
            reg_number,         # Registration Number
            rfid_tag_id,        # RFID Tag ID
            new_status          # Status (IN/OUT)
        ]

        attendance_worksheet.append_row(attendance_row)
        
        print(f"ATTENDANCE SUCCESS: {name} ({reg_number}) marked as {new_status}")
        return jsonify({
            "status": "success",
            "message": f"Attendance recorded: {name} is now marked as {new_status}",
            "time": date_time_str,
            "action": new_status
        }), 200

    except Exception as e:
        print(f"An error occurred during attendance recording: {e}")
        return jsonify({"status": "error", "message": "Internal server error."}), 500

if __name__ == '__main__':
    # Ensure the necessary directories exist
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Run the application
    # host='0.0.0.0' is required for the ESP32 to connect on the local network
    app.run(host='0.0.0.0', debug=True, port=5000)