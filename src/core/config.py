"""
Central config. All secrets come from environment variables / .env file.
Never hardcode API keys in the scripts.
"""
import os
from dotenv import load_dotenv

# Always load .env from the root directory, regardless of where invoked.
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_PATH = os.path.join(_ROOT_DIR, ".env")
load_dotenv(dotenv_path=_ENV_PATH, override=True)

# --- Groq (free tier LLM for scripts, titles, descriptions) ---
GROQ_API_KEYS = [v for k, v in os.environ.items() if k.startswith("GROQ_API_KEY") and v]
# If none found from environ loop, fallback to straight getenv
if not GROQ_API_KEYS and os.getenv("GROQ_API_KEY"):
    GROQ_API_KEYS = [os.getenv("GROQ_API_KEY")]
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")


# --- AI Video Generation APIs ---
PEXELS_API_KEY = os.getenv("pexel")
PIXVERSE_API_KEY = os.getenv("PIXVERSE_API_KEY") or os.getenv("platform_pixverse")  # supports both key names
KLING_API_KEY = os.getenv("kling_ai")
QWEN_API_KEY = os.getenv("qwen_api")
RUNWAYML_API_KEY = os.getenv("runwayml_key")

# --- Coverr stock video API (50 free requests/hour) ---
COVERR_API_KEY = os.getenv("COVERR_API_KEY", "")

# --- Inworld TTS API ---
INWORLD_API_KEY = os.getenv("inworld")

# --- Fish Audio TTS API ---
FISH_AUDIO_KEY = os.getenv("fish_audio_key")

# --- YouTube OAuth (created once in Google Cloud Console) ---
YT_CLIENT_SECRETS_FILE = os.getenv("YT_CLIENT_SECRETS_FILE", "client_secret.json")
YT_TOKEN_FILE = os.getenv("YT_TOKEN_FILE", "token.json")  # holds the refresh token
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# --- Content niche / channel settings ---
CHANNEL_NICHES = [
    os.getenv("CHANNEL_NICHE_1", "sad heartbreaking real love stories"),
    os.getenv("CHANNEL_NICHE_2", "thriller real love stories with twists"),
    os.getenv("CHANNEL_NICHE_3", "sacrificing incredible real love stories"),
    os.getenv("CHANNEL_NICHE_4", "unbelievable historical true love stories"),
    os.getenv("CHANNEL_NICHE_5", "beautiful tear-jerking real love stories"),
]
VIDEO_LENGTH_SECONDS = int(os.getenv("VIDEO_LENGTH_SECONDS", "50"))  # good for Shorts
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
