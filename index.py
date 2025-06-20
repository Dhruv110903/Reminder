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
    try:
        current_time_ist = get_ist_now()
        print(f"Checking for due reminders at {current_time_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
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
                    
                    print(f"Sending due reminder to {email} (ID: {reminder_id}) - Due: {reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')}")
                    
                    # Send the email
                    send_email(subject, message, email)
                    
                    # Update status to Sent
                    airtable_update_status(record['id'], "Sent")
                    
                    print(f"✅ Successfully sent reminder to {email}")
                    
            except Exception as e:
                print(f"Error processing reminder {fields.get('ReminderID', 'unknown')}: {e}")
                # Update status to Error
                airtable_update_status(record['id'], "Error")
                
    except Exception as e:
        print(f"Error in check_and_send_due_reminders: {e}")

# -------- STREAMLIT UI -------- #
st.title("📧 Email Reminder System (Cron Job + Airtable)")
st.markdown("Set a reminder and receive an email when it's due (checked every 10 minutes by cron job).")

# Display current IST time
current_ist = get_ist_now()
st.info(f"🕒 Current IST Time: {current_ist.strftime('%Y-%m-%d %H:%M:%S')}")

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
            st.success(f"Reminder set for {reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')}. It will be sent when due.")

# -------- MANUAL TRIGGER FOR TESTING -------- #
st.markdown("---")
st.subheader("🔧 Manual Trigger (For Testing)")
st.markdown("*This button manually runs the cron job function to check for due reminders*")
if st.button("Check & Send Due Reminders Now"):
    try:
        check_and_send_due_reminders()
        st.success("Manual check completed. Check the console for details.")
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

# -------- CRON JOB SETUP INSTRUCTIONS -------- #
st.markdown("---")
st.subheader("⚙️ Cron Job Setup Instructions")
st.markdown("""
**To set up the cron job on cron-job.org:**

1. **Create Account**: Go to https://cron-job.org/en/ and create a free account

2. **Create New Cron Job**:
   - Click "Create cronjob"
   - **URL**: Enter your Streamlit app URL + `?cron_trigger=true`
   - **Title**: "Email Reminder Checker"
   - **Schedule**: `*/10 * * * *` (every 10 minutes)
   - **Enabled**: Check this box

3. **Schedule Explanation**:
   - `*/10 * * * *` means: every 10 minutes
   - `*/5 * * * *` means: every 5 minutes (if you want more frequent checks)
   - `0 * * * *` means: every hour at minute 0

4. **Alternative - Manual Trigger**: Use the "Manual Trigger" button above to test the functionality

5. **Monitoring**: Check the cron job logs on cron-job.org to ensure it's running properly
""")

# -------- HANDLE CRON JOB TRIGGER -------- #
# This will be triggered when the cron job calls the URL with ?cron_trigger=true
query_params = st.query_params
if query_params.get('cron_trigger') == 'true':
    st.write("🤖 Cron job triggered - checking for due reminders...")
    try:
        check_and_send_due_reminders()
        st.write("✅ Cron job completed successfully")
    except Exception as e:
        st.write(f"❌ Cron job error: {e}")
