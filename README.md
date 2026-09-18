# Project Phoebe

Project Phoebe is a desktop AI assistant built with Python and Tkinter. It connects to a chat completion API using your configured API key, model, and base URL, and adds voice output, a system tray presence, background music, and a small "thought visualizer" window on top of the chat.

## Features

- OpenAI-compatible API support
- Image attachment support
- Emoji picker (with an option to try your OS's native picker instead)
- Voice output (text-to-speech) with configurable voice, and a mute toggle in the UI
- "AI Visualizer" window that visualizes Phoebe's thoughts (View menu)
- Dark mode and always-on-top toggles (View menu)
- Background music playback from a local folder, with a volume control
- Tray icon and background behavior (closing the window minimizes to tray instead of quitting)
- Local autosave and conversation management, including saving/loading encrypted `.phbe` conversation files
- A separate Config Editor GUI (`config.py`) for editing `config.json` without hand-writing JSON

---

## Requirements

Before running the app, make sure you have:

- Python 3.10+ recommended
- pip installed
- An AI provider with an OpenAI-compatible API endpoint

Common examples:

- Gemini
- OpenRouter
- OpenAI
- Local Ollama server
- Any compatible API service that supports `/chat/completions`

---

## Project structure

```text
Project Phoebe/
├── Phoebe.py            # main app
├── config.py            # standalone Config Editor GUI
├── config.json          # your AI settings (created on first run if missing)
├── components/
│   ├── voice.py          # text-to-speech
│   ├── visualizer.py      # AI Visualizer window
│   ├── emoji_list.py      # emoji picker
│   └── themes.py          # light/dark theme + UI settings persistence
├── assets/
│   ├── images/            # icons
│   └── musics/            # optional background music (.mp3/.wav/.ogg)
├── settings.json         # UI preferences (dark mode, voice on/off, etc.), created automatically
└── error_log.txt         # created automatically when something goes wrong
```

---

## 1) Install Python dependencies

Open a terminal in the project folder and run:

```bash
python -m pip install --upgrade pip
python -m pip install requests pystray pillow pygame pyttsx3
```

Voice output relies on `pyttsx3`. On Windows, also install `comtypes` so the speech engine works reliably across threads:

```bash
python -m pip install comtypes
```

If either `pyttsx3` or `comtypes` is missing, the app still runs — voice output is simply disabled and the speaker button is greyed out.

If you want to build a Windows executable later, you can also install:

```bash
python -m pip install pyinstaller
```

> The app imports `requests`, `pystray`, `PIL`, and `pygame`, so these packages are required for normal operation. `pyttsx3` (and `comtypes` on Windows) are required only for voice output.

---

## 2) Configure the AI in config.json

The app reads its settings from `config.json` in the project root. You can edit it manually, or run `python config.py` to open the Config Editor GUI, which autosaves every field to `config.json` as you type.

Example configuration:

```json
{
  "model": "openai/gpt-4o-mini",
  "api_key": "your_api_key_here",
  "api_base": "https://openrouter.ai/api/v1",
  "system_context": "You are a helpful assistant.",
  "error_message": "Err... :/ Check error_log for more info.",
  "voice_id": "",
  "voice_volume": 1.0,
  "core_ai_color": "#00FFFF"
}
```

### Field explanations

- `model`: the model name your provider expects.
- `api_key`: your API key from the provider.
- `api_base`: the base URL for the provider's OpenAI-compatible endpoint.
- `system_context`: optional custom system prompt for the assistant.
- `error_message`: message shown when the API call fails.
- `voice_id` *(optional)*: the TTS voice identifier to use (as reported by `pyttsx3`/SAPI). Leave blank for the system default voice.
- `voice_volume` *(optional)*: voice output volume from `0.0` to `1.0`. Defaults to `1.0`.
- `core_ai_color` *(optional)*: hex accent color used in the UI. Defaults to `#00FFFF`.

---

## 3) Example provider setups

### Option A: OpenRouter

Use:

```json
{
  "model": "openai/gpt-4o-mini",
  "api_key": "YOUR_OPENROUTER_KEY",
  "api_base": "https://openrouter.ai/api/v1"
}
```

Then start the app:

```bash
python Phoebe.py
```

### Option B: OpenAI

Use:

```json
{
  "model": "gpt-4o-mini",
  "api_key": "YOUR_OPENAI_KEY",
  "api_base": "https://api.openai.com/v1"
}
```

### Option C: Local Ollama

If your Ollama server is running locally, it usually exposes an OpenAI-compatible endpoint at:

```text
http://localhost:11434/v1
```

Example:

```json
{
  "model": "llama3.2",
  "api_key": "ollama",
  "api_base": "http://localhost:11434/v1"
}
```

> Some local servers accept any non-empty bearer token. If the server does not require a key, using `ollama` is a common workaround.

---

## 4) Run the app

From the project folder:

```bash
python Phoebe.py
```

If the app cannot find `config.json`, it creates a default one with blank values. You should fill in your own API information before using the chat — either by hand or with:

```bash
python config.py
```

---

## 5) Using the app

- **Voice output** — click the speaker icon next to the send button to toggle Phoebe reading replies aloud. The button is disabled if `pyttsx3` isn't installed.
- **Attachments & emoji** — use the attachment button to attach an image to your message, and the emoji button to open the emoji picker (right-click or middle-click it to try your OS's native picker instead).
- **AI Visualizer** — View menu → "AI Visualizer" opens a small window visualizing Phoebe's "neural behaviour."
- **Dark mode / Always on top** — also under the View menu.
- **Background music** — drop `.mp3`, `.wav`, or `.ogg` files into `assets/musics/` and Phoebe shuffles and plays them automatically on launch. Click the music label at the bottom-right to adjust volume; hover it for track info.
- **System tray** — closing the window minimizes Phoebe to the system tray instead of quitting; right-click the tray icon for Open/Exit.
- **Saving/loading conversations** — File menu → "Save/Save As Consciousness" saves the current conversation as an encrypted `.phbe` file; "Import Consciousness" reloads one.
- **Resetting personality** — delete `delete_me_to_reset_personality.phbe`, or click **Reset AI** in the Config Editor, which saves your current settings and deletes that file for you.

---

## 6) Troubleshooting

### config.json is missing or empty

Check that the file exists in the project folder and contains valid JSON. You can also run `python config.py` and click "Reload" to see what the app currently has, or just start typing to regenerate it.

### AI is not responding

Verify:

- `api_key` is correct
- `model` matches your provider's supported model names
- `api_base` points to the correct API endpoint
- your internet connection is working

### API error from provider

Open the `error_log.txt` file in the project folder to view the exact error message.

### Voice output isn't working / speaker button is greyed out

Make sure `pyttsx3` is installed (and `comtypes` on Windows). If a specific `voice_id` in `config.json` is invalid for your system, clear it to fall back to the default voice.

---

## 7) Recommended configuration template

Copy this exact template into `config.json` and replace the values:

```json
{
  "model": "openai/gpt-4o-mini",
  "api_key": "your_api_key_here",
  "api_base": "https://openrouter.ai/api/v1",
  "system_context": "You are a helpful assistant.",
  "error_message": "Err... :/ Check error_log for more info.",
  "voice_id": "",
  "voice_volume": 1.0,
  "core_ai_color": "#FA2A55"
}
```

## License

This project is distributed as-is. Please check the repository for any project-specific licensing details before publishing or redistributing it.

---

## Quick Start

```bash
cd "Project Phoebe"
python -m pip install requests pystray pillow pygame pyttsx3
# edit config.json, or run: python config.py
python Phoebe.py
```

## Disclaimer

This project is provided for educational and personal use. It connects to third-party AI APIs using your own API key and credentials, and you are responsible for complying with the terms of service of those providers. The developer is not responsible for API costs, rate limits, usage restrictions, data privacy, or any issues caused by external services or misconfigured settings.