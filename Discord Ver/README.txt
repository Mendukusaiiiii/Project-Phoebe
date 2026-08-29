Project Phoebe Discord Bot

A Python Discord bot that responds in a configured channel using an OpenAI-compatible AI provider.

Features:
- Channel-based activation with /setup and /unsetup
- Per-user memory tracking
- Simple slash-style commands
- OpenAI-compatible API support
- Custom system prompt and error message

Files:
- main.py - Main bot script
- config.json - AI and bot settings
- requirements.txt - Python dependencies

Requirements:
- Python 3.10+
- A Discord bot token
- An AI provider with an OpenAI-compatible API endpoint

Setup:

1. Install dependencies

   python -m pip install -r requirements.txt

2. Edit config.json

   Example:
   {
     "model": "gpt-4o-mini",
     "api_key": "YOUR_API_KEY",
     "api_base": "https://api.openai.com/v1",
     "system_context": "You are a helpful assistant.",
     "error_message": "Err... :/",
     "channel_id": ""
   }

   Field notes:
   - model: model name supported by your AI provider
   - api_key: your provider API key
   - api_base: OpenAI-compatible API base URL
   - system_context: assistant personality/instructions
   - error_message: message shown if a request fails
   - channel_id: automatically set by /setup

   Common examples:
   - OpenAI: model = gpt-4o-mini, api_base = https://api.openai.com/v1
   - OpenRouter: model = openai/gpt-4o-mini, api_base = https://openrouter.ai/api/v1
   - Gemini-compatible endpoint: model = gemini-2.0-flash, api_base = https://generativelanguage.googleapis.com/v1beta/openai
   - Ollama: model = llama3.2, api_base = http://localhost:11434/v1

3. Add your Discord bot token

   Open main.py and replace the empty value in:
   bot.run("")

   with your actual bot token.

4. Run the bot

   python main.py

Commands:
- /setup - Enables the bot in the current text channel
- /unsetup - Disables the bot in the selected channel
- /help - Shows available commands
- /clearmemory - Clears the user's memory
- /test and /stoptest - Demo binary message loop

Important:
- The bot only responds in the setup channel.
- It ignores bot messages and messages starting with '/'.
- If the API call fails, the configured error_message is returned.

Disclaimer:
This project connects to third-party AI services using your own API key and provider configuration. You are responsible for all usage, billing, rate limits, and compliance with provider terms. The developer is not responsible for API failures, service outages, or issues caused by external providers or incorrect settings.