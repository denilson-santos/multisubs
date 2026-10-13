"""Public composition of subtitle templates and sparse presentation overrides."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

from .config import apply_subtitle_feature_disables, validate_subtitle_config
from .custom_templates import ResolvedSubtitleTemplate, resolve_subtitle_template
from .errors import ValidationError
from .models import RelativeLength, SubtitleConfig, SubtitlePosition

_APPEARANCE_FIELDS = (
    "font",
    "text_color",
    "font_weight",
    "bold",
    "italic",
    "backdrop",
    "backdrop_color",
    "word_backdrop",
    "word_backdrop_color",
    "opacity",
    "text_case",
    "fonts_dir",
)
_RELATIVE_FIELDS = {
    "font_size": "font_size",
    "letter_spacing": "letter_spacing",
    "line_height": "line_height",
    "backdrop_size": "outline_weight",
    "word_backdrop_size": "word_backdrop_size",
    "shadow_size": "shadow_weight",
    "margin_left": "margin_left",
    "margin_right": "margin_right",
    "margin_top": "margin_top",
    "margin_bottom": "margin_bottom",
    "max_width": "max_width",
    "max_height": "max_height",
    "position_x": "position_x",
    "position_y": "position_y",
}
_ANIMATION_FIELDS = (
    *(
        f"animation_{scope}_{element}_{phase}{suffix}"
        for scope in ("cue", "word")
        for element in ("text", "backdrop")
        for phase in ("entrance", "emphasis", "exit")
        for suffix in ("", "_duration")
    ),
    "animation_word_text_mode",
    "animation_word_backdrop_mode",
    "animation_word_text_highlight_color",
)
_DISABLE_FIELDS = ("disable_cue_animations", "disable_word_animations")
_SUBTITLE_OVERRIDE_NAMES = (
    *_APPEARANCE_FIELDS,
    *_RELATIVE_FIELDS,
    *_ANIMATION_FIELDS,
    *_DISABLE_FIELDS,
    "position",
    "anchor",
)


def build_subtitle_config(
    *,
    template: str | None = None,
    template_dir: str | Path | None = None,
    overrides: Mapping[str, object] | None = None,
) -> SubtitleConfig:
    """Compose an immutable semantic configuration using native CLI rules.

    Select a built-in or custom template (default: ``default``). Override keys
    are presentation option names with underscores, without leading ``--``;
    for example ``font_size``, ``backdrop_size``, and
    ``animation_word_text_emphasis``. Values use the same units, choices, and
    booleans as the CLI; ``fonts_dir`` accepts a string or Path.

    Missing keys and ``None`` inherit the template. Explicit ``False`` and
    permitted zero lengths/opacity are preserved. Scoped animation disables
    apply after validating overrides, with the same precedence as the CLI.
    Neither the caller's mapping nor template baselines are modified.

    Raise public ValidationError for unknown keys or invalid values/combinations,
    and TemplateError for invalid custom directories/files or packaged templates.
    No media, models, font faces, network, or asset materialization is involved.
    Relative lengths remain unresolved until rendering against final geometry.
    """
    _, config = _resolve_subtitle_config(
        template=template, template_dir=template_dir, overrides=overrides
    )
    return config


def _resolve_subtitle_config(
    *,
    template: str | None,
    template_dir: str | Path | None,
    overrides: Mapping[str, object] | None,
) -> tuple[ResolvedSubtitleTemplate, SubtitleConfig]:
    """Share composition with the CLI while retaining its template provenance."""
    if template is not None and not isinstance(template, str):
        raise ValidationError("subtitle-template must be a template name")
    if template_dir is not None and not isinstance(template_dir, (str, Path)):
        raise ValidationError("template-dir must be a directory path")
    if overrides is not None and not isinstance(overrides, Mapping):
        raise ValidationError("subtitle overrides must be a mapping of option names")
    values = dict(overrides) if overrides is not None else {}
    if any(not isinstance(key, str) for key in values):
        raise ValidationError("subtitle override names must be strings")
    unknown = set(values).difference(_SUBTITLE_OVERRIDE_NAMES)
    if unknown:
        raise ValidationError(
            "Unknown subtitle override(s): " + ", ".join(sorted(unknown))
        )
    values = {key: value for key, value in values.items() if value is not None}
    disables = {}
    for key in _DISABLE_FIELDS:
        value = values.get(key, False)
        if not isinstance(value, bool):
            raise ValidationError(
                f"{key.replace('_', '-')} must be enabled or disabled"
            )
        disables[key] = value

    selection = resolve_subtitle_template(template, template_dir)
    config = validate_subtitle_config(
        None,
        defaults=selection.template.config,
        appearance_values={
            key: values[key] for key in _APPEARANCE_FIELDS if key in values
        },
        relative_values={
            field: cast(RelativeLength | str, values[key])
            for key, field in _RELATIVE_FIELDS.items()
            if key in values
        },
        animation_values={
            key.removeprefix("animation_"): values[key]
            for key in _ANIMATION_FIELDS
            if key in values
        },
        position=cast(SubtitlePosition | str | None, values.get("position")),
        anchor=cast(SubtitlePosition | str | None, values.get("anchor")),
    )
    return selection, apply_subtitle_feature_disables(config, **disables)
