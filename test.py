import gspread
from google.oauth2.service_account import Credentials

SERVICE_ACCOUNT_FILE = 'googlekey.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# 📝 This MUST match the spreadsheet TITLE, not the tab at the bottom
sheet = client.open("reminder").sheet1

# ✅ Write a test row
sheet.append_row(["TestID", "test@example.com", "Hello", "Message", "2025-06-20T12:00:00", "Pending"])

print("✅ Successfully wrote to Google Sheet")
