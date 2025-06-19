import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
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
load_dotenv()

# -------- CONFIG -------- #
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

AIRTABLE_PERSONAL_ACCESS_TOKEN = "patcaeugTNWcUq9PJ.f8bf988d3573c623eec345fd8bbbf52f4f69a555bc44f3b820e773418e33a49a"
AIRTABLE_BASE_ID = "app8hL7GbcrLutTp2"       # from https://airtable.com/api
AIRTABLE_TABLE_NAME = "Reminders"

table = Table(AIRTABLE_PERSONAL_ACCESS_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

# -------- SCHEDULER SETUP -------- #
scheduler = BackgroundScheduler()
scheduler.start()

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
    table.create({
        "ReminderID": reminder_id,
        "Email": email,
        "Subject": subject,
        "Message": message,
        "ReminderTime": reminder_time.isoformat(),
        "Status": status
    })

def airtable_read_reminders():
    return table.all()

def airtable_update_status(record_id, new_status):
    table.update(record_id, {"Status": new_status})

# -------- SCHEDULER JOB -------- #
def schedule_reminder(reminder_id, reminder_time, subject, message, email):
    def job():
        send_email(subject, message, email)
        print(f"✅ Sent reminder to {email} at {reminder_time}")
        # Find record by ReminderID and update status
        records = airtable_read_reminders()
        for rec in records:
            if rec['fields'].get('ReminderID') == reminder_id:
                airtable_update_status(rec['id'], "Sent")
                break

    scheduler.add_job(job, 'date', run_date=reminder_time, id=reminder_id, replace_existing=True)
    airtable_append_reminder(reminder_id, email, subject, message, reminder_time, status="Pending")

# -------- STREAMLIT UI -------- #
st.title("📧 Email Reminder System (Airtable Backend)")
st.markdown("Set a reminder and receive an email at the specified time.")

with st.form("reminder_form"):
    email = st.text_input("Your Email Address")
    subject = st.text_input("Subject")
    message = st.text_area("Reminder Message")
    date = st.date_input("Date")
    time = st.time_input("Time")
    submitted = st.form_submit_button("Set Reminder")

    if submitted:
        reminder_time = datetime.combine(date, time)
        reminder_id = str(uuid.uuid4())
        schedule_reminder(reminder_id, reminder_time, subject, message, email)
        st.success(f"Reminder set for {reminder_time.strftime('%Y-%m-%d %H:%M')}")

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
    now = datetime.now()
    display = []
    for r in records:
        f = r.get("fields", {})
        reminder_time_str = f.get("ReminderTime", "")
        try:
            reminder_time = datetime.fromisoformat(reminder_time_str)
            time_left = reminder_time - now
            time_left_str = str(time_left).split('.')[0] if time_left.total_seconds() > 0 else "Past due"
        except Exception:
            time_left_str = "Invalid or unknown"

        display.append({
            "Email": f.get("Email", ""),
            "Subject": f.get("Subject", ""),
            "ReminderTime": reminder_time_str,
            "Time Left": time_left_str,
            "Status": f.get("Status", "")
        })

    df = pd.DataFrame(display)
    st.dataframe(df)
else:
    st.info("No reminders found.")