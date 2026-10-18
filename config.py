"""Читає секрети з .env або змінних середовища; не містить секретних даних."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent


def setup_environment() -> tuple[str, frozenset[int]]:
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "ВСТАВ_ТОКЕН_ВІД_BOTFATHER":
        raise RuntimeError("Вкажи справжній TELEGRAM_BOT_TOKEN у файлі .env (див. README.md).")

    credential_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if credential_path:
        file_path = Path(credential_path)
        if not file_path.is_absolute():
            file_path = BASE_DIR / file_path
        if not file_path.is_file():
            raise RuntimeError(f"Не знайдено JSON-ключ Google Cloud: {file_path}")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(file_path.resolve())
    # Якщо шлях не вказаний, бібліотека Google застосує ADC з gcloud login.
    raw_ids = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "").strip()
    try:
        allowed = frozenset(int(s.strip()) for s in raw_ids.split(",") if s.strip())
    except ValueError as exc:
        raise RuntimeError("ALLOWED_TELEGRAM_USER_IDS: вкажи числа через кому або залиш порожнім.") from exc
    return token, allowed
