
"""Налаштування користувача, що зберігаються в пам'яті бота."""
from dataclasses import dataclass

LANGUAGES = {
    "uk-UA": "🇺🇦 Українська",
    "en-US": "🇺🇸 Англійська (США)",
    "pl-PL": "🇵🇱 Польська",
}

# Ідентифікатори профілів відповідають Google Cloud TTS AudioConfig.effects_profile_id.
DEVICE_PROFILES = {
    "none": "Без додаткового профілю",
    "handset-class-device": "📱 Смартфон",
    "headphone-class-device": "🎧 Навушники",
    "small-bluetooth-speaker-class-device": "🔊 Маленька Bluetooth-колонка",
    "medium-bluetooth-speaker-class-device": "🔉 Домашня колонка",
    "telephony-class-application": "☎️ Телефонний зв'язок",
}


@dataclass
class UserPreferences:
    language: str = "uk-UA"
    voice_name: str = "uk-UA-Standard-B"
    speed: float = 1.0
    pitch: float = 0.0
    audio_format: str = "MP3"
    input_mode: str = "text"
    device_profile: str = "none"

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES:
            raise ValueError("Непідтримувана мова.")
        self.language = language
        # Назва голосу попередньої мови не підходить до нової мови.
        self.voice_name = ""


def current_settings_text(settings: UserPreferences, *, show_hint: bool = True) -> str:
    lines = [
        "⚙️ Поточні параметри",
        "",
        f"🌍 Мова: {LANGUAGES[settings.language]}",
        f"🎙 Голос: {settings.voice_name or 'автоматично'}",
        f"⏩ Швидкість: {settings.speed:g}×",
        f"🎼 Висота: {settings.pitch:+g} півтонів",
        f"💾 Формат: {settings.audio_format}",
        f"🔊 Профіль: {DEVICE_PROFILES[settings.device_profile]}",
        f"📝 Режим: {'SSML' if settings.input_mode == 'ssml' else 'звичайний текст'}",
    ]
    if show_hint:
        lines.extend(["", "Надішли текст. Перед генерацією зможеш змінити параметри."])
    return "\n".join(lines)