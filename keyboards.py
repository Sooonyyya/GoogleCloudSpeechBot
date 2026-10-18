
"""Клавіатури Telegram для меню, перегляду чернетки й редагування параметрів."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from models import DEVICE_PROFILES, LANGUAGES


def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Мова", callback_data="lang"),
         InlineKeyboardButton("🎙 Голос", callback_data="voices:0")],
        [InlineKeyboardButton("⏩ Швидкість", callback_data="speed"),
         InlineKeyboardButton("🎼 Висота", callback_data="pitch")],
        [InlineKeyboardButton("💾 MP3 / WAV", callback_data="format")],
        [InlineKeyboardButton("🔊 Профіль пристрою", callback_data="profile")],
        [InlineKeyboardButton("📝 Звичайний текст", callback_data="mode:text"),
         InlineKeyboardButton("🔤 SSML", callback_data="mode:ssml")],
        [InlineKeyboardButton("❔ Довідка", callback_data="help")],
    ])


def review_keyboard() -> InlineKeyboardMarkup:
    """Кнопки під отриманим текстом — до надсилання запиту Google Cloud."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Редагувати мову", callback_data="lang"),
         InlineKeyboardButton("🎙 Редагувати голос", callback_data="voices:0")],
        [InlineKeyboardButton("⏩ Редагувати швидкість", callback_data="speed"),
         InlineKeyboardButton("🎼 Редагувати висоту", callback_data="pitch")],
        [InlineKeyboardButton("💾 Редагувати формат", callback_data="format")],
        [InlineKeyboardButton("🔊 Підлаштувати під пристрій", callback_data="profile")],
        [InlineKeyboardButton("✏️ Змінити текст", callback_data="change_text"),
         InlineKeyboardButton("❌ Скасувати", callback_data="cancel_text")],
        [InlineKeyboardButton("▶️ Згенерувати аудіо", callback_data="generate")],
    ])


def options_keyboard(prefix: str, options: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"{prefix}:{value}")]
            for label, value in options]
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(rows)


def voice_keyboard(names: list[str], page: int, page_size: int = 5) -> InlineKeyboardMarkup:
    first = page * page_size
    rows = [
        [InlineKeyboardButton(name, callback_data=f"voice:{i}")]
        for i, name in enumerate(names[first:first + page_size], start=first)
    ]
    controls = []
    if page:
        controls.append(InlineKeyboardButton("◀️", callback_data=f"voices:{page-1}"))
    if first + page_size < len(names):
        controls.append(InlineKeyboardButton("▶️", callback_data=f"voices:{page+1}"))
    if controls:
        rows.append(controls)
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(rows)


def language_keyboard() -> InlineKeyboardMarkup:
    return options_keyboard("lang", [(name, code) for code, name in LANGUAGES.items()])


def profile_keyboard() -> InlineKeyboardMarkup:
    return options_keyboard("profile", [(name, code) for code, name in DEVICE_PROFILES.items()])
