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

# -------- HELPER FUNCTIONS -------- #
def safe_float(value):
    """Safely convert value to float, return 0.0 if conversion fails"""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def safe_date_string(date_str):
    """Safely format date string, return empty string if invalid"""
    if not date_str:
        return ""
    try:
        # Try to parse and reformat the date
        if isinstance(date_str, str):
            parsed_date = pd.to_datetime(date_str, errors='coerce')
            if pd.isna(parsed_date):
                return ""
            return parsed_date.strftime('%d-%b-%y')
        return date_str
    except:
        return ""

# -------- AIRTABLE HELPERS -------- #
def airtable_read_records():
    """Read and clean Airtable records"""
    try:
        airtable_records = table.all()
        records = []
        
        for r in airtable_records:
            f = r.get("fields", {})
            
            # Clean and format the record data
            record = {
                "ARN No": str(f.get("ARN No", "")).strip(),
                "ISIN": str(f.get("ISIN", "")).strip(),
                "Security Type": str(f.get("Security Type", "")).strip(),
                "Company Name": str(f.get("Company Name", "")).strip(),
                "ISIN Allotment Date": safe_date_string(f.get("ISIN Allotment Date", "")),
                "Company reffered By": str(f.get("Company reffered By", "")).strip(),
                "Email ID": str(f.get("Email ID", "")).strip(),
                "COMPANY SPOC": str(f.get("COMPANY SPOC", "")).strip(),
                "GSTIN": str(f.get("GSTIN", "")).strip(),
                "ADDRESS": str(f.get("ADDRESS", "")).strip(),
                "Bill Amount": safe_float(f.get("Bill Amount", "")),
                "BILL Date 1": safe_date_string(f.get("BILL Date 1", "")),
                "BILL Date 2": safe_date_string(f.get("BILL Date 2", "")),
                "BILL Date 3": safe_date_string(f.get("BILL Date 3", "")),
                "BILL Date 4": safe_date_string(f.get("BILL Date 4", "")),
                "BILL Date 5": safe_date_string(f.get("BILL Date 5", "")),
                "BILL Date 6": safe_date_string(f.get("BILL Date 6", "")),
                "BILL Date 7": safe_date_string(f.get("BILL Date 7", "")),
                "LINK": str(f.get("LINK", "")).strip(),
                "Company Path": str(f.get("Company Path", "")).strip()
            }
            records.append(record)
            
        return records
    except Exception as e:
        st.error(f"Error reading Airtable records: {str(e)}")
        return []

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
                    st.error(f"Failed to add record: {str(e)}")

def database_page():
    st.title("📊 Company & Bills Database")
    
    with st.spinner("Loading database records..."):
        records = airtable_read_records()
    
    if records:
        try:
            df = pd.DataFrame(records)
            
            # Ensure Bill Amount is properly formatted as numeric
            df['Bill Amount'] = pd.to_numeric(df['Bill Amount'], errors='coerce').fillna(0.0)
            
            # Format Bill Amount for display
            df['Bill Amount'] = df['Bill Amount'].apply(lambda x: f"₹{x:,.2f}" if x > 0 else "₹0.00")
            
            st.dataframe(df, use_container_width=True)
            
            # Add some statistics
            st.subheader("📈 Database Statistics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Records", len(df))
            
            with col2:
                unique_companies = df['Company Name'].nunique()
                st.metric("Unique Companies", unique_companies)
            
            with col3:
                unique_isins = df['ISIN'].nunique()
                st.metric("Unique ISINs", unique_isins)
                
        except Exception as e:
            st.error(f"Error displaying database: {str(e)}")
            st.info("Raw data preview:")
            st.json(records[:3] if len(records) > 0 else {})
    else:
        st.info("No records found in the database.")

def edit_page():
    st.title("✏️ Edit Company Record by ISIN")

    with st.spinner("Loading records..."):
        records = airtable_read_records()
    
    if not records:
        st.error("No records found in the database.")
        return
    
    # Filter records with valid ISIN
    valid_records = [rec for rec in records if rec.get("ISIN", "").strip()]
    
    if not valid_records:
        st.error("No records with valid ISIN found.")
        return
    
    isin_options = [rec["ISIN"] for rec in valid_records]
    selected_isin = st.selectbox("Select ISIN to Edit", ["--- Select ---"] + isin_options)

    if selected_isin != "--- Select ---":
        record = next((r for r in valid_records if r["ISIN"] == selected_isin), None)

        if record:
            with st.form("edit_form"):
                st.subheader(f"Editing Record for ISIN: `{selected_isin}`")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    arn_no = st.text_input("ARN No", value=record.get("ARN No", ""))
                    company_name = st.text_input("Company Name", value=record.get("Company Name", ""))
                    security_type = st.text_input("Security Type", value=record.get("Security Type", ""))
                    company_referred_by = st.text_input("Company referred By", value=record.get("Company reffered By", ""))
                    email_id = st.text_input("Email ID", value=record.get("Email ID", ""))
                    company_spoc = st.text_input("COMPANY SPOC", value=record.get("COMPANY SPOC", ""))
                    gstin = st.text_input("GSTIN", value=record.get("GSTIN", ""))
                
                with col2:
                    address = st.text_area("ADDRESS", value=record.get("ADDRESS", ""))
                    bill_amount = st.number_input("Bill Amount", value=safe_float(record.get("Bill Amount", 0)))
                    link = st.text_input("LINK", value=record.get("LINK", ""))
                    company_path = st.text_input("Company Path", value=record.get("Company Path", ""))
                    
                    # Parse stored date string to date object for default value
                    try:
                        bill_date_1_str = record.get("BILL Date 1", "")
                        if bill_date_1_str:
                            # Try different date formats
                            for date_format in ["%Y-%m-%d", "%d-%b-%y", "%d-%B-%Y"]:
                                try:
                                    default_bill_date = datetime.strptime(bill_date_1_str, date_format).date()
                                    break
                                except ValueError:
                                    continue
                            else:
                                default_bill_date = datetime.now().date()
                        else:
                            default_bill_date = datetime.now().date()
                    except Exception:
                        default_bill_date = datetime.now().date()

                    bill_date_1 = st.date_input("BILL Date 1", value=default_bill_date, key="bill_date_1")

                submit = st.form_submit_button("✅ Update Record")
                
                if submit:
                    try:
                        # Find the Airtable record ID
                        airtable_records = table.all()
                        airtable_id = None
                        
                        for airtable_record in airtable_records:
                            if airtable_record["fields"].get("ISIN") == selected_isin:
                                airtable_id = airtable_record["id"]
                                break
                        
                        if airtable_id:
                            bill_date_str = bill_date_1.strftime("%Y-%m-%d") if bill_date_1 else ""
                            
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
                            st.success("✅ Record updated successfully!")
                            
                            # Clear cache to refresh data
                            if hasattr(st, 'cache_data'):
                                st.cache_data.clear()
                            
                        else:
                            st.error("❌ Failed to locate Airtable record by ISIN.")
                            
                    except Exception as e:
                        st.error(f"❌ Error updating record: {str(e)}")

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
elif st.session_state.page == "Edit":
    edit_page()
