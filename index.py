import streamlit as st
from datetime import datetime, timedelta
import json
import smtplib
import ssl
from email.message import EmailMessage
import os
import uuid
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from pyairtable import Table
from dotenv import load_dotenv
import pytz
load_dotenv()

# -------- TIMEZONE SETUP -------- #
IST = pytz.timezone('Asia/Kolkata')

# -------- CONFIG -------- #
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
AIRTABLE_PERSONAL_ACCESS_TOKEN = os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

table = Table(AIRTABLE_PERSONAL_ACCESS_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)


def convert_to_ist(dt):
    """Convert datetime to IST timezone"""
    if dt.tzinfo is None:
        # If naive datetime, assume it's in IST
        return IST.localize(dt)
    else:
        # If timezone aware, convert to IST
        return dt.astimezone(IST)

#-------- CRON JOB DEBUGGING -------- #
def log_cron_activity(message):
    """Log cron job activity with timestamp"""
    timestamp = get_ist_now().strftime('%Y-%m-%d %H:%M:%S IST')
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    
    # Also try to write to a simple log (if possible)
    try:
        # This will show in Streamlit if the page is visited
        if 'cron_logs' not in st.session_state:
            st.session_state.cron_logs = []
        st.session_state.cron_logs.append(log_message)
        # Keep only last 10 logs
        if len(st.session_state.cron_logs) > 10:
            st.session_state.cron_logs = st.session_state.cron_logs[-10:]
    except:
        pass

# Log every page load
log_cron_activity("Page loaded/accessed")

# -------- EMAIL FUNCTION -------- #
def send_email(subject, body, to):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to

    context = ssl._create_unverified_context()  # for macOS testing
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# -------- AIRTABLE HELPERS -------- #
def airtable_append_reminder(reminder_id, email, subject, message, reminder_time, status="Pending"):
    # Convert reminder_time to IST and store
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

def airtable_update_status(record_id, new_status):
    table.update(record_id, {"Status": new_status})

# -------- CRON JOB FUNCTION -------- #
def check_and_send_due_reminders():
    """
    This function should be called by the cron job every 10 minutes.
    It checks for due reminders and sends them.
    """
    sent_count = 0
    error_count = 0
    
    try:
        current_time_ist = get_ist_now()
        log_cron_activity(f"Checking for due reminders at {current_time_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
        records = airtable_read_reminders()
        
        for record in records:
            fields = record.get('fields', {})
            status = fields.get('Status', '')
            
            # Only process pending reminders
            if status != 'Pending':
                continue
                
            reminder_time_str = fields.get('ReminderTime', '')
            if not reminder_time_str:
                continue
                
            try:
                # Parse the stored time and ensure it's in IST
                reminder_time = datetime.fromisoformat(reminder_time_str.replace('Z', '+00:00'))
                reminder_time_ist = convert_to_ist(reminder_time)
                
                # Check if reminder is due (current IST time >= reminder IST time)
                if current_time_ist >= reminder_time_ist:
                    email = fields.get('Email', '')
                    subject = fields.get('Subject', '')
                    message = fields.get('Message', '')
                    reminder_id = fields.get('ReminderID', '')
                    
                    log_message = f"Sending due reminder to {email} (ID: {reminder_id}) - Due: {reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')}"
                    print(log_message)
                    log_cron_activity(log_message)
                    
                    # Send the email
                    send_email(subject, message, email)
                    
                    # Update status to Sent
                    airtable_update_status(record['id'], "Sent")
                    
                    success_message = f"✅ Successfully sent reminder to {email}"
                    print(success_message)
                    log_cron_activity(success_message)
                    sent_count += 1
                    
            except Exception as e:
                error_message = f"Error processing reminder {fields.get('ReminderID', 'unknown')}: {e}"
                print(error_message)
                log_cron_activity(error_message)
                # Update status to Error
                airtable_update_status(record['id'], "Error")
                error_count += 1
                
    except Exception as e:
        error_message = f"Error in check_and_send_due_reminders: {e}"
        print(error_message)
        log_cron_activity(error_message)
        error_count += 1
        
    return sent_count, error_count

# -------- AUTO-CHECK ON EVERY PAGE LOAD -------- #
# This will automatically check and send due reminders on every page refresh
def auto_check_reminders():
    """Auto-check reminders on page load"""
    try:
        with st.spinner("🔄 Checking for due reminders..."):
            sent_count, error_count = check_and_send_due_reminders()
        
        if sent_count > 0:
            st.success(f"✅ Auto-sent {sent_count} due reminder(s)")
        elif error_count > 0:
            st.warning(f"⚠️ {error_count} error(s) occurred while checking reminders")
        else:
            st.info("ℹ️ No due reminders found")
            
    except Exception as e:
        st.error(f"❌ Auto-check error: {e}")

# -------- STREAMLIT UI -------- #
st.title("📧 Email Reminder System (Auto-send on Refresh)")
st.markdown("Set a reminder and receive an email when it's due. **Reminders are automatically checked and sent on every page refresh!**")

# Display current IST time
current_ist = get_ist_now()
st.info(f"🕒 Current IST Time: {current_ist.strftime('%Y-%m-%d %H:%M:%S')}")

# -------- AUTO-CHECK RUNS HERE -------- #
# This will run on every page load/refresh
auto_check_reminders()

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
            reminder_time_ist = IST.localize(reminder_time)  # Treat input as IST
            reminder_id = str(uuid.uuid4())
            
            # Store the reminder in Airtable
            airtable_append_reminder(reminder_id, email, subject, message, reminder_time_ist, status="Pending")
            st.success(f"Reminder set for {reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')}. It will be sent automatically when due.")

# -------- MANUAL TRIGGER FOR TESTING -------- #
st.markdown("---")
st.subheader("🔧 Manual Trigger (For Additional Testing)")
st.markdown("*This button manually runs the reminder check function (though it also runs automatically on page load)*")
if st.button("Check & Send Due Reminders Now"):
    try:
        sent_count, error_count = check_and_send_due_reminders()
        if sent_count > 0:
            st.success(f"✅ Manual check completed. Sent {sent_count} reminder(s).")
        elif error_count > 0:
            st.warning(f"⚠️ Manual check completed with {error_count} error(s).")
        else:
            st.info("ℹ️ Manual check completed. No due reminders found.")
    except Exception as e:
        st.error(f"Error during manual check: {e}")

# -------- TEST EMAIL -------- #
st.markdown("---")
st.subheader("📨 Test Email Sending")
test_email = st.text_input("Enter email to send test mail", key="test_email")
if st.button("Send Test Email"):
    if not test_email:
        st.warning("Please enter an email address.")
    else:
        try:
            send_email("✅ Test Email from Reminder App",
                       "This is a test email to verify your email setup.",
                       test_email)
            st.success(f"Test email sent to {test_email}")
        except Exception as e:
            st.error(f"Failed to send email: {e}")

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

# -------- ACTIVITY LOGS -------- #
st.markdown("---")
st.subheader("📋 Recent Activity Logs")
if 'cron_logs' in st.session_state and st.session_state.cron_logs:
    for log in reversed(st.session_state.cron_logs[-5:]):  # Show last 5 logs
        st.text(log)
else:
    st.info("No recent activity logs")

# -------- ENHANCED CRON JOB SETUP INSTRUCTIONS -------- #
st.markdown("---")
st.subheader("⚙️ Cron Job Setup Instructions (Optional - Auto-check already enabled)")
st.markdown("""
**Current Status**: ✅ **Auto-check is ENABLED** - Due reminders are automatically checked and sent on every page refresh!

**For additional reliability, you can still set up external cron jobs:**

**Option 1: cron-job.org (Recommended)**
1. Go to https://cron-job.org/en/ and create a free account
2. Create New Cron Job:
   - **URL**: Your Streamlit app URL
   - **Title**: "Email Reminder Auto-Refresh"
   - **Schedule**: `*/10 * * * *` (every 10 minutes)
   - **Enabled**: Check this box

**Option 2: UptimeRobot (Alternative)**
1. Go to https://uptimerobot.com/ and create account
2. Add New Monitor:
   - **Monitor Type**: HTTP(s)
   - **URL**: Your Streamlit app URL
   - **Monitoring Interval**: Every 5 minutes
   
**How it works now:**
- ✅ **Auto-check on page load**: Every time someone visits your app, it automatically checks for due reminders
- ✅ **External cron jobs**: Additional reliability by automatically visiting your app every few minutes
- ✅ **Manual trigger**: Still available for immediate testing

**Benefits of this approach:**
- No dependency on external triggers alone
- Works even if cron jobs fail
- Immediate checking when you visit the app
- Multiple layers of reliability
""")

# Force a small delay and refresh indicator
if st.button("🔄 Refresh Page to Check Reminders Again"):
    st.rerun()
