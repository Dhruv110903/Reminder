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
from streamlit_option_menu import option_menu
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import base64
import re

# --- HIDE STREAMLIT STYLE ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# It must be the first Streamlit command to run.
st.set_page_config(
    page_title="Nivis",
    initial_sidebar_state="expanded",
    layout="wide"
)

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
    if 'page' not in st.session_state:
        st.session_state.page = "Overview"

def is_otp_expired():
    """Check if OTP has expired"""
    if st.session_state.otp_expiry is None:
        return True
    return datetime.now() > st.session_state.otp_expiry
def check_authentication():
    """Improved authentication system with pre-loading and smoother UI transition."""
    init_session_state()
    
    if st.session_state.authenticated:
        return True
    
    if not SMTP_EMAIL or not SMTP_PASSWORD or not ADMIN_EMAIL:
        st.error("❌ Email configuration missing. Please check your environment variables.")
        st.code("""
        SMTP_EMAIL=your-email@gmail.com
        SMTP_PASSWORD=your-app-password
        ADMIN_EMAIL=your-email@gmail.com
        """)
        st.stop()
    
    st.markdown("<h1 style='text-align: center;'>Nivis</h1>", unsafe_allow_html=True)

    login_col1, login_col2, login_col3 = st.columns([1, 1.5, 1])

    with login_col2:
        # This is now a single if/elif chain to fix the SyntaxError
        if not st.session_state.credentials_verified:
            with st.form("login_form"):
                st.markdown("<h4 style='text-align: left;'>Enter Credentials</h4>", unsafe_allow_html=True)
                
                username = st.text_input("Username", placeholder="Username", label_visibility="collapsed")
                password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
                
                login_submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
                
                if login_submitted:
                    if username == AUTH_USERNAME and password == AUTH_PASSWORD:
                        with st.spinner("Sending verification email..."):
                            otp = generate_otp()
                            success, message = send_otp_email(ADMIN_EMAIL, otp)
                            
                            if success:
                                st.session_state.credentials_verified = True
                                st.session_state.otp_code = otp
                                st.session_state.otp_sent = True
                                st.session_state.otp_expiry = datetime.now() + timedelta(minutes=5)
                                st.session_state.otp_attempts = 0
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                    else:
                        st.session_state.login_attempts += 1
                        st.error(f"❌ Invalid credentials. Attempt {st.session_state.login_attempts}/5")
                        if st.session_state.login_attempts >= 5:
                            st.error("🚫 Too many failed attempts. Please refresh the page and try again later.")
                            st.stop()

        elif st.session_state.otp_sent and not is_otp_expired():
            st.markdown("---")
            with st.form("otp_form"):
                st.markdown("<h3 style='text-align: center;'>Email Verification</h3>", unsafe_allow_html=True)
                st.info("Please check your email for the verification code.")
                
                entered_otp = st.text_input("Enter 6-digit verification code", max_chars=6, placeholder="Enter 6-digit code", label_visibility="collapsed")
                
                otp_submitted = st.form_submit_button("Verify", type="primary", use_container_width=True)
                
                if otp_submitted:
                    if entered_otp == st.session_state.otp_code:
                        with st.spinner("Preparing your dashboard..."):
                            airtable_read_records()
                        
                        st.session_state.authenticated = True
                        st.success("✅ Login successful!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.session_state.otp_attempts += 1
                        st.error(f"❌ Invalid verification code. Attempt {st.session_state.otp_attempts}/3")
                        if st.session_state.otp_attempts >= 3:
                            st.error("🚫 Too many attempts. Please login again.")
                            logout()
            
            if st.button("Resend Code"):
                st.session_state.otp_sent = False
                st.session_state.credentials_verified = False
                st.rerun()
    
        elif st.session_state.credentials_verified and is_otp_expired():
            st.error("Verification code has expired. Please login again.")
            logout()
    
    return False
    
def logout():
    """Logs out the user with a full cache and session state clear."""
    st.success("👋 Logged out successfully! Resetting application...")
    st.cache_data.clear()
    keys = list(st.session_state.keys())
    for key in keys:
        st.session_state.pop(key)
    time.sleep(1) 
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
        if isinstance(date_str, str):
            # Added dayfirst=True to correctly parse D/M/Y formats
            parsed_date = pd.to_datetime(date_str, errors='coerce', dayfirst=True) 
            if pd.isna(parsed_date):
                return ""
            return parsed_date.strftime('%Y-%m-%d')
        return date_str
    except:
        return ""

# -------- AIRTABLE HELPERS (FINAL VERSION) -------- #
@st.cache_data(ttl=120)
def airtable_read_records():
    """Read and clean Airtable records using case-insensitive lookup."""
    try:
        airtable_records = table.all()
        records = []
        
        for r in airtable_records:
            f = r.get("fields", {})
            f_lower = {k.lower(): v for k, v in f.items()}
            
            record = {
                "Depository": str(f_lower.get("depository", "")).strip(),
                "ISIN": str(f_lower.get("isin", "")).strip(),
                "Issuer": str(f_lower.get("issuer", "")).strip(),
                "ARN": str(f_lower.get("arn if isin na (nsdl)", "")).strip(),
                "Status": str(f_lower.get("status", "")).strip(),
                "No of ISINs": str(f_lower.get("no of isin", "")).strip(),
                "ISIN Allotment Date": safe_date_string(f_lower.get("isin allotment date", "")),
                "GSTIN": str(f_lower.get("gstin", "")).strip(),
                "Address": str(f_lower.get("address", "")).strip(),
                "Company Link": str(f_lower.get("company link", "")).strip(),
                "Email ID": str(f_lower.get("email id", "")).strip(),
                "Company Referred By": str(f_lower.get("company referred by", "")).strip(),
                "Amount": safe_float(f_lower.get("amount", 0)),
            }
            
            for i in range(1, 73):
                field_name = f"bill date {i}"
                display_name = f"Bill Date {i}"
                record[display_name] = safe_date_string(f_lower.get(field_name, ""))
            
            records.append(record)
            
        return records
    except Exception as e:
        st.error(f"Error reading Airtable records: {str(e)}")
        return []

def overview_page():
    st.title("Overview")
    
    # Data is pre-loaded during login, so no spinner is needed here.
    records = airtable_read_records()
    
    if records:
        try:
            df = pd.DataFrame(records)
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)
            analytics_df = df.copy()
            
            # ===== ANALYTICS SECTION =====
            st.subheader("Analytics")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", len(df))
            with col2:
                st.metric("Unique Companies", df['Issuer'].nunique())
            with col3:
                total_bill_amount = analytics_df['Amount'].sum()
                show_amount = st.checkbox("Show Total Value", value=False)
                if show_amount:
                    st.metric("Total Billing value", f"₹{total_bill_amount:,.2f}")
                else:
                    st.metric("Total Billing value", "****")
            
            # New Entries Analysis
            st.subheader("New contracts")
            
            incomplete_entries = analytics_df[
                (analytics_df['ARN'].fillna('').str.strip() == '') &
                (analytics_df['Issuer'].fillna('').str.strip() != '') &
                (analytics_df['ISIN'].fillna('').str.strip() != '')
            ]
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📥 New/Incomplete Entries", len(incomplete_entries))
            with col2:
                st.metric("⏳ Pending Completion", len(incomplete_entries))
            
            if len(incomplete_entries) > 0:
                with st.expander(f"🔍 View Incomplete Records ({len(incomplete_entries)} records)", expanded=False):
                    st.write("**Records requiring completion:**")
                    incomplete_display = incomplete_entries[['Issuer', 'ISIN', 'Status']].copy()
                    st.dataframe(incomplete_display, use_container_width=True)
            
            # Bill Due Analysis
            st.subheader("📅 Bill Due Date Analysis")
            
            current_date = datetime.now().date()
            bill_dates = []
            for index, row in analytics_df.iterrows():
                issuer_name = row['Issuer']
                for i in range(1, 73):
                    bill_date_col = f'Bill Date {i}'
                    if bill_date_col in row and pd.notna(row[bill_date_col]) and row[bill_date_col] != '':
                        try:
                            bill_date = datetime.strptime(row[bill_date_col], '%Y-%m-%d').date()
                            if bill_date >= current_date:
                                days_until_due = (bill_date - current_date).days
                                bill_dates.append({
                                    'Issuer': issuer_name,
                                    'Bill Date': bill_date,
                                    'Days Until Due': days_until_due
                                })
                        except:
                            continue
            
            if bill_dates:
                bills_df = pd.DataFrame(bill_dates)
                due_1_week = bills_df[bills_df['Days Until Due'] <= 7]
                due_1_month = bills_df[bills_df['Days Until Due'] <= 30]
                due_3_months = bills_df[bills_df['Days Until Due'] <= 90]
                
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("🚨 Due in 1 Week", len(due_1_week))
                with col2: st.metric("⚠️ Due in 1 Month", len(due_1_month))
                with col3: st.metric("📋 Due in 3 Months", len(due_3_months))
                with col4: st.metric("📊 Total Upcoming Bills", len(bills_df))
                
                if len(due_1_week) > 0:
                    with st.expander(f"🚨 View Urgent Bills ({len(due_1_week)} bills due in 1 week)", expanded=False):
                        st.dataframe(due_1_week.sort_values('Days Until Due'), use_container_width=True)
                
                bills_df['Due Category'] = bills_df['Days Until Due'].apply(
                    lambda x: '1 Week' if x <= 7 else '1 Month' if x <= 30 else '3 Months' if x <= 90 else 'Later'
                )
                due_distribution = bills_df['Due Category'].value_counts()
                st.bar_chart(due_distribution)
            else:
                st.info("No upcoming bill dates found in the database.")
            
            # Company-wise Analysis
            st.subheader("🏢 Company-wise Analysis")
            company_counts = analytics_df.groupby('Issuer').agg({
                'ISIN': 'count',
                'Amount': 'sum',
                'ARN': lambda x: (x.fillna('').str.strip() != '').sum()
            }).round(2)
            
            company_counts.columns = ['Total Records', 'Total Bill Amount', 'Completed Records']
            company_counts['Completion Rate'] = (company_counts['Completed Records'] / company_counts['Total Records'] * 100).round(1)
            company_counts['Total Bill Amount'] = company_counts['Total Bill Amount'].apply(lambda x: f"₹{x:,.2f}")
            
            with st.expander(f"📊 View Company-wise Analysis ({len(company_counts)} companies)", expanded=False):
                st.dataframe(company_counts.sort_values('Total Records', ascending=False), use_container_width=True)
            
            # Status Distribution
            st.subheader("📊 Status Distribution")
            status_distribution = analytics_df['Status'].value_counts()
            st.bar_chart(status_distribution)
            
            # Financial Health Indicators
            st.subheader("💡 Financial Health Indicators")
            avg_bill_amount = analytics_df['Amount'].mean()
            high_value_clients = len(analytics_df[analytics_df['Amount'] > avg_bill_amount * 2])
            
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("💰 Average Bill Amount", f"₹{avg_bill_amount:,.2f}")
            with col2: st.metric("🌟 High Value Clients", high_value_clients)
            with col3: st.metric("📊 Median Bill Amount", f"₹{analytics_df['Amount'].median():,.2f}")
            with col4: st.metric("🏢 Active Companies", len(analytics_df[analytics_df['Amount'] > 0]))
                
        except Exception as e:
            st.error(f"Error displaying database: {str(e)}")
            st.info("Raw data preview:")
            st.json(records[:3] if len(records) > 0 else {})
    else:
        st.info("No records found in the database.")

def database_page():
    st.title("Database")
    
    # Data is pre-loaded during login
    records = airtable_read_records()
    
    if records:
        try:
            df = pd.DataFrame(records)
            # Create a numeric 'Amount' column for calculations before formatting
            df['NumericAmount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)

            # --- Main Database View ---
            st.subheader("All Records")
            
            # 1. Create a list for the main filter dropdown
            issuer_list = sorted(df['Issuer'].unique())
            isin_list = sorted(df['ISIN'].unique())
            search_options_top = ["— Select to Filter by Issuer or ISIN —"] + issuer_list + isin_list

            search_selection_top = st.selectbox(
                "🔍 **Filter Table**",
                options=search_options_top
            )

            # 2. Filter the DataFrame for the main table view
            if search_selection_top != "— Select to Filter by Issuer or ISIN —":
                filtered_df = df[
                    (df['Issuer'] == search_selection_top) | 
                    (df['ISIN'] == search_selection_top)
                ].copy()
            else:
                filtered_df = df.copy()
            
            # Format 'Amount' for display in the main table
            filtered_df['Amount'] = filtered_df['NumericAmount'].apply(lambda x: f"₹{x:,.2f}" if x > 0 else "₹0.00")
            
            # Configure columns to hide
            column_config_main = { 'NumericAmount': None } # Hide the numeric amount column
            for i in range(2, 73):
                column_config_main[f"Bill Date {i}"] = None

            st.dataframe(
                filtered_df.drop(columns=['NumericAmount']),
                use_container_width=True,
                height=400,
                hide_index=True,
                column_config=column_config_main
            )

            # --- Company Performance Dashboard Section ---
            st.divider()
            st.header("Company Performance Dashboard")

            # 1. Create a second dropdown for the performance section
            search_options_bottom = ["— Search for a Company to see its Performance —"] + issuer_list
            
            selection_bottom = st.selectbox(
                "🏢 **Select a Company**", 
                options=search_options_bottom
            )

            # 2. If a company is selected, display its dashboard
            if selection_bottom != "— Search for a Company to see its Performance —":
                company_df = df[df['Issuer'] == selection_bottom].copy()
                
                # --- Calculate Metrics ---
                total_billed_amount = company_df['NumericAmount'].sum()
                total_records = len(company_df)
                
                all_dates = []
                for i in range(1, 73):
                    date_col = f'Bill Date {i}'
                    # Coerce to datetime, invalid dates will become NaT
                    valid_dates = pd.to_datetime(company_df[date_col], errors='coerce').dropna()
                    all_dates.extend(valid_dates.tolist())
                
                all_dates = sorted(list(set(all_dates))) # Get unique sorted dates
                
                first_bill_date = all_dates[0] if all_dates else None
                last_bill_date = all_dates[-1] if all_dates else None
                
                # Count upcoming bills
                today = pd.Timestamp.now()
                upcoming_bills_count = sum(1 for date in all_dates if date > today)


                # --- Display Metrics ---
                st.subheader("Performance Metrics")
                metric_cols = st.columns(4)
                metric_cols[0].metric("Total Billed Amount", f"₹{total_billed_amount:,.2f}")
                metric_cols[1].metric("Total Records / ISINs", f"{total_records}")
                metric_cols[2].metric("Upcoming Bills", f"{upcoming_bills_count}")
                metric_cols[3].metric("First Bill Date", first_bill_date.strftime('%b %d, %Y') if first_bill_date else "N/A")
                
                # --- Display Bill Dates by Year ---
                st.subheader("Billing History")

                if all_dates:
                    dates_by_year = {}
                    for date in all_dates:
                        year = date.year
                        if year not in dates_by_year:
                            dates_by_year[year] = []
                        dates_by_year[year].append(date.strftime('%B %d, %Y'))
                    
                    for year in sorted(dates_by_year.keys(), reverse=True):
                        with st.expander(f"🗓️ **{year}** ({len(dates_by_year[year])} bills)"):
                            st.write(dates_by_year[year])
                else:
                    st.info("No billing dates found for this company.")

        except Exception as e:
            st.error(f"Error displaying database page: {str(e)}")
            st.info("Raw data preview:")
            st.json(records[:3] if len(records) > 0 else {})
    else:
        st.info("No records found in the database.")

        
def new_entry_page():
    st.title("Create a New Entry")

    with st.form("new_entry_form", clear_on_submit=True):
        st.subheader("Enter New Record Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            issuer = st.text_input("Issuer (Company Name) *")
            isin = st.text_input("ISIN *")
            arn = st.text_input("ARN if ISIN NA (NSDL)")
            status = st.text_input("Status")
            # FIX 1: Changed text_input to number_input for numeric data
            no_of_isins = st.number_input("No of ISINs", min_value=0, step=1, value=None, placeholder="Enter a number...")
            company_referred_by = st.text_input("Company Referred By")
            email_id = st.text_input("Email ID")
            
        with col2:
            gstin = st.text_input("GSTIN")
            depository = st.text_input("Depository")
            address = st.text_area("Address")
            amount = st.number_input("Amount", value=0.0, format="%.2f")
            company_link = st.text_input("Company Link")
            isin_allotment_date = st.date_input("ISIN Allotment Date", value=None)
            bill_date_1 = st.date_input("Bill Date 1", value=None)

        st.markdown("_* Fields are required_")
        submit_button = st.form_submit_button("Create New Entry", type="primary")
        
        if submit_button:
            if not issuer or not isin:
                st.error("❌ Issuer and ISIN are required fields.")
            else:
                try:
                    with st.spinner("Creating record in Airtable..."):
                        new_record_data = {
                            "Issuer": issuer,
                            "ISIN": isin,
                            "ARN if ISIN NA (NSDL)": arn,
                            "Status": status,
                            # FIX 2: Convert the value to an integer before sending
                            "No of ISIN": int(no_of_isins) if no_of_isins is not None else None,
                            "Depository": depository,
                            "Company Referred By": company_referred_by,
                            "Email ID": email_id,
                            "GSTIN": gstin,
                            "Address": address,
                            "Amount": amount,
                            "Company Link": company_link,
                            "ISIN allotment date": isin_allotment_date.strftime("%Y-%m-%d") if isin_allotment_date else None,
                            "Bill Date 1": bill_date_1.strftime("%Y-%m-%d") if bill_date_1 else None,
                        }
                        
                        table.create(new_record_data)
                        st.success("✅ New entry created successfully!")
                        airtable_read_records.clear()
                        
                except Exception as e:
                    st.error(f"Failed to create new entry: {e}")
        
def edit_page():
    st.title("Edit or Delete a Record")

    # Initialize session state to hold the selected record's data
    if 'selected_record_to_edit' not in st.session_state:
        st.session_state.selected_record_to_edit = None
    if 'selected_record_id' not in st.session_state:
        st.session_state.selected_record_id = None

    # --- Data Loading and Search UI ---
    records = airtable_read_records()
    if not records:
        st.error("No records found in the database.")
        return

    # Create a list of unique issuers and ISINs for the dropdown
    df = pd.DataFrame(records)
    issuer_list = sorted(df['Issuer'].unique())
    isin_list = sorted(df['ISIN'].unique())
    search_options = ["— Search by Issuer or ISIN to Edit/Delete —"] + issuer_list + isin_list

    # Use a dropdown for a fast search experience
    search_selection = st.selectbox(
        "🔍 **Find a record to edit or delete**",
        options=search_options,
        index=0 # Default to the placeholder
    )

    # --- Find and Display the Edit Form ---
    if search_selection != "— Search by Issuer or ISIN to Edit/Delete —":
        # Find the full record details from the original list
        # We need the Airtable record ID which isn't in the DataFrame
        raw_airtable_records = table.all()
        
        found_record = None
        airtable_id = None

        for rec in raw_airtable_records:
            fields = rec.get("fields", {})
            if fields.get("Issuer") == search_selection or fields.get("ISIN") == search_selection:
                found_record = fields
                airtable_id = rec.get("id")
                break
        
        if found_record:
            st.session_state.selected_record_to_edit = found_record
            st.session_state.selected_record_id = airtable_id
        else:
            st.warning("Record not found.")
            st.session_state.selected_record_to_edit = None


    # If a record has been selected and is in session state, show the form
    if st.session_state.selected_record_to_edit:
        record = st.session_state.selected_record_to_edit
        st.markdown("---")
        st.subheader(f"Editing Record for: `{record.get('Issuer', 'N/A')}`")

        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                issuer = st.text_input("Issuer", value=record.get("Issuer", ""))
                arn = st.text_input("ARN if ISIN NA (NSDL)", value=record.get("ARN if ISIN NA (NSDL)", ""))
                status = st.text_input("Status", value=record.get("Status", ""))
                company_referred_by = st.text_input("Company Referred By", value=record.get("Company Referred By", ""))
                email_id = st.text_input("Email ID", value=record.get("Email ID", ""))
                no_of_isins = st.number_input("No of ISINs", min_value=0, step=1, value=record.get("No of ISIN", 0))

            with col2:
                gstin = st.text_input("GSTIN", value=record.get("GSTIN", ""))
                address = st.text_area("Address", value=record.get("Address", ""))
                amount = st.number_input("Amount", value=safe_float(record.get("Amount", 0)))
                company_link = st.text_input("Company Link", value=record.get("Company Link", ""))
                
                try:
                    date_str = record.get("ISIN allotment date", "")
                    default_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
                except (ValueError, TypeError):
                    default_date = None
                isin_allotment_date = st.date_input("ISIN Allotment Date", value=default_date)

            # --- Form Buttons ---
            button_col1, button_col2 = st.columns(2)
            with button_col1:
                update_submitted = st.form_submit_button("✅ Update Record", use_container_width=True)
            with button_col2:
                delete_submitted = st.form_submit_button("❌ Delete Record", type="primary", use_container_width=True)

            # --- Update Logic ---
            if update_submitted:
                try:
                    updated_data = {
                        "Issuer": issuer,
                        "ARN if ISIN NA (NSDL)": arn,
                        "Status": status,
                        "Company Referred By": company_referred_by,
                        "Email ID": email_id,
                        "GSTIN": gstin,
                        "Address": address,
                        "Amount": amount,
                        "Company Link": company_link,
                        "No of ISIN": int(no_of_isins),
                        "ISIN allotment date": isin_allotment_date.strftime("%Y-%m-%d") if isin_allotment_date else None,
                    }
                    table.update(st.session_state.selected_record_id, updated_data)
                    st.success("✅ Record updated successfully!")
                    airtable_read_records.clear()
                    st.session_state.selected_record_to_edit = None # Clear selection
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error updating record: {e}")

            # --- Delete Logic ---
            if delete_submitted:
                try:
                    table.delete(st.session_state.selected_record_id)
                    st.success("❌ Record deleted successfully!")
                    airtable_read_records.clear()
                    st.session_state.selected_record_to_edit = None # Clear selection
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error deleting record: {e}")


# -------- MAIN APP -------- #
if not check_authentication():
    st.stop()

with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: #0d6efd;'>Reminder App</h1>", unsafe_allow_html=True)
    
    pages = ["Overview", "Database", "New Record", "Edit Record", "Logout"]
    icons = ["speedometer2", "table", "plus-square-dotted", "pencil-square", "box-arrow-right"]

    try:
        default_index = pages.index(st.session_state.page)
    except (ValueError, AttributeError):
        default_index = 0
        st.session_state.page = pages[default_index]

    selected_page = option_menu(
        menu_title=None,
        options=pages,
        icons=icons,
        menu_icon="cast",
        default_index=default_index,
        styles={
            "container": {"padding": "15px 5px !important", "background-color": "transparent"},
            "icon": {"color": "#6c757d", "font-size": "20px"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "margin": "0px",
                "padding": "10px",
                "color": "#6c757d",
                "--hover-color": "#e9ecef",
                "border-radius": "5px",
            },
            "nav-link-selected": {"background-color": "#0d6efd", "color": "white"},
        },
    )

    if selected_page != st.session_state.page:
        st.session_state.page = selected_page
        st.rerun()

if st.session_state.page == "Logout":
    logout()
elif st.session_state.page == "Overview":
    overview_page()
elif st.session_state.page == "Database":
    database_page()
elif st.session_state.page == "New Record":
    new_entry_page()
elif st.session_state.page == "Edit Record":
    edit_page()
