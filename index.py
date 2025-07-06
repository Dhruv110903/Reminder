import streamlit as st
from datetime import datetime, timedelta
import uuid
import pandas as pd
from pyairtable import Api
from dotenv import load_dotenv
import pytz
import os
import random
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import io
# from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import base64
import re

load_dotenv()

# -------- TIMEZONE SETUP -------- #
IST = pytz.timezone('Asia/Kolkata')

# -------- CONFIG -------- #
AIRTABLE_PERSONAL_ACCESS_TOKEN = os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

# -------- AUTHENTICATION CONFIG -------- #
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "admin")

# -------- EMAIL OTP CONFIG -------- #
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# -------- GOOGLE API CONFIG -------- #
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
SUBJECT_FILTER = "ISIN Activated"

# -------- EMAIL FUNCTIONS -------- #
def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

def create_otp_email_template(otp):
    """Create a professional OTP email template"""
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; color: #2c3e50; margin-bottom: 30px; }}
            .otp-box {{ background-color: #3498db; color: white; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0; }}
            .otp-code {{ font-size: 32px; font-weight: bold; letter-spacing: 5px; }}
            .warning {{ background-color: #f39c12; color: white; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .footer {{ text-align: center; color: #7f8c8d; font-size: 12px; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Reminder System Login</h1>
                <h2>One-Time Password (OTP)</h2>
            </div>
            
            <p>Hello,</p>
            <p>You are attempting to log into the Reminder System. Please use the following OTP to complete your login:</p>
            
            <div class="otp-box">
                <div class="otp-code">{otp}</div>
                <p style="margin: 10px 0 0 0; font-size: 14px;">Enter this code in the login form</p>
            </div>
            
            <div class="warning">
                <strong>⚠️ Security Notice:</strong>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li>This OTP expires in <strong>5 minutes</strong></li>
                    <li>Do not share this code with anyone</li>
                    <li>If you didn't request this, please ignore this email</li>
                </ul>
            </div>
            
            <p>If you have any issues, please contact the system administrator.</p>
            
            <div class="footer">
                <p>This is an automated email from Reminder System</p>
                <p>Time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_template

def send_otp_email(to_email, otp):
    """Send OTP via email using SMTP"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        msg['Subject'] = f"🔐 Login OTP: {otp} - Reminder System"
        
        html_content = create_otp_email_template(otp)
        html_part = MIMEText(html_content, 'html')
        
        text_content = f"""
        Reminder System - Login OTP
        
        Your One-Time Password: {otp}
        
        This OTP expires in 5 minutes.
        Do not share this code with anyone.
        
        Time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}
        """
        text_part = MIMEText(text_content, 'plain')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True, "OTP sent successfully to your email!"
        
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

# -------- AUTHENTICATION FUNCTIONS -------- #
def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'credentials_verified' not in st.session_state:
        st.session_state.credentials_verified = False
    if 'otp_sent' not in st.session_state:
        st.session_state.otp_sent = False
    if 'otp_code' not in st.session_state:
        st.session_state.otp_code = None
    if 'otp_expiry' not in st.session_state:
        st.session_state.otp_expiry = None
    if 'login_attempts' not in st.session_state:
        st.session_state.login_attempts = 0
    if 'otp_attempts' not in st.session_state:
        st.session_state.otp_attempts = 0
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Home"

def reset_auth_state():
    """Reset authentication state"""
    st.session_state.authenticated = False
    st.session_state.credentials_verified = False
    st.session_state.otp_sent = False
    st.session_state.otp_code = None
    st.session_state.otp_expiry = None
    st.session_state.otp_attempts = 0

def is_otp_expired():
    """Check if OTP has expired"""
    if st.session_state.otp_expiry is None:
        return True
    return datetime.now() > st.session_state.otp_expiry

def check_authentication():
    """Simplified authentication system with Email OTP"""
    init_session_state()
    
    if st.session_state.authenticated:
        return True
    
    # Check if email configuration is set
    if not SMTP_EMAIL or not SMTP_PASSWORD or not ADMIN_EMAIL:
        st.error("❌ Email configuration missing. Please check your environment variables:")
        st.code("""
        SMTP_EMAIL=your-email@gmail.com
        SMTP_PASSWORD=your-app-password
        ADMIN_EMAIL=your-email@gmail.com
        """)
        st.stop()
    
    st.title("🔐 Login to Reminder System")
    
    # Combined login form
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="admin")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_submitted = st.form_submit_button("🔑 Login", type="primary")
        
        if login_submitted:
            if username == AUTH_USERNAME and password == AUTH_PASSWORD:
                # Credentials verified, send OTP
                with st.spinner("Sending verification email..."):
                    otp = generate_otp()
                    success, message = send_otp_email(ADMIN_EMAIL, otp)
                    
                    if success:
                        st.session_state.credentials_verified = True
                        st.session_state.otp_code = otp
                        st.session_state.otp_sent = True
                        st.session_state.otp_expiry = datetime.now() + timedelta(minutes=5)
                        st.session_state.otp_attempts = 0
                        st.info(f"📧 Verification email sent to your registered email: {ADMIN_EMAIL}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
            else:
                st.session_state.login_attempts += 1
                st.error(f"❌ Invalid credentials. Attempt {st.session_state.login_attempts}/5")
                
                if st.session_state.login_attempts >= 5:
                    st.error("🚫 Too many failed attempts. Please refresh the page and try again later.")
                    st.stop()
    
    # OTP verification form (shown after credentials are verified)
    if st.session_state.credentials_verified and st.session_state.otp_sent and not is_otp_expired():
        st.markdown("---")
        st.subheader("📧 Email Verification")
        st.info(f"Please check your email registered email for the verification code.")
        
        with st.form("otp_form"):
            entered_otp = st.text_input("Enter 6-digit verification code", max_chars=6, placeholder="123456")
            otp_submitted = st.form_submit_button("🔐 Verify", type="primary")
            
            if otp_submitted:
                if entered_otp == st.session_state.otp_code:
                    st.session_state.authenticated = True
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.session_state.otp_attempts += 1
                    st.error(f"❌ Invalid verification code. Attempt {st.session_state.otp_attempts}/3")
                    
                    if st.session_state.otp_attempts >= 3:
                        st.error("🚫 Too many attempts. Please login again.")
                        reset_auth_state()
                        st.rerun()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📧 Resend Code"):
                st.session_state.otp_sent = False
                st.session_state.credentials_verified = False
                st.rerun()
    
    elif st.session_state.credentials_verified and is_otp_expired():
        st.error("⏰ Verification code has expired. Please login again.")
        reset_auth_state()
        st.rerun()
    
    return False

def logout():
    """Logout function"""
    reset_auth_state()
    st.success("👋 Logged out successfully!")
    st.rerun()

# -------- AIRTABLE SETUP -------- #
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
# def airtable_append_reminder(reminder_id, email, subject, message, reminder_time, status="Pending"):
#     reminder_time_ist = convert_to_ist(reminder_time)
#     table.create({
#         "ReminderID": reminder_id,
#         "Email": email,
#         "Subject": subject,
#         "Message": message,
#         "ReminderTime": reminder_time_ist.isoformat(),
#         "Status": status
#     })

def airtable_read_records():
    airtable_records = table.all()
    records = []
    for r in airtable_records:
        f = r.get("fields", {})
        record = {
            "ARN No": f.get("ARN No", ""),
            "ISIN": f.get("ISIN", ""),
            "Security Type": f.get("Security Type", ""),
            "Company Name": f.get("Company Name", ""),
            "ISIN Allotment Date": f.get("ISIN Allotment Date", ""),
            "Company reffered By": f.get("Company reffered By", ""),
            "Email ID": f.get("Email ID", ""),
            "COMPANY SPOC": f.get("COMPANY SPOC", ""),
            "GSTIN": f.get("GSTIN", ""),
            "ADDRESS": f.get("ADDRESS", ""),
            "Bill Amount": f.get("Bill Amount", ""),
            "BILL Date 1": f.get("BILL Date 1", ""),
            "BILL Date 2": f.get("BILL Date 2", ""),
            "BILL Date 3": f.get("BILL Date 3", ""),
            "BILL Date 4": f.get("BILL Date 4", ""),
            "BILL Date 5": f.get("BILL Date 5", ""),
            "BILL Date 6": f.get("BILL Date 6", ""),
            "BILL Date 7": f.get("BILL Date 7", ""),
            "LINK": f.get("LINK", ""),
            "Company Path": f.get("Company Path", "")
        }
        records.append(record)
    return records

# def get_reminders_analytics():
#     """Get analytics for reminders"""
#     records = airtable_read_reminders()
#     now_ist = get_ist_now()
    
#     analytics = {
#         "1_week": [],
#         "1_month": [],
#         "3_months": [],
#         "6_months": [],
#         "6_months_plus": []
#     }
    
#     for r in records:
#         f = r.get("fields", {})
#         reminder_time_str = f.get("ReminderTime", "")
#         try:
#             reminder_time = datetime.fromisoformat(reminder_time_str.replace('Z', '+00:00'))
#             reminder_time_ist = convert_to_ist(reminder_time)
            
#             time_diff = reminder_time_ist - now_ist
#             days_diff = time_diff.days
            
#             reminder_data = {
#                 "email": f.get("Email", ""),
#                 "subject": f.get("Subject", ""),
#                 "reminder_time": reminder_time_ist,
#                 "status": f.get("Status", "")
#             }
            
#             if days_diff <= 7:
#                 analytics["1_week"].append(reminder_data)
#             elif days_diff <= 30:
#                 analytics["1_month"].append(reminder_data)
#             elif days_diff <= 90:
#                 analytics["3_months"].append(reminder_data)
#             elif days_diff <= 180:
#                 analytics["6_months"].append(reminder_data)
#             else:
#                 analytics["6_months_plus"].append(reminder_data)
#         except:
#             continue
    
#     return analytics

# -------- PAGES -------- #
def home_page(gmail_data=None):
    st.title("📧 Company & Bills Database Entry")
    st.markdown("Add a new company & bill record to the database.")
    current_ist = get_ist_now()
    st.caption(f"🕒 Current IST Time: {current_ist.strftime('%Y-%m-%d %H:%M:%S')}")

    selected_entry = None
    if gmail_data:
        st.subheader("📥 Use Gmail Extracted Data")
        options = [f"{d['Company']} | {d['ISIN']} | {d['Instrument']}" for d in gmail_data]
        selected = st.selectbox("Select Extracted Entry", ["--- Select ---"] + options)

        if selected != "--- Select ---":
            selected_entry = next(d for d in gmail_data if f"{d['Company']} | {d['ISIN']} | {d['Instrument']}" == selected)

    # Pre-fill fields if selected_entry exists
    with st.form("record_form"):
        st.subheader("📝 New Record Details")

        col1, col2 = st.columns(2)
        with col1:
            arn_no = st.text_input("ARN No")
            isin = st.text_input("ISIN", value=selected_entry["ISIN"] if selected_entry else "")
            security_type = st.text_input("Security Type", value=selected_entry["Instrument"] if selected_entry else "")
            company_name = st.text_input("Company Name", value=selected_entry["Company"] if selected_entry else "")
            isin_allotment_date = st.date_input("ISIN Allotment Date", value=datetime.now().date())
            company_referred_by = st.text_input("Company Referred By")
            email_id = st.text_input("Email ID")
            company_spoc = st.text_input("COMPANY SPOC")
            gstin = st.text_input("GSTIN")

        with col2:
            address = st.text_area("ADDRESS", height=150)
            bill_amount = st.number_input("Bill Amount", min_value=0.0, step=0.01, format="%.2f")
            bill_date_1 = st.date_input("BILL Date 1", value=datetime.now().date())
            bill_date_2 = st.date_input("BILL Date 2", value=datetime.now().date())
            bill_date_3 = st.date_input("BILL Date 3", value=datetime.now().date())
            bill_date_4 = st.date_input("BILL Date 4", value=datetime.now().date())
            bill_date_5 = st.date_input("BILL Date 5", value=datetime.now().date())
            bill_date_6 = st.date_input("BILL Date 6", value=datetime.now().date())
            bill_date_7 = st.date_input("BILL Date 7", value=datetime.now().date())
            link = st.text_input("LINK")
            company_path = st.text_input("Company Path")

        submitted = st.form_submit_button("➕ Add Record")

        if submitted:
            if not arn_no or not company_name:
                st.error("Please fill at least ARN No. and Company Name.")
            else:
                record = {
                    "ARN No": arn_no,
                    "ISIN": isin,
                    "Security Type": security_type,
                    "Company Name": company_name,
                    "ISIN Allotment Date": isin_allotment_date.strftime("%Y-%m-%d"),
                    "Company reffered By": company_referred_by,
                    "Email ID": email_id,
                    "COMPANY SPOC": company_spoc,
                    "GSTIN": gstin,
                    "ADDRESS": address,
                    "Bill Amount": bill_amount,
                    "BILL Date 1": bill_date_1.strftime("%Y-%m-%d"),
                    "BILL Date 2": bill_date_2.strftime("%Y-%m-%d"),
                    "BILL Date 3": bill_date_3.strftime("%Y-%m-%d"),
                    "BILL Date 4": bill_date_4.strftime("%Y-%m-%d"),
                    "BILL Date 5": bill_date_5.strftime("%Y-%m-%d"),
                    "BILL Date 6": bill_date_6.strftime("%Y-%m-%d"),
                    "BILL Date 7": bill_date_7.strftime("%Y-%m-%d"),
                    "LINK": link,
                    "Company Path": company_path
                }
                try:
                    table.create(record)
                    st.success(f"✅ Record for {company_name} added successfully!")
                except Exception as e:
                    st.error(f"Failed to add record: {e}")

def database_page():
    st.title("📊 Company & Bills Database")
    records = airtable_read_records()
    
    if records:
        df = pd.DataFrame(records)
        
        # Format date columns if you want (optional)
        date_cols = [
            "ISIN Allotment Date",
            "BILL Date 1", "BILL Date 2", "BILL Date 3",
            "BILL Date 4", "BILL Date 5", "BILL Date 6", "BILL Date 7"
        ]
        for col in date_cols:
            if col in df.columns:
                # Try to parse with known format
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%d-%b-%y')
        
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No records found.")

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def get_email_body(payload):
    """
    Recursively search payload parts to find plain text or html content.
    Returns a tuple (plain_text, html_content) where either can be None.
    """
    plain_text = None
    html_content = None

    if 'parts' in payload:
        for part in payload['parts']:
            pt, ht = get_email_body(part)
            if pt and not plain_text:
                plain_text = pt
            if ht and not html_content:
                html_content = ht
    else:
        mime_type = payload.get('mimeType')
        data = payload.get('body', {}).get('data')
        if data:
            decoded = base64.urlsafe_b64decode(data).decode(errors='replace')
            if mime_type == 'text/plain':
                plain_text = decoded
            elif mime_type == 'text/html':
                html_content = decoded

    return plain_text, html_content


def extract_isin_details_from_text(text):
    results = []
    for line in text.splitlines():
        line = line.strip()
        # Skip header or empty lines
        if not line or 'Company' in line or 'ISIN' in line or 'Instrument' in line:
            continue
        
        # Look for ISIN pattern in line
        match = re.search(r'(INE[A-Z0-9]{9})', line)
        if match:
            isin = match.group(1)
            parts = line.split()
            isin_index = parts.index(isin)
            company = " ".join(parts[:isin_index])
            instrument = " ".join(parts[isin_index+1:])
            results.append({
                "Company": company,
                "ISIN": isin,
                "Instrument": instrument
            })
    return results
def fetch_and_parse_emails(service, subject_filter=SUBJECT_FILTER):
    existing_isins = {rec["ISIN"] for rec in airtable_read_records() if rec.get("ISIN")}

    results = service.users().messages().list(userId='me', q=f'subject:"{subject_filter}"', maxResults=30).execute()
    messages = results.get('messages', [])
    
    parsed_data = []
    email_metadata = []

    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = msg_data['payload']['headers']

        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        to = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')

        payload = msg_data['payload']
        plain_text, html_content = get_email_body(payload)

        # # ✅ DEBUG: Show subject
        # st.write(f"📧 Email Subject: {subject}")

        text_to_parse = plain_text or BeautifulSoup(html_content, "html.parser").get_text(separator="\n") if html_content else None

        # # ✅ DEBUG: Show email body snippet
        # st.write(f"📄 Body (first 300 chars): {text_to_parse[:300] if text_to_parse else 'No content'}")

        if text_to_parse:
            extracted = extract_isin_details_from_text(text_to_parse)
            # st.write(f"🧪 Extracted ISINs: {extracted}")  # DEBUG: What was extracted?

            for entry in extracted:
                if entry["ISIN"] not in existing_isins:
                    parsed_data.append(entry)
                    email_metadata.append({
                        "Subject": subject,
                        "From": sender,
                        "To": to,
                        "Company": entry["Company"]
                    })
            else:
                # Optional: You can still log the email for debugging
                email_metadata.append({
                    "Subject": subject,
                    "From": sender,
                    "To": to,
                    "Company": "❌ No ISIN Found"
                })

    return email_metadata, parsed_data


def isin_record_exists(company_name, isin):
    records = airtable_read_records()
    for r in records:
        if r.get("Company Name", "").strip().lower() == company_name.strip().lower() and \
           r.get("ISIN", "").strip().lower() == isin.strip().lower():
            return True
    return False

def gmail_extractor_page():
    st.set_page_config(page_title="📧 NSDL ISIN Email Extractor", layout="wide")
    st.title("📧 NSDL ISIN Details Extractor from Gmail")

    # Don't initialize `data` here — keep it scoped
    if st.button("Fetch NSDL Emails"):
        try:
            with st.spinner("Authenticating and reading Gmail..."):
                service = authenticate_gmail()
                email_meta, data = fetch_and_parse_emails(service)

            # if email_meta:
            #     st.subheader("📨 Last 5 Fetched Email Subjects")
            #     st.table(pd.DataFrame(email_meta))

            if data:
                st.subheader("📋 Extracted ISIN Details")
                st.dataframe(data)
                st.success("ISIN Data fetched successfully! Now go to Home to use it.")

                # ✅ Save to both session_state
                st.session_state.gmail_data = data
                st.session_state.fetched_isin_data = data
            else:
                st.warning("No ISIN data found in emails.")
        except Exception as e:
            st.error(f"Error: {e}")

    # ✅ This part runs if previously fetched data exists
    if 'fetched_isin_data' in st.session_state:
        data = st.session_state.fetched_isin_data
        st.subheader("📋 Extracted ISIN Details")
        st.dataframe(data)

        if st.button("📥 Save All New Entries to Airtable"):
            added = 0
            skipped = 0
            for entry in data:
                company = entry["Company"]
                isin = entry["ISIN"]
                instrument = entry["Instrument"]

                if isin_record_exists(company, isin):
                    skipped += 1
                    continue

                record = {
                    "ISIN": isin,
                    "Security Type": instrument,
                    "Company Name": company,
                    "ISIN Allotment Date": datetime.now().strftime("%Y-%m-%d")
                }

                try:
                    table.create(record)
                    added += 1
                except Exception as e:
                    st.error(f"Error adding record for {company}: {e}")

            st.success(f"✅ Added {added} new records. Skipped {skipped} existing ones.")


def edit_page():
    st.title("✏️ Edit Company Record by ISIN")

    records = airtable_read_records()
    isin_options = [rec["ISIN"] for rec in records if rec["ISIN"]]
    selected_isin = st.selectbox("Select ISIN to Edit", ["--- Select ---"] + isin_options)

    if selected_isin != "--- Select ---":
        record = next((r for r in records if r["ISIN"] == selected_isin), None)

        if record:
            with st.form("edit_form"):
                st.subheader(f"Editing Record for ISIN: `{selected_isin}`")
                arn_no = st.text_input("ARN No", value=record.get("ARN No", ""))
                company_name = st.text_input("Company Name", value=record.get("Company Name", ""))
                security_type = st.text_input("Security Type", value=record.get("Security Type", ""))
                company_referred_by = st.text_input("Company referred By", value=record.get("Company reffered By", ""))
                email_id = st.text_input("Email ID", value=record.get("Email ID", ""))
                company_spoc = st.text_input("COMPANY SPOC", value=record.get("COMPANY SPOC", ""))
                gstin = st.text_input("GSTIN", value=record.get("GSTIN", ""))
                address = st.text_area("ADDRESS", value=record.get("ADDRESS", ""))

                def safe_float(val):
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return 0.0

                bill_amount = st.number_input("Bill Amount", value=safe_float(record.get("Bill Amount", 0)))
                link = st.text_input("LINK", value=record.get("LINK", ""))
                company_path = st.text_input("Company Path", value=record.get("Company Path", ""))
                # Parse stored date string to date object for default value
                try:
                    default_bill_date = datetime.datetime.strptime(record.get("BILL Date 1", ""), "%Y-%m-%d").date()
                except Exception:
                    default_bill_date = datetime.date.today()

                Bill_Date_1 = st.date_input("BILL Date 1", value=default_bill_date, key="bill_date_1")

                submit = st.form_submit_button("✅ Update Record")
                if submit:
                    airtable_id = next((r["id"] for r in table.all() if r["fields"].get("ISIN") == selected_isin), None)
                    bill_date_str = Bill_Date_1.strftime("%Y-%m-%d") if Bill_Date_1 else ""
                    if airtable_id:
                        updated_data = {
                            "ARN No": arn_no,
                            "Company Name": company_name,
                            "Security Type": security_type,
                            "Company reffered By": company_referred_by,
                            "Email ID": email_id,
                            "COMPANY SPOC": company_spoc,
                            "GSTIN": gstin,
                            "ADDRESS": address,
                            "Bill Amount": bill_amount,
                            "LINK": link,
                            "Company Path": company_path,
                            "BILL Date 1": bill_date_str,
                        }
                        table.update(airtable_id, updated_data)
                        st.write("Updating Airtable record with data:", updated_data)  # debug
                        st.success("Record updated successfully!")
                    else:
                        st.error("Failed to locate Airtable record by ISIN.")



# -------- MAIN APP -------- #
# Check authentication first
if not check_authentication():
    st.stop()

# Configure page
st.set_page_config(
    page_title="Reminder System",
    page_icon="📧",
    initial_sidebar_state="expanded",
    layout="wide"
)

# Professional sidebar navigation
with st.sidebar:
    st.markdown("### Navigation")

    if st.button("Database", use_container_width=True):
        st.session_state.page = "Database"
        
    if st.button("Home", use_container_width=True):
        st.session_state.page = "Home"

    if st.button("Gmail Extractor", use_container_width=True):
        st.session_state.page = "Gmail"

    if st.button("✏️ Edit Record", use_container_width=True):
        st.session_state.page = "Edit"


    st.markdown("---")
    if st.button("Logout", type="primary", use_container_width=True):
        logout()
    


# Initialize page if not set
if 'page' not in st.session_state:
    st.session_state.page = "Database"

# Display selected page
if st.session_state.page == "Database":
    database_page()
elif st.session_state.page == "Home":
    gmail_data = st.session_state.get("gmail_data", [])
    home_page(gmail_data=gmail_data)
elif st.session_state.page == "Gmail":
    gmail_extractor_page()
elif st.session_state.page == "Edit":
    edit_page()
