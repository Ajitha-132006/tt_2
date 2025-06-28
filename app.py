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

def refresh_sidebar():
    sidebar = st.sidebar.empty()
    with sidebar:
        st.title("📌 Today's Schedule (IST)")
        todays_events = get_todays_events()
        if not todays_events:
            st.info("No events scheduled today.")
        else:
            for e in todays_events:
                start = e['start'].get('dateTime', e['start'].get('date'))
                start_dt = datetime.datetime.fromisoformat(start).astimezone(pytz.timezone('Asia/Kolkata'))
                st.write(f"✅ **{e['summary']}** at {start_dt.strftime('%I:%M %p')}")

refresh_sidebar()

st.markdown("""
<style>
.stButton > button { background-color: #007acc; color: white; font-weight: bold; border-radius: 6px; }
.stChatMessage { background-color: #eef6fb; padding: 10px; border-radius: 10px; }
h1, h2, h3, h4 { color: #007acc; }
</style>
""", unsafe_allow_html=True)

st.title("💬 Interactive Calendar Booking Bot")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}
if "clicked_type" not in st.session_state:
    st.session_state.clicked_type = None

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

    # Initialize states
    if f"time_{clicked}" not in st.session_state:
        st.session_state[f"time_{clicked}"] = datetime.datetime.now().replace(second=0, microsecond=0).time()
    if f"duration_{clicked}" not in st.session_state:
        st.session_state[f"duration_{clicked}"] = 30

    # Time input
    hour = st.selectbox("Hour", list(range(1, 13)), index=(st.session_state[f"time_{clicked}"].hour % 12)-1)
    minute = st.selectbox("Minute", list(range(0, 60)), index=st.session_state[f"time_{clicked}"].minute)
    am_pm = st.selectbox("AM/PM", ["AM", "PM"], index=0 if st.session_state[f"time_{clicked}"].hour < 12 else 1)

    # Apply + / - buttons for time
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

    # Duration input
    duration_dropdown = st.selectbox("Duration (minutes)", list(range(15, 241, 15)), index=(st.session_state[f"duration_{clicked}"] // 15) - 1)

    col_dur1, col_dur2 = st.columns(2)
    with col_dur1:
        if st.button("− duration"):
            if st.session_state[f"duration_{clicked}"] > 15:
                st.session_state[f"duration_{clicked}"] -= 1
    with col_dur2:
        if st.button("+ duration"):
            if st.session_state[f"duration_{clicked}"] < 240:
                st.session_state[f"duration_{clicked}"] += 1

    # Update time and duration state from dropdowns
    hr24 = hour % 12 + (12 if am_pm == "PM" else 0)
    st.session_state[f"time_{clicked}"] = datetime.time(hr24, minute)
    st.session_state[f"duration_{clicked}"] = duration_dropdown

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
                msg = f"✅ **{summary} booked** — [👉 View here]({link})"
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.chat_message("assistant").markdown(msg)
                refresh_sidebar()
            else:
                msg = f"❌ {summary} time slot is busy. Please try a different time."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.chat_message("assistant").markdown(msg)

# Chat input / history (unchanged)
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
