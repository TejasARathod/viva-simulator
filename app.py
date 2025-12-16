import streamlit as st
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from pypdf import PdfReader
from streamlit_mic_recorder import mic_recorder

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(page_title="Gemini Viva Coach", layout="wide")

# Load environment variables (for local use)
load_dotenv()

# API Key Strategy: Check Streamlit Secrets (Cloud) first, then Local (.env)
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("❌ API Key missing! Add GOOGLE_API_KEY to Streamlit Secrets.")
    st.stop()

# --- 2. CORE LOGIC FUNCTIONS ---

def get_system_instruction(pdf_text):
    """Constructs the system prompt with the PDF content and Drill-Down rules."""
    return f"""
    You are a strict but fair "Viva Examiner" for a technical interview. 
    Your goal is to quiz the user based ONLY on the provided study notes.

    ### STUDY NOTES:
    {pdf_text}

    ### EXAM RULES (The "Drill-Down" Protocol):
    1.  **Step 1 (The Hook):** Start by asking a generic, high-level question from the notes.
    2.  **Step 2 (The Drill-Down):**
        * **Good Answer:** If the answer is correct, DO NOT move to a new topic yet. Ask a "Level 2" follow-up question probing a specific technical nuance or edge case of that same concept.
        * **Vague Answer:** If the user uses layman terms (e.g., "the function calls itself"), stop and correct them: "The technical term is Recursion. Try defining it again using that word."
        * **Wrong Answer:** Briefly explain the correct concept and ask a simpler remedial question.
    3.  **Step 3 (Depth Limit):** You must maintain a "Depth Counter" for the current topic. 
        * After 3 exchanges on the same topic, you MUST switch to a completely new topic from the notes.

    ### RESPONSE FORMAT:
    You must ALWAYS start your response with a JSON object containing the score (0-100) and feedback. Follow it immediately with your spoken response.
    
    Format:
    {{ "score": 85, "precision_feedback": "Good use of technical terms." }}
    <Your spoken response to the user here>
    """

def process_audio(audio_bytes):
    """Transcribes audio bytes to text using Gemini 1.5 Flash."""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([
            "Transcribe the following audio exactly.",
            {"mime_type": "audio/wav", "data": audio_bytes}
        ])
        return response.text
    except Exception as e:
        st.error(f"Error processing audio: {e}")
        return None

def generate_response(user_input, chat_history, system_instruction):
    """Generates a response from Gemini based on chat history and rules."""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)
        
        # Convert chat history to Gemini format
        gemini_history = []
        for msg in chat_history:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]
            # Clean out JSON from history to keep context pure
            if role == "model" and "{" in content:
                try:
                    parts = content.split("}", 1)
                    if len(parts) > 1: content = parts[1].strip()
                except: pass
            gemini_history.append({"role": role, "parts": [content]})
            
        gemini_history.append({"role": "user", "parts": [user_input]})
        
        response = model.generate_content(gemini_history)
        return response.text
    except Exception as e:
        st.error(f"Error generating response: {e}")
        return None

# --- 3. MAIN UI ---

def main():
    # Sidebar
    with st.sidebar:
        st.title("Viva Settings")
        uploaded_file = st.file_uploader("Upload Study Notes (PDF)", type=["pdf"])
        
        st.divider()
        st.metric("Technical Score", st.session_state.get("score", 0))
        if "precision_feedback" in st.session_state:
            st.info(st.session_state.precision_feedback)

    # Main Chat Area
    st.title("🎓 Gemini Viva Coach")

    # Initialize State
    if "chat_history" not in st.session_state: st.session_state.chat_history = []
    if "score" not in st.session_state: st.session_state.score = 0
    if "pdf_text" not in st.session_state: st.session_state.pdf_text = None

    # Display Chat History
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            content = message["content"]
            if message["role"] == "assistant" and content.strip().startswith("{"):
                try:
                    _, text_part = content.split("}", 1)
                    st.write(text_part.strip())
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
        
        # Trigger First Question
        if not st.session_state.chat_history:
            system_instruction = get_system_instruction(st.session_state.pdf_text)
            response_text = generate_response("Start the viva. Ask me a question from the notes.", [], system_instruction)
            if response_text:
                st.session_state.chat_history.append({"role": "assistant", "content": response_text})
                st.rerun()

    # Audio Input
    # Note: mic_recorder only works when the app is secure (HTTPS), which Streamlit Cloud is!
    audio = mic_recorder(start_prompt="🎤 Answer", stop_prompt="⏹️ Stop", key='recorder')
    
    if audio:
        st.spinner("Listening...")
        user_text = process_audio(audio['bytes'])
        if user_text:
            st.session_state.chat_history.append({"role": "user", "content": user_text})
            
            system_instruction = get_system_instruction(st.session_state.pdf_text) if st.session_state.pdf_text else "You are a helpful assistant."
            response_text = generate_response(user_text, st.session_state.chat_history[:-1], system_instruction)
            
            if response_text:
                # Parse JSON for Score Update
                try:
                    if response_text.strip().startswith("{"):
                        json_str, _ = response_text.split("}", 1)
                        json_data = json.loads(json_str + "}")
                        st.session_state.score = json_data.get("score", st.session_state.score)
                        st.session_state.precision_feedback = json_data.get("precision_feedback", "")
                except:
                    pass
                
                st.session_state.chat_history.append({"role": "assistant", "content": response_text})
                st.rerun()

if __name__ == "__main__":
    main()
