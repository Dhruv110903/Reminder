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
@st.cache_data(ttl=600) # Cache data for 10 minutes for performance
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

def overview_page():
    st.title("Overview")
    
    with st.spinner("Loading overview ..."):
        records = airtable_read_records()
    
    if records:
        try:
            df = pd.DataFrame(records)
            
            # Ensure Bill Amount is properly formatted as numeric
            df['Bill Amount'] = pd.to_numeric(df['Bill Amount'], errors='coerce').fillna(0.0)
            
            # Create a copy for analytics
            analytics_df = df.copy()
            
            # ===== ANALYTICS SECTION =====
            st.subheader("Analytics")
            
            # Basic Statistics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Records", len(df))
            
            with col2:
                unique_companies = df['Company Name'].nunique()
                st.metric("Unique Companies", unique_companies)

            with col3:
                total_bill_amount = analytics_df['Bill Amount'].sum()
                # Add toggle button for showing/hiding bill amount
                show_amount = st.checkbox("👁️ Show Total Bill Amount", value=False)
                if show_amount:
                    st.metric("Total Bill Amount", f"₹{total_bill_amount:,.2f}")
                else:
                    st.metric("Total Bill Amount", "₹-- --")
            
            # New Entries Analysis (Gmail extracted entries)
            st.subheader("New contracts")
            
            # Identify new entries - records that have only ISIN, Instrument, and Company Name filled
            # Consider an entry "new" if ARN No is empty (indicating it came from Gmail extraction)
            new_entries = analytics_df[
                (analytics_df['ARN No'].fillna('').str.strip() == '') |
                (analytics_df['Email ID'].fillna('').str.strip() == '') |
                (analytics_df['COMPANY SPOC'].fillna('').str.strip() == '')
            ]
            
            # More specific check - entries that have basic info but missing critical fields
            incomplete_entries = analytics_df[
                (analytics_df['ARN No'].fillna('').str.strip() == '') &
                (analytics_df['Company Name'].fillna('').str.strip() != '') &
                (analytics_df['ISIN'].fillna('').str.strip() != '')
            ]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("📥 New/Incomplete Entries", len(incomplete_entries))
                
            with col2:
                pending_entries = len(incomplete_entries)
                st.metric("⏳ Pending Completion", pending_entries)
            
            # Show incomplete entries if any
            if len(incomplete_entries) > 0:
                with st.expander(f"🔍 View Incomplete Records ({len(incomplete_entries)} records)", expanded=False):
                    st.write("**Records requiring completion:**")
                    incomplete_display = incomplete_entries[['Company Name', 'ISIN', 'Security Type']].copy()
                    st.dataframe(incomplete_display, use_container_width=True)
            
            # Bill Due Analysis
            st.subheader("📅 Bill Due Date Analysis")
            
            # Get current date
            current_date = datetime.now().date()
            
            # Initialize variables
            due_1_week = pd.DataFrame()
            due_1_month = pd.DataFrame()
            due_3_months = pd.DataFrame()
            bills_df = pd.DataFrame()
            
            # Process all bill dates
            bill_dates = []
            for index, row in analytics_df.iterrows():
                company_name = row['Company Name']
                for i in range(1, 8):  # BILL Date 1 to 7
                    bill_date_col = f'BILL Date {i}'
                    if bill_date_col in row and pd.notna(row[bill_date_col]):
                        try:
                            if isinstance(row[bill_date_col], str):
                                bill_date = datetime.strptime(row[bill_date_col], '%Y-%m-%d').date()
                            else:
                                bill_date = row[bill_date_col]
                            
                            # Only consider future dates
                            if bill_date >= current_date:
                                days_until_due = (bill_date - current_date).days
                                bill_dates.append({
                                    'Company Name': company_name,
                                    'Bill Date': bill_date,
                                    'Days Until Due': days_until_due
                                })
                        except:
                            continue
            
            if bill_dates:
                bills_df = pd.DataFrame(bill_dates)
                
                # Categorize bills by due date
                due_1_week = bills_df[bills_df['Days Until Due'] <= 7]
                due_1_month = bills_df[bills_df['Days Until Due'] <= 30]
                due_3_months = bills_df[bills_df['Days Until Due'] <= 90]
                
                # Display due date metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("🚨 Due in 1 Week", len(due_1_week))
                    
                with col2:
                    st.metric("⚠️ Due in 1 Month", len(due_1_month))
                    
                with col3:
                    st.metric("📋 Due in 3 Months", len(due_3_months))
                    
                with col4:
                    st.metric("📊 Total Upcoming Bills", len(bills_df))
                
                # Show urgent bills (due in 1 week)
                if len(due_1_week) > 0:
                    with st.expander(f"🚨 View Urgent Bills ({len(due_1_week)} bills due in 1 week)", expanded=False):
                        urgent_bills = due_1_week.sort_values('Days Until Due')
                        st.dataframe(urgent_bills, use_container_width=True)
                
                # Show upcoming bills (due in 1 month)
                if len(due_1_month) > 0:
                    with st.expander(f"⚠️ View Upcoming Bills ({len(due_1_month)} bills due in 1 month)", expanded=False):
                        upcoming_bills = due_1_month.sort_values('Days Until Due')
                        st.dataframe(upcoming_bills, use_container_width=True)
                
                # Bill due distribution chart
                st.subheader("📊 Bill Due Distribution")
                
                # Create time buckets for visualization
                bills_df['Due Category'] = bills_df['Days Until Due'].apply(
                    lambda x: '1 Week' if x <= 7 else 
                             '1 Month' if x <= 30 else 
                             '3 Months' if x <= 90 else 
                             'Later'
                )
                
                due_distribution = bills_df['Due Category'].value_counts()
                
                # Display as bar chart
                st.bar_chart(due_distribution)
                
            else:
                st.info("No upcoming bill dates found in the database.")
                # Set metrics to 0 when no bills found
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🚨 Due in 1 Week", 0)
                with col2:
                    st.metric("⚠️ Due in 1 Month", 0)
                with col3:
                    st.metric("📋 Due in 3 Months", 0)
                with col4:
                    st.metric("📊 Total Upcoming Bills", 0)
            
                # Generate 48 months from Jan 2021
                start_date = datetime(2021, 1, 1)
                months = [start_date + pd.DateOffset(months=i) for i in range(48)]

                # Generate more realistic mock data with growth and spikes
                registrations = []
                revenues = []
                base_registrations = 20
                base_revenue = 80000

                for i in range(48):
                    # Calculate growth with a stronger upward trend over time
                    reg_growth = base_registrations * (1 + (i / 48) * 2.5)
                    rev_growth = base_revenue * (1 + (i / 48) * 3.5)

                    # Add seasonality/random spikes for realism
                    if i % 12 in [2, 3, 9, 10]:  # Simulate busy seasons (e.g., Mar-Apr, Oct-Nov)
                        reg_multiplier = random.uniform(1.3, 1.8)
                        rev_multiplier = random.uniform(1.4, 2.0)
                    else:
                        reg_multiplier = random.uniform(0.85, 1.1)
                        rev_multiplier = random.uniform(0.9, 1.2)

                    current_registrations = int(reg_growth * reg_multiplier)
                    current_revenue = int(rev_growth * rev_multiplier)

                    # Ensure a minimum value to avoid unrealistic dips
                    registrations.append(max(18, current_registrations))
                    revenues.append(max(75000, current_revenue))

                # Create DataFrame
                trend_df = pd.DataFrame({
                    "Month": months,
                    "New Registrations": registrations,
                    "Total Bill Amount": revenues
                })

                # Add time grouping columns
                trend_df["Month_Year"] = trend_df["Month"].dt.to_period("M").astype(str)
                trend_df["Quarter"] = trend_df["Month"].dt.to_period("Q").astype(str)
                trend_df["Year"] = trend_df["Month"].dt.year.astype(str)

                # Add toggle
                st.subheader("📅 Monthly Trends")
                granularity = st.radio("Select Time Granularity", ["Monthly", "Quarterly", "Yearly"], horizontal=True)

                if granularity == "Monthly":
                    plot_df = trend_df.copy()
                    x_axis = "Month_Year"
                elif granularity == "Quarterly":
                    plot_df = trend_df.groupby("Quarter").agg({
                        "New Registrations": "sum",
                        "Total Bill Amount": "sum"
                    }).reset_index()
                    x_axis = "Quarter"
                else:
                    plot_df = trend_df.groupby("Year").agg({
                        "New Registrations": "sum",
                        "Total Bill Amount": "sum"
                    }).reset_index()
                    x_axis = "Year"

                # Show charts
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader(f"📊 {granularity} Registrations")
                    st.line_chart(data=plot_df, x=x_axis, y="New Registrations")

                with col2:
                    st.subheader(f"💰 {granularity} Revenue Trend")
                    st.line_chart(data=plot_df, x=x_axis, y="Total Bill Amount")




            # Company-wise Analysis
            st.subheader("🏢 Company-wise Analysis")
            
            # Count records per company
            company_counts = analytics_df.groupby('Company Name').agg({
                'ISIN': 'count',
                'Bill Amount': 'sum',
                'ARN No': lambda x: (x.fillna('').str.strip() != '').sum()  # Count completed records
            }).round(2)
            
            company_counts.columns = ['Total Records', 'Total Bill Amount', 'Completed Records']
            company_counts['Completion Rate'] = (company_counts['Completed Records'] / company_counts['Total Records'] * 100).round(1)
            company_counts['Total Bill Amount'] = company_counts['Total Bill Amount'].apply(lambda x: f"₹{x:,.2f}")
            
            with st.expander(f"📊 View Company-wise Analysis ({len(company_counts)} companies)", expanded=False):
                st.dataframe(company_counts.sort_values('Total Records', ascending=False), use_container_width=True)
            
            # # ===== BUSINESS INTELLIGENCE SECTION =====
            # st.subheader("📈 Business Intelligence Dashboard")
            
            # # Monthly Trends Analysis
            # st.subheader("📅 Monthly Trends")
            
            # # Convert ISIN Allotment Date to datetime for analysis
            # analytics_df['ISIN Allotment Date'] = pd.to_datetime(analytics_df['ISIN Allotment Date'], errors='coerce')
            # analytics_df['Month_Year'] = analytics_df['ISIN Allotment Date'].dt.to_period('M')
            
            # # Monthly registration trends
            # monthly_trends = analytics_df.groupby('Month_Year').agg({
            #     'Company Name': 'count',
            #     'Bill Amount': 'sum'
            # }).reset_index()
            # monthly_trends.columns = ['Month', 'New Registrations', 'Total Bill Amount']
            
            # if len(monthly_trends) > 0:
            #     col1, col2 = st.columns(2)
            #     with col1:
            #         st.subheader("📊 Monthly Registrations")
            #         st.line_chart(monthly_trends.set_index('Month')['New Registrations'])
                
            #     with col2:
            #         st.subheader("💰 Monthly Revenue Trend")
            #         st.line_chart(monthly_trends.set_index('Month')['Total Bill Amount'])
            
            # Security Type Distribution
            st.subheader("🏷️ Security Type Distribution")
            security_distribution = analytics_df['Security Type'].value_counts()
            
            # Only show the bar chart (removed the top security types section)
            st.bar_chart(security_distribution)
            
            # Financial Health Indicators
            st.subheader("💡 Financial Health Indicators")
            
            # Calculate key financial metrics
            total_revenue = analytics_df['Bill Amount'].sum()
            avg_bill_amount = analytics_df['Bill Amount'].mean()
            high_value_clients = len(analytics_df[analytics_df['Bill Amount'] > avg_bill_amount * 2])
            
            # Revenue per security type
            revenue_by_security = analytics_df.groupby('Security Type')['Bill Amount'].sum().sort_values(ascending=False)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Average Bill Amount", f"₹{avg_bill_amount:,.2f}")
            
            with col2:
                st.metric("🌟 High Value Clients", high_value_clients)
            
            with col3:
                median_bill = analytics_df['Bill Amount'].median()
                st.metric("📊 Median Bill Amount", f"₹{median_bill:,.2f}")
            
            with col4:
                active_companies = len(analytics_df[analytics_df['Bill Amount'] > 0])
                st.metric("🏢 Active Companies", active_companies)
            
            # Quick Action Items
            st.subheader("🎯 Quick Action Items")
            
            action_items = []
            
            if len(incomplete_entries) > 0:
                action_items.append(f"📝 Complete {len(incomplete_entries)} incomplete records")
            
            if len(due_1_week) > 0:
                action_items.append(f"🚨 Follow up on {len(due_1_week)} urgent bills")
            
            if len(action_items) > 0:
                for item in action_items:
                    st.warning(item)
            else:
                st.success("🎉 All systems running smoothly!")
                
        except Exception as e:
            st.error(f"Error displaying database: {str(e)}")
            st.info("Raw data preview:")
            st.json(records[:3] if len(records) > 0 else {})
    else:
        st.info("No records found in the database.")

def database_page():
    st.title("📋 Complete Database Records")
    
    with st.spinner("Loading database records..."):
        records = airtable_read_records()
    
    if records:
        try:
            df = pd.DataFrame(records)
            
            # Ensure Bill Amount is properly formatted as numeric
            df['Bill Amount'] = pd.to_numeric(df['Bill Amount'], errors='coerce').fillna(0.0)
            
            # Create a copy for analytics before formatting
            analytics_df = df.copy()
            
            # Format Bill Amount for display
            df['Bill Amount'] = df['Bill Amount'].apply(lambda x: f"₹{x:,.2f}" if x > 0 else "₹0.00")
            
            # ===== SEARCH SECTION =====
            col1, col2 = st.columns([4, 1])
            
            with col1:
                search_term = st.text_input("🔍 Search by Company Name, ISIN, ARN, or any field", placeholder="Enter search term...")
            
            # ===== APPLY SEARCH FILTER =====
            filtered_df = df.copy()
            
            if search_term and (search_term):
                # Search across multiple columns
                search_columns = ['Company Name', 'ISIN', 'ARN No', 'Email ID', 'COMPANY SPOC', 'Security Type']
                
                # Create a mask for search across all specified columns
                search_mask = pd.Series([False] * len(df))
                
                for col in search_columns:
                    if col in df.columns:
                        search_mask |= df[col].fillna('').str.contains(search_term, case=False, na=False)
                
                filtered_df = df[search_mask]
            
            # ===== DATABASE TABLE =====
            st.dataframe(
                filtered_df,
                use_container_width=True,
                height=600,
                hide_index=True,
                column_config={
                    "BILL Date 2": None,
                    "BILL Date 3": None,
                    "BILL Date 4": None,
                    "BILL Date 5": None,
                    "BILL Date 6": None,
                    "BILL Date 7": None
                }
            )
                    
                
        except Exception as e:
            st.error(f"Error displaying database: {str(e)}")
            st.info("Raw data preview:")
            st.json(records[:3] if len(records) > 0 else {})
    else:
        st.info("No records found in the database.")

def new_entry_page():
    """Page for creating a new record."""
    st.title("➕ Create a New Entry")

    with st.form("new_entry_form", clear_on_submit=True):
        st.subheader("Enter New Record Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input("Company Name *")
            isin = st.text_input("ISIN *")
            arn_no = st.text_input("ARN No")
            security_type = st.text_input("Security Type")
            company_referred_by = st.text_input("Company Referred By")
            email_id = st.text_input("Email ID")
            company_spoc = st.text_input("COMPANY SPOC")
            gstin = st.text_input("GSTIN")
        
        with col2:
            address = st.text_area("ADDRESS")
            bill_amount = st.number_input("Bill Amount", value=0.0, format="%.2f")
            link = st.text_input("LINK")
            company_path = st.text_input("Company Path")
            
            # Date inputs
            isin_allotment_date = st.date_input("ISIN Allotment Date", value=None)
            bill_date_1 = st.date_input("BILL Date 1", value=None)

        st.markdown("_* Fields are required_")
        submit_button = st.form_submit_button("✅ Create New Entry", type="primary")
        
        if submit_button:
            # Basic validation
            if not company_name or not isin:
                st.error("❌ Company Name and ISIN are required fields.")
            else:
                try:
                    with st.spinner("Creating record in Airtable..."):
                        new_record_data = {
                            "Company Name": company_name,
                            "ISIN": isin,
                            "ARN No": arn_no,
                            "Security Type": security_type,
                            "Company reffered By": company_referred_by,
                            "Email ID": email_id,
                            "COMPANY SPOC": company_spoc,
                            "GSTIN": gstin,
                            "ADDRESS": address,
                            "Bill Amount": bill_amount,
                            "LINK": link,
                            "Company Path": company_path,
                            "ISIN Allotment Date": isin_allotment_date.strftime("%Y-%m-%d") if isin_allotment_date else None,
                            "BILL Date 1": bill_date_1.strftime("%Y-%m-%d") if bill_date_1 else None,
                        }
                        
                        table.create(new_record_data)
                        st.success("✅ New entry created successfully!")
                        airtable_read_records.clear() # Clear cache to show new record
                        
                except Exception as e:
                    st.error(f"❌ Failed to create new entry: {str(e)}")

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
                                default_bill_date = None
                        else:
                            default_bill_date = None
                    except Exception:
                        default_bill_date = None

                    bill_date_1 = st.date_input("BILL Date 1", value=default_bill_date, key="bill_date_1")

                submit = st.form_submit_button("✅ Update Record")
                
                if submit:
                    try:
                        # Find the Airtable record ID
                        airtable_records = table.all(formula=f"{{ISIN}}='{selected_isin}'")
                        if airtable_records:
                            airtable_id = airtable_records[0]["id"]
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
                            airtable_read_records.clear() # Clear cache to show updated data
                            
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
    initial_sidebar_state="collapsed",
    layout="wide"
)

# Professional sidebar navigation using streamlit-option-menu
with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: #0d6efd;'>Reminder App</h1>", unsafe_allow_html=True)
    
    # List of pages and their icons
    pages = ["Overview", "Database", "New Record", "Edit Record", "Logout"]
    icons = ["speedometer2", "table", "plus-square-dotted", "pencil-square", "box-arrow-right"]

    # Get the index of the current page, default to 0 if not found
    try:
        default_index = pages.index(st.session_state.page)
    except (ValueError, AttributeError):
        default_index = 0
        st.session_state.page = pages[default_index]

    # Create the option menu
    selected_page = option_menu(
        menu_title=None,
        options=pages,
        icons=icons,
        menu_icon="cast",
        default_index=default_index,
        styles={
            "container": {"padding": "5px !important", "background-color": "#f8f9fa"},
            "icon": {"color": "#495057", "font-size": "20px"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "margin": "0px",
                "padding": "10px",
                "--hover-color": "#e9ecef",
                "border-radius": "5px",
            },
            "nav-link-selected": {"background-color": "#0d6efd", "color": "white"},
        },
    )

    # Handle page selection
    if selected_page != st.session_state.page:
        st.session_state.page = selected_page
        st.rerun()


# Display selected page or handle logout
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
