"""Перевірка вхідного тексту перед платним зверненням до Cloud TTS."""
import re
import xml.etree.ElementTree as ET

MAX_INPUT_BYTES = 5000  # Офіційний ліміт Cloud Text-to-Speech (UTF-8 bytes).
ALLOWED_TAGS = {"speak", "break", "prosody", "emphasis", "say-as", "sub", "p", "s", "phoneme"}
ALLOWED_ATTRIBUTES = {
    "speak": set(),
    "break": {"time", "strength"},
    "prosody": {"rate", "pitch", "volume"},
    "emphasis": {"level"},
    "say-as": {"interpret-as", "format", "detail"},
    "sub": {"alias"},
    "p": set(),
    "s": set(),
    "phoneme": {"alphabet", "ph"},
}


def validate_input(text: str, *, is_ssml: bool) -> str:
    """Повернути нормалізований текст або підняти ValueError українською."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Текст порожній. Надішли повідомлення для озвучення.")
    actual_bytes = len(cleaned.encode("utf-8"))
    if actual_bytes > MAX_INPUT_BYTES:
        raise ValueError(
            f"Текст завеликий: {actual_bytes} байтів UTF-8. "
            f"Ліміт API — {MAX_INPUT_BYTES} байтів на один запит. Скороти текст."
        )
    if not is_ssml:
        return cleaned

    # Заборонено DTD, entity і зовнішнє аудіо, щоб не приймати довільні ресурси.
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", cleaned, flags=re.I):
        raise ValueError("SSML не може містити DOCTYPE або ENTITY.")
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        raise ValueError("Невірний XML/SSML. Перевір закриття тегів.") from exc
    if root.tag != "speak":
        raise ValueError("SSML має починатися з <speak> і завершуватися </speak>.")
    for node in root.iter():
        if node.tag not in ALLOWED_TAGS:
            raise ValueError(f"Тег <{node.tag}> не підтримується в цьому PoC.")
        unsupported_attributes = set(node.attrib) - ALLOWED_ATTRIBUTES[node.tag]
        if unsupported_attributes:
            raise ValueError(f"Непідтримуваний атрибут у <{node.tag}>.")
    if not "".join(root.itertext()).strip():
        raise ValueError("SSML має містити текст, який треба озвучити.")
    return cleaned