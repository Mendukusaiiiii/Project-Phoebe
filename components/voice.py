import json
import os
import queue
import sys
import threading

try:
    import comtypes.client
    comtypes.client.gen_dir = None
except ImportError:
    comtypes = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

VOICE_RATE = 175

if getattr(sys, "frozen", False):

    _APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
  
    _APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_PATH = os.path.join(_APP_DIR, "config.json")

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    CONFIG = {}

VOICE_ID = CONFIG.get("voice_id", "")

try:
    VOICE_VOLUME = float(CONFIG.get("voice_volume", 1.0))
except (TypeError, ValueError):
    VOICE_VOLUME = 1.0
VOICE_VOLUME = max(0.0, min(1.0, VOICE_VOLUME))



def tts_available():
    return pyttsx3 is not None


class TextToSpeech:
    def __init__(self, rate=VOICE_RATE, volume=VOICE_VOLUME, on_error=None):
        self.rate = rate
        self.volume = max(0.0, min(1.0, volume))
        self.on_error = on_error
        self._queue = queue.Queue()
        self._thread = None
        self._engine = None
        self._engine_lock = threading.Lock()

    def start(self):
        if pyttsx3 is None or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        com_initialized = False
        if comtypes is not None:
            try:
                comtypes.CoInitialize()
                com_initialized = True
            except Exception:
                pass

        while True:
            text = self._queue.get()
            if text is None:
                break

            engine = None
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                try:
                    engine.setProperty("volume", self.volume)
                except Exception:
                    pass
                if VOICE_ID:
                    try:
                        engine.setProperty("voice", VOICE_ID)
                    except Exception:
                        pass
                with self._engine_lock:
                    self._engine = engine
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
            finally:
                with self._engine_lock:
                    self._engine = None
                if engine is not None:
                    try:
                        engine.stop()
                    except Exception:
                        pass

        if com_initialized:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

    def speak(self, text):
        if pyttsx3 is None:
            return
        cleaned = (text or "").strip()
        if cleaned:
            self._queue.put(cleaned)

    def clear_pending(self):
        with self._queue.mutex:
            self._queue.queue.clear()

    def stop_current(self):
        with self._engine_lock:
            engine = self._engine
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

    def stop(self):
        if self._thread is not None:
            self._queue.put(None)