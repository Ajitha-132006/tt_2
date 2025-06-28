import json
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
from dateparser.search import search_dates
import pytz

# --- GOOGLE CALENDAR SETUP ---
SCOPES = ['https://www.googleapis.com/auth/calendar']

service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES
)

service = build('calendar', 'v3', credentials=credentials)
CALENDAR_ID = 'chalasaniajitha@gmail.com'

# --- FUNCTIONS ---
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

def get_upcoming_events(n=3):
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now,
        maxResults=n,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

# --- SIDEBAR ---
st.sidebar.title("📌 Your Calendar")
upcoming = get_upcoming_events()
if not upcoming:
    st.sidebar.info("No upcoming events.")
else:
    for e in upcoming:
        start = e['start'].get('dateTime', e['start'].get('date'))
        st.sidebar.write(f"✅ **{e['summary']}**  \n📅 `{start}`")

with st.sidebar.expander("ℹ How to use"):
    st.markdown("""
    - Type or use buttons to book an event  
    - Example: `Book a meeting tomorrow at 4 PM`  
    - Bot suggests next slots if busy  
    """)

# --- MAIN UI ---
now_str = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%A, %d %B %Y %I:%M %p')
st.markdown(f"### 🕒 {now_str}")
st.title("💬 Interactive Calendar Booking Bot")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

# Quick action buttons
col1, col2, col3, col4 = st.columns(4)
if col1.button("📞 Call"):
    st.session_state.messages.append({"role": "user", "content": "Book a call"})
if col2.button("✈ Flight"):
    st.session_state.messages.append({"role": "user", "content": "Book a flight"})
if col3.button("📅 Meeting"):
    st.session_state.messages.append({"role": "user", "content": "Book a meeting"})
if col4.button("📝 Other"):
    st.session_state.messages.append({"role": "user", "content": "Book an event"})

# Chat input
user_input = st.chat_input("Ask me to book your meeting...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

# Display chat
for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])

# Process user input
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    user_msg = st.session_state.messages[-1]["content"].strip().lower()
    reply = ""
    pending = st.session_state.pending_suggestion

    if user_msg in ["yes", "ok", "sure"] and "time" in pending:
        with st.spinner("Booking your event..."):
            start_local = pending["time"]
            end_local = start_local + datetime.timedelta(minutes=30)
            summary = pending.get("summary", "Scheduled Event")
            link = create_event(summary, start_local, end_local)
            reply = f"""
            <div style='background-color:#d0f0c0;padding:10px;border-radius:10px'>
            ✅ **Booked {summary} for {start_local.strftime('%Y-%m-%d %I:%M %p')}**  
            [📌 View in Calendar]({link})
            </div>
            """
            st.session_state.pending_suggestion = {}

    elif user_msg in ["no", "reject"]:
        reply = "<div style='background-color:#ffe0e0;padding:10px;border-radius:10px'>❌ Okay, suggest a different time.</div>"
        st.session_state.pending_suggestion = {}

    else:
        if "flight" in user_msg:
            summary = "Flight"
        elif "call" in user_msg:
            summary = "Call"
        elif "meeting" in user_msg:
            summary = "Meeting"
        else:
            summary = "Scheduled Event"

        result = search_dates(
            user_msg,
            settings={
                'PREFER_DATES_FROM': 'future',
                'RETURN_AS_TIMEZONE_AWARE': True,
                'TIMEZONE': 'Asia/Kolkata',
                'RELATIVE_BASE': datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
            }
        )

        if not result:
            reply = "<div style='background-color:#fff3cd;padding:10px;border-radius:10px'>⚠ Couldn’t parse date/time. Try `tomorrow 4 PM`.</div>"
        else:
            parsed = result[0][1]
            if parsed.tzinfo is None:
                parsed = pytz.timezone('Asia/Kolkata').localize(parsed)
            end_local = parsed + datetime.timedelta(minutes=30)

            if check_availability(parsed, end_local):
                with st.spinner("Booking your event..."):
                    link = create_event(summary, parsed, end_local)
                    reply = f"""
                    <div style='background-color:#d0f0c0;padding:10px;border-radius:10px'>
                    ✅ **Booked {summary} for {parsed.strftime('%Y-%m-%d %I:%M %p')}**  
                    [📌 View in Calendar]({link})
                    </div>
                    """
            else:
                for i in range(1, 4):
                    alt_start = parsed + datetime.timedelta(hours=i)
                    alt_end = alt_start + datetime.timedelta(minutes=30)
                    if check_availability(alt_start, alt_end):
                        reply = f"""
                        <div style='background-color:#fff3cd;padding:10px;border-radius:10px'>
                        ❌ Busy at requested time. How about **{alt_start.strftime('%Y-%m-%d %I:%M %p')}**?  
                        Reply `yes` to confirm.
                        </div>
                        """
                        st.session_state.pending_suggestion = {"time": alt_start, "summary": summary}
                        break
                else:
                    reply = "<div style='background-color:#ffe0e0;padding:10px;border-radius:10px'>❌ Busy at requested time. No nearby slots found.</div>"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.chat_message("assistant").markdown(reply, unsafe_allow_html=True)
