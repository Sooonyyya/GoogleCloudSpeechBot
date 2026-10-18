
"""Інтеграція з Google Cloud Text-to-Speech (ListVoices і SynthesizeSpeech)."""
from dataclasses import dataclass

from models import UserPreferences
from validators import validate_input


@dataclass(frozen=True)
class VoiceInfo:
    name: str
    gender: str
    family: str


class TextToSpeechService:
    def __init__(self) -> None:
        from google.cloud import texttospeech
        self._api = texttospeech
        self._client = texttospeech.TextToSpeechClient()

    def list_voices(self, language: str) -> list[VoiceInfo]:
        """Для PoC пропонуємо тільки Standard/WaveNet, як у вихідному проєкті."""
        response = self._client.list_voices(language_code=language)
        voices: list[VoiceInfo] = []
        for voice in response.voices:
            if "-Standard-" in voice.name:
                family = "Standard"
            elif "-Wavenet-" in voice.name:
                family = "WaveNet"
            else:
                continue
            gender = self._api.SsmlVoiceGender(voice.ssml_gender).name
            voices.append(VoiceInfo(name=voice.name, gender=gender, family=family))
        return sorted(voices, key=lambda v: (0 if v.family == "Standard" else 1, v.name))

    def synthesize(self, raw_input: str, settings: UserPreferences) -> bytes:
        text = validate_input(raw_input, is_ssml=settings.input_mode == "ssml")
        synthesis_input = (
            self._api.SynthesisInput(ssml=text)
            if settings.input_mode == "ssml"
            else self._api.SynthesisInput(text=text)
        )
        voice_kwargs = {"language_code": settings.language}
        if settings.voice_name:
            voice_kwargs["name"] = settings.voice_name
        request_voice = self._api.VoiceSelectionParams(**voice_kwargs)
        encoding = (
            self._api.AudioEncoding.MP3
            if settings.audio_format == "MP3"
            else self._api.AudioEncoding.LINEAR16
        )
        audio_kwargs = {
            "audio_encoding": encoding,
            "speaking_rate": settings.speed,
            "pitch": settings.pitch,
        }
        if settings.device_profile != "none":
            audio_kwargs["effects_profile_id"] = [settings.device_profile]
        audio_config = self._api.AudioConfig(**audio_kwargs)
        response = self._client.synthesize_speech(
            input=synthesis_input, voice=request_voice, audio_config=audio_config
        )
        if not response.audio_content:
            raise RuntimeError("Google Cloud повернув порожній аудіофайл.")
        return bytes(response.audio_content)
