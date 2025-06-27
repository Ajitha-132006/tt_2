import streamlit as st
import datetime
import pytz
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account

from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

# CONFIG
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'chalasaniajitha@gmail.com'

# GOOGLE SERVICE ACCOUNT
service_account_info = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES
)
service = build('calendar', 'v3', credentials=credentials)

# LLM SETUP
llm = ChatOpenAI(
    api_key=st.secrets["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    model_name="mistralai/mistral-7b-instruct"  # Or another free model on OpenRouter
)

# PROMPT TEMPLATE
prompt_template = ChatPromptTemplate.from_template("""
You are a smart assistant. The user will describe an event to schedule.
Extract:
- summary: A short title for the event
- datetime: The exact date and time in format YYYY-MM-DD HH:MM (24h)

User input: {input}

Respond as JSON like: {{"summary": "...", "datetime": "..."}}
""")

def ask_llm_for_datetime(user_input):
    prompt = prompt_template.format_messages(input=user_input)
    response = llm(prompt)
    text = response.content
    try:
        data = json.loads(text)
        return data["summary"], data["datetime"]
    except:
        return None, None

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

# UI
st.title("📅 Smart Calendar Booking Bot")
if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.chat_input("Ask me to book your meeting...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    reply = ""

    summary, dt_str = ask_llm_for_datetime(user_input)

    if summary and dt_str:
        try:
            dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            dt = pytz.timezone("Asia/Kolkata").localize(dt)
            end_dt = dt + datetime.timedelta(minutes=30)

            if check_availability(dt, end_dt):
                link = create_event(summary, dt, end_dt)
                reply = f"✅ Booked {summary} for {dt.strftime('%Y-%m-%d %I:%M %p')}. [View in Calendar]({link})"
            else:
                reply = f"❌ Time slot busy. Please suggest another time."

        except Exception as e:
            reply = f"⚠ Could not parse LLM response datetime."
    else:
        reply = "⚠ Could not extract datetime. Please rephrase your request."

    st.session_state.messages.append({"role": "assistant", "content": reply})

for m in st.session_state.messages:
    if m["role"] == "user":
        st.chat_message("user").write(m["content"])
    else:
        st.chat_message("assistant").write(m["content"])
