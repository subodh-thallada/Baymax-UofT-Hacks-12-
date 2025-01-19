import os
import sys
import openai
import paramiko
from core import run_tts_script
from pydub import AudioSegment
import speech_recognition as sr
import cv2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# List available microphones
print("Available Microphones:")
print(sr.Microphone.list_microphone_names())

# Ensure the core module is in the Python path
sys.path.append(os.path.dirname(__file__))

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Ensure the API key is set in .env
openai.api_key = OPENAI_API_KEY


# Emotion Detection Class
class EmotionDetector:
    def __init__(self):
        # Initialize webcam
        self.cap = cv2.VideoCapture(0)

        # Load Haar Cascades for face and smile detection
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.smile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

    def detect_emotion(self):
        ret, frame = self.cap.read()
        if not ret:
            return "Neutral"  # Default to Neutral if no frame is captured

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        for (x, y, w, h) in faces:
            face_roi = gray_frame[y:y+h, x:x+w]

            # Detect smiles and eyes
            smiles = self.smile_cascade.detectMultiScale(face_roi, scaleFactor=1.5, minNeighbors=15, minSize=(20, 20))
            eyes = self.eye_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=10, minSize=(15, 15))

            if len(smiles) > 0:
                return "Happy"
            elif len(eyes) > 0:
                stress_detected = False
                for (ex, ey, ew, eh) in eyes:
                    eye_height = eh / ew
                    if eye_height > 0.5:
                        stress_detected = True
                        break
                if stress_detected:
                    return "Stressed"
                else:
                    return "Sad"

        return "Neutral"

    def release(self):
        self.cap.release()
        cv2.destroyAllWindows()


# Baymax Response Generator
def baymax_response_generator(prompt, emotion="Neutral"):
    """
    Generates Baymax-like responses with simple, pure sentences (1-3 max), adjusted for emotion.
    """
    try:
        # Generate a response in Baymax's tone and style
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are Baymax, a personal healthcare companion. "
                        f"Respond in a calm, empathetic tone, adjusted to match the emotion '{emotion}'. "
                        f"Limit responses to 1-3 concise sentences. Prioritize simplicity, kindness, and clarity."
                    )
                },
                {"role": "user", "content": prompt}
            ]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        print(f"Error fetching response from ChatGPT: {e}")
        return "I encountered an error generating a response."


# Text-to-Speech Conversion
def baymax_tts(text, out_wav="baymax_output_amplified.wav"):
    """
    Converts text to a Baymax-style TTS WAV file.
    """
    placeholder_text_file = "temp_input.txt"
    with open(placeholder_text_file, "w", encoding="utf-8") as f:
        f.write(text)

    your_pth = "logs/Baymax/Baymax_250e_4750s_best_epoch.pth"
    your_index = "logs/Baymax/added_Baymax_v2.index"

    run_tts_script(
        tts_file=placeholder_text_file,
        tts_text=text,
        tts_voice="en-US-AndrewMultilingualNeural",
        tts_rate=0,
        pitch=5,
        filter_radius=2,
        index_rate=0.3,
        volume_envelope=1,
        protect=0.5,
        hop_length=128,
        f0_method="rmvpe",
        output_tts_path="temp_tts.wav",
        output_rvc_path=out_wav,
        pth_path=your_pth,
        index_path=your_index,
        split_audio=False,
        f0_autotune=False,
        f0_autotune_strength=0.2,
        clean_audio=False,
        clean_strength=1,
        export_format="WAV",
        f0_file=None,
        embedder_model="contentvec",
        embedder_model_custom=None,
        sid=0
    )

    return out_wav


# Play the Baymax Response
def play_baymax_response(response_text):
    """
    Converts Baymax's response into TTS audio and plays it on the Raspberry Pi.
    """
    print(f"Baymax Response: {response_text}")  # Log the response for debugging
    output_file = baymax_tts(response_text, "baymax_output_amplified.wav")

    # Raspberry Pi configuration
    pi_ip = "192.168.1.6"
    pi_user = "Pi"
    pi_password = "Max2025"
    remote_path = "/home/Pi/Downloads/Hacks/baymax_output_amplified.wav"

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(pi_ip, username=pi_user, password=pi_password)

        sftp = ssh.open_sftp()
        sftp.put(output_file, remote_path)
        sftp.close()
        print("Uploaded to Raspberry Pi via SFTP.")

        stdin, stdout, stderr = ssh.exec_command(f"aplay {remote_path}")
        print("STDOUT:", stdout.read().decode())
        print("STDERR:", stderr.read().decode())
        ssh.close()
        print("Playback triggered on Raspberry Pi.")
    except Exception as e:
        print(f"Error with Raspberry Pi connection or playback: {e}")


# Main Application
if __name__ == "__main__":
    recognizer = sr.Recognizer()
    emotion_detector = EmotionDetector()
    session_active = True

    try:
        with sr.Microphone() as source:
            print("Listening for audio input (say 'Baymax' to start, or 'quit' to exit)...")

            while session_active:
                try:
                    print("Speak now...")
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    user_input = recognizer.recognize_google(audio).lower()
                    print(f"You said: {user_input}")

                    if "baymax" in user_input:
                        introduction = "Hello. I am Baymax. Your personal healthcare companion. I was alerted to the need for medical attention."
                        play_baymax_response(introduction)

                    elif "quit" in user_input:
                        while True:
                            satisfaction_query = "Are you satisfied with my care?"
                            play_baymax_response(satisfaction_query)

                            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                            response = recognizer.recognize_google(audio).lower()
                            print(f"You said: {response}")

                            if "satisfied" in response:
                                farewell = "Goodbye. I hope you have a healthy day."
                                play_baymax_response(farewell)
                                session_active = False
                                break
                            elif "no" in response:
                                play_baymax_response("I will continue to assist you.")
                            else:
                                play_baymax_response("I did not understand. Are you satisfied with my care?")
                    else:
                        emotion = emotion_detector.detect_emotion()
                        baymax_reply = baymax_response_generator(user_input, emotion)
                        play_baymax_response(baymax_reply)

                except sr.UnknownValueError:
                    print("Could not understand audio. Please try again.")
                except sr.WaitTimeoutError:
                    print("No speech detected within the timeout period. Listening again...")
    except KeyboardInterrupt:
        print("\nGoodbye!")
        emotion_detector.release()
