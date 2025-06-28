import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
import pytz
from dateparser.search import search_dates

# Setup
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

# Sidebar
st.sidebar.title("📌 Today's Schedule (IST)")
todays_events = get_todays_events()
if not todays_events:
    st.sidebar.info("No events scheduled today.")
else:
    for e in todays_events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        start_dt = datetime.datetime.fromisoformat(start).astimezone(pytz.timezone('Asia/Kolkata'))
        st.sidebar.write(f"✅ **{e['summary']}** at {start_dt.strftime('%I:%M %p')}")

# Main
st.title("💬 Interactive Calendar Booking Bot")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

# Quick Book Buttons
st.markdown("### Quick Book")
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
        st.markdown(f"#### Book: {clicked}")
        custom_name = ""
        if clicked == "Other":
            custom_name = st.text_input("Enter event name")

        date = st.date_input("Pick date", datetime.date.today())

        col_t1, col_t2, col_t3 = st.columns([3,2,2])
        hour = col_t1.selectbox("Hour", list(range(1,13)))
        minute = col_t2.selectbox("Minute", [0, 15, 30, 45])
        am_pm = col_t3.selectbox("AM/PM", ["AM", "PM"])

        manual_time = st.checkbox("Manually enter time (HH:MM AM/PM)")
        manual_time_input = ""
        if manual_time:
            manual_time_input = st.text_input("Enter time manually (e.g. 7:13 PM)")

        duration = st.selectbox("Duration (minutes)", [15, 30, 45, 60, 90, 120])
        manual_duration = st.checkbox("Manually enter duration")
        if manual_duration:
            duration = st.number_input("Enter duration (minutes)", min_value=1, max_value=480, value=duration)

        submit = st.form_submit_button("Book Now")

        if submit:
            tz = pytz.timezone('Asia/Kolkata')
            if manual_time and manual_time_input:
                try:
                    parsed_time = datetime.datetime.strptime(manual_time_input, "%I:%M %p").time()
                except:
                    st.error("Invalid time format. Use HH:MM AM/PM.")
                    st.stop()
            else:
                hour_24 = hour % 12 + (12 if am_pm == "PM" else 0)
                parsed_time = datetime.time(hour=hour_24, minute=minute)

            start_dt = tz.localize(datetime.datetime.combine(date, parsed_time))
            end_dt = start_dt + datetime.timedelta(minutes=duration)
            summary = custom_name if clicked == "Other" else clicked

            if check_availability(start_dt, end_dt):
                link = create_event(summary, start_dt, end_dt)
                msg = f"✅ **{summary} booked on {start_dt.strftime('%Y-%m-%d %I:%M %p')} IST** [👉 View here]({link})"
            else:
                msg = f"❌ {summary} time slot is busy. Please try a different time."

            st.session_state.messages.append({"role": "assistant", "content": msg})
            st.chat_message("assistant").markdown(msg)

# Chat Input
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
            reply = f"✅ **{summary} booked on {start.strftime('%Y-%m-%d %I:%M %p')} IST** [👉 View here]({link})"
            st.session_state.pending_suggestion = {}

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
                    reply = f"✅ **{summary} booked on {parsed.strftime('%Y-%m-%d %I:%M %p')} IST** [👉 View here]({link})"
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
        st.chat_message("assistant").markdown(reply)

# Render chat history
for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").markdown(m["content"])
