import json
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
from dateparser.search import search_dates
import pytz

SCOPES = ['https://www.googleapis.com/auth/calendar']

service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES)

service = build('calendar', 'v3', credentials=credentials)

CALENDAR_ID = 'chalasaniajitha@gmail.com'

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

# --- SIDEBAR ---
st.sidebar.title("📌 Instructions")
st.sidebar.markdown("""
- Type a message or use quick buttons below.
- Example: `Book meeting tomorrow 3 PM`
- The bot will suggest times if busy.
""")

# Show upcoming 3 events
now = datetime.datetime.utcnow().isoformat() + 'Z'
events_result = service.events().list(
    calendarId=CALENDAR_ID, timeMin=now,
    maxResults=3, singleEvents=True,
    orderBy='startTime'
).execute()
events = events_result.get('items', [])

st.sidebar.markdown("### ⏳ Next Events")
if not events:
    st.sidebar.write("No upcoming events.")
else:
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        st.sidebar.write(f"- **{event['summary']}** at {start}")

# --- MAIN CHAT ---
st.title("💬 Interactive Calendar Booking Bot")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

# Quick buttons
col1, col2, col3, col4 = st.columns(4)
if col1.button("📞 Call"):
    st.session_state.messages.append({"role": "user", "content": "Book a call"})
if col2.button("✈ Flight"):
    st.session_state.messages.append({"role": "user", "content": "Book a flight"})
if col3.button("📅 Meeting"):
    st.session_state.messages.append({"role": "user", "content": "Book a meeting"})
if col4.button("📝 Other"):
    st.session_state.messages.append({"role": "user", "content": "Book an event"})

# Prompt input
user_input = st.chat_input("Ask me to book your meeting...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

# Handle messages
for idx, m in enumerate(st.session_state.messages):
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])

# Process latest user message
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    user_msg = st.session_state.messages[-1]["content"]
    reply = ""
    msg = user_msg.strip().lower()
    pending = st.session_state.pending_suggestion

    if msg in ["yes", "ok", "sure"] and "time" in pending:
        start_local = pending["time"]
        end_local = start_local + datetime.timedelta(minutes=30)
        summary = pending.get("summary", "Scheduled Event")
        link = create_event(summary, start_local, end_local)
        reply = f"✅ **Booked {summary} for {start_local.strftime('%Y-%m-%d %I:%M %p')}**. [📌 View in Calendar]({link})"
        st.session_state.pending_suggestion = {}

    elif msg in ["no", "reject"]:
        reply = "❌ Okay, please suggest a different time."
        st.session_state.pending_suggestion = {}

    else:
        # Determine event summary
        if "flight" in msg:
            summary = "Flight"
        elif "call" in msg:
            summary = "Call"
        elif "meeting" in msg:
            summary = "Meeting"
        else:
            summary = "Scheduled Event"

        result = search_dates(
            msg,
            settings={
                'PREFER_DATES_FROM': 'future',
                'RETURN_AS_TIMEZONE_AWARE': True,
                'TIMEZONE': 'Asia/Kolkata',
                'RELATIVE_BASE': datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
            }
        )

        if not result:
            reply = "⚠ I couldn’t understand the date/time. Try saying 'tomorrow 4 PM' or 'next Friday 10 AM'."
        else:
            parsed = result[0][1]
            if parsed.tzinfo is None:
                parsed = pytz.timezone('Asia/Kolkata').localize(parsed)

            end_local = parsed + datetime.timedelta(minutes=30)

            if check_availability(parsed, end_local):
                link = create_event(summary, parsed, end_local)
                reply = f"✅ **Booked {summary} for {parsed.strftime('%Y-%m-%d %I:%M %p')}**. [📌 View in Calendar]({link})"
            else:
                for i in range(1, 4):
                    alt_start = parsed + datetime.timedelta(hours=i)
                    alt_end = alt_start + datetime.timedelta(minutes=30)
                    if check_availability(alt_start, alt_end):
                        reply = f"❌ Busy at requested time. How about **{alt_start.strftime('%Y-%m-%d %I:%M %p')}**?"
                        st.session_state.pending_suggestion = {"time": alt_start, "summary": summary}
                        break
                else:
                    reply = "❌ Busy at requested time and no nearby slots found. Please suggest another time."

    st.session_state.messages.append({"role": "assistant", "content": reply})
