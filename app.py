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
    st.session_state.latest_event = {
        "summary": summary,
        "time": start_dt.strftime('%I:%M %p'),
        "link": created_event.get('htmlLink')
    }
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

def refresh_sidebar():
    with st.sidebar:
        st.empty()
        st.title("📌 Latest Booking")
        event = st.session_state.latest_event
        if event:
            st.write(f"✅ **{event['summary']}** at {event['time']} — [👉 View here]({event['link']})")
        else:
            st.info("No bookings yet.")

# --- CSS ---
st.markdown("""
<style>
.stButton > button {
    background-color: #007acc;
    color: white !important;
    font-weight: bold;
    border-radius: 6px;
    padding: 6px 12px;
}
.stButton > button:hover {
    background-color: #005f99;
    color: white !important;
}
.stChatMessage {
    background-color: #eef6fb;
    padding: 10px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# --- State ---
if "quickbox_open" not in st.session_state:
    st.session_state.quickbox_open = False
if "clicked_type" not in st.session_state:
    st.session_state.clicked_type = None
if "latest_event" not in st.session_state:
    st.session_state.latest_event = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

# --- Sidebar ---
refresh_sidebar()

# --- Main ---
st.title("💬 Interactive Calendar Booking Bot")

toggle_label = "🔽 Quick Book (open)" if st.session_state.quickbox_open else "▶ Quick Book (closed)"
if st.button(toggle_label):
    st.session_state.quickbox_open = not st.session_state.quickbox_open
    st.session_state.clicked_type = None
    st.stop()

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
                    st.chat_message("assistant").markdown(f"✅ **{summary} booked** — [👉 View here]({link})")
                    refresh_sidebar()
                else:
                    st.chat_message("assistant").markdown(f"❌ {summary} time slot is busy. Try a different time.")

# --- Chat input ---
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
