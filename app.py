import streamlit as st
import datetime
import pytz
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account
import parsedatetime

# CONFIG
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'chalasaniajitha@gmail.com'

# SERVICE ACCOUNT
service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES
)
service = build('calendar', 'v3', credentials=credentials)

cal = parsedatetime.Calendar()

# FUNCTIONS
def parse_datetime(text):
    time_struct, parse_status = cal.parse(text)
    if parse_status == 0:
        return None
    dt = datetime.datetime(*time_struct[:6])
    return pytz.timezone('Asia/Kolkata').localize(dt)

def detect_summary(text):
    if "flight" in text.lower():
        return "Flight"
    elif "call" in text.lower():
        return "Call"
    elif "meeting" in text.lower():
        return "Meeting"
    else:
        return "Scheduled Event"

def check_availability(start, end):
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return len(events) == 0

def create_event(summary, start, end):
    event = {
        'summary': summary,
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Kolkata'}
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')

# UI
st.title("📅 Smart Calendar Booking Bot")

if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.chat_input("Ask me to book your meeting...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    reply = ""

    summary = detect_summary(user_input)
    dt = parse_datetime(user_input)

    if dt:
        end_dt = dt + datetime.timedelta(minutes=30)
        if check_availability(dt, end_dt):
            link = create_event(summary, dt, end_dt)
            reply = f"✅ Booked {summary} for {dt.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
        else:
            reply = "❌ Time slot busy. Please suggest another time."
    else:
        reply = "⚠ Could not parse your date/time. Please try a clearer phrase."

    st.session_state.messages.append({"role": "assistant", "content": reply})

for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])
