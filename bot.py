
"""Telegram-бот з редагуванням параметрів перед генерацією аудіо."""

import asyncio
import io
import logging
import time
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import setup_environment
from keyboards import (
    language_keyboard,
    menu_keyboard,
    options_keyboard,
    profile_keyboard,
    review_keyboard,
    voice_keyboard,
)
from models import (
    DEVICE_PROFILES,
    UserPreferences,
    current_settings_text,
)
from tts_service import TextToSpeechService
from validators import validate_input


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)


HELP_TEXT = (
    "🔊 Google Cloud Speech Bot — навчальний PoC\n\n"
    "1. Вибери звичайний текст або SSML.\n"
    "2. Надішли текст для озвучення.\n"
    "3. Відредагуй мову, голос, швидкість, висоту, "
    "формат або профіль пристрою.\n"
    "4. Натисни «▶️ Згенерувати аудіо».\n"
    "5. Після генерації можеш змінити параметри "
    "та озвучити текст повторно.\n\n"
    "Приклад SSML:\n"
    '<speak>Привіт! <break time="500ms"/> '
    '<prosody rate="slow">Я говорю повільно.</prosody></speak>\n\n'
    "Команди: /start, /settings, /voices, /text, "
    "/ssml, /id, /help."
)


def preferences(
    context: ContextTypes.DEFAULT_TYPE
) -> UserPreferences:
    if "preferences" not in context.user_data:
        context.user_data["preferences"] = UserPreferences()
    return context.user_data["preferences"]


def has_draft(
    context: ContextTypes.DEFAULT_TYPE
) -> bool:
    return "pending_text" in context.user_data


def clear_draft(
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    context.user_data.pop("pending_text", None)
    context.user_data.pop("pending_mode", None)


def is_allowed(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> bool:
    allowed = context.application.bot_data["allowed_ids"]
    return not allowed or (
        update.effective_user is not None
        and update.effective_user.id in allowed
    )


async def deny(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer(
            "Доступ до цього бота обмежено.",
            show_alert=True,
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            "⛔ Цей бот приватний. "
            "Твій ID можна подивитися командою /id."
        )


async def send_or_edit(
    update: Update,
    text: str,
    reply_markup=None
) -> None:
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
            )
        except BadRequest as exc:
            if "not modified" not in str(exc).lower():
                raise
    else:
        await update.effective_message.reply_text(
            text,
            reply_markup=reply_markup,
        )


async def show_current_screen(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    p = preferences(context)

    if has_draft(context):
        raw = context.user_data["pending_text"]
        fragment = raw[:1300] + (
            "…" if len(raw) > 1300 else ""
        )

        text = (
            "📝 Текст отримано. Перед генерацією "
            "можеш змінити налаштування.\n\n"
            f"Текст: {fragment}\n\n"
            f"{current_settings_text(p, show_hint=False)}\n\n"
            "Коли все готово, натисни "
            "«▶️ Згенерувати аудіо»."
        )

        await send_or_edit(
            update,
            text,
            review_keyboard(),
        )
    else:
        await send_or_edit(
            update,
            current_settings_text(p),
            menu_keyboard(),
        )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_allowed(update, context):
        await deny(update)
        return

    clear_draft(context)

    await send_or_edit(
        update,
        "👋 Вітаю! Я озвучую тексти через "
        "Google Cloud Text-to-Speech.\n\n"
        + current_settings_text(preferences(context)),
        menu_keyboard(),
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_allowed(update, context):
        await deny(update)
        return

    await send_or_edit(
        update,
        HELP_TEXT,
        review_keyboard()
        if has_draft(context)
        else menu_keyboard(),
    )


async def user_id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    await update.effective_message.reply_text(
        f"Твій Telegram user ID: {update.effective_user.id}"
    )


async def settings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_allowed(update, context):
        await deny(update)
        return

    await show_current_screen(update, context)


async def mode_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    mode: str
) -> None:
    if not is_allowed(update, context):
        await deny(update)
        return

    clear_draft(context)
    preferences(context).input_mode = mode

    await send_or_edit(
        update,
        current_settings_text(preferences(context))
        + (
            "\n\nПриклад SSML можна знайти у /help."
            if mode == "ssml"
            else ""
        ),
        menu_keyboard(),
    )


async def plain_mode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    await mode_command(update, context, "text")


async def ssml_mode(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    await mode_command(update, context, "ssml")


async def voice_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0
) -> None:
    p = preferences(context)

    try:
        service: TextToSpeechService = (
            context.application.bot_data["tts_service"]
        )

        voice_data = await asyncio.to_thread(
            service.list_voices,
            p.language,
        )

    except Exception as exc:
        LOGGER.exception(
            "Не вдалося отримати список голосів"
        )

        await send_or_edit(
            update,
            "❌ Не вдалося завантажити голоси. "
            "Перевір API, Billing і JSON-ключ.\n"
            f"Тип помилки: {type(exc).__name__}.",
            review_keyboard()
            if has_draft(context)
            else menu_keyboard(),
        )
        return

    context.user_data["voice_catalog"] = voice_data

    if not voice_data:
        await send_or_edit(
            update,
            "Для обраної мови не знайдено доступних "
            "голосів. Вибери іншу мову.",
            review_keyboard()
            if has_draft(context)
            else menu_keyboard(),
        )
        return

    page_size = 5
    page = max(
        0,
        min(page, (len(voice_data) - 1) // page_size),
    )

    if p.language == "uk-UA":
        names = [
            (
                f"{'👨 Чоловічий' if v.gender == 'MALE' else '👩 Жіночий'}"
                f" · {v.name}"
            )
            for v in voice_data
        ]

        intro = (
            "🎙 Голоси для української мови\n"
            "Chirp 3 HD має окрему тарифікацію.\n"
        )
    else:
        names = [
            f"{v.name} · {v.gender}"
            for v in voice_data
        ]

        intro = f"🎙 Голоси для {p.language}\n"

    await send_or_edit(
        update,
        intro
        + f"Сторінка {page + 1} із "
        f"{(len(names) + page_size - 1) // page_size}.\n\n"
        "Вибери голос:",
        voice_keyboard(names, page),
    )


async def voices_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_allowed(update, context):
        await deny(update)
        return

    await voice_list(update, context)


async def generate_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query

    if not has_draft(context):
        await query.answer(
            "Спочатку надішли текст.",
            show_alert=True,
        )
        return

    p = preferences(context)
    raw = context.user_data["pending_text"]
    mode = context.user_data["pending_mode"]

    try:
        cleaned = validate_input(
            raw,
            is_ssml=mode == "ssml",
        )
    except ValueError as exc:
        await query.answer(
            str(exc),
            show_alert=True,
        )
        return

    last = context.user_data.get(
        "last_synthesis_at",
        0.0,
    )

    if time.monotonic() - last < 3.0:
        await query.answer(
            "Зачекай 3 секунди перед наступною генерацією.",
            show_alert=True,
        )
        return

    context.user_data["last_synthesis_at"] = (
        time.monotonic()
    )

    await query.answer("Генерую аудіо…")

    progress = await query.message.reply_text(
        "🔄 Надсилаю запит у Google Cloud Text-to-Speech…"
    )

    chat_id = update.effective_chat.id

    try:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.UPLOAD_DOCUMENT,
        )
    except TimedOut:
        LOGGER.warning(
            "Не вдалося надіслати індикатор завантаження"
        )

    # Генерація аудіо через Google Cloud.
    try:
        p.input_mode = mode

        service: TextToSpeechService = (
            context.application.bot_data["tts_service"]
        )

        audio = await asyncio.to_thread(
            service.synthesize,
            cleaned,
            p,
        )

    except Exception as exc:
        LOGGER.exception(
            "Помилка синтезу Google Cloud Text-to-Speech"
        )

        await progress.edit_text(
            "❌ Не вдалося створити аудіо через Google Cloud.\n"
            "Перевір API, Billing, голос або формат SSML.\n"
            f"Тип помилки: {type(exc).__name__}. "
            "Подробиці — у консолі Visual Studio.",
            reply_markup=review_keyboard(),
        )
        return

    extension = (
        "mp3" if p.audio_format == "MP3" else "wav"
    )

    name = (
        f"tts_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}"
        f".{extension}"
    )

    file = io.BytesIO(audio)
    file.name = name

    caption = (
        f"✅ {p.language} · "
        f"{p.voice_name or 'авто'} · "
        f"{p.speed:g}× · {p.audio_format}"
    )

    # Надсилання готового файлу до Telegram.
    try:
        await progress.edit_text(
            "📤 Аудіо створено. Надсилаю файл у Telegram…"
        )

        if extension == "mp3":
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=file,
                filename=name,
                title="Google Cloud TTS",
                caption=caption,
                connect_timeout=60,
                read_timeout=300,
                write_timeout=300,
                pool_timeout=60,
            )
        else:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file,
                filename=name,
                caption=caption,
                connect_timeout=60,
                read_timeout=300,
                write_timeout=300,
                pool_timeout=60,
            )

    except TimedOut:
        LOGGER.warning(
            "Telegram не підтвердив надсилання аудіо"
        )

        await progress.edit_text(
            "⏳ Telegram не підтвердив доставку аудіо. "
            "Файл міг уже надійти — перевір чат.\n"
            "Можеш продовжити редагування параметрів.",
            reply_markup=review_keyboard(),
        )
        return

    except Exception as exc:
        LOGGER.exception(
            "Помилка надсилання аудіо до Telegram"
        )

        await progress.edit_text(
            "❌ Аудіо створено, але виникла помилка "
            "під час надсилання у Telegram.\n"
            f"Тип помилки: {type(exc).__name__}. "
            "Подробиці — у консолі Visual Studio.",
            reply_markup=review_keyboard(),
        )
        return

    # Зберігаємо чернетку, щоб редагування
    # працювало і після генерації аудіо.
    await progress.edit_text(
        "✅ Аудіо створено через Google Cloud "
        "Text-to-Speech API.\n"
        "Можеш змінити параметри й озвучити "
        "цей самий текст ще раз.",
        reply_markup=review_keyboard(),
    )


async def callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_allowed(update, context):
        await deny(update)
        return

    query = update.callback_query
    data = query.data or ""
    p = preferences(context)

    if data in ("home", "back"):
        await show_current_screen(update, context)

    elif data == "help":
        await help_command(update, context)

    elif data == "generate":
        await generate_audio(update, context)

    elif data == "cancel_text":
        clear_draft(context)

        await send_or_edit(
            update,
            "❌ Озвучення скасовано.\n\n"
            + current_settings_text(p),
            menu_keyboard(),
        )

    elif data == "change_text":
        clear_draft(context)

        await send_or_edit(
            update,
            "✏️ Надішли новий текст або SSML. "
            "Після цього знову побачиш "
            "кнопки редагування.",
            menu_keyboard(),
        )

    elif data == "lang":
        await send_or_edit(
            update,
            "🌍 Вибери мову синтезу:",
            language_keyboard(),
        )

    elif data.startswith("lang:"):
        try:
            p.set_language(
                data.split(":", 1)[1]
            )
        except ValueError:
            await query.answer(
                "Невідома мова.",
                show_alert=True,
            )
            return

        context.user_data.pop(
            "voice_catalog",
            None,
        )

        await show_current_screen(update, context)

    elif data.startswith("voices:"):
        try:
            page = int(
                data.split(":", 1)[1]
            )
        except ValueError:
            page = 0

        await voice_list(update, context, page)

    elif data.startswith("voice:"):
        voices = context.user_data.get(
            "voice_catalog",
            [],
        )

        try:
            index = int(
                data.split(":", 1)[1]
            )
            choice = voices[index]
        except (ValueError, IndexError):
            await query.answer(
                "Онови список голосів.",
                show_alert=True,
            )
            return

        if p.language not in choice.name:
            await query.answer(
                "Цей голос не підходить до обраної мови.",
                show_alert=True,
            )
            return

        p.voice_name = choice.name

        # Chirp 3 HD не підтримує зміну висоти.
        if "-Chirp3-HD-" in p.voice_name:
            p.pitch = 0.0

        await show_current_screen(update, context)

    elif data == "speed":
        await send_or_edit(
            update,
            "⏩ Вибери швидкість мовлення:",
            options_keyboard(
                "speed",
                [
                    (f"{s:g}×", str(s))
                    for s in (
                        0.5,
                        0.75,
                        1.0,
                        1.25,
                        1.5,
                    )
                ],
            ),
        )

    elif data.startswith("speed:"):
        try:
            value = float(
                data.split(":", 1)[1]
            )
        except ValueError:
            value = 0

        if value not in (
            0.5,
            0.75,
            1.0,
            1.25,
            1.5,
        ):
            await query.answer(
                "Недопустима швидкість.",
                show_alert=True,
            )
            return

        p.speed = value
        await show_current_screen(update, context)

    elif data == "pitch":
        if "-Chirp3-HD-" in p.voice_name:
            await query.answer(
                "Для Chirp 3 HD зміна висоти недоступна.",
                show_alert=True,
            )
            return

        await send_or_edit(
            update,
            "🎼 Вибери висоту голосу:",
            options_keyboard(
                "pitch",
                [
                    (f"{v:+g} півтонів", str(v))
                    for v in (
                        -4.0,
                        -2.0,
                        0.0,
                        2.0,
                        4.0,
                    )
                ],
            ),
        )

    elif data.startswith("pitch:"):
        if "-Chirp3-HD-" in p.voice_name:
            await query.answer(
                "Для Chirp 3 HD зміна висоти недоступна.",
                show_alert=True,
            )
            return

        try:
            value = float(
                data.split(":", 1)[1]
            )
        except ValueError:
            value = 100

        if value not in (
            -4.0,
            -2.0,
            0.0,
            2.0,
            4.0,
        ):
            await query.answer(
                "Недопустима висота.",
                show_alert=True,
            )
            return

        p.pitch = value
        await show_current_screen(update, context)

    elif data == "format":
        await send_or_edit(
            update,
            "💾 Вибери формат:",
            options_keyboard(
                "format",
                [
                    ("🎵 MP3", "MP3"),
                    ("📄 WAV", "WAV"),
                ],
            ),
        )

    elif data.startswith("format:"):
        value = data.split(":", 1)[1]

        if value not in ("MP3", "WAV"):
            await query.answer(
                "Невідомий формат.",
                show_alert=True,
            )
            return

        p.audio_format = value
        await show_current_screen(update, context)

    elif data == "profile":
        await send_or_edit(
            update,
            "🔊 Обери пристрій для оптимізації звучання:",
            profile_keyboard(),
        )

    elif data.startswith("profile:"):
        value = data.split(":", 1)[1]

        if value not in DEVICE_PROFILES:
            await query.answer(
                "Невідомий профіль пристрою.",
                show_alert=True,
            )
            return

        p.device_profile = value
        await show_current_screen(update, context)

    elif data.startswith("mode:"):
        value = data.split(":", 1)[1]

        if value not in ("text", "ssml"):
            await query.answer(
                "Невідомий режим.",
                show_alert=True,
            )
            return

        clear_draft(context)
        p.input_mode = value

        await show_current_screen(update, context)

    else:
        await query.answer(
            "Невідома команда.",
            show_alert=True,
        )


async def on_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not is_allowed(update, context):
        await deny(update)
        return

    p = preferences(context)
    raw = update.effective_message.text or ""

    try:
        cleaned = validate_input(
            raw,
            is_ssml=p.input_mode == "ssml",
        )
    except ValueError as exc:
        await update.effective_message.reply_text(
            f"⚠️ {exc}"
        )
        return

    context.user_data["pending_text"] = cleaned
    context.user_data["pending_mode"] = p.input_mode

    await show_current_screen(update, context)


def main() -> None:
    token, allowed = setup_environment()

    try:
        service = TextToSpeechService()
    except Exception as exc:
        raise RuntimeError(
            "Google Cloud не авторизовано. "
            "Перевір GOOGLE_APPLICATION_CREDENTIALS "
            "у .env або налаштуй "
            "Application Default Credentials."
        ) from exc

    app = (
        Application.builder()
        .token(token)
        .connect_timeout(30)
        .read_timeout(30)
        .get_updates_connect_timeout(30)
        .get_updates_read_timeout(30)
        .build()
    )

    app.bot_data["tts_service"] = service
    app.bot_data["allowed_ids"] = allowed

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", user_id_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("voices", voices_command))
    app.add_handler(CommandHandler("ssml", ssml_mode))
    app.add_handler(CommandHandler("text", plain_mode))

    app.add_handler(
        CallbackQueryHandler(callback)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            on_text,
        )
    )

    LOGGER.info(
        "Бот запущений (long polling). "
        "Щоб завершити, натисни Ctrl+C."
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
