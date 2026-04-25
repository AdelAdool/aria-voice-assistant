#!/usr/bin/env python3
"""
ARIA CLI — Terminal interface for the Local Voice Assistant.
Usage:
    python cli.py                  # Interactive voice mode
    python cli.py --text           # Text-only mode (no mic/speaker)
    python cli.py --text "Hello"   # Single query
"""

import os
import sys
import time
import wave
import struct
import argparse
import tempfile
import threading
import requests
import subprocess

SERVER = os.getenv("ARIA_SERVER", "http://localhost:5000")

# ─── Colors ──────────────────────────────────────────────────────────────────

R  = "\033[91m"
G  = "\033[92m"
Y  = "\033[93m"
B  = "\033[94m"
M  = "\033[95m"
C  = "\033[96m"
W  = "\033[97m"
DIM = "\033[2m"
RST = "\033[0m"
BOLD = "\033[1m"

def banner():
    print(f"""
{C}{BOLD}
  ░█████╗░██████╗░██╗░█████╗░
  ██╔══██╗██╔══██╗██║██╔══██╗
  ███████║██████╔╝██║███████║
  ██╔══██║██╔══██╗██║██╔══██║
  ██║  ██║██║  ██║██║██║  ██║
  ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝
{RST}{DIM}  Adaptive Reasoning Intelligence Assistant
  Fully Offline · Whisper + Ollama + Coqui TTS{RST}
""")

# ─── Health Check ─────────────────────────────────────────────────────────────

def check_server():
    try:
        r = requests.get(f"{SERVER}/health", timeout=5)
        data = r.json()
        print(f"  {G}✓{RST} Server online")
        print(f"  {G}✓{RST} Whisper: {data['whisper_model']}")
        ollama = data["ollama"]
        if ollama["running"]:
            status = G + "✓" + RST if ollama["model_available"] else Y + "⚠" + RST
            print(f"  {status} Ollama: {ollama['selected_model']} {'(ready)' if ollama['model_available'] else '(model not found)'}")
        else:
            print(f"  {R}✗{RST} Ollama: not running — run `ollama serve`")
        print()
        return True
    except requests.exceptions.ConnectionError:
        print(f"  {R}✗ Cannot connect to ARIA server at {SERVER}{RST}")
        print(f"  {DIM}Start it with: python backend/server.py{RST}\n")
        return False

# ─── Audio Recording ──────────────────────────────────────────────────────────

def record_audio(duration: int = 5, sample_rate: int = 16000) -> bytes:
    """Record audio from microphone using pyaudio."""
    try:
        import pyaudio
    except ImportError:
        print(f"{R}pyaudio not installed. Run: pip install pyaudio{RST}")
        sys.exit(1)

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1

    pa = pyaudio.PyAudio()
    stream = pa.open(format=FORMAT, channels=CHANNELS, rate=sample_rate,
                     input=True, frames_per_buffer=CHUNK)

    print(f"  {R}● Recording{RST} ({duration}s) — speak now...")
    frames = []
    for _ in range(0, int(sample_rate / CHUNK * duration)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    pa.terminate()

    # Write to WAV buffer
    buf = tempfile.SpooledTemporaryFile()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pa.get_sample_size(FORMAT))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
    buf.seek(0)
    return buf.read()


def play_audio(audio_bytes: bytes):
    """Play WAV audio bytes."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        if sys.platform == "darwin":
            subprocess.run(["afplay", tmp], check=True)
        elif sys.platform == "win32":
            import winsound
            winsound.PlaySound(tmp, winsound.SND_FILENAME)
        else:
            subprocess.run(["aplay", tmp], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"  {Y}⚠ Could not play audio: {e}{RST}")
    finally:
        os.unlink(tmp)

# ─── Modes ────────────────────────────────────────────────────────────────────

def text_chat(single_query: str = None):
    """Interactive text-only chat."""
    if single_query:
        queries = [single_query]
    else:
        queries = None

    print(f"{DIM}  Type your message. Commands: /clear /history /quit{RST}\n")

    while True:
        try:
            if queries:
                user_input = queries.pop(0)
                print(f"  {B}You:{RST} {user_input}")
            else:
                user_input = input(f"  {B}You:{RST} ").strip()

            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                print(f"\n  {DIM}Goodbye!{RST}\n")
                break
            if user_input.lower() == "/clear":
                requests.delete(f"{SERVER}/history")
                print(f"  {DIM}History cleared.{RST}")
                continue
            if user_input.lower() == "/history":
                r = requests.get(f"{SERVER}/history")
                history = r.json()["history"]
                for msg in history:
                    color = B if msg["role"] == "user" else M
                    print(f"  {color}{msg['role'].capitalize()}:{RST} {msg['content'][:100]}")
                continue

            # Stream response
            print(f"  {M}ARIA:{RST} ", end="", flush=True)
            t0 = time.time()

            r = requests.post(f"{SERVER}/chat/stream",
                              json={"message": user_input},
                              stream=True, timeout=120)
            import json as _json
            for line in r.iter_lines():
                if line and line.startswith(b"data: "):
                    chunk = _json.loads(line[6:])
                    if "token" in chunk:
                        print(chunk["token"], end="", flush=True)
                    if chunk.get("done"):
                        break

            elapsed = round(time.time() - t0, 1)
            print(f"\n  {DIM}({elapsed}s){RST}\n")

            if queries is not None and not queries:
                break

        except KeyboardInterrupt:
            print(f"\n\n  {DIM}Interrupted. Goodbye!{RST}\n")
            break


def voice_chat(record_seconds: int = 5):
    """Interactive voice mode."""
    print(f"{DIM}  Press Enter to record, Ctrl+C to quit.{RST}\n")

    while True:
        try:
            input(f"  {DIM}[Enter to speak]{RST}")

            # Record
            audio_bytes = record_audio(duration=record_seconds)

            # Send to full pipeline
            print(f"  {Y}⟳{RST} Processing...")
            t0 = time.time()

            r = requests.post(
                f"{SERVER}/voice",
                files={"audio": ("recording.wav", audio_bytes, "audio/wav")},
                timeout=180
            )

            if r.status_code != 200:
                print(f"  {R}Error: {r.json().get('error', 'Unknown error')}{RST}")
                continue

            total = round(time.time() - t0, 1)
            user_text  = r.headers.get("X-User-Text", "???")
            reply_text = r.headers.get("X-Reply-Text", "???")

            import json as _json
            timings = _json.loads(r.headers.get("X-Timings", "{}"))

            print(f"  {B}You:{RST} {user_text}")
            print(f"  {M}ARIA:{RST} {reply_text}")
            print(f"  {DIM}STT:{timings.get('stt','?')}s  LLM:{timings.get('llm','?')}s  TTS:{timings.get('tts','?')}s  Total:{total}s{RST}")

            # Play audio response
            play_audio(r.content)
            print()

        except KeyboardInterrupt:
            print(f"\n\n  {DIM}Goodbye!{RST}\n")
            break

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ARIA Local Voice Assistant CLI")
    parser.add_argument("--text", nargs="?", const=True, metavar="QUERY",
                        help="Text-only mode. Optionally pass a single query.")
    parser.add_argument("--seconds", type=int, default=5,
                        help="Recording duration in seconds (default: 5)")
    parser.add_argument("--server", type=str, default=SERVER,
                        help=f"Backend server URL (default: {SERVER})")
    args = parser.parse_args()

    global SERVER
    SERVER = args.server

    banner()

    if not check_server():
        sys.exit(1)

    if args.text is not None:
        query = args.text if isinstance(args.text, str) else None
        text_chat(single_query=query)
    else:
        voice_chat(record_seconds=args.seconds)


if __name__ == "__main__":
    main()
