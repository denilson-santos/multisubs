"""Static ASR capabilities used before importing model runtimes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType

from ..config import MODELS as WHISPERX_MODELS
from ..config import SUPPORTED_LANGUAGES as WHISPERX_LANGUAGES
from ..errors import TranscriptionError, ValidationError
from .base import ASRBackend

_LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}$")

FASTER_WHISPER_MODELS = (
    "tiny.en",
    "tiny",
    "base.en",
    "base",
    "small.en",
    "small",
    "medium.en",
    "medium",
    "large-v1",
    "large-v2",
    "large-v3",
    "large-v3-turbo",
    "turbo",
)

FASTER_WHISPER_LANGUAGES = (
    "af",
    "am",
    "ar",
    "as",
    "az",
    "ba",
    "be",
    "bg",
    "bn",
    "bo",
    "br",
    "bs",
    "ca",
    "cs",
    "cy",
    "da",
    "de",
    "el",
    "en",
    "es",
    "et",
    "eu",
    "fa",
    "fi",
    "fo",
    "fr",
    "gl",
    "gu",
    "ha",
    "haw",
    "he",
    "hi",
    "hr",
    "ht",
    "hu",
    "hy",
    "id",
    "is",
    "it",
    "ja",
    "jw",
    "ka",
    "kk",
    "km",
    "kn",
    "ko",
    "la",
    "lb",
    "ln",
    "lo",
    "lt",
    "lv",
    "mg",
    "mi",
    "mk",
    "ml",
    "mn",
    "mr",
    "ms",
    "mt",
    "my",
    "ne",
    "nl",
    "nn",
    "no",
    "oc",
    "pa",
    "pl",
    "ps",
    "pt",
    "ro",
    "ru",
    "sa",
    "sd",
    "si",
    "sk",
    "sl",
    "sn",
    "so",
    "sq",
    "sr",
    "su",
    "sv",
    "sw",
    "ta",
    "te",
    "tg",
    "th",
    "tk",
    "tl",
    "tr",
    "tt",
    "uk",
    "ur",
    "uz",
    "vi",
    "yi",
    "yo",
    "zh",
)

PARAKEET_LANGUAGES = (
    "bg",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "fi",
    "fr",
    "de",
    "el",
    "hu",
    "it",
    "lv",
    "lt",
    "mt",
    "pl",
    "pt",
    "ro",
    "sk",
    "sl",
    "es",
    "sv",
    "ru",
    "uk",
)

QWEN_LANGUAGE_NAMES = MappingProxyType(
    {
        "zh": "Chinese",
        "en": "English",
        "yue": "Cantonese",
        "ar": "Arabic",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "pt": "Portuguese",
        "id": "Indonesian",
        "it": "Italian",
        "ko": "Korean",
        "ru": "Russian",
        "th": "Thai",
        "vi": "Vietnamese",
        "ja": "Japanese",
        "tr": "Turkish",
        "hi": "Hindi",
        "ms": "Malay",
        "nl": "Dutch",
        "sv": "Swedish",
        "da": "Danish",
        "fi": "Finnish",
        "pl": "Polish",
        "cs": "Czech",
        "fil": "Filipino",
        "fa": "Persian",
        "el": "Greek",
        "hu": "Hungarian",
        "mk": "Macedonian",
        "ro": "Romanian",
    }
)
QWEN_ALIGNMENT_LANGUAGES = frozenset(
    {"zh", "en", "yue", "fr", "de", "it", "ja", "ko", "pt", "ru", "es"}
)


@dataclass(frozen=True)
class ASRSpec:
    """User-visible capability catalog for one adapter."""

    default_model: str
    models: tuple[str, ...]
    languages: tuple[str, ...]
    supports_translation: bool


ASR_SPECS = MappingProxyType(
    {
        ASRBackend.WHISPERX: ASRSpec(
            default_model="turbo",
            models=WHISPERX_MODELS,
            languages=WHISPERX_LANGUAGES,
            supports_translation=True,
        ),
        ASRBackend.FASTER_WHISPER: ASRSpec(
            default_model="turbo",
            models=FASTER_WHISPER_MODELS,
            languages=FASTER_WHISPER_LANGUAGES,
            supports_translation=True,
        ),
        ASRBackend.PARAKEET: ASRSpec(
            default_model="nvidia/parakeet-tdt-0.6b-v3",
            models=("nvidia/parakeet-tdt-0.6b-v3",),
            languages=PARAKEET_LANGUAGES,
            supports_translation=False,
        ),
        ASRBackend.QWEN: ASRSpec(
            default_model="Qwen/Qwen3-ASR-1.7B",
            models=("Qwen/Qwen3-ASR-1.7B",),
            languages=tuple(QWEN_LANGUAGE_NAMES),
            supports_translation=False,
        ),
    }
)

ASR_CHOICES = tuple(backend.value for backend in ASRBackend)
ALL_LANGUAGE_CODES = tuple(
    sorted({language for spec in ASR_SPECS.values() for language in spec.languages})
)


def parse_backend(value: str | ASRBackend) -> ASRBackend:
    if isinstance(value, ASRBackend):
        return value
    try:
        return ASRBackend(value)
    except ValueError as exc:
        raise ValidationError(
            f"Unknown ASR backend '{value}'. Choose one of: {', '.join(ASR_CHOICES)}."
        ) from exc


def normalise_language_code(value: str) -> str:
    language = value.strip().lower()
    if not _LANGUAGE_CODE.fullmatch(language):
        raise ValidationError(
            f"Invalid source language code '{value}'; use a two- or three-letter code."
        )
    return language


def resolve_model(backend: ASRBackend, model_name: str | None) -> str:
    spec = ASR_SPECS[backend]
    resolved = spec.default_model if model_name is None else model_name
    if resolved not in spec.models:
        raise ValidationError(
            f"Model '{resolved}' is not supported by {backend.value}. Choose one of: "
            + ", ".join(spec.models)
            + "."
        )
    return resolved


def validate_request(
    backend: ASRBackend,
    language: str | None,
    task: str,
    model_name: str,
) -> str | None:
    """Validate a backend request before loading its optional dependencies."""
    spec = ASR_SPECS[backend]
    if task not in {"transcribe", "translate"}:
        raise ValidationError("Task must be 'transcribe' or 'translate'.")
    if task == "translate" and not spec.supports_translation:
        raise ValidationError(
            f"{backend.value} does not support --task translate; use whisperx or "
            "faster-whisper, or select --task transcribe."
        )
    if task == "translate" and (
        model_name.endswith(".en") or "turbo" in model_name.lower()
    ):
        raise ValidationError(
            f"Model '{model_name}' does not support translation. Choose a "
            "multilingual non-Turbo Whisper model."
        )

    if language is not None:
        language = normalise_language_code(language)
    if language is not None and language not in spec.languages:
        raise ValidationError(
            f"Source language '{language}' is not supported by {backend.value}."
        )
    if model_name.endswith(".en"):
        if language not in (None, "en"):
            raise ValidationError(
                f"Model '{model_name}' is English-only; use --lang en or choose a "
                "multilingual model."
            )
        return "en"
    return language


def validate_result_language(backend: ASRBackend, language: str) -> str:
    try:
        normalised = normalise_language_code(language)
    except ValidationError as exc:
        raise TranscriptionError(
            f"{backend.value} returned an invalid source language; specify "
            "--lang CODE and retry."
        ) from exc
    if normalised not in ASR_SPECS[backend].languages:
        raise TranscriptionError(
            f"{backend.value} detected unsupported source language '{normalised}'; "
            "specify a supported --lang CODE and retry."
        )
    return normalised


def qwen_language_name(code: str) -> str:
    return QWEN_LANGUAGE_NAMES[code]


def qwen_language_code(name: str) -> str:
    normalised = name.strip().casefold()
    for code, candidate in QWEN_LANGUAGE_NAMES.items():
        if candidate.casefold() == normalised or code == normalised:
            return code
    raise TranscriptionError(
        f"qwen returned unsupported source language '{name}'; specify a "
        "supported --lang CODE and retry."
    )
