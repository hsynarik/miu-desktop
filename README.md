# Miu Robot — AI Desktop Companion App 🤖🧠

![Python](https://img.shields.io/badge/Language-Python%203.8%2B-blue?logo=python)
![AI](https://img.shields.io/badge/AI-Google%20Gemini%20%2F%20Ollama-orange?logo=google)
![Fork](https://img.shields.io/badge/Forked%20From-dorianborian%2Fsesame--companion--app-brightgreen)
![GUI](https://img.shields.io/badge/UI-Tkinter%20%2F%20CLI-green)
![TTS](https://img.shields.io/badge/Audio-PyAudio%20%2F%20pyttsx3-purple)

AI-powered natural language desktop interface and voice assistant for the **Miu Robot**.

> [!NOTE]
> This project is a customized fork and evolution of the open-source [**Sesame Companion App**](https://github.com/dorianborian/sesame-companion-app) created by [Dorian Borian](https://github.com/dorianborian).

---

## 🌟 Miu Enhancements over Upstream

- **Tkinter GUI (`miu_gui.py`)**: Added a dedicated graphical desktop control panel with interactive chat, pose buttons, emotion triggers, and status diagnostics.
- **Dual AI Engine**:
  - **Google Gemini Cloud AI**: Natural conversation and emotion/action extraction (`gemini-1.5-flash`, `gemini-2.5-flash`).
  - **Local Offline LLMs**: Direct integration with Ollama / LM Studio (`http://localhost:11434/v1`).
- **Audio-Reactive Lip Sync**: Real-time microphone and TTS audio RMS level analysis via `PyAudio` to sync OLED mouth movements (`talk_happy`, `talk_sad`, etc.) with spoken audio.
- **Custom Personality Engine**: Comedic, sarcastic, self-aware robot persona.
- **Configurable Wake Word**: Voice detection with customizable wake words (default: `"hey miu"`).

---

## 🛠️ Installation & Setup

### 1. Requirements
- Python 3.8+
- Microphone & Speakers
- Miu robot connected on the same local network

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

*(Windows users: If `pyaudio` fails to compile, install via `pip install pipwin && pipwin install pyaudio` or unofficial wheels).*

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Set your configuration inside `.env`:

```ini
MIU_LOCAL=false
MIU_ROBOT_IP=192.168.4.1
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
VOICE_ENABLED=true
TTS_ENGINE=pyttsx3
WAKE_WORD=hey miu
WAKE_WORD_MODE=false
LOCAL_LLM_URL="http://localhost:11434/v1"
LOCAL_LLM_MODEL="gemma4:e4b"
GEMINI_MODEL="gemini-1.5-flash"
```

---

## 🚀 Running the Companion

### Graphical User Interface (GUI)
```bash
python miu_gui.py
```

### Interactive Command Line (CLI)
```bash
python miu_companion.py
```

---

## 🏗️ Architecture

```
┌────────────────────────────────┐
│   Miu Companion (GUI / CLI)    │
├────────────────────────────────┤
│  • Google Gemini / Local LLM   │
│  • Voice Interface (SpeechRec) │
│  • PyAudio RMS Lip-Sync Engine │
└───────────────┬────────────────┘
                │ HTTP API (/api/command, /setFace)
                ▼
┌────────────────────────────────┐
│      Miu Robot (ESP32)         │
│  • 8-DOF Kinematics Servos     │
│  • SSD1306 Dynamic OLED Faces  │
└────────────────────────────────┘
```

---

## 🤝 Upstream & Credits

This project builds upon the original **Sesame Companion App** by **Dorian Borian**:
- **Original Repository**: [https://github.com/dorianborian/sesame-companion-app](https://github.com/dorianborian/sesame-companion-app)
- Licensed under the [MIT License](LICENSE).
