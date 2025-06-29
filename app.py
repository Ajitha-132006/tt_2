import streamlit as st
from datetime import datetime, timedelta
import requests
from dateutil.parser import parse
from typing import Optional, Tuple
from langgraph.graph import Graph
from langgraph.prebuilt import create_react_agent, ToolExecutor
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_vertexai import ChatVertexAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
import re

# Configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'
CALENDAR_ID = 'primary'
TIMEZONE = 'UTC'

# Initialize Streamlit session state
def initialize_session_state():
    if 'conversation' not in st.session_state:
        st.session_state.conversation = []
    if 'calendar_authenticated' not in st.session_state:
        st.session_state.calendar_authenticated = False

# Google Calendar Authentication
def authenticate_google_calendar():
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    st.session_state.calendar_authenticated = True
    return creds

# Calendar Operations
def check_availability(start: str, end: str) -> Tuple[bool, str]:
    try:
        creds = authenticate_google_calendar()
        service = build('calendar', 'v3', credentials=creds)
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if events:
            conflicting_events = "\n".join([
                f"- {e['summary']} ({e['start'].get('dateTime', e['start'].get('date'))} to {e['end'].get('dateTime', e['end'].get('date'))})"
                for e in events
            ])
            return (False, f"Sorry, the selected time slot conflicts with:\n{conflicting_events}")
        return (True, "This time slot is available!")
    
    except Exception as e:
        return (False, f"Error checking availability: {str(e)}")

def book_appointment(start: str, end: str, summary: str) -> Tuple[bool, str]:
    try:
        creds = authenticate_google_calendar()
        service = build('calendar', 'v3', credentials=creds)
        
        event = {
            'summary': summary,
            'start': {'dateTime': start, 'timeZone': TIMEZONE},
            'end': {'dateTime': end, 'timeZone': TIMEZONE},
        }
        
        event = service.events().insert(
            calendarId=CALENDAR_ID,
            body=event
        ).execute()
        
        return (True, f"Successfully booked '{summary}' from {start} to {end}!")
    
    except Exception as e:
        return (False, f"Error booking appointment: {str(e)}")

# Conversation Tools
def parse_time_range(user_input: str) -> Optional[Tuple[str, str]]:
    try:
        # Try to parse absolute times
        if "to" in user_input.lower() or "-" in user_input:
            parts = re.split(r'to|-', user_input, maxsplit=1)
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            
            start_dt = parse(start_str, fuzzy=True)
            end_dt = parse(end_str, fuzzy=True)
            
            return (start_dt.isoformat(), end_dt.isoformat())
        
        # Try to parse relative times
        elif "today" in user_input.lower() or "tomorrow" in user_input.lower():
            base_dt = datetime.now()
            if "tomorrow" in user_input.lower():
                base_dt += timedelta(days=1)
            
            if "morning" in user_input.lower():
                start = base_dt.replace(hour=9, minute=0, second=0, microsecond=0)
                end = start + timedelta(hours=1)
            elif "afternoon" in user_input.lower():
                start = base_dt.replace(hour=13, minute=0, second=0, microsecond=0)
                end = start + timedelta(hours=1)
            elif "evening" in user_input.lower():
                start = base_dt.replace(hour=17, minute=0, second=0, microsecond=0)
                end = start + timedelta(hours=1)
            else:
                start = base_dt + timedelta(hours=1)
                end = start + timedelta(hours=1)
            
            return (start.isoformat(), end.isoformat())
        
        return None
    
    except Exception:
        return None

def get_available_slots(date: datetime = None) -> Tuple[bool, str]:
    try:
        if date is None:
            date = datetime.now()
        
        start_of_day = date.replace(hour=9, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=17, minute=0, second=0, microsecond=0)
        
        creds = authenticate_google_calendar()
        service = build('calendar', 'v3', credentials=creds)
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        busy_slots = [
            (parse(e['start'].get('dateTime', e['start'].get('date'))),
             parse(e['end'].get('dateTime', e['end'].get('date'))))
            for e in events
        ]
        
        # Find available slots (simplified)
        available_slots = []
        current_time = start_of_day
        
        while current_time < end_of_day:
            slot_end = current_time + timedelta(hours=1)
            
            # Check if current slot is available
            is_available = True
            for busy_start, busy_end in busy_slots:
                if not (slot_end <= busy_start or current_time >= busy_end):
                    is_available = False
                    break
            
            if is_available:
                available_slots.append((current_time, slot_end))
            
            current_time += timedelta(minutes=30)
        
        if not available_slots:
            return (False, "No available slots found for this date.")
        
        slot_strings = [
            f"{start.strftime('%I:%M %p')} to {end.strftime('%I:%M %p')}"
            for start, end in available_slots
        ]
        
        return (True, "Available slots:\n" + "\n".join(slot_strings))
    
    except Exception as e:
        return (False, f"Error getting available slots: {str(e)}")

# Define the tools for the agent
def check_availability_tool(time_range: str) -> str:
    parsed = parse_time_range(time_range)
    if not parsed:
        return "Could not understand the time range. Please specify clearly (e.g., 'tomorrow 2pm to 3pm')"
    
    available, message = check_availability(parsed[0], parsed[1])
    return message

def book_appointment_tool(time_range: str, summary: str) -> str:
    parsed = parse_time_range(time_range)
    if not parsed:
        return "Could not understand the time range. Please specify clearly (e.g., 'tomorrow 2pm to 3pm')"
    
    success, message = book_appointment(parsed[0], parsed[1], summary)
    return message

def get_available_slots_tool(date_str: str) -> str:
    try:
        date = parse(date_str, fuzzy=True).replace(hour=0, minute=0, second=0, microsecond=0)
        success, message = get_available_slots(date)
        return message
    except Exception:
        return "Could not understand the date. Please specify clearly (e.g., 'this Friday' or 'April 15')"

# Set up the agent
def create_agent():
    llm = ChatVertexAI(model="gemini-pro")
    
    tools = [
        {
            "name": "check_availability",
            "description": "Check if a specific time slot is available for booking",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_range": {
                        "type": "string",
                        "description": "The time range to check (e.g., 'tomorrow 2pm to 3pm')"
                    }
                },
                "required": ["time_range"]
            }
        },
        {
            "name": "book_appointment",
            "description": "Book an appointment for a specific time slot",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_range": {
                        "type": "string",
                        "description": "The time range to book (e.g., 'tomorrow 2pm to 3pm')"
                    },
                    "summary": {
                        "type": "string",
                        "description": "The title or description of the appointment"
                    }
                },
                "required": ["time_range", "summary"]
            }
        },
        {
            "name": "get_available_slots",
            "description": "Get all available time slots for a specific date",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {
                        "type": "string",
                        "description": "The date to check (e.g., 'this Friday' or 'April 15')"
                    }
                },
                "required": ["date_str"]
            }
        }
    ]
    
    tool_executor = ToolExecutor(tools={
        "check_availability": check_availability_tool,
        "book_appointment": book_appointment_tool,
        "get_available_slots": get_available_slots_tool
    })
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful calendar assistant that helps users book appointments. 
         Always be polite and ask clarifying questions when needed. 
         Break down complex questions into multiple steps. 
         Confirm all details with the user before booking."""),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    agent = create_react_agent(llm, tools, prompt)
    workflow = Graph()
    
    workflow.add_node("agent", agent)
    workflow.add_node("action", tool_executor)
    
    workflow.add_edge("action", "agent")
    workflow.add_conditional_edges(
        "agent",
        lambda x: "tool_uses" in x if x else False,
        {True: "action", False: "agent"}
    )
    
    workflow.set_entry_point("agent")
    
    return workflow.compile()

# Main App
def main():
    initialize_session_state()
    
    st.set_page_config(page_title="Calendar Booking Assistant", page_icon="📅")
    
    st.title("📅 Calendar Booking Assistant")
    st.caption("A conversational AI assistant for scheduling appointments")
    
    # Check if credentials exist
    if not os.path.exists(CREDENTIALS_FILE):
        st.error("Google Calendar credentials file not found. Please upload your credentials.json file.")
        uploaded_file = st.file_uploader("Upload credentials.json", type=["json"])
        
        if uploaded_file is not None:
            with open(CREDENTIALS_FILE, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success("Credentials file saved! Please refresh the page.")
        return
    
    # Display conversation
    for msg in st.session_state.conversation:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.write(msg.content)
        elif isinstance(msg, AIMessage):
            with st.chat_message("assistant"):
                st.write(msg.content)
    
    # User input
    if prompt := st.chat_input("How can I help you book an appointment?"):
        st.session_state.conversation.append(HumanMessage(content=prompt))
        
        with st.chat_message("user"):
            st.write(prompt)
        
        try:
            # Check if agent is initialized
            if 'agent' not in st.session_state:
                st.session_state.agent = create_agent()
            
            # Process user input
            agent_input = {
                "messages": st.session_state.conversation
            }
            
            with st.spinner("Thinking..."):
                response = st.session_state.agent.invoke(agent_input)
                ai_message = AIMessage(content=response['messages'][-1].content)
                st.session_state.conversation.append(ai_message)
                
                with st.chat_message("assistant"):
                    st.write(ai_message.content)
        
        except Exception as e:
            error_msg = f"Error processing your request: {str(e)}"
            st.session_state.conversation.append(AIMessage(content=error_msg))
            
            with st.chat_message("assistant"):
                st.error(error_msg)

if __name__ == "__main__":
    main()
