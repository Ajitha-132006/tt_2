import json
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
from dateparser.search import search_dates
import pytz

SCOPES = ['https://www.googleapis.com/auth/calendar']

# Authenticate
service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES)

service = build('calendar', 'v3', credentials=credentials)

CALENDAR_ID = 'chalasaniajitha@gmail.com'  # Replace with your calendar ID

# Helper functions
def get_today_events():
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    end_of_day = tz.localize(datetime.datetime.combine(now.date(), datetime.time(23, 59)))
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def check_availability(start, end):
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return len(events) == 0, events

def delete_events(events):
    for event in events:
        service.events().delete(calendarId=CALENDAR_ID, eventId=event['id']).execute()

def create_event(summary, start, end):
    _, overlapping = check_availability(start, end)
    if overlapping:
        delete_events(overlapping)
    event = {
        'summary': summary,
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Kolkata'}
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')

def parse_time_from_input(text):
    tz = pytz.timezone('Asia/Kolkata')
    result = search_dates(
        text,
        settings={
            'PREFER_DATES_FROM': 'future',
            'RETURN_AS_TIMEZONE_AWARE': True,
            'TIMEZONE': 'Asia/Kolkata',
            'RELATIVE_BASE': datetime.datetime.now(tz)
        }
    )
    if not result:
        return None
    parsed = result[0][1]
    if parsed.tzinfo is None:
        parsed = tz.localize(parsed)
    return parsed

# Sidebar with today’s schedule
st.sidebar.header("📌 Today's Schedule")
today_events = get_today_events()
if today_events:
    for e in today_events:
        start_time = e['start'].get('dateTime', e['start'].get('date'))
        st.sidebar.write(f"- **{e['summary']}** at {start_time}")
else:
    st.sidebar.write("No events today.")

# Main UI
st.title("📅 Smart Calendar Booking Bot")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

user_input = st.chat_input("Ask me to book your meeting...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    reply = ""
    msg = user_input.strip().lower()
    pending = st.session_state.pending_suggestion

    # Confirmation of pending suggestion
    if msg in ["yes", "ok", "sure"] and pending:
        start = pending["time"]
        end = start + datetime.timedelta(minutes=30)
        summary = pending.get("summary", "Scheduled Event")
        link = create_event(summary, start, end)
        reply = f"✅ Booked {summary} for {start.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
        st.session_state.pending_suggestion = {}

    elif msg in ["no", "reject"]:
        reply = "❌ Okay, please provide a different time."
        st.session_state.pending_suggestion = {}

    else:
        # Decide summary
        summary = "Scheduled Event"
        if "call" in msg:
            summary = "Call"
        elif "meeting" in msg:
            summary = "Meeting"
        elif "flight" in msg:
            summary = "Flight"

        parsed = parse_time_from_input(user_input)

        if parsed:
            tz = pytz.timezone('Asia/Kolkata')
            now = datetime.datetime.now(tz)

            if parsed < now:
                reply = "⚠ The time you provided is in the past. Please give a future time."
            else:
                end = parsed + datetime.timedelta(minutes=30)
                free, _ = check_availability(parsed, end)
                if free:
                    link = create_event(summary, parsed, end)
                    reply = f"✅ Booked {summary} for {parsed.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
                else:
                    # Suggest alternative slots
                    suggested = None
                    for i in range(1, 5):
                        alt_start = parsed + datetime.timedelta(hours=i)
                        alt_end = alt_start + datetime.timedelta(minutes=30)
                        if alt_start > now:
                            free_alt, _ = check_availability(alt_start, alt_end)
                            if free_alt:
                                suggested = alt_start
                                break
                    if suggested:
                        reply = f"❌ Busy at requested time. How about {suggested.strftime('%Y-%m-%d %I:%M %p')}?"
                        st.session_state.pending_suggestion = {"time": suggested, "summary": summary}
                    else:
                        reply = "❌ Busy at requested time and no nearby slots found. Please suggest another time."
        else:
            # Handle vague / ambiguous input
            if any(word in msg for word in ["afternoon", "evening", "morning", "soon", "asap", "office hours"]):
                tz = pytz.timezone('Asia/Kolkata')
                now = datetime.datetime.now(tz)
                # Default to next slot in guessed period
                if "afternoon" in msg:
                    tentative = now.replace(hour=15, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                elif "morning" in msg:
                    tentative = now.replace(hour=10, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                elif "evening" in msg:
                    tentative = now.replace(hour=18, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                else:
                    tentative = now + datetime.timedelta(hours=1)

                end = tentative + datetime.timedelta(minutes=30)
                free, _ = check_availability(tentative, end)
                if free:
                    link = create_event(summary, tentative, end)
                    reply = f"✅ Booked {summary} for {tentative.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
                else:
                    reply = "❌ You're busy at the guessed time. Please provide a specific time."
            else:
                reply = "⚠ I couldn’t understand your time request. Please specify a proper date and time (e.g., 'tomorrow at 3 PM')."

    st.session_state.messages.append({"role": "assistant", "content": reply})

# Display chat history
for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])
