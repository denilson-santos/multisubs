"""Font-aware subtitle text measurement with a deterministic fallback."""

from __future__ import annotations

import shutil
import subprocess
import unicodedata
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import SubtitleAppearance

_FONT_SUFFIXES = frozenset({".otf", ".ttc", ".ttf"})
_FONT_COLLECTION_LIMIT = 32
_MEASUREMENT_CACHE_LIMIT = 4096
_FONTCONFIG_FIELD_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class TextMeasurementInfo:
    """Portable details about the strategy used to measure subtitle text."""

    mode: str
    requested_font: str
    resolved_font: str | None
    resolved_style: str | None
    font_source: str
    shaping: str | None
    metric_size: int | None

    def as_json(self) -> dict[str, str | int | None]:
        """Return metadata without exposing a machine-specific font path."""
        return {
            "mode": self.mode,
            "requested_font": self.requested_font,
            "resolved_font": self.resolved_font,
            "resolved_style": self.resolved_style,
            "font_source": self.font_source,
            "shaping": self.shaping,
            "metric_size": self.metric_size,
        }


class TextMeasurer:
    """Measure text in PlayRes pixels and cache values for one pipeline run."""

    def __init__(
        self,
        info: TextMeasurementInfo,
        measure: Callable[[str], float],
        *,
        line_height: float | None = None,
    ) -> None:
        self.info = info
        self._measure = measure
        self.line_height = max(
            1.0,
            float(line_height if line_height is not None else info.metric_size or 1),
        )
        self._cache: OrderedDict[str, float] = OrderedDict()

    def measure(self, text: str) -> float:
        """Return the measured advance width for one line of text."""
        cached = self._cache.get(text)
        if cached is not None:
            self._cache.move_to_end(text)
            return cached
        width = max(0.0, float(self._measure(text)))
        self._cache[text] = width
        if len(self._cache) > _MEASUREMENT_CACHE_LIMIT:
            self._cache.popitem(last=False)
        return width

    @property
    def diagnostic(self) -> str | None:
        """Describe a fallback or substitution once without leaking a path."""
        if self.info.mode == "unicode-estimate":
            return (
                f"Font '{self.info.requested_font}' could not be resolved for "
                "measurement; adaptive wrapping is using Unicode width estimates."
            )
        resolved = self.info.resolved_font
        if resolved and _normalise_font_name(resolved) != _normalise_font_name(
            self.info.requested_font
        ):
            return (
                f"Font '{self.info.requested_font}' resolved to '{resolved}' for "
                "subtitle width measurement."
            )
        return None


@dataclass(frozen=True)
class _ResolvedFace:
    font: Any
    family: str
    style: str
    source: str
    shaping: str
    metric_size: int
    line_height: float


def build_text_measurer(
    appearance: SubtitleAppearance,
    *,
    language: str | None = None,
) -> TextMeasurer:
    """Build a font-aware measurer or the explicit Unicode fallback."""
    font_size = appearance.font_size
    if isinstance(font_size, bool) or not isinstance(font_size, int):
        raise ValueError("font size must be resolved before text measurement")

    pillow = _load_pillow()
    if pillow is not None:
        image_font, features = pillow
        resolved = _resolve_face(
            image_font,
            features,
            appearance,
            font_size,
        )
        if resolved is not None:
            direction = _text_direction

            def measure(text: str) -> float:
                if resolved.shaping == "raqm":
                    return float(
                        resolved.font.getlength(
                            text,
                            direction=direction(text),
                            language=language or None,
                        )
                    )
                return float(resolved.font.getlength(text))

            return TextMeasurer(
                TextMeasurementInfo(
                    mode="font-metrics",
                    requested_font=appearance.font,
                    resolved_font=resolved.family,
                    resolved_style=resolved.style,
                    font_source=resolved.source,
                    shaping=resolved.shaping,
                    metric_size=resolved.metric_size,
                ),
                measure,
                line_height=resolved.line_height,
            )

    return build_unicode_text_measurer(
        appearance.font,
        font_size,
    )


def build_unicode_text_measurer(
    requested_font: str,
    font_size: int,
) -> TextMeasurer:
    """Build the deterministic fallback used when no concrete face is known."""
    return TextMeasurer(
        TextMeasurementInfo(
            mode="unicode-estimate",
            requested_font=requested_font,
            resolved_font=None,
            resolved_style=None,
            font_source="unresolved",
            shaping=None,
            metric_size=None,
        ),
        lambda text: estimate_unicode_text_width(text, font_size),
        line_height=font_size * 1.2,
    )


def estimate_unicode_text_width(text: str, font_size: int) -> float:
    """Estimate proportional glyph advances using Unicode-aware categories."""
    factors = (
        _estimated_cluster_factor(cluster) for cluster in _grapheme_clusters(text)
    )
    return sum(factors) * font_size


def _load_pillow() -> tuple[Any, Any] | None:
    try:
        from PIL import ImageFont, features
    except ImportError:
        return None
    return ImageFont, features


def _resolve_face(
    image_font: Any,
    features: Any,
    appearance: SubtitleAppearance,
    font_size: int,
) -> _ResolvedFace | None:
    if appearance.fonts_dir is not None:
        face = _resolve_face_from_directory(
            image_font,
            features,
            appearance.fonts_dir,
            appearance.font,
            font_size,
            bold=appearance.bold,
            italic=appearance.italic,
        )
        if face is not None:
            return face
    return _resolve_face_from_fontconfig(
        image_font,
        features,
        appearance.font,
        font_size,
        bold=appearance.bold,
        italic=appearance.italic,
    )


def _resolve_face_from_directory(
    image_font: Any,
    features: Any,
    fonts_dir: Path,
    family: str,
    font_size: int,
    *,
    bold: bool,
    italic: bool,
) -> _ResolvedFace | None:
    best: tuple[int, _ResolvedFace] | None = None
    for path in sorted(fonts_dir.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file() or path.suffix.casefold() not in _FONT_SUFFIXES:
            continue
        for index in range(_FONT_COLLECTION_LIMIT):
            loaded = _load_face(image_font, features, path, font_size, index=index)
            if loaded is None:
                break
            (
                loaded_font,
                loaded_family,
                loaded_style,
                shaping,
                metric_size,
                line_height,
            ) = loaded
            if _normalise_font_name(loaded_family) != _normalise_font_name(family):
                continue
            score = _style_distance(loaded_style, bold=bold, italic=italic)
            face = _ResolvedFace(
                font=loaded_font,
                family=loaded_family,
                style=loaded_style,
                source="fonts-dir",
                shaping=shaping,
                metric_size=metric_size,
                line_height=line_height,
            )
            if best is None or score < best[0]:
                best = (score, face)
            if score == 0:
                return face
    return best[1] if best is not None else None


def _resolve_face_from_fontconfig(
    image_font: Any,
    features: Any,
    family: str,
    font_size: int,
    *,
    bold: bool,
    italic: bool,
) -> _ResolvedFace | None:
    executable = shutil.which("fc-match")
    if executable is None:
        return None
    style = _requested_style(bold=bold, italic=italic)
    pattern = f"{family}:style={style}"
    try:
        completed = subprocess.run(
            [
                executable,
                f"--format=%{{family}}{_FONTCONFIG_FIELD_SEPARATOR}"
                f"%{{style}}{_FONTCONFIG_FIELD_SEPARATOR}%{{file}}"
                f"{_FONTCONFIG_FIELD_SEPARATOR}%{{index}}",
                pattern,
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    fields = completed.stdout.split(_FONTCONFIG_FIELD_SEPARATOR)
    if len(fields) != 4:
        return None
    resolved_family, resolved_style, raw_path, raw_index = (
        field.strip() for field in fields
    )
    path = Path(raw_path).expanduser().resolve(strict=False)
    if not resolved_family or not path.is_file():
        return None
    try:
        index = int(raw_index or "0")
    except ValueError:
        return None
    loaded = _load_face(image_font, features, path, font_size, index=index)
    if loaded is None:
        return None
    (
        loaded_font,
        loaded_family,
        loaded_style,
        shaping,
        metric_size,
        line_height,
    ) = loaded
    return _ResolvedFace(
        font=loaded_font,
        family=loaded_family or resolved_family.split(",", 1)[0],
        style=loaded_style or resolved_style.split(",", 1)[0],
        source="fontconfig",
        shaping=shaping,
        metric_size=metric_size,
        line_height=line_height,
    )


def _load_face(
    image_font: Any,
    features: Any,
    path: Path,
    font_size: int,
    *,
    index: int,
) -> tuple[Any, str, str, str, int, float] | None:
    shaping = "raqm" if features.check("raqm") else "basic"
    layout = image_font.Layout.RAQM if shaping == "raqm" else image_font.Layout.BASIC
    try:
        font = image_font.truetype(
            str(path),
            font_size,
            index=index,
            layout_engine=layout,
        )
        metric_size = _ass_metric_size(font, font_size)
        if metric_size != font_size:
            font = image_font.truetype(
                str(path),
                metric_size,
                index=index,
                layout_engine=layout,
            )
        family, style = font.getname()
        ascent, descent = font.getmetrics()
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    line_height = max(1.0, float(ascent + descent))
    return font, str(family), str(style), shaping, metric_size, line_height


def _ass_metric_size(font: Any, ass_font_size: int) -> int:
    """Approximate libass's FreeType real-dimension size request in Pillow."""
    try:
        ascent, descent = font.getmetrics()
    except (AttributeError, OSError, TypeError, ValueError):
        return ass_font_size
    metric_height = ascent + descent
    if metric_height <= 0:
        return ass_font_size
    scaled = ass_font_size * ass_font_size / metric_height
    return max(1, int(scaled + 0.5))


def _requested_style(*, bold: bool, italic: bool) -> str:
    if bold and italic:
        return "Bold Italic"
    if bold:
        return "Bold"
    if italic:
        return "Italic"
    return "Regular"


def _style_distance(style: str, *, bold: bool, italic: bool) -> int:
    normalised = style.casefold()
    actual_bold = any(
        marker in normalised for marker in ("bold", "black", "demi", "semibold")
    )
    actual_italic = "italic" in normalised or "oblique" in normalised
    return int(actual_bold != bold) + int(actual_italic != italic)


def _normalise_font_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _text_direction(text: str) -> str | None:
    for character in text:
        direction = unicodedata.bidirectional(character)
        if direction in {"R", "AL", "AN"}:
            return "rtl"
        if direction == "L":
            return "ltr"
    return None


def _estimated_cluster_factor(cluster: str) -> float:
    visible = [
        character
        for character in cluster
        if unicodedata.category(character) not in {"Mn", "Me", "Cf"}
    ]
    if not visible:
        return 0.0
    if any(_is_wide_character(character) for character in visible):
        return 1.0
    character = visible[0]
    if character.isspace():
        return 0.28
    if character in "ilI|!.,:;'`":
        return 0.28
    if character in "mwMW@%&":
        return 0.82
    category = unicodedata.category(character)
    if category == "Lu":
        return 0.62
    if category.startswith("N"):
        return 0.56
    if category.startswith(("P", "S")):
        return 0.4
    return 0.52


def _grapheme_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    current = ""
    for character in text:
        category = unicodedata.category(character)
        if current and (
            category in {"Mn", "Me", "Cf"}
            or character in {"\ufe0e", "\ufe0f"}
            or current.endswith("\u200d")
        ):
            current += character
            continue
        if current:
            clusters.append(current)
        current = character
    if current:
        clusters.append(current)
    return clusters


def _is_wide_character(character: str) -> bool:
    if unicodedata.east_asian_width(character) in {"W", "F"}:
        return True
    codepoint = ord(character)
    return 0x1F000 <= codepoint <= 0x1FAFF or 0x2600 <= codepoint <= 0x27BF
