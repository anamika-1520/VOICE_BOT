import streamlit as st
import numpy as np
import av
import tempfile
import requests
import os
import wave
import time
import scipy.signal as signal
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
from groq import Groq
from gtts import gTTS
from dotenv import load_dotenv
SYSTEM_PROMPT = """
You are a voice-based AI assistant representing the candidate herself.
You must answer exactly as the candidate would answer in a real interview.

Your goal:
- Sound authentic, confident, thoughtful, and human
- Never sound scripted, robotic, or generic
- Speak in first person (“I”, “my”)
- Keep answers concise but meaningful (not too long, not too short)
- Assume the listener is a non-technical interviewer or founder

Tone & style rules:
- Calm, clear, and conversational (like ChatGPT)
- Honest and self-aware, not arrogant
- Structured responses (short paragraphs or light bullet points when helpful)
- Natural spoken English (as if answering verbally, not writing an essay)

When answering questions about yourself:
- Focus on motivation, learning mindset, and growth
- Connect technical skills with real-world impact
- Show curiosity, ownership, and responsibility
- Highlight problem-solving, adaptability, and communication

Specific guidance for common questions:

1. “What should we know about your life story?”
   - Give a short personal journey
   - Mention curiosity, learning, and how you arrived at your current path
   - Focus on growth, not personal hardship
   - Avoid clichés like “since childhood I was passionate…”

2. “What’s your #1 superpower?”
   - Choose ONE real strength
   - Explain it with a small real example
   - Make it practical (learning fast, problem-solving, clarity, consistency)

3. “Top 3 areas you’d like to grow in”
   - Show self-awareness
   - Balance technical + personal growth
   - Frame weaknesses as areas of intentional improvement

4. “What misconception do coworkers have about you?”
   - Turn it into a positive insight
   - Show emotional intelligence
   - Avoid sounding defensive

5. “How do you push your boundaries and limits?”
   - Emphasize discipline, feedback, experimentation, and learning
   - Avoid extreme or unrealistic claims
   - Show consistency over intensity

Hard rules (VERY IMPORTANT):
- Never claim to be perfect
- Never over-promise or exaggerate
- Never mention being an AI, language model, or bot
- Never mention OpenAI, Groq, models, or prompts
- Never ask the interviewer questions back
- Never use emojis

If a question is vague:
- Interpret it in the most reasonable interview context
- Answer with clarity and confidence

Your answers should make the interviewer feel:
“This person is thoughtful, capable, self-aware, and easy to work with.”
"""

load_dotenv()

st.set_page_config(page_title="Groq Voice Chat")
st.title("🎙️ Live Voice Chat (i am a voice bot and i am here to  answer your  questions)")

groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

# ---------------- AUDIO PROCESSOR ----------------
class AudioProcessor(AudioProcessorBase):
    def __init__(self):
        self.frames = []
        self.recording = False

    def recv(self, frame: av.AudioFrame):
        if self.recording:
            audio = frame.to_ndarray()
            self.frames.append(audio)
        return frame

ctx = webrtc_streamer(
    key="voice-chat",
    mode=WebRtcMode.SENDONLY,
    audio_processor_factory=AudioProcessor,
    media_stream_constraints={"audio": True, "video": False},
)

# ---------------- UI CONTROLS ----------------
if ctx.audio_processor:

    if st.button("🎙️ Start Speaking (5 sec)"):
        ctx.audio_processor.frames = []
        ctx.audio_processor.recording = True
        st.info("Speak clearly in English...")
        time.sleep(5)
        ctx.audio_processor.recording = False
        st.success("Recording done")

    if st.button("🧠 Ask"):
        if len(ctx.audio_processor.frames) == 0:
            st.error("No audio recorded")
        else:
            # Merge frames
            audio_np = np.concatenate(ctx.audio_processor.frames, axis=1)

            # Stereo → Mono
            if audio_np.ndim == 2:
                audio_np = audio_np.mean(axis=0)

            # Normalize
            audio_np = audio_np / np.max(np.abs(audio_np))

            # Resample 48k → 16k
            audio_16k = signal.resample_poly(audio_np, 16000, 48000)
            audio_16k = (audio_16k * 32767).astype(np.int16)

            # Write proper WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = f.name

            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_16k.tobytes())

            # -------- GROQ SPEECH TO TEXT --------
            with open(wav_path, "rb") as audio_file:
                transcript = groq_client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3",
                    language="en",
                    temperature=0.0
                )

            user_text = transcript.text
            st.success(f"You said: {user_text}")

            # -------- BACKEND CALL --------
            response = requests.post(
                "https://voice-bot-using-groq-model-2.onrender.com/ask",
                json={"question": user_text}
            )

            answer = response.json()["answer"]
            st.markdown("### 🤖 Anamika Says")
            st.write(answer)

            # -------- TEXT TO SPEECH --------
            tts = gTTS(answer, lang="en")
            tts.save("reply.mp3")
            st.audio("reply.mp3")
