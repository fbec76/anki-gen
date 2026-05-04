import json
from datetime import datetime
from config import COURSES_FILE, APP_DIR


API_KEY_FILE = APP_DIR / "api_key.json"
OPENAI_SETTINGS_FILE = APP_DIR / "openai_settings.json"


def _load() -> dict:
    if not COURSES_FILE.exists():
        return {}
    return json.loads(COURSES_FILE.read_text())


def _save(data: dict) -> None:
    COURSES_FILE.write_text(json.dumps(data, indent=2))


def get_api_key() -> str:
    """Load stored API key from app data."""
    if not API_KEY_FILE.exists():
        return ""
    try:
        data = json.loads(API_KEY_FILE.read_text())
        return data.get("api_key", "")
    except Exception:
        return ""


def set_api_key(api_key: str) -> None:
    """Store API key in app data."""
    data = {"api_key": api_key}
    API_KEY_FILE.write_text(json.dumps(data))


def get_openai_settings() -> dict:
    """Load stored OpenAI-compatible endpoint settings from app data."""
    if not OPENAI_SETTINGS_FILE.exists():
        return {"api_key": "", "base_url": "", "model": ""}
    try:
        data = json.loads(OPENAI_SETTINGS_FILE.read_text())
    except Exception:
        return {"api_key": "", "base_url": "", "model": ""}
    return {
        "api_key": data.get("api_key", ""),
        "base_url": data.get("base_url", ""),
        "model": data.get("model", ""),
    }


def set_openai_settings(api_key: str = "", base_url: str = "", model: str = "") -> None:
    """Store OpenAI-compatible endpoint settings in app data."""
    payload = {"api_key": api_key, "base_url": base_url, "model": model}
    OPENAI_SETTINGS_FILE.write_text(json.dumps(payload, indent=2))


def create_course(name: str) -> None:
    data = _load()
    if name in data:
        raise ValueError(f"Course '{name}' already exists.")
    data[name] = {"created": datetime.now().isoformat(), "decks": []}
    _save(data)


def list_courses() -> list[str]:
    return list(_load().keys())


def add_deck(course: str, deck_path: str, num_cards: int) -> None:
    data = _load()
    data[course]["decks"].append(
        {"path": deck_path, "cards": num_cards, "created": datetime.now().isoformat()}
    )
    _save(data)


def delete_course(name: str) -> None:
    data = _load()
    if name not in data:
        raise ValueError(f"Course '{name}' not found.")
    del data[name]
    _save(data)