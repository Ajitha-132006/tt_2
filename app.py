import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
import pytz
from dateparser.search import search_dates

# --- Google Calendar Setup ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES
)
service = build('calendar', 'v3', credentials=credentials)
CALENDAR_ID = 'chalasaniajitha@gmail.com'

def create_event(summary, start_dt, end_dt):
    event = {
        'summary': summary,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'}
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')

def get_todays_events():
    tz = pytz.timezone('Asia/Kolkata')
    today_start = datetime.datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + datetime.timedelta(days=1)
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=today_start.isoformat(),
        timeMax=today_end.isoformat(),
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
    return len(events_result.get('items', [])) == 0

# --- Sidebar: Today's Events ---
def refresh_sidebar():
   st.sidebar.markdown("## 📌 <span style='color:#4CAF50'>Today's Schedule (IST)</span>", unsafe_allow_html=True)
    todays_events = get_todays_events()
    if not todays_events:
        st.sidebar.info("No events scheduled today.")
    else:
        for e in todays_events:
            start = e['start'].get('dateTime', e['start'].get('date'))
            start_dt = datetime.datetime.fromisoformat(start).astimezone(pytz.timezone('Asia/Kolkata'))
            st.sidebar.markdown(
                f"<div style='background-color:#e8f5e9;padding:5px;border-radius:5px;'>"
                f"<b>{e['summary']}</b> at {start_dt.strftime('%I:%M %p')}</div>",
                unsafe_allow_html=True
            )

refresh_sidebar()

# --- Main ---
st.markdown("<h1 style='color:#3f51b5;'>💬 Interactive Calendar Booking Bot</h1>", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

# --- Quick Book ---
st.markdown("### <span style='color:#009688'>Quick Book</span>", unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
clicked = None
if col1.button("📞 Call"):
    clicked = "Call"
if col2.button("📅 Meeting"):
    clicked = "Meeting"
if col3.button("✈ Flight"):
    clicked = "Flight"
if col4.button("📝 Other"):
    clicked = "Other"

if clicked:
    with st.form(f"{clicked}_form"):
        st.markdown(f"<h4 style='color:#607d8b;'>Booking: {clicked}</h4>", unsafe_allow_html=True)
        custom_name = ""
        if clicked == "Other":
            custom_name = st.text_input("Enter event name")

        date = st.date_input("Pick date", datetime.date.today())
        col_t1, col_t2, col_t3 = st.columns([3,2,2])
        hour = col_t1.selectbox("Hour", list(range(1, 13)))
        minute = col_t2.selectbox("Minute", [0, 15, 30, 45])
        am_pm = col_t3.selectbox("AM/PM", ["AM", "PM"])

        manual_time_input = st.text_input("Optional manual time (HH:MM AM/PM)", "")

        duration = st.selectbox("Duration (minutes)", [15, 30, 45, 60, 90, 120])
        manual_duration = st.text_input("Optional manual duration (minutes)", "")

        submit = st.form_submit_button("✅ Book Now")

        if submit:
            tz = pytz.timezone('Asia/Kolkata')
            try:
                if manual_time_input:
                    parsed_time = datetime.datetime.strptime(manual_time_input.strip(), "%I:%M %p").time()
                else:
                    hour_24 = hour % 12 + (12 if am_pm == "PM" else 0)
                    parsed_time = datetime.time(hour=hour_24, minute=minute)

                duration_val = int(manual_duration) if manual_duration else duration

                start_dt = tz.localize(datetime.datetime.combine(date, parsed_time))
                end_dt = start_dt + datetime.timedelta(minutes=duration_val)

                summary = custom_name if clicked == "Other" else clicked

                if check_availability(start_dt, end_dt):
                    link = create_event(summary, start_dt, end_dt)
                    msg = f"<div style='background-color:#d0f0c0;padding:10px;border-radius:5px;'>✅ <b>{summary} booked on {start_dt.strftime('%Y-%m-%d %I:%M %p')} IST</b> 👉 <a href='{link}' target='_blank'>View here</a></div>"
                else:
                    msg = f"<div style='background-color:#ffe0e0;padding:10px;border-radius:5px;'>❌ {summary} time slot is busy. Try another time.</div>"

                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.chat_message("assistant").markdown(msg, unsafe_allow_html=True)
                refresh_sidebar()  # Auto-refresh sidebar to show new event
            except:
                st.error("⚠ Invalid manual time or duration format.")

# --- Chat Input ---
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
            reply = f"<div style='background-color:#d0f0c0;padding:10px;border-radius:5px;'>✅ <b>{summary} booked on {start.strftime('%Y-%m-%d %I:%M %p')} IST</b> 👉 <a href='{link}' target='_blank'>View here</a></div>"
            st.session_state.pending_suggestion = {}
            refresh_sidebar()

        elif msg in ["no", "reject"]:
            reply = "<div style='background-color:#ffe0e0;padding:10px;border-radius:5px;'>❌ Okay, suggest a different time.</div>"
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
                reply = "<div style='background-color:#fff3cd;padding:10px;border-radius:5px;'>⚠ Could not parse date/time. Try `tomorrow 4 PM`.</div>"
            else:
                parsed = result[0][1]
                if parsed.tzinfo is None:
                    parsed = pytz.timezone('Asia/Kolkata').localize(parsed)
                end = parsed + datetime.timedelta(minutes=30)

                if check_availability(parsed, end):
                    link = create_event(summary, parsed, end)
                    reply = f"<div style='background-color:#d0f0c0;padding:10px;border-radius:5px;'>✅ <b>{summary} booked on {parsed.strftime('%Y-%m-%d %I:%M %p')} IST</b> 👉 <a href='{link}' target='_blank'>View here</a></div>"
                    refresh_sidebar()
                else:
                    for i in range(1, 4):
                        alt_start = parsed + datetime.timedelta(hours=i)
                        alt_end = alt_start + datetime.timedelta(minutes=30)
                        if check_availability(alt_start, alt_end):
                            reply = f"<div style='background-color:#fff3cd;padding:10px;border-radius:5px;'>❌ Busy at requested time. How about <b>{alt_start.strftime('%Y-%m-%d %I:%M %p')} IST</b>? Reply `yes` to confirm.</div>"
                            st.session_state.pending_suggestion = {"time": alt_start, "summary": summary}
                            break
                    else:
                        reply = "<div style='background-color:#ffe0e0;padding:10px;border-radius:5px;'>❌ Busy at requested time. No nearby slots found.</div>"

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.chat_message("assistant").markdown(reply, unsafe_allow_html=True)

# --- Render chat history ---
for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").markdown(m["content"], unsafe_allow_html=True)
