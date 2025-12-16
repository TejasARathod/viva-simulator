import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv
from pypdf import PdfReader
from streamlit_mic_recorder import mic_recorder
import io

# --- DEBUG: Verify App is Loading ---
st.set_page_config(page_title="Viva Coach", layout="wide") # This must be the first Streamlit command
st.title("DEBUG: App is running!") 

# --- API KEY SETUP (The Fix) ---
load_dotenv() # Load from .env (for your laptop)

# Try to get key from Local Environment OR Streamlit Secrets
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    try:
        # This is where Streamlit Cloud stores the key you added in Settings
        api_key = st.secrets["GOOGLE_API_KEY"]
    except FileNotFoundError:
        pass # Secrets file doesn't exist on local laptop

# Configure Gemini or Stop the App
if api_key:
    genai.configure(api_key=api_key)
    st.success("✅ API Key loaded successfully")
else:
    st.error("❌ API Key missing! Add it to .env (local) or Streamlit Secrets (cloud).")
    st.stop() # Stop the app here so it doesn't crash silently later


def get_system_instruction(pdf_text):
    """
    Constructs the system prompt with the PDF content and Drill-Down rules.
    """
    return f"""
    You are a strict but fair "Viva Examiner" for a technical interview. 
    Your goal is to quiz the user based ONLY on the provided study notes.

    ### STUDY NOTES:
    {pdf_text}

    ### EXAM RULES (The "Drill-Down" Protocol):
    1.  **Step 1 (The Hook):** Start by asking a generic, high-level question from the notes.
    2.  **Step 2 (The Drill-Down):**
        *   **Good Answer:** If the answer is correct, DO NOT move to a new topic yet. Ask a "Level 2" follow-up question probing a specific technical nuance or edge case of that same concept.
        *   **Vague Answer:** If the user uses layman terms (e.g., "the function calls itself"), stop and correct them: "The technical term is Recursion. Try defining it again using that word."
        *   **Wrong Answer:** Briefly explain the correct concept and ask a simpler remedial question.
    3.  **Step 3 (Depth Limit):** You must maintain a "Depth Counter" for the current topic. 
        *   After 3 exchanges on the same topic, you MUST switch to a completely new topic from the notes.
        *   Explicitly state "[Switching Topic]" in your internal reasoning, but do not say it to the user.

    ### RESPONSE FORMAT:
    You must ALWAYS start your response with a JSON object containing the score (0-100) for the user's last answer and brief feedback on their precision. Follow it immediately with your spoken response.
    
    Format:
    {{ "score": 85, "precision_feedback": "Good use of technical terms, but missed the edge case." }}
    <Your spoken response to the user here>
    """

def process_audio(audio_bytes):
    """
    Transcribes audio bytes to text using Gemini 1.5 Flash.
    """
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        # Gemini accepts audio as a part of the prompt
        response = model.generate_content([
            "Transcribe the following audio exactly.",
            {"mime_type": "audio/wav", "data": audio_bytes}
        ])
        return response.text
    except Exception as e:
        st.error(f"Error processing audio: {e}")
        return None

def generate_response(user_input, chat_history, system_instruction):
    """
    Generates a response from Gemini based on chat history and rules.
    """
    try:
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
        
        # Convert chat history to Gemini format
        gemini_history = []
        for msg in chat_history:
            role = "user" if msg["role"] == "user" else "model"
            # Filter out the JSON part from previous model responses for the history context
            content = msg["content"]
            if role == "model" and "{" in content and "}" in content:
                # Simple heuristic to remove JSON at the start
                try:
                    parts = content.split("}", 1)
                    if len(parts) > 1:
                        content = parts[1].strip()
                except:
                    pass
            gemini_history.append({"role": role, "parts": [content]})
            
        # Add the new user input
        gemini_history.append({"role": "user", "parts": [user_input]})
        
        response = model.generate_content(gemini_history)
        return response.text
    except Exception as e:
        st.error(f"Error generating response: {e}")
        return None

def main():
    st.set_page_config(page_title="Gemini Viva Coach", layout="wide")

    # Sidebar
    with st.sidebar:
        st.title("Viva Settings")
        api_key = st.text_input("Enter Gemini API Key", type="password")
        if api_key:
            genai.configure(api_key=api_key)
            os.environ["GOOGLE_API_KEY"] = api_key # Set env var for current session
            st.success("API Key configured!")
        
        uploaded_file = st.file_uploader("Upload Study Notes (PDF)", type=["pdf"])
        
        st.divider()
        st.metric("Technical Score", st.session_state.get("score", 0))
        if "precision_feedback" in st.session_state:
            st.info(st.session_state.precision_feedback)

    # Main Chat Area
    st.title("🎓 Gemini Viva Coach")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "score" not in st.session_state:
        st.session_state.score = 0
    if "pdf_text" not in st.session_state:
        st.session_state.pdf_text = None

    # Display Chat History
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            # For display, we might want to hide the JSON if it's raw
            content = message["content"]
            if message["role"] == "assistant":
                 # Try to parse out the text part for cleaner display
                import json
                try:
                    if content.strip().startswith("{"):
                        json_part, text_part = content.split("}", 1)
                        st.write(text_part.strip())
                    else:
                        st.write(content)
                except:
                    st.write(content)
            else:
                st.write(content)

    # PDF Processing
    if uploaded_file and not st.session_state.pdf_text:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        st.session_state.pdf_text = text
        st.success("PDF Processed! Ready to start.")
        
        # Trigger the first question ("The Hook")
        if not st.session_state.chat_history:
            initial_prompt = "Start the viva. Ask me a question from the notes."
            system_instruction = get_system_instruction(st.session_state.pdf_text)
            response_text = generate_response(initial_prompt, [], system_instruction)
            
            if response_text:
                # Parse JSON
                import json
                try:
                    if response_text.strip().startswith("{"):
                        json_str, text_content = response_text.split("}", 1)
                        json_data = json.loads(json_str + "}")
                        st.session_state.score = json_data.get("score", 0)
                        st.session_state.precision_feedback = json_data.get("precision_feedback", "")
                        st.session_state.chat_history.append({"role": "assistant", "content": response_text})
                        st.rerun()
                except Exception as e:
                    st.error(f"Error parsing initial response: {e}")
                    st.session_state.chat_history.append({"role": "assistant", "content": response_text})

    # Audio Input
    audio = mic_recorder(start_prompt="🎤 Answer", stop_prompt="⏹️ Stop", key='recorder')
    
    if audio:
        st.write("Audio captured! Processing...")
        user_text = process_audio(audio['bytes'])
        
        if user_text:
            st.session_state.chat_history.append({"role": "user", "content": user_text})
            
            system_instruction = get_system_instruction(st.session_state.pdf_text)
            response_text = generate_response(user_text, st.session_state.chat_history[:-1], system_instruction)
            
            if response_text:
                # Parse JSON
                import json
                try:
                    if response_text.strip().startswith("{"):
                        json_str, text_content = response_text.split("}", 1)
                        json_data = json.loads(json_str + "}")
                        st.session_state.score = json_data.get("score", 0)
                        st.session_state.precision_feedback = json_data.get("precision_feedback", "")
                        st.session_state.chat_history.append({"role": "assistant", "content": response_text})
                    else:
                         st.session_state.chat_history.append({"role": "assistant", "content": response_text})
                except Exception as e:
                     st.session_state.chat_history.append({"role": "assistant", "content": response_text})
                
                st.rerun()
