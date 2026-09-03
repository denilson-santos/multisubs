"""Immutable built-in subtitle presentation templates."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from .config import validate_subtitle_config
from .errors import ValidationError
from .models import SubtitleConfig

DEFAULT_SUBTITLE_TEMPLATE = "default"


@dataclass(frozen=True)
class SubtitleTemplate:
    """One named semantic configuration baseline."""

    name: str
    description: str
    config: SubtitleConfig


def _template(
    name: str,
    description: str,
    *,
    appearance: dict[str, object] | None = None,
    relative: dict[str, str] | None = None,
    position: str | None = None,
    effects: dict[str, object] | None = None,
) -> SubtitleTemplate:
    return SubtitleTemplate(
        name=name,
        description=description,
        config=validate_subtitle_config(
            None,
            appearance_values=appearance,
            relative_values=relative,
            position=position,
            effects_values=effects,
        ),
    )


SUBTITLE_TEMPLATES = (
    _template(
        "default",
        "Current general-purpose white captions on a translucent black box.",
    ),
    _template(
        "clean-outline",
        "Neutral modern captions for interviews, courses, and demonstrations.",
        appearance={
            "font": "Inter",
            "font_weight": "medium",
            "backdrop": "outline",
            "backdrop_color": "#000000CC",
        },
        relative={
            "font_size": "4%",
            "outline_weight": "5%",
            "shadow_weight": "0px",
            "margin_left": "14%",
            "margin_right": "14%",
            "margin_bottom": "3%",
            "max_width": "100%",
            "max_height": "14%",
        },
        position="bottom-center",
    ),
    _template(
        "social-bold",
        "Large energetic uppercase captions for short-form video.",
        appearance={
            "font": "Montserrat",
            "font_weight": "extra-bold",
            "text_case": "uppercase",
            "backdrop": "outline",
            "backdrop_color": "#000000E6",
        },
        relative={
            "font_size": "5%",
            "outline_weight": "8%",
            "shadow_weight": "3%",
            "margin_left": "8%",
            "margin_right": "8%",
            "margin_bottom": "3%",
            "max_width": "100%",
            "max_height": "22%",
        },
        position="bottom-center",
    ),
    _template(
        "classic-yellow",
        "Familiar yellow captions with a strong dark edge.",
        appearance={
            "font": "Roboto",
            "font_weight": "bold",
            "text_color": "#FFD54F",
            "backdrop": "outline",
            "backdrop_color": "#000000E6",
        },
        relative={
            "font_size": "4.2%",
            "outline_weight": "6%",
            "shadow_weight": "3%",
            "margin_left": "12%",
            "margin_right": "12%",
            "margin_bottom": "3%",
            "max_width": "100%",
            "max_height": "16%",
        },
        position="bottom-center",
    ),
    _template(
        "newsroom",
        "Compact left-aligned treatment for reports and factual updates.",
        appearance={
            "font": "Oswald",
            "font_weight": "semi-bold",
            "text_case": "uppercase",
            "backdrop": "box",
            "backdrop_color": "#0B1F3ACC",
        },
        relative={
            "font_size": "4.2%",
            "letter_spacing": "1%",
            "outline_weight": "8%",
            "shadow_weight": "0px",
            "margin_left": "5%",
            "margin_right": "35%",
            "margin_bottom": "3%",
            "max_width": "100%",
            "max_height": "16%",
        },
        position="bottom-left",
    ),
    _template(
        "editorial",
        "Quiet serif styling for documentary and cultural material.",
        appearance={
            "font": "Lora",
            "font_weight": "semi-bold",
            "italic": True,
            "text_color": "#FFF8E7",
            "opacity": "95%",
            "backdrop": "outline",
            "backdrop_color": "#111111CC",
        },
        relative={
            "font_size": "4%",
            "outline_weight": "4%",
            "shadow_weight": "3%",
            "margin_left": "16%",
            "margin_right": "16%",
            "margin_bottom": "3%",
            "max_width": "100%",
            "max_height": "15%",
        },
        position="bottom-center",
    ),
    _template(
        "high-contrast",
        "Strong letter differentiation on an opaque yellow contrast surface.",
        appearance={
            "font": "Atkinson Hyperlegible Next",
            "font_weight": "bold",
            "text_color": "#000000",
            "backdrop": "box",
            "backdrop_color": "#FFD600FF",
        },
        relative={
            "font_size": "4.3%",
            "outline_weight": "10%",
            "shadow_weight": "0px",
            "margin_left": "10%",
            "margin_right": "10%",
            "margin_bottom": "3%",
            "max_width": "100%",
            "max_height": "18%",
        },
        position="bottom-center",
    ),
    _template(
        "neon-karaoke",
        "High-energy captions with progressive word highlighting.",
        appearance={
            "font": "Montserrat",
            "font_weight": "bold",
            "backdrop": "outline",
            "backdrop_color": "#080012E6",
        },
        relative={
            "font_size": "5%",
            "outline_weight": "7%",
            "shadow_weight": "5%",
            "margin_left": "8%",
            "margin_right": "8%",
            "margin_bottom": "3%",
            "max_width": "100%",
            "max_height": "20%",
        },
        position="bottom-center",
        effects={
            "karaoke": True,
            "karaoke_mode": "progressive",
            "highlight_color": "#00F5D4",
        },
    ),
)

TEMPLATE_CHOICES = tuple(template.name for template in SUBTITLE_TEMPLATES)
_TEMPLATE_BY_NAME = MappingProxyType(
    {template.name: template for template in SUBTITLE_TEMPLATES}
)


def get_subtitle_template(name: str | None) -> SubtitleTemplate:
    """Return a stable built-in template, resolving omission to ``default``."""
    resolved_name = DEFAULT_SUBTITLE_TEMPLATE if name is None else name
    try:
        return _TEMPLATE_BY_NAME[resolved_name]
    except KeyError as exc:
        raise ValidationError(
            "subtitle-template must be one of: " + ", ".join(TEMPLATE_CHOICES)
        ) from exc
