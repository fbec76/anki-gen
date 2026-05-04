from pathlib import Path
import os

# Where course metadata is stored
APP_DIR = Path.home() / ".anki-gen"
APP_DIR.mkdir(exist_ok=True)
COURSES_FILE = APP_DIR / "courses.json"

# LLM settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
MODEL = os.getenv("MODEL", "gpt-4.1")
MODEL_NAME = MODEL
MAX_CHUNK_CHARS = 8000        # chunk size for long slide decks