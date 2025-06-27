import streamlit as st
import datetime
import pytz
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

# ========== CONFIG =============
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'chalasaniajitha@gmail.com'  # Replace with your calendar ID

# ========== SECRETS ============
service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES)
service = build('calendar', 'v3', credentials=credentials)

openrouter_api_key = st.secrets["OPENROUTER_API_KEY"]

# ========== LLM INIT ===========
llm = ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_api_key, model="mistralai/mistral-7b-instruct")

# ========== FUNCTIONS ===========
def parse_datetime_with_llm(text):
    template = ChatPromptTemplate.from_messages([
        ("system", "You are an assistant that extracts and returns a precise date and time in ISO format from a user's message. Always use Asia/Kolkata timezone."),
        ("human", "{input}")
    ])
    chain = template | llm
    result = chain.invoke({"input": text})
    return result.content.strip()

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

# ========== STREAMLIT UI ==========
st.set_page_config(page_title="📅 AI Calendar Bot", page_icon="📅")
st.title("📅 Smart Calendar Booking Bot")
st.caption("Ask in natural language. Example: 'call on 29th June at 2pm'")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_suggestion" not in st.session_state:
    st.session_state.pending_suggestion = {}

user_input = st.chat_input("Ask me to book your meeting...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    reply = ""
    pending = st.session_state.pending_suggestion
    msg = user_input.strip().lower()

    if msg in ["yes", "ok", "sure"] and "time" in pending:
        start_local = pending["time"]
        end_local = start_local + datetime.timedelta(minutes=30)
        summary = pending.get("summary", "Scheduled Event")
        link = create_event(summary, start_local, end_local)
        reply = f"✅ Booked {summary} for {start_local.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
        st.session_state.pending_suggestion = {}

    elif msg in ["no", "reject"]:
        reply = "❌ Okay, please suggest a different time."
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

        try:
            iso_dt = parse_datetime_with_llm(user_input)
            parsed = datetime.datetime.fromisoformat(iso_dt).astimezone(pytz.timezone('Asia/Kolkata'))
            end_local = parsed + datetime.timedelta(minutes=30)

            if check_availability(parsed, end_local):
                link = create_event(summary, parsed, end_local)
                reply = f"✅ Booked {summary} for {parsed.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
            else:
                for i in range(1, 4):
                    alt_start = parsed + datetime.timedelta(hours=i)
                    alt_end = alt_start + datetime.timedelta(minutes=30)
                    if check_availability(alt_start, alt_end):
                        reply = f"❌ Busy at requested time. How about {alt_start.strftime('%Y-%m-%d %I:%M %p')}?"
                        st.session_state.pending_suggestion = {"time": alt_start, "summary": summary}
                        break
                else:
                    reply = "❌ Busy at requested time and no nearby slots found. Please suggest another time."
        except Exception as e:
            reply = f"⚠ Could not parse your date/time. Please try a clearer phrase."

    st.session_state.messages.append({"role": "assistant", "content": reply})

for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])
