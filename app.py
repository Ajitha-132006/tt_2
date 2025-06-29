import streamlit as st
import threading
from fastapi import FastAPI, Request
import uvicorn
from langgraph.graph import Graph
from langgraph.prebuilt import create_react_agent, ToolExecutor
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime, timedelta
import pytz
import re

# ---- GOOGLE CALENDAR SETUP ----
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_INFO = st.secrets["SERVICE_ACCOUNT_JSON"]
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, scopes=SCOPES
)
calendar_service = build('calendar', 'v3', credentials=credentials)

calendar_id = 'primary'

# ---- FASTAPI SETUP ----
app = FastAPI()

@app.post("/chat")
async def chat_api(req: Request):
    data = await req.json()
    user_message = data.get("message", "")
    response = handle_chat(user_message)
    return {"reply": response}

def start_fastapi():
    uvicorn.run(app, host="127.0.0.1", port=8000)

threading.Thread(target=start_fastapi, daemon=True).start()

# ---- LANGGRAPH AGENT SETUP ----
def search_slots(start_time, end_time):
    events_result = calendar_service.events().list(
        calendarId=calendar_id,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return events

def suggest_slot():
    now = datetime.utcnow().isoformat() + 'Z'
    later = (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'
    events = search_slots(datetime.utcnow(), datetime.utcnow() + timedelta(days=7))
    
    busy_times = []
    for event in events:
        start = event['start'].get('dateTime')
        end = event['end'].get('dateTime')
        if start and end:
            busy_times.append((start, end))
    
    # Naive suggestion: suggest tomorrow at 3 PM UTC
    tomorrow = datetime.utcnow() + timedelta(days=1)
    suggested = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 15, 0, 0, tzinfo=pytz.UTC)
    return suggested.isoformat()

def create_event(start_time, end_time, summary="Meeting"):
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'UTC'},
        'end': {'dateTime': end_time, 'timeZone': 'UTC'}
    }
    created_event = calendar_service.events().insert(calendarId=calendar_id, body=event).execute()
    return created_event.get('htmlLink')

def parse_time_input(text):
    # Simplified regex time extraction
    if "tomorrow" in text:
        start = datetime.utcnow() + timedelta(days=1, hours=15)
        end = start + timedelta(hours=1)
    elif "next week" in text:
        start = datetime.utcnow() + timedelta(days=7, hours=15)
        end = start + timedelta(hours=1)
    elif "friday" in text:
        today = datetime.utcnow()
        days_ahead = (4 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        start = today + timedelta(days=days_ahead, hours=15)
        end = start + timedelta(hours=1)
    else:
        start = datetime.utcnow() + timedelta(days=1, hours=15)
        end = start + timedelta(hours=1)
    return start, end

def handle_chat(user_input):
    if re.search(r'book|schedule|meeting|appointment', user_input, re.I):
        start, end = parse_time_input(user_input)
        existing = search_slots(start, end)
        if existing:
            suggestion = suggest_slot()
            return f"You're busy at that time. How about {suggestion}?"
        else:
            link = create_event(start.isoformat(), end.isoformat())
            return f"Meeting booked! Here is the link: {link}"
    elif re.search(r'free|available|slot', user_input, re.I):
        suggestion = suggest_slot()
        return f"You're free at {suggestion}. Shall I book it?"
    else:
        return "Can you please specify a date or time for the appointment?"

# ---- STREAMLIT CHAT UI ----
st.title("📅 AI Appointment Booking Assistant")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_input = st.chat_input("Type your appointment request...")

if user_input:
    st.session_state.chat_history.append(("user", user_input))
    response = handle_chat(user_input)
    st.session_state.chat_history.append(("ai", response))

for role, msg in st.session_state.chat_history:
    if role == "user":
        st.chat_message("user").write(msg)
    else:
        st.chat_message("assistant").write(msg)
