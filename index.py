# import streamlit as st
# from datetime import datetime
# import uuid
# import pandas as pd
# from pyairtable import Api
# from dotenv import load_dotenv
# import pytz
# import os

# load_dotenv()

# # -------- TIMEZONE SETUP -------- #
# IST = pytz.timezone('Asia/Kolkata')

# # -------- CONFIG -------- #
# AIRTABLE_PERSONAL_ACCESS_TOKEN = os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN")
# AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
# AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

# # -------- AUTHENTICATION CONFIG -------- #
# AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")  # Default username
# AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "password123")  # Default password

# # -------- AUTHENTICATION FUNCTION -------- #
# def check_authentication():
#     """Simple authentication system"""
#     if 'authenticated' not in st.session_state:
#         st.session_state.authenticated = False
    
#     if not st.session_state.authenticated:
#         st.title("🔐 Login Required")
#         st.markdown("Please enter your credentials to access the Email Reminder System.")
#         st.markdown("Username- admin, password= admin")
        
#         with st.form("login_form"):
#             username = st.text_input("Username")
#             password = st.text_input("Password", type="password")
#             login_submitted = st.form_submit_button("Login")
            
#             if login_submitted:
#                 if username == AUTH_USERNAME and password == AUTH_PASSWORD:
#                     st.session_state.authenticated = True
#                     st.success("✅ Login successful!")
#                     st.rerun()
#                 else:
#                     st.error("❌ Invalid credentials. Please try again.")
        
#         return False
    
#     return True

# def logout():
#     """Logout function"""
#     st.session_state.authenticated = False
#     st.rerun()

# table = Api(AIRTABLE_PERSONAL_ACCESS_TOKEN).table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

# def get_ist_now():
#     """Get current time in IST"""
#     return datetime.now(IST)

# def convert_to_ist(dt):
#     """Convert datetime to IST timezone"""
#     if dt.tzinfo is None:
#         return IST.localize(dt)
#     else:
#         return dt.astimezone(IST)

# # -------- AIRTABLE HELPERS -------- #
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

# def airtable_read_reminders():
#     return table.all()

# # -------- STREAMLIT UI -------- #
# # Check authentication first
# if not check_authentication():
#     st.stop()

# # Configure sidebar to be collapsed by default
# st.set_page_config(initial_sidebar_state="collapsed")

# # Add logout button in sidebar
# with st.sidebar:
#     st.markdown("---")
#     if st.button("🚪 Logout"):
#         logout()

# st.title("📧 Reminder system")
# st.markdown("Set a reminder and receive an email when it's due.")

# # # Display current IST time
# # current_ist = get_ist_now()
# # st.info(f"🕒 Current IST Time: {current_ist.strftime('%Y-%m-%d %H:%M:%S')}")

# # -------- REMINDER FORM -------- #
# with st.form("reminder_form"):
#     email = st.text_input("Your Email Address")
#     subject = st.text_input("Subject")
#     message = st.text_area("Reminder Message")
#     date = st.date_input("Date")
#     time = st.time_input("Time")
#     submitted = st.form_submit_button("Set Reminder")

#     if submitted:
#         if not email or not subject or not message:
#             st.error("Please fill in all fields.")
#         else:
#             # Create naive datetime and treat as IST
#             reminder_time = datetime.combine(date, time)
#             reminder_time_ist = IST.localize(reminder_time)
#             reminder_id = str(uuid.uuid4())
            
#             # Store the reminder in Airtable
#             airtable_append_reminder(reminder_id, email, subject, message, reminder_time_ist, status="Pending")
#             st.success(f"Reminder set for {reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')}. It will be sent automatically when due.")

# # -------- DISPLAY REMINDERS -------- #
# st.markdown("---")
# st.subheader("📅 Scheduled Reminders")

# records = airtable_read_reminders()
# if records:
#     now_ist = get_ist_now()
#     display = []
#     for r in records:
#         f = r.get("fields", {})
#         reminder_time_str = f.get("ReminderTime", "")
#         try:
#             # Parse stored time and convert to IST
#             reminder_time = datetime.fromisoformat(reminder_time_str.replace('Z', '+00:00'))
#             reminder_time_ist = convert_to_ist(reminder_time)
            
#             time_left = reminder_time_ist - now_ist
#             if time_left.total_seconds() > 0:
#                 days = time_left.days
#                 hours, remainder = divmod(time_left.seconds, 3600)
#                 minutes, _ = divmod(remainder, 60)
#                 if days > 0:
#                     time_left_str = f"{days}d {hours}h {minutes}m"
#                 elif hours > 0:
#                     time_left_str = f"{hours}h {minutes}m"
#                 else:
#                     time_left_str = f"{minutes}m"
#             else:
#                 time_left_str = "Due/Overdue"
                
#             # Format display time in IST
#             display_time = reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')
#         except Exception as e:
#             time_left_str = "Invalid time"
#             display_time = reminder_time_str

#         display.append({
#             "Email": f.get("Email", ""),
#             "Subject": f.get("Subject", ""),
#             "Reminder Time": display_time,
#             "Time Left": time_left_str,
#             "Status": f.get("Status", "")
#         })

#     # Sort by reminder time
#     display.sort(key=lambda x: x.get("Reminder Time", ""))
#     df = pd.DataFrame(display)
#     st.dataframe(df, use_container_width=True)
# else:
#     st.info("No reminders found.")



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

def get_reminders_analytics():
    """Get analytics for reminders"""
    records = airtable_read_reminders()
    now_ist = get_ist_now()
    
    analytics = {
        "1_week": [],
        "1_month": [],
        "3_months": [],
        "6_months": [],
        "6_months_plus": []
    }
    
    for r in records:
        f = r.get("fields", {})
        reminder_time_str = f.get("ReminderTime", "")
        try:
            reminder_time = datetime.fromisoformat(reminder_time_str.replace('Z', '+00:00'))
            reminder_time_ist = convert_to_ist(reminder_time)
            
            time_diff = reminder_time_ist - now_ist
            days_diff = time_diff.days
            
            reminder_data = {
                "email": f.get("Email", ""),
                "subject": f.get("Subject", ""),
                "reminder_time": reminder_time_ist,
                "status": f.get("Status", "")
            }
            
            if days_diff <= 7:
                analytics["1_week"].append(reminder_data)
            elif days_diff <= 30:
                analytics["1_month"].append(reminder_data)
            elif days_diff <= 90:
                analytics["3_months"].append(reminder_data)
            elif days_diff <= 180:
                analytics["6_months"].append(reminder_data)
            else:
                analytics["6_months_plus"].append(reminder_data)
        except:
            continue
    
    return analytics

# -------- PAGES -------- #
def home_page():
    """Home page with reminder creation"""
    st.title("📧 Reminder System")
    st.markdown("Set a reminder and receive an email when it's due.")

    # Show current time
    current_ist = get_ist_now()
    st.caption(f"🕒 Current IST Time: {current_ist.strftime('%Y-%m-%d %H:%M:%S')}")

    # -------- REMINDER FORM -------- #
    with st.form("reminder_form"):
        st.subheader("📝 Create New Reminder")
        
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Your Email Address", placeholder="example@gmail.com")
            subject = st.text_input("Subject", placeholder="Meeting reminder")
        
        with col2:
            date = st.date_input("Date", min_value=datetime.now().date())
            time = st.time_input("Time")
        
        message = st.text_area("Reminder Message", placeholder="Don't forget about the team meeting...")
        
        submitted = st.form_submit_button("🔔 Set Reminder", type="primary")

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
                st.success(f"✅ Reminder set for {reminder_time_ist.strftime('%Y-%m-%d %H:%M IST')}. It will be sent automatically when due.")

def database_page():
    """Database page with analytics and data management"""
    st.title("📊 Database")
    
    # Get analytics
    analytics = get_reminders_analytics()
    
    # Analytics cards
    st.subheader("📈 Overview")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Due in 1 Week", len(analytics["1_week"]))
        st.metric("Due in 1 Month", len(analytics["1_month"]))
    
    with col2:
        st.metric("Due in 3 Months", len(analytics["3_months"]))
        st.metric("Due in 6 Months", len(analytics["6_months"]))
    
    with col3:
        st.metric("Due in 6+ Months", len(analytics["6_months_plus"]))
    
    # Full database view
    st.markdown("---")
    st.subheader("🗃️ Complete Database")
    
    # Display all data
    records = airtable_read_reminders()
    if records:
        now_ist = get_ist_now()
        display = []
        
        for r in records:
            f = r.get("fields", {})
            
            reminder_time_str = f.get("ReminderTime", "")
            try:
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
                    
                display_time = reminder_time_ist.strftime('%d %B, %Y at %I:%M %p IST')
            except:
                time_left_str = "Invalid time"
                display_time = reminder_time_str

            display.append({
                "Email": f.get("Email", ""),
                "Subject": f.get("Subject", ""),
                "Reminder Time": display_time,
                "Time Left": time_left_str,
                "Status": f.get("Status", "")
            })

        if display:
            # Sort by reminder time
            display.sort(key=lambda x: x.get("Reminder Time", ""))
            df = pd.DataFrame(display)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No reminders found.")
    else:
        st.info("No reminders found in the database.")

# -------- MAIN APP -------- #
# Check authentication first
if not check_authentication():
    st.stop()

# Configure page
st.set_page_config(
    page_title="Reminder System",
    page_icon="📧",
    initial_sidebar_state="expanded"
)

# Professional sidebar navigation
with st.sidebar:
    st.markdown("### Navigation")
    
    if st.button("Home", use_container_width=True):
        st.session_state.page = "Home"
    
    if st.button("Database", use_container_width=True):
        st.session_state.page = "Database"
    
    st.markdown("---")
    if st.button("Logout", type="primary", use_container_width=True):
        logout()

# Initialize page if not set
if 'page' not in st.session_state:
    st.session_state.page = "Home"

# Display selected page
if st.session_state.page == "Home":
    home_page()
elif st.session_state.page == "Database":
    database_page()

