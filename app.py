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

CALENDAR_ID = 'chalasaniajitha@gmail.com'  # Or the specific calendar ID your service account has access to

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

# Streamlit chat interface
st.title("📅 Calendar Booking Chatbot")

if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.chat_input("Ask me to book your meeting...")

pending_suggestion = st.session_state.get("pending_suggestion", {})

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    reply = ""

    msg = user_input.strip().lower()

    if msg in ["yes", "ok", "sure"] and "time" in pending_suggestion:
        start_local = pending_suggestion["time"]
        end_local = start_local + datetime.timedelta(minutes=30)
        summary = pending_suggestion.get("summary", "Scheduled Event")
        link = create_event(summary, start_local, end_local)
        reply = f"✅ Booked {summary} for {start_local.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
        pending_suggestion = {}

    elif msg in ["no", "reject"]:
        reply = "❌ Okay, please suggest a different time."
        pending_suggestion = {}

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
                reply = f"✅ Booked {summary} for {parsed.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
            else:
                # Suggest next 3 slots
                for i in range(1, 4):
                    alt_start = parsed + datetime.timedelta(hours=i)
                    alt_end = alt_start + datetime.timedelta(minutes=30)
                    if check_availability(alt_start, alt_end):
                        reply = f"❌ Busy at requested time. How about {alt_start.strftime('%Y-%m-%d %I:%M %p')}?"
                        pending_suggestion = {"time": alt_start, "summary": summary}
                        break
                else:
                    reply = "❌ Busy at requested time and no nearby slots found. Please suggest another time."

    st.session_state["pending_suggestion"] = pending_suggestion
    st.session_state.messages.append({"role": "assistant", "content": reply})

for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])
