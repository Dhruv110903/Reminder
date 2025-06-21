import streamlit as st
from datetime import datetime
import uuid
import pandas as pd
from pyairtable import Api
from dotenv import load_dotenv
import pytz
import os

load_dotenv()

# -------- TIMEZONE SETUP -------- #
IST = pytz.timezone('Asia/Kolkata')

# -------- CONFIG -------- #
AIRTABLE_PERSONAL_ACCESS_TOKEN = os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

# -------- AUTHENTICATION CONFIG -------- #
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")  # Default username
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "password123")  # Default password

# -------- AUTHENTICATION FUNCTION -------- #
def check_authentication():
    """Simple authentication system"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔐 Login Required")
        st.markdown("Please enter your credentials to access the Email Reminder System.")
        st.markdown("Username- admin, password= admin")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_submitted = st.form_submit_button("Login")
            
            if login_submitted:
                if username == AUTH_USERNAME and password == AUTH_PASSWORD:
                    st.session_state.authenticated = True
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials. Please try again.")
        
        return False
    
    return True

def logout():
    """Logout function"""
    st.session_state.authenticated = False
    st.rerun()

table = Api(AIRTABLE_PERSONAL_ACCESS_TOKEN).table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)

def convert_to_ist(dt):
    """Convert datetime to IST timezone"""
    if dt.tzinfo is None:
        return IST.localize(dt)
    else:
        return dt.astimezone(IST)

# -------- AIRTABLE HELPERS -------- #
def airtable_append_reminder(reminder_id, email, subject, message, reminder_time, status="Pending"):
    reminder_time_ist = convert_to_ist(reminder_time)
    table.create({
        "ReminderID": reminder_id,
        "Email": email,
        "Subject": subject,
        "Message": message,
        "ReminderTime": reminder_time_ist.isoformat(),
        "Status": status
    })

def airtable_read_reminders():
    return table.all()

# -------- STREAMLIT UI -------- #
# Check authentication first
if not check_authentication():
    st.stop()

# Configure sidebar to be collapsed by default
st.set_page_config(initial_sidebar_state="collapsed")

# Add logout button in sidebar
with st.sidebar:
    st.markdown("---")
    if st.button("🚪 Logout"):
        logout()

st.title("📧 Reminder system")
st.markdown("Set a reminder and receive an email when it's due.")

# # Display current IST time
# current_ist = get_ist_now()
# st.info(f"🕒 Current IST Time: {current_ist.strftime('%Y-%m-%d %H:%M:%S')}")

# -------- REMINDER FORM -------- #
with st.form("reminder_form"):
    email = st.text_input("Your Email Address")
    subject = st.text_input("Subject")
    message = st.text_area("Reminder Message")
    date = st.date_input("Date")
    time = st.time_input("Time")
    submitted = st.form_submit_button("Set Reminder")

    if submitted:
        if not email or not subject or not message:
            st.error("Please fill in all fields.")
        else:
            # Create naive datetime and treat as IST
            reminder_time = datetime.combine(date, time)
            reminder_time_ist = IST.localize(reminder_time)
            reminder_id = str(uuid.uuid4())
            
            # Store the reminder in Airtable
            airtable_append_reminder(reminder_id, email, subject, message, reminder_time_ist, status="Pending")
            st.success(f"Reminder set for {reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')}. It will be sent automatically when due.")

# -------- DISPLAY REMINDERS -------- #
st.markdown("---")
st.subheader("📅 Scheduled Reminders")

records = airtable_read_reminders()
if records:
    now_ist = get_ist_now()
    display = []
    for r in records:
        f = r.get("fields", {})
        reminder_time_str = f.get("ReminderTime", "")
        try:
            # Parse stored time and convert to IST
            reminder_time = datetime.fromisoformat(reminder_time_str.replace('Z', '+00:00'))
            reminder_time_ist = convert_to_ist(reminder_time)
            
            time_left = reminder_time_ist - now_ist
            if time_left.total_seconds() > 0:
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if days > 0:
                    time_left_str = f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    time_left_str = f"{hours}h {minutes}m"
                else:
                    time_left_str = f"{minutes}m"
            else:
                time_left_str = "Due/Overdue"
                
            # Format display time in IST
            display_time = reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')
        except Exception as e:
            time_left_str = "Invalid time"
            display_time = reminder_time_str

        display.append({
            "Email": f.get("Email", ""),
            "Subject": f.get("Subject", ""),
            "Reminder Time": display_time,
            "Time Left": time_left_str,
            "Status": f.get("Status", "")
        })

    # Sort by reminder time
    display.sort(key=lambda x: x.get("Reminder Time", ""))
    df = pd.DataFrame(display)
    st.dataframe(df, use_container_width=True)
else:
    st.info("No reminders found.")
