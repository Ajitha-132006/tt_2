import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
import pytz
from dateparser.search import search_dates

# Setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
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
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_range = today_start + datetime.timedelta(days=3)

    events = get_events_in_range(today_start, end_range)

    st.sidebar.title("📌 Today's Events + Next 2 Days")
    if not events:
        st.sidebar.info("No events scheduled.")
    else:
        for e in events:
            start = e['start'].get('dateTime', e['start'].get('date'))
            start_dt = datetime.datetime.fromisoformat(start).astimezone(tz)
            label = start_dt.strftime('%Y-%m-%d %I:%M %p')
            st.sidebar.write(f"✅ **{e['summary']}** at {label}")

# Initial state
if "clicked_type" not in st.session_state:
    st.session_state.clicked_type = None
if "quickbox_open" not in st.session_state:
    st.session_state.quickbox_open = True
if "last_booking_msg" not in st.session_state:
    st.session_state.last_booking_msg = None

refresh_sidebar()

# Styling
st.markdown("""
<style>
.stButton > button { background-color: #007acc; color: white; font-weight: bold; border-radius: 6px; }
.stChatMessage { background-color: #eef6fb; padding: 10px; border-radius: 10px; }
h1, h2, h3, h4 { color: #007acc; }
</style>
""", unsafe_allow_html=True)

st.title("💬 Interactive Calendar Booking Bot")

# Quick Book toggle
toggle_icon = "🔽" if st.session_state.quickbox_open else "🔼"
if st.button(f"{toggle_icon} Quick Book"):
    st.session_state.quickbox_open = not st.session_state.quickbox_open

if st.session_state.quickbox_open:
    st.markdown("### Quick Book")
    col1, col2, col3, col4 = st.columns(4)

    if col1.button("📞 Call"):
        st.session_state.clicked_type = "Call"
    if col2.button("📅 Meeting"):
        st.session_state.clicked_type = "Meeting"
    if col3.button("✈ Flight"):
        st.session_state.clicked_type = "Flight"
    if col4.button("📝 Other"):
        st.session_state.clicked_type = "Other"

    clicked = st.session_state.clicked_type

    if clicked:
        st.markdown(f"#### Book: {clicked}")
        custom_name = ""
        if clicked == "Other":
            custom_name = st.text_input("Enter event name")

        date = st.date_input("Pick date", datetime.date.today())

        if f"time_{clicked}" not in st.session_state:
            st.session_state[f"time_{clicked}"] = datetime.datetime.now().replace(second=0, microsecond=0).time()
        if f"duration_{clicked}" not in st.session_state:
            st.session_state[f"duration_{clicked}"] = 30

        # Time controls
        col_hr, col_min, col_ampm = st.columns(3)
        hour = col_hr.selectbox("Hour", list(range(1, 13)), index=(st.session_state[f"time_{clicked}"].hour % 12) - 1)
        minute = col_min.selectbox("Minute", list(range(0, 60)), index=st.session_state[f"time_{clicked}"].minute)
        am_pm = col_ampm.selectbox("AM/PM", ["AM", "PM"], index=0 if st.session_state[f"time_{clicked}"].hour < 12 else 1)

        col_time1, col_time2 = st.columns(2)
        with col_time1:
            if st.button("−1 min"):
                dt_comb = datetime.datetime.combine(datetime.date.today(), st.session_state[f"time_{clicked}"])
                dt_comb = (dt_comb - datetime.timedelta(minutes=1)).time()
                st.session_state[f"time_{clicked}"] = dt_comb
        with col_time2:
            if st.button("+1 min"):
                dt_comb = datetime.datetime.combine(datetime.date.today(), st.session_state[f"time_{clicked}"])
                dt_comb = (dt_comb + datetime.timedelta(minutes=1)).time()
                st.session_state[f"time_{clicked}"] = dt_comb

        hr24 = hour % 12 + (12 if am_pm == "PM" else 0)
        st.session_state[f"time_{clicked}"] = datetime.time(hr24, minute)

        duration = st.selectbox("Duration (min)", list(range(15, 241, 15)),
                                index=(st.session_state[f"duration_{clicked}"] // 15) - 1)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            if st.button("− duration"):
                if st.session_state[f"duration_{clicked}"] > 15:
                    st.session_state[f"duration_{clicked}"] -= 1
        with col_d2:
            if st.button("+ duration"):
                if st.session_state[f"duration_{clicked}"] < 240:
                    st.session_state[f"duration_{clicked}"] += 1

        st.session_state[f"duration_{clicked}"] = duration

        with st.form(f"{clicked}_form"):
            st.write("✅ Confirm above settings and click below to book:")
            submit = st.form_submit_button("✅ Book Now")

            if submit:
                tz = pytz.timezone('Asia/Kolkata')
                start_dt = tz.localize(datetime.datetime.combine(date, st.session_state[f"time_{clicked}"]))
                end_dt = start_dt + datetime.timedelta(minutes=st.session_state[f"duration_{clicked}"])
                summary = custom_name if clicked == "Other" else clicked

                if check_availability(start_dt, end_dt):
                    link = create_event(summary, start_dt, end_dt)
                    st.session_state.last_booking_msg = f"✅ **{summary} booked** — [👉 View here]({link})"
                    refresh_sidebar()
                else:
                    st.session_state.last_booking_msg = f"❌ {summary} time slot is busy. Try a different time."

# Show last booking message
if st.session_state.last_booking_msg:
    st.chat_message("assistant").markdown(st.session_state.last_booking_msg)

# Chat part unchanged
user_input = st.chat_input("Ask me to book your meeting...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

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
