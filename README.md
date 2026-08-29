# Project Phoebe

Project Phoebe is a desktop AI assistant built with Python and Tkinter. It connects to an chat completion API using your configured API key, model, and base URL.

## Features

- Desktop chat interface
- OpenAI-compatible API support
- Image attachment support
- Tray icon and background behavior
- Local autosave and conversation management

---

## Requirements

Before running the app, make sure you have:

- Python 3.10+ recommended
- pip installed
- An AI provider with an OpenAI-compatible API endpoint

---

## 1) Install Python dependencies

Open a terminal in the project folder and run:

```bash
python -m pip install --upgrade pip
python -m pip install requests pystray pillow pygame
```

If you want to build a Windows executable later, you can also install:

```bash
python -m pip install pyinstaller
```

> The app imports `requests`, `pystray`, `PIL`, and `pygame`, so these packages are required for normal operation.

---

## 2) Configure the AI in config.json

The app reads its AI settings from `config.json` in the project root. You can edit it manually.

Example configuration:

```json
{
  "model": "openai/gpt-4o-mini",
  "api_key": "your_api_key_here",
  "api_base": "https://openrouter.ai/api/v1",
  "system_context": "You are a helpful assistant.",
  "error_message": "Err... :/ Check error_log for more info."
}
```

### Field explanations

- `model`: the model name your provider expects.
- `api_key`: your API key from the provider.
- `api_base`: the base URL for the provider's 
- `system_context`: optional custom system prompt for the assistant.
- `error_message`: message shown when the API call fails.

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

If the app cannot find `config.json`, it creates a default one with blank values. You should fill in your own API information before using the chat.

---

## 5) Troubleshooting

### config.json is missing or empty

Check that the file exists in the project folder and contains valid JSON.

### AI is not responding

Verify:

- `api_key` is correct
- `model` matches your provider's supported model names
- `api_base` points to the correct API endpoint
- your internet connection is working

### API error from provider

Open the `error_log.txt` file in the project folder to view the exact error message.

---

## 6) Recommended configuration template

Copy this exact template into `config.json` and replace the values:

```json
{
  "model": "openai/gpt-4o-mini",
  "api_key": "your_api_key_here",
  "api_base": "https://openrouter.ai/api/v1",
  "system_context": "You are a helpful assistant.",
  "error_message": "Err... :/ Check error_log for more info."
}
```

## License

This project is distributed as-is. Please check the repository for any project-specific licensing details before publishing or redistributing it.

---

## Quick Start

```bash
cd "Project Phoebe"
python -m pip install requests pystray pillow pygame
# edit config.json
python Phoebe.py
```

## Disclaimer

This project is provided for educational and personal use. It connects to third-party AI APIs using your own API key and credentials, and you are responsible for complying with the terms of service of those providers. The developer is not responsible for API costs, rate limits, usage restrictions, data privacy, or any issues caused by external services or misconfigured settings.
