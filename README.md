# Gemini Viva Coach

A "Viva Simulator" that quizzes you on your study notes using Google Gemini.

## Prerequisites

-   Python 3.8+
-   A Google Gemini API Key (Get one [here](https://aistudio.google.com/app/apikey))

## Installation (Ubuntu/Linux)

1.  **Clone/Navigate to the project:**
    ```bash
    cd /home/tejas/Desktop/Interview
    ```

2.  **Create a virtual environment (Recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: We removed `SpeechRecognition` to avoid complex audio driver issues on Ubuntu. We use Gemini's native multimodal capabilities for audio transcription.*

4.  **Setup API Key:**
    -   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    -   Edit `.env` and add your `GOOGLE_API_KEY`.
    -   Alternatively, you can enter the key in the sidebar when running the app.

## Running the App

```bash
streamlit run app.py
```

## Usage

1.  Upload your Study Notes (PDF) in the sidebar.
2.  Wait for the "PDF Processed!" message.
3.  The AI will ask the first question.
4.  Click **Start Recording** (microphone icon) to answer.
5.  Click **Stop** to submit your answer.
6.  The AI will grade you and ask a follow-up question.
