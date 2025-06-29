import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import datetime
import pytz
import dateparser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage

# ---- SETUP ----
SCOPES = ['https://www.googleapis.com/auth/calendar']
service_account_info = dict(st.secrets["SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
calendar_service = build('calendar', 'v3', credentials=credentials)
CALENDAR_ID = 'primary'

gemini = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=st.secrets["GEMINI_API_KEY"])

tz = pytz.timezone('Asia/Kolkata')

# ---- FUNCTIONS ----
def is_free(start, end):
    events = calendar_service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True
    ).execute().get('items', [])
    return len(events) == 0

def create_event(summary, start, end):
    event = {
        'summary': summary,
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Kolkata'}
    }
    created = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created.get('htmlLink')

def find_next_free_slots(start, duration, count=3):
    slots = []
    current = start
    while len(slots) < count:
        end = current + duration
        if is_free(current, end):
            slots.append(current)
        current += datetime.timedelta(minutes=30)
    return slots

def gemini_understand_intent(chat_history):
    messages = [HumanMessage(m["content"]) if m["role"] == "user" else AIMessage(m["content"]) for m in chat_history]
    response = gemini.invoke(messages + [HumanMessage("Extract intent, date, time, duration and purpose clearly in JSON.")])
    return response.content

# ---- STREAMLIT ----
st.title("📅 AI Calendar Booking Agent")

if "chat" not in st.session_state:
    st.session_state.chat = []

user_input = st.chat_input("Ask to book, check, or suggest...")

if user_input:
    st.session_state.chat.append({"role": "user", "content": user_input})
    reply = ""

    # 1️⃣ Ask Gemini to understand intent
    gemini_reply = gemini_understand_intent(st.session_state.chat)

    # 2️⃣ Try to parse date/time
    try:
        data = eval(gemini_reply) if isinstance(gemini_reply, str) else gemini_reply
        time_str = data.get("time", "")
        summary = data.get("purpose", "Meeting")
        duration_mins = int(data.get("duration_mins", 30))

        parsed_dt = dateparser.parse(time_str, settings={'TIMEZONE': 'Asia/Kolkata', 'RETURN_AS_TIMEZONE_AWARE': True})
        if parsed_dt:
            end_dt = parsed_dt + datetime.timedelta(minutes=duration_mins)
            if is_free(parsed_dt, end_dt):
                link = create_event(summary, parsed_dt, end_dt)
                reply = f"✅ Booked *{summary}* for {parsed_dt.strftime('%Y-%m-%d %I:%M %p')}. [View event]({link})"
            else:
                slots = find_next_free_slots(parsed_dt, datetime.timedelta(minutes=duration_mins))
                if slots:
                    slot_list = "\n".join([f"- {s.strftime('%Y-%m-%d %I:%M %p')}" for s in slots])
                    reply = f"❌ You're busy at requested time. Here are some alternatives:\n{slot_list}\nShall I book one?"
                else:
                    reply = "❌ No suitable free slots found nearby. Please suggest another time."
        else:
            reply = "⚠ I couldn’t parse a valid date/time. Please rephrase."

    except Exception as e:
        reply = f"⚠ I couldn’t understand. Please try rephrasing. (Debug: {e})"

    st.session_state.chat.append({"role": "assistant", "content": reply})

for m in st.session_state.chat:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])
