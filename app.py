import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
import pytz
from dateparser.search import search_dates

# ---- GOOGLE CALENDAR SETUP ----
SCOPES = ['https://www.googleapis.com/auth/calendar']
service_account_info = dict(st.secrets["SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)
CALENDAR_ID = 'primary'

# ---- HELPER FUNCTIONS ----
def get_today_events():
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    end_of_day = now.replace(hour=23, minute=59, second=59)

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    return events_result.get('items', [])

def is_free(start, end):
    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])
    return len(events) == 0

def create_event(summary, start, end):
    event = {
        'summary': summary,
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Kolkata'}
    }
    created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created.get('htmlLink')

def parse_datetime_from_text(text):
    result = search_dates(
        text,
        settings={
            'PREFER_DATES_FROM': 'future',
            'RETURN_AS_TIMEZONE_AWARE': True,
            'TIMEZONE': 'Asia/Kolkata',
            'RELATIVE_BASE': datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        }
    )
    if result:
        return result[0][1]
    return None

def handle_user_input(msg):
    msg_lower = msg.lower()
    parsed_dt = parse_datetime_from_text(msg)

    if any(x in msg_lower for x in ["book", "schedule", "set up", "arrange"]) and parsed_dt:
        end_dt = parsed_dt + datetime.timedelta(minutes=30)
        if is_free(parsed_dt, end_dt):
            link = create_event("Scheduled Event", parsed_dt, end_dt)
            return f"✅ Event booked for {parsed_dt.strftime('%Y-%m-%d %I:%M %p')}.\n[View in Calendar]({link})"
        else:
            return "❌ That time is busy. Please suggest another time."
    
    elif any(x in msg_lower for x in ["free", "available", "do i have time", "am i free"]) and parsed_dt:
        end_dt = parsed_dt + datetime.timedelta(minutes=30)
        if is_free(parsed_dt, end_dt):
            return f"✅ Yes, you're free at {parsed_dt.strftime('%Y-%m-%d %I:%M %p')}."
        else:
            return f"❌ You're busy at {parsed_dt.strftime('%Y-%m-%d %I:%M %p')}."

    elif parsed_dt:
        # Vague prompt that at least had time -> treat as booking request
        end_dt = parsed_dt + datetime.timedelta(minutes=30)
        if is_free(parsed_dt, end_dt):
            link = create_event("Scheduled Event", parsed_dt, end_dt)
            return f"✅ Event booked for {parsed_dt.strftime('%Y-%m-%d %I:%M %p')}.\n[View in Calendar]({link})"
        else:
            return f"❌ That time is busy. Please suggest another time."

    else:
        return "⚠ I couldn't understand the date/time. Try saying something like 'Book a meeting tomorrow at 3 PM'."

# ---- STREAMLIT UI ----
st.title("📅 AI Calendar Booking Assistant")

# Sidebar showing today's schedule
st.sidebar.header("📌 Today's Schedule")
events_today = get_today_events()
if events_today:
    for event in events_today:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'No Title')
        st.sidebar.write(f"**{summary}**: {start}")
else:
    st.sidebar.write("No events scheduled today.")

# Chat session
if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.chat_input("Ask me to book/check availability...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    reply = handle_user_input(user_input)
    st.session_state.messages.append({"role": "assistant", "content": reply})

    # Update sidebar after booking
    st.experimental_rerun()

for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])
