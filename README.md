# 🎙️ ARIA — Local Voice Assistant

> **Adaptive Reasoning Intelligence Assistant**  
> 100% offline voice assistant powered by Whisper + Ollama + Coqui TTS.  
> No API keys. No cloud. No subscriptions. Just intelligence on your machine.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Offline](https://img.shields.io/badge/Runs-100%25%20Offline-purple?style=flat-square)
![Whisper](https://img.shields.io/badge/STT-OpenAI%20Whisper-orange?style=flat-square)
![Ollama](https://img.shields.io/badge/LLM-Ollama-black?style=flat-square)
![Coqui](https://img.shields.io/badge/TTS-Coqui-red?style=flat-square)

---

## ✨ Features

- 🎤 **Speech-to-Text** — OpenAI Whisper (local, multiple model sizes)
- 🧠 **Local LLM** — Any model via Ollama (Mistral, LLaMA 3, Phi-3, Gemma, etc.)
- 🔊 **Text-to-Speech** — Coqui TTS (natural-sounding, offline)
- 💬 **Streaming responses** — Token-by-token output, no waiting
- 🌐 **Beautiful Web UI** — Dark-themed, responsive, real-time stats
- 💻 **CLI mode** — Text or voice, works in any terminal
- 🔄 **Conversation memory** — Full multi-turn context
- 🔀 **Hot-swap models** — Switch LLMs mid-conversation from the UI
- 📊 **Latency tracking** — STT / LLM / TTS timing per message
- 🧹 **Zero data retention** — Nothing leaves your machine

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                     User Input                          │
│           (voice via mic OR text via UI/CLI)            │
└──────────────────────┬─────────────────────────────────┘
                       │
             ┌─────────▼──────────┐
             │   Flask Backend    │  ← server.py
             │  localhost:5000    │
             └──┬─────┬──────┬───┘
                │     │      │
     ┌──────────▼─┐ ┌─▼───┐ ┌▼──────────┐
     │   Whisper  │ │Ollam│ │ Coqui TTS │
     │   (STT)    │ │ (LM)│ │  (TTS)    │
     └────────────┘ └─────┘ └───────────┘
                       │
             ┌─────────▼──────────┐
             │    Web Frontend    │  ← frontend/index.html
             │   or CLI Client    │  ← cli.py
             └────────────────────┘
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| POST | `/transcribe` | Audio → text (Whisper) |
| POST | `/chat` | Text → LLM response |
| POST | `/chat/stream` | Text → streaming SSE response |
| POST | `/speak` | Text → WAV audio (TTS) |
| POST | `/voice` | **Full pipeline**: audio → text → LLM → audio |
| GET | `/history` | Get conversation history |
| DELETE | `/history` | Clear conversation |
| GET | `/models` | List Ollama models |
| POST | `/models/switch` | Switch active model |

---

## ⚡ Quick Start

### Prerequisites

| Dependency | Install |
|---|---|
| Python 3.10+ | [python.org](https://python.org) |
| ffmpeg | `sudo apt install ffmpeg` / `brew install ffmpeg` |
| Ollama | [ollama.com/download](https://ollama.com/download) |

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/aria-voice-assistant
cd aria-voice-assistant

# Run automated setup
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 2. Pull an LLM

```bash
# Pick any model (examples):
ollama pull mistral       # fast, general purpose (4.1GB)
ollama pull llama3        # Meta's flagship (4.7GB)
ollama pull phi3          # Microsoft's compact model (2.3GB)
ollama pull gemma         # Google's model (5.0GB)
ollama pull openchat      # Strong chat model (4.1GB)
```

### 3. Start the Backend

```bash
# Make sure Ollama is running first
ollama serve

# In another terminal:
source .venv/bin/activate
python backend/server.py
```

### 4. Open the UI

Open `frontend/index.html` in your browser (or serve it):
```bash
# Python quick server:
python -m http.server 8080 --directory frontend
# Then open: http://localhost:8080
```

Or use the CLI:
```bash
python cli.py           # voice mode
python cli.py --text    # text only mode
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and adjust:

```env
# Whisper model size (tiny | base | small | medium | large)
WHISPER_MODEL=base

# Ollama settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral

# Server port
PORT=5000
```

### Whisper Model Guide

| Model | Size | Speed | Accuracy | VRAM |
|-------|------|-------|----------|------|
| tiny  | 39M  | ⚡⚡⚡⚡ | ★★☆☆ | ~1GB |
| base  | 74M  | ⚡⚡⚡ | ★★★☆ | ~1GB |
| small | 244M | ⚡⚡  | ★★★★ | ~2GB |
| medium| 769M | ⚡   | ★★★★ | ~5GB |
| large | 1550M| 🐢  | ★★★★★ | ~10GB |

---

## 🖥️ CLI Usage

```bash
# Voice mode (hold Enter to record)
python cli.py

# Text mode (interactive)
python cli.py --text

# Single query
python cli.py --text "What is the capital of France?"

# Custom recording duration (seconds)
python cli.py --seconds 8

# Custom server
python cli.py --server http://192.168.1.100:5000
```

### CLI Commands

| Command | Action |
|---------|--------|
| `/clear` | Clear conversation history |
| `/history` | Show conversation history |
| `/quit` | Exit |

---

## 🔧 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| GPU | None (CPU mode) | NVIDIA 8GB VRAM |
| Disk | 5 GB free | 20+ GB (for multiple models) |
| OS | Linux / macOS / Windows | Linux / macOS |

> **GPU acceleration**: Ollama automatically uses CUDA/Metal if available. Whisper also supports GPU via PyTorch.

---

## 🧩 Extending ARIA

### Add a custom TTS voice

1. Find a XTTS v2 model or voice sample
2. Update `synthesize_speech()` in `server.py`:

```python
tts.tts_to_file(text=text, speaker_wav="path/to/your-voice.wav", file_path=tmp_path)
```

### Change the personality

Edit `SYSTEM_PROMPT` in `server.py`:

```python
SYSTEM_PROMPT = """You are MAX, a sarcastic but helpful assistant who loves puns..."""
```

### Add tools / function calling

Use Ollama's tool-calling API by extending the `chat_with_ollama()` function with a `tools` parameter.

---

## 🗺️ Roadmap

- [ ] Wake word detection (offline, e.g. openWakeWord)
- [ ] Multi-language support (Whisper + multilingual TTS)
- [ ] Plugin system (calculator, weather, calendar)
- [ ] Voice profiles & speaker diarization
- [ ] Electron desktop app
- [ ] Raspberry Pi / edge device deployment guide

---

## 🤝 Contributing

PRs welcome! Please open an issue first for major changes.

1. Fork the repo
2. Create your branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push and open a PR

---

## 📄 License

MIT © [AdelAdool](https://github.com/YOUR_USERNAME)

---

<div align="center">
  Built with ❤️ and zero cloud dependencies.
  <br>
  <sub>Whisper · Ollama · Coqui TTS · Flask · Vanilla JS</sub>
</div>
