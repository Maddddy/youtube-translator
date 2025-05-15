# process.py

import os
import json
import re
import uuid
import tempfile
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from gtts import gTTS
from pydub import AudioSegment

GEMINI_API_KEY = "AIzaSyB_Ogy_9sbFRm9-SLd4ejOD7D6dwR_MIQM"

lang_map = {
    "english": "en",
    "hindi": "hi",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "chinese": "zh-CN",
    "arabic": "ar",
    "japanese": "ja",
    "korean": "ko",
    "russian": "ru",
    "italian": "it",
    "portuguese": "pt",
    "polish": "pl",
}

def extract_video_id(url):
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    return match.group(1) if match else None

def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([t['text'] for t in transcript])
    except Exception as e:
        return f"Error: {str(e)}"

def chunk_text(text, max_words=5000):
    words = text.split()
    return [" ".join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

def translate_with_gemini(transcript, target_language):
    chunks = chunk_text(transcript)
    translated_chunks = []

    for i, chunk in enumerate(chunks):
        prompt = f"Translate the following text to {target_language} like it's a modern YouTube video conversation:\n\n{chunk}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        headers = { "Content-Type": "application/json" }
        data = { "contents": [{ "parts": [{ "text": prompt }] }] }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            try:
                translated = response.json()['candidates'][0]['content']['parts'][0]['text']
                translated_chunks.append(translated)
            except Exception as e:
                translated_chunks.append(f"[Error parsing chunk {i}: {e}]")
        else:
            translated_chunks.append(f"[API error in chunk {i}: {response.text}]")

    return "\n".join(translated_chunks)

def text_to_speech(text, language_code):
    tts = gTTS(text=text, lang=language_code)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as original_file:
        tts.save(original_file.name)
        audio = AudioSegment.from_file(original_file.name)
        faster_audio = audio.speedup(playback_speed=1.25)

        final_path = original_file.name.replace(".mp3", "_faster.mp3")
        faster_audio.export(final_path, format="mp3")

    return final_path

# 🧠 Entry point for Vercel
def handler(request):
    try:
        body = request.get_json()
        youtube_url = body.get("youtube_url")
        target_language = body.get("target_language")

        if not youtube_url or not target_language:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing youtube_url or target_language"})
            }

        video_id = extract_video_id(youtube_url)
        if not video_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid YouTube URL"})
            }

        transcript = get_transcript(video_id)
        translated = translate_with_gemini(transcript, target_language)
        lang_code = lang_map.get(target_language.lower(), "en")
        audio_path = text_to_speech(translated, lang_code)

        return {
            "statusCode": 200,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({
                "video_id": video_id,
                "translated": translated,
                "audio_path": audio_path
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({ "error": str(e) })
        }
