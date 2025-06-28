import streamlit as st
import datetime
import pytz
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from dateparser.search import search_dates

SCOPES = ['https://www.googleapis.com/auth/calendar']

# AUTH HANDLER
def get_credentials():
    creds = None
    if "token_info" in st.session_state:
        creds = Credentials.from_authorized_user_info(st.session_state["token_info"], SCOPES)
    else:
        client_config = json.loads(st.secrets["CLIENT_SECRET_JSON"])
        flow = Flow.from_client_config(client_config, SCOPES)
        flow.redirect_uri = "https://gxmeprxbxwjpyuansmifxn.streamlit.app/"

        params = st.experimental_get_query_params()
        if "code" not in params:
            auth_url, _ = flow.authorization_url(prompt='consent')
            st.markdown(f"[👉 Click here to authorize Google Calendar access]({auth_url})")
            st.stop()
        else:
            code = params["code"][0]
            flow.fetch_token(code=code)
            creds = flow.credentials
            st.session_state["token_info"] = json.loads(creds.to_json())
    
    return creds

creds = get_credentials()
service = build("calendar", "v3", credentials=creds)

# HELPERS
def create_event(summary, start_dt, end_dt):
    event = {
        'summary': summary,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'}
    }
    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event.get('htmlLink')

def get_todays_events():
    tz = pytz.timezone('Asia/Kolkata')
    today_start = datetime.datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + datetime.timedelta(days=1)
    events_result = service.events().list(
        calendarId='primary',
        timeMin=today_start.isoformat(),
        timeMax=today_end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def check_availability(start, end):
    events = service.events().list(
        calendarId='primary',
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True
    ).execute().get('items', [])
    return len(events) == 0

def refresh_sidebar():
    st.sidebar.markdown("## 📌 <span style='color:#4CAF50'>Today's Schedule (IST)</span>", unsafe_allow_html=True)
    events = get_todays_events()
    if not events:
        st.sidebar.info("No events scheduled today.")
    else:
        for e in events:
            start = e['start'].get('dateTime', e['start'].get('date'))
            start_dt = datetime.datetime.fromisoformat(start).astimezone(pytz.timezone('Asia/Kolkata'))
            st.sidebar.markdown(
                f"<div style='background-color:#e8f5e9;padding:5px;border-radius:5px;'>"
                f"<b>{e['summary']}</b> at {start_dt.strftime('%I:%M %p')}</div>",
                unsafe_allow_html=True
            )

# UI HEADER
st.markdown("<h1 style='color:#3f51b5;'>💬 Interactive Calendar Booking Bot</h1>", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

refresh_sidebar()

# QUICK BOOKING
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
        st.markdown(f"#### Booking: {clicked}")
        custom_name = ""
        if clicked == "Other":
            custom_name = st.text_input("Enter event name")
        date = st.date_input("Pick date", datetime.date.today())
        col_t1, col_t2, col_t3 = st.columns([3,2,2])
        hour = col_t1.selectbox("Hour", list(range(1, 13)))
        minute = col_t2.selectbox("Minute", [0, 15, 30, 45])
        am_pm = col_t3.selectbox("AM/PM", ["AM", "PM"])
        duration = st.selectbox("Duration (minutes)", [15,30,45,60,90,120])
        submit = st.form_submit_button("✅ Book Now")

        if submit:
            hour_24 = hour % 12 + (12 if am_pm == "PM" else 0)
            time_obj = datetime.time(hour_24, minute)
            tz = pytz.timezone('Asia/Kolkata')
            start_dt = tz.localize(datetime.datetime.combine(date, time_obj))
            end_dt = start_dt + datetime.timedelta(minutes=duration)
            summary = custom_name if clicked == "Other" else clicked

            if check_availability(start_dt, end_dt):
                link = create_event(summary, start_dt, end_dt)
                msg = f"✅ <b>{summary}</b> booked for {start_dt.strftime('%Y-%m-%d %I:%M %p')} IST 👉 [View here]({link})"
            else:
                msg = f"❌ {summary} time slot is busy. Try another time."

            st.session_state.messages.append({"role":"assistant","content":msg})
            st.chat_message("assistant").markdown(msg, unsafe_allow_html=True)
            refresh_sidebar()

# CHAT INTERFACE
user_input = st.chat_input("Ask me to book your meeting...")
if user_input:
    st.session_state.messages.append({"role":"user","content":user_input})

if st.session_state.messages:
    last = st.session_state.messages[-1]
    if last["role"]=="user":
        msg = last["content"].strip().lower()
        pending = st.session_state.pending_suggestion
        reply = ""

        if msg in ["yes","ok","sure"] and "time" in pending:
            start = pending["time"]
            end = start + datetime.timedelta(minutes=30)
            summary = pending.get("summary","Event")
            link = create_event(summary,start,end)
            reply = f"✅ <b>{summary}</b> booked for {start.strftime('%Y-%m-%d %I:%M %p')} IST 👉 [View here]({link})"
            st.session_state.pending_suggestion = {}
            refresh_sidebar()

        elif msg in ["no","reject"]:
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
                summary = "Event"

            result = search_dates(
                msg,
                settings={
                    'PREFER_DATES_FROM':'future',
                    'RETURN_AS_TIMEZONE_AWARE':True,
                    'TIMEZONE':'Asia/Kolkata',
                    'RELATIVE_BASE':datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
                }
            )

            if not result:
                reply = "⚠ Could not parse date/time. Try `tomorrow 4 PM`."
            else:
                parsed = result[0][1]
                if parsed.tzinfo is None:
                    parsed = pytz.timezone('Asia/Kolkata').localize(parsed)
                end = parsed + datetime.timedelta(minutes=30)

                if check_availability(parsed,end):
                    link = create_event(summary,parsed,end)
                    reply = f"✅ <b>{summary}</b> booked for {parsed.strftime('%Y-%m-%d %I:%M %p')} IST 👉 [View here]({link})"
                    refresh_sidebar()
                else:
                    for i in range(1,4):
                        alt = parsed + datetime.timedelta(hours=i)
                        alt_end = alt + datetime.timedelta(minutes=30)
                        if check_availability(alt,alt_end):
                            reply = f"❌ Busy at requested time. How about {alt.strftime('%Y-%m-%d %I:%M %p')} IST? Reply `yes` to confirm."
                            st.session_state.pending_suggestion = {"time":alt,"summary":summary}
                            break
                    else:
                        reply = "❌ Busy at requested time. No nearby slots found."

        st.session_state.messages.append({"role":"assistant","content":reply})
        st.chat_message("assistant").markdown(reply, unsafe_allow_html=True)

# SHOW HISTORY
for m in st.session_state.messages:
    if m["role"]=="user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").markdown(m["content"], unsafe_allow_html=True)
