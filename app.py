import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
import pytz
from dateparser.search import search_dates

# --- Google Calendar Setup ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)
CALENDAR_ID = 'chalasaniajitha@gmail.com'

# --- Functions ---
def create_event(summary, start_dt, end_dt):
    event = {
        'summary': summary,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'}
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')

def check_availability(start, end):
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return len(events_result.get('items', [])) == 0

def get_events_in_range(start, end):
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def refresh_sidebar():
    with st.sidebar:
        st.empty()
        st.title("📌 Calendar Schedule")

        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + datetime.timedelta(days=1)
        day_after_start = tomorrow_start + datetime.timedelta(days=1)

        today_events = get_events_in_range(today_start, tomorrow_start)
        tomorrow_events = get_events_in_range(tomorrow_start, day_after_start)

        st.subheader("Today's Events")
        if not today_events:
            st.info("No events today.")
        else:
            for e in today_events:
                start = e['start'].get('dateTime', e['start'].get('date'))
                start_dt = datetime.datetime.fromisoformat(start).astimezone(tz)
                st.write(f"✅ **{e['summary']}** at {start_dt.strftime('%I:%M %p')}")

        st.markdown("<hr style='border: 1px solid #ccc;'>", unsafe_allow_html=True)

        st.subheader("Tomorrow's Events")
        if not tomorrow_events:
            st.info("No events tomorrow.")
        else:
            for e in tomorrow_events:
                start = e['start'].get('dateTime', e['start'].get('date'))
                start_dt = datetime.datetime.fromisoformat(start).astimezone(tz)
                st.write(f"✅ **{e['summary']}** at {start_dt.strftime('%I:%M %p')}")

# --- Styling ---
st.markdown("""
<style>
.stButton > button {
    background-color: #007acc;
    color: white;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 12px;
}
.stButton > button:hover {
    background-color: #005f99;
}
.stChatMessage {
    background-color: #eef6fb;
    padding: 10px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# --- Session state ---
if "quickbox_open" not in st.session_state:
    st.session_state.quickbox_open = False
if "clicked_type" not in st.session_state:
    st.session_state.clicked_type = None
if "last_booking_msg" not in st.session_state:
    st.session_state.last_booking_msg = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

# --- Sidebar ---
refresh_sidebar()

# --- Main UI ---
st.title("💬 Interactive Calendar Booking Bot")

# Toggle button
toggle_label = "🔽 Quick Book (open)" if st.session_state.quickbox_open else "▶ Quick Book (closed)"
if st.button(toggle_label):
    st.session_state.quickbox_open = not st.session_state.quickbox_open
    st.session_state.clicked_type = None
    st.stop()  # Ensure clean re-render on toggle

# Quick Box
if st.session_state.quickbox_open:
    if st.session_state.clicked_type is None:
        col1, col2, col3, col4 = st.columns(4)
        if col1.button("📞 Call"):
            st.session_state.clicked_type = "Call"
            st.stop()
        if col2.button("📅 Meeting"):
            st.session_state.clicked_type = "Meeting"
            st.stop()
        if col3.button("✈ Flight"):
            st.session_state.clicked_type = "Flight"
            st.stop()
        if col4.button("📝 Other"):
            st.session_state.clicked_type = "Other"
            st.stop()
    else:
        clicked = st.session_state.clicked_type
        st.markdown(f"#### Book: {clicked}")
        custom_name = ""
        if clicked == "Other":
            custom_name = st.text_input("Enter event name")

        date = st.date_input("Pick date", datetime.date.today())
        hour = st.selectbox("Hour", list(range(1, 13)))
        minute = st.selectbox("Minute", list(range(0, 60)))
        am_pm = st.selectbox("AM/PM", ["AM", "PM"])
        duration = st.selectbox("Duration (min)", list(range(15, 241, 15)))

        with st.form(f"{clicked}_form"):
            submit = st.form_submit_button("✅ Book Now")
            if submit:
                tz = pytz.timezone('Asia/Kolkata')
                hr24 = hour % 12 + (12 if am_pm == "PM" else 0)
                time_val = datetime.time(hr24, minute)
                start_dt = tz.localize(datetime.datetime.combine(date, time_val))
                end_dt = start_dt + datetime.timedelta(minutes=duration)
                summary = custom_name if clicked == "Other" else clicked

                if check_availability(start_dt, end_dt):
                    link = create_event(summary, start_dt, end_dt)
                    st.session_state.last_booking_msg = f"✅ **{summary} booked** — [👉 View here]({link})"
                    refresh_sidebar()
                else:
                    st.session_state.last_booking_msg = f"❌ {summary} time slot is busy. Try a different time."

# Show booking result
if st.session_state.last_booking_msg:
    st.chat_message("assistant").markdown(st.session_state.last_booking_msg)

# Chat input + processing
user_input = st.chat_input("Ask me to book your meeting...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

if st.session_state.messages:
    last_msg = st.session_state.messages[-1]
    if last_msg["role"] == "user":
        msg = last_msg["content"].lower().strip()
        pending = st.session_state.pending_suggestion
        reply = ""

        if msg in ["yes", "ok", "sure"] and "time" in pending:
            start = pending["time"]
            end = start + datetime.timedelta(minutes=30)
            summary = pending.get("summary", "Scheduled Event")
            link = create_event(summary, start, end)
            reply = f"✅ **{summary} booked** — [👉 View here]({link})"
            st.session_state.pending_suggestion = {}
            refresh_sidebar()
        elif msg in ["no", "reject"]:
            reply = "❌ Okay, suggest a different time."
            st.session_state.pending_suggestion = {}
        else:
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
                reply = "⚠ Could not parse date/time. Try `tomorrow 4 PM`."
            else:
                parsed = result[0][1]
                if parsed.tzinfo is None:
                    parsed = pytz.timezone('Asia/Kolkata').localize(parsed)
                end = parsed + datetime.timedelta(minutes=30)

                if check_availability(parsed, end):
                    link = create_event(summary, parsed, end)
                    reply = f"✅ **{summary} booked** — [👉 View here]({link})"
                    refresh_sidebar()
                else:
                    for i in range(1, 4):
                        alt_start = parsed + datetime.timedelta(hours=i)
                        alt_end = alt_start + datetime.timedelta(minutes=30)
                        if check_availability(alt_start, alt_end):
                            reply = f"❌ Busy at requested time. How about **{alt_start.strftime('%Y-%m-%d %I:%M %p')} IST**? Reply `yes` to confirm."
                            st.session_state.pending_suggestion = {"time": alt_start, "summary": summary}
                            break
                    else:
                        reply = "❌ Busy at requested time and no nearby slots found."

        st.session_state.messages.append({"role": "assistant", "content": reply})

for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").markdown(m["content"])
