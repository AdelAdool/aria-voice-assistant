#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  ARIA Local Voice Assistant — Setup Script
#  Installs all dependencies and checks system requirements.
# ─────────────────────────────────────────────────────────────

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════╗"
echo -e "  ║    ARIA Voice Assistant — Setup     ║"
echo -e "  ╚══════════════════════════════════════╝${NC}"
echo ""

# ── 1. Python version ──────────────────────────────────────────

PYTHON=$(which python3 || which python || true)
if [ -z "$PYTHON" ]; then
    fail "Python not found. Install Python 3.10+"
    exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    fail "Python 3.10+ required. Found: $PY_VERSION"
    exit 1
fi
ok "Python $PY_VERSION"

# ── 2. ffmpeg ─────────────────────────────────────────────────

if command -v ffmpeg &> /dev/null; then
    ok "ffmpeg found"
else
    warn "ffmpeg not found — required by Whisper"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        info "Installing ffmpeg..."
        sudo apt-get install -y ffmpeg
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        info "Run: brew install ffmpeg"
    else
        warn "Please install ffmpeg manually: https://ffmpeg.org/download.html"
    fi
fi

# ── 3. Ollama ──────────────────────────────────────────────────

if command -v ollama &> /dev/null; then
    ok "Ollama found"
else
    warn "Ollama not found"
    info "Install Ollama from: https://ollama.com/download"
    info "Then run: ollama pull mistral"
fi

# ── 4. Virtual environment ────────────────────────────────────

if [ ! -d ".venv" ]; then
    info "Creating virtual environment..."
    $PYTHON -m venv .venv
    ok "Virtual environment created"
else
    ok "Virtual environment exists"
fi

source .venv/bin/activate
info "Activated .venv"

# ── 5. Pip upgrade ─────────────────────────────────────────────

pip install --upgrade pip --quiet

# ── 6. Install dependencies ───────────────────────────────────

info "Installing Python dependencies (this may take a few minutes)..."
pip install -r backend/requirements.txt -q
ok "Python dependencies installed"

# ── 7. PyAudio (optional, for CLI voice mode) ─────────────────

info "Attempting to install PyAudio for mic input..."
if pip install pyaudio -q 2>/dev/null; then
    ok "PyAudio installed"
else
    warn "PyAudio install failed (mic recording unavailable in CLI mode)"
    warn "On Linux try: sudo apt install portaudio19-dev && pip install pyaudio"
fi

# ── 8. Check .env ─────────────────────────────────────────────

if [ ! -f ".env" ]; then
    cp .env.example .env
    ok ".env created from .env.example"
else
    ok ".env already exists"
fi

# ── 9. Done ───────────────────────────────────────────────────

echo ""
echo -e "${GREEN}  ════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup complete! Next steps:${NC}"
echo ""
echo -e "  ${DIM}1. Start Ollama:${NC}         ollama serve"
echo -e "  ${DIM}2. Pull a model:${NC}          ollama pull mistral"
echo -e "  ${DIM}3. Start the server:${NC}      source .venv/bin/activate && python backend/server.py"
echo -e "  ${DIM}4. Open the UI:${NC}           open frontend/index.html  (or use a local server)"
echo -e "  ${DIM}   OR use the CLI:${NC}        python cli.py"
echo ""
echo -e "  ${DIM}Docs: README.md${NC}"
echo -e "${GREEN}  ════════════════════════════════════════${NC}"
echo ""
