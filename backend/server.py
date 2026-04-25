"""
Local Voice Assistant - Backend Server
Whisper (STT) + Ollama (LLM) + Coqui TTS
Fully offline, no API keys required.
"""

import os
import io
import json
import time
import wave
import tempfile
import threading
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
import whisper
import requests
from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS

# ─── Config ──────────────────────────────────────────────────────────────────

WHISPER_MODEL   = os.getenv("WHISPER_MODEL", "base")          # tiny | base | small | medium | large
OLLAMA_HOST     = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral")         # any model pulled via `ollama pull`
TTS_SPEAKER     = os.getenv("TTS_SPEAKER", None)               # None = default speaker
TTS_LANGUAGE    = os.getenv("TTS_LANGUAGE", "en")
PORT            = int(os.getenv("PORT", 5000))
SAMPLE_RATE     = 16000

# System prompt for the assistant personality
SYSTEM_PROMPT = """You are ARIA (Adaptive Reasoning Intelligence Assistant), a helpful, 
concise, and friendly offline voice assistant. You run entirely on the user's machine 
with no internet connection. Keep your answers clear and appropriately brief for 
voice output — avoid bullet points, markdown, or formatting. Speak naturally."""

# ─── App Setup ───────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

# Conversation history (in-memory, per session)
conversation_history = []
history_lock = threading.Lock()

# ─── Model Loading ───────────────────────────────────────────────────────────

print(f"[ARIA] Loading Whisper model: {WHISPER_MODEL} ...")
whisper_model = whisper.load_model(WHISPER_MODEL)
print("[ARIA] Whisper ready.")

# Lazy-load TTS to avoid slow startup
_tts_model = None
_tts_lock  = threading.Lock()

def get_tts():
    global _tts_model
    with _tts_lock:
        if _tts_model is None:
            print("[ARIA] Loading Coqui TTS model...")
            from TTS.api import TTS
            _tts_model = TTS("tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
            print("[ARIA] TTS ready.")
    return _tts_model

# ─── Helper Functions ─────────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes) -> str:
    """Convert audio bytes → text via Whisper."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        result = whisper_model.transcribe(tmp_path, language="en", fp16=False)
        return result["text"].strip()
    finally:
        os.unlink(tmp_path)


def chat_with_ollama(user_message: str, stream: bool = False):
    """Send message to local Ollama LLM and return response."""
    with history_lock:
        conversation_history.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history.copy()

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": 0.7,
            "num_predict": 300,
        }
    }

    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json=payload,
        stream=stream,
        timeout=120
    )
    response.raise_for_status()

    if stream:
        return response  # caller handles streaming
    else:
        data = response.json()
        assistant_reply = data["message"]["content"].strip()
        with history_lock:
            conversation_history.append({"role": "assistant", "content": assistant_reply})
        return assistant_reply


def synthesize_speech(text: str) -> bytes:
    """Convert text → WAV audio bytes via Coqui TTS."""
    tts = get_tts()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    try:
        tts.tts_to_file(text=text, file_path=tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


def check_ollama() -> dict:
    """Check if Ollama is running and the model is available."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        return {
            "running": True,
            "models": models,
            "selected_model": OLLAMA_MODEL,
            "model_available": any(OLLAMA_MODEL in m for m in models)
        }
    except Exception as e:
        return {"running": False, "error": str(e), "models": []}


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """System health check."""
    ollama_status = check_ollama()
    return jsonify({
        "status": "ok",
        "whisper_model": WHISPER_MODEL,
        "ollama": ollama_status,
        "tts_loaded": _tts_model is not None,
    })


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """POST audio file → returns transcribed text."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()

    if not audio_bytes:
        return jsonify({"error": "Empty audio file"}), 400

    try:
        t0 = time.time()
        text = transcribe_audio(audio_bytes)
        elapsed = round(time.time() - t0, 2)
        return jsonify({"text": text, "transcription_time": elapsed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    """POST text message → returns LLM text response."""
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "No message provided"}), 400

    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    try:
        t0 = time.time()
        reply = chat_with_ollama(user_message)
        elapsed = round(time.time() - t0, 2)
        return jsonify({"reply": reply, "llm_time": elapsed})
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot connect to Ollama. Is it running? Run: ollama serve"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    """POST text message → streams LLM response token by token (SSE)."""
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    def generate():
        full_reply = ""
        try:
            with history_lock:
                conversation_history.append({"role": "user", "content": user_message})
                messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history.copy()

            payload = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": True,
                "options": {"temperature": 0.7, "num_predict": 300}
            }
            response = requests.post(
                f"{OLLAMA_HOST}/api/chat", json=payload, stream=True, timeout=120
            )
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    full_reply += token
                    yield f"data: {json.dumps({'token': token, 'done': chunk.get('done', False)})}\n\n"
                    if chunk.get("done"):
                        break

            with history_lock:
                conversation_history.append({"role": "assistant", "content": full_reply})

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/speak", methods=["POST"])
def speak():
    """POST text → returns WAV audio file."""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400

    text = data["text"].strip()
    if not text:
        return jsonify({"error": "Empty text"}), 400

    try:
        t0 = time.time()
        audio_bytes = synthesize_speech(text)
        elapsed = round(time.time() - t0, 2)

        return send_file(
            io.BytesIO(audio_bytes),
            mimetype="audio/wav",
            as_attachment=False,
            download_name="response.wav",
            headers={"X-TTS-Time": str(elapsed)}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/voice", methods=["POST"])
def voice_pipeline():
    """Full pipeline: audio → STT → LLM → TTS → audio response."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_bytes = request.files["audio"].read()
    timings = {}

    # 1. Transcribe
    t0 = time.time()
    try:
        user_text = transcribe_audio(audio_bytes)
        timings["stt"] = round(time.time() - t0, 2)
    except Exception as e:
        return jsonify({"error": f"STT failed: {e}"}), 500

    if not user_text:
        return jsonify({"error": "Could not transcribe audio. Please speak clearly."}), 400

    # 2. LLM
    t0 = time.time()
    try:
        reply_text = chat_with_ollama(user_text)
        timings["llm"] = round(time.time() - t0, 2)
    except Exception as e:
        return jsonify({"error": f"LLM failed: {e}"}), 500

    # 3. TTS
    t0 = time.time()
    try:
        audio_response = synthesize_speech(reply_text)
        timings["tts"] = round(time.time() - t0, 2)
    except Exception as e:
        return jsonify({"error": f"TTS failed: {e}"}), 500

    # Return audio + metadata in headers
    response = send_file(
        io.BytesIO(audio_response),
        mimetype="audio/wav",
        as_attachment=False,
        download_name="response.wav"
    )
    response.headers["X-User-Text"]   = user_text
    response.headers["X-Reply-Text"]  = reply_text[:200]  # truncated for header limits
    response.headers["X-Timings"]     = json.dumps(timings)
    return response


@app.route("/history", methods=["GET"])
def get_history():
    """Return conversation history."""
    with history_lock:
        return jsonify({"history": conversation_history.copy()})


@app.route("/history", methods=["DELETE"])
def clear_history():
    """Clear conversation history."""
    with history_lock:
        conversation_history.clear()
    return jsonify({"status": "cleared"})


@app.route("/models", methods=["GET"])
def list_models():
    """List available Ollama models."""
    status = check_ollama()
    return jsonify(status)


@app.route("/models/switch", methods=["POST"])
def switch_model():
    """Switch the active Ollama model."""
    global OLLAMA_MODEL
    data = request.get_json()
    model = data.get("model", "").strip()
    if not model:
        return jsonify({"error": "No model specified"}), 400
    OLLAMA_MODEL = model
    return jsonify({"status": "switched", "model": OLLAMA_MODEL})


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════╗
║        ARIA Voice Assistant              ║
║  Whisper + Ollama + Coqui TTS            ║
║  100% Offline · No API Keys              ║
╚══════════════════════════════════════════╝
  Server  : http://localhost:{PORT}
  Whisper : {WHISPER_MODEL}
  LLM     : {OLLAMA_MODEL} via {OLLAMA_HOST}
""")
    ollama_info = check_ollama()
    if not ollama_info["running"]:
        print("⚠️  WARNING: Ollama is not running. Start it with: ollama serve")
    elif not ollama_info["model_available"]:
        print(f"⚠️  WARNING: Model '{OLLAMA_MODEL}' not found. Pull it with: ollama pull {OLLAMA_MODEL}")
    else:
        print(f"✅  Ollama connected. Model '{OLLAMA_MODEL}' is ready.")

    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
