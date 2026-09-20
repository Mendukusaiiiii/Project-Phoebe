# Project Phoebe

This folder contains the packaged Windows build of Project Phoebe, desktop AI chat companion with voice output, a system tray presence, background music, and a small "thought visualizer" window.

## Run the app

Double-click the executable:

- `Phoebe.exe`

Or run it from a terminal:

```powershell
./Phoebe.exe
```

## Configure the AI

Before using the app, you need to fill in your provider details in `config.json`. You can do this two ways:

1. **Config Editor (recommended)** — double-click `Config Editor.exe` in this folder. It opens a small form for every setting below and autosaves to `config.json` as you type, so you don't have to edit JSON by hand.
2. **Manual edit** — open `config.json` in this same folder in a text editor and fill in your provider details directly.

Example `config.json`:

```json
{
  "model": "gpt-4o-mini",
  "api_key": "YOUR_API_KEY",
  "api_base": "https://api.openai.com/v1",
  "system_context": "You are a helpful assistant.",
  "error_message": "Err... :/ Check error_log for more info.",
  "voice_id": "",
  "voice_volume": 1.0,
  "core_ai_color": "#00FFFF"
}
```

### Config fields

| Field | Description |
| --- | --- |
| `model` | Model name supported by your chosen provider. |
| `api_key` | API key for that provider. |
| `api_base` | Base URL of an OpenAI-compatible endpoint. |
| `system_context` | System prompt that defines Phoebe's personality/behavior. |
| `error_message` | Message shown in the chat if a request fails. |
| `voice_id` | (Optional) Windows SAPI voice ID to use for voice output. Leave blank to use the system default voice. |
| `voice_volume` | (Optional) Voice output volume, from `0.0` to `1.0`. |
| `core_ai_color` | (Optional) Accent color (hex) used in the UI. |

### Common provider examples

- OpenAI:
  - model: `gpt-4o-mini`
  - api_base: `https://api.openai.com/v1`
- OpenRouter:
  - model: `openai/gpt-4o-mini`
  - api_base: `https://openrouter.ai/api/v1`
- Gemini-compatible endpoint:
  - model: `gemini-2.0-flash`
  - api_base: `https://generativelanguage.googleapis.com/v1beta/openai`
- Ollama:
  - model: `llama3.2`
  - api_base: `http://localhost:11434/v1`

## Using the app

- **Voice output** — click the speaker icon next to the send button to toggle Phoebe reading replies aloud. Requires text-to-speech to be available on your system; the button is disabled otherwise.
- **Attachments & emoji** — use the attachment button to attach an image to your message, and the emoji button to open the emoji picker (right-click/middle-click it to try your OS's native picker instead).
- **AI Visualizer** — under the **View** menu, "AI Visualizer" opens a small window that visualizes Phoebe's "neural behaviour."
- **Dark mode / Always on top** — also under the **View** menu.
- **Background music** — if an `assets/musics` folder with audio files (`.mp3`, `.wav`, `.ogg`) is present, Phoebe shuffles and plays them automatically. Click the music label at the bottom-right to adjust volume; hover it for track info.
- **System tray** — closing the window minimizes Phoebe to the system tray instead of quitting; right-click the tray icon for Open/Exit.
- **Saving/loading conversations** — under the **File** menu you can save the current conversation as a `.phbe` file ("Save/Save As Consciousness") and reload one later ("Import Consciousness"). These files are encrypted and specific to Phoebe.

## Important notes

- The app expects a valid OpenAI-compatible API endpoint.
- `api_key` must match the provider you are using.
- `model` must be a model name supported by that provider.
- If `config.json` is missing or invalid, the app creates/falls back to a blank one automatically and logs the issue.
- If a request fails, check `error_log.txt` in this folder.
- To reset the AI's personality, either delete `delete_me_to_reset_personality.phbe` yourself, or click **Reset AI** in the Config Editor (which saves your settings and deletes it for you).

## Disclaimer

This executable connects to third-party AI services using your own API key and provider configuration. You are responsible for all API usage, billing, rate limits, compliance with provider terms, and data handling. The developer is not responsible for costs, service outages, API restrictions, or issues caused by external providers or misconfigured settings.