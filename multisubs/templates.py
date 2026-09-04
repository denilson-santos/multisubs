"""Strict loader for immutable built-in subtitle presentation templates."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from importlib import resources
from types import MappingProxyType
from typing import Any

from .config import parse_relative_length, validate_subtitle_config
from .errors import TemplateError, ValidationError
from .models import SubtitleConfig

DEFAULT_SUBTITLE_TEMPLATE = "default"
_TEMPLATE_SCHEMA_VERSION = 1
_INDEX_RESOURCE = "index.json"
_RESOURCE_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.json$")


@dataclass(frozen=True)
class SubtitleTemplate:
    """One named semantic configuration baseline."""

    name: str
    description: str
    config: SubtitleConfig


class _DuplicateKeyError(ValueError):
    """Internal signal raised while decoding duplicate JSON object keys."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKeyError(f"duplicate key {key!r}")
        value[key] = item
    return value


def _read_json(resource: Any) -> dict[str, Any]:
    try:
        raw = resource.read_text(encoding="utf-8")
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, _DuplicateKeyError) as exc:
        raise TemplateError(
            f"Could not read packaged subtitle template resource '{resource.name}': "
            f"{exc}"
        ) from exc
    if type(value) is not dict:
        raise TemplateError(
            f"Packaged subtitle template resource '{resource.name}' must contain "
            "a JSON object"
        )
    return value


def _expect_keys(value: Mapping[str, Any], expected: set[str], *, context: str) -> None:
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise TemplateError(
            f"{context} is missing field(s): {', '.join(sorted(missing))}"
        )
    if unknown:
        raise TemplateError(
            f"{context} contains unknown field(s): {', '.join(sorted(unknown))}"
        )


def _expect_object(value: Any, *, context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise TemplateError(f"{context} must be a JSON object")
    return value


def _expect_string(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TemplateError(f"{context} must be a non-empty string")
    return value


def _expect_nullable_string(value: Any, *, context: str) -> str | None:
    if value is None:
        return None
    return _expect_string(value, context=context)


def _expect_boolean(value: Any, *, context: str) -> bool:
    if type(value) is not bool:
        raise TemplateError(f"{context} must be a boolean")
    return value


def _expect_schema_version(value: Any, *, context: str) -> None:
    if type(value) is not int or value != _TEMPLATE_SCHEMA_VERSION:
        raise TemplateError(
            f"{context} must use schema_version {_TEMPLATE_SCHEMA_VERSION}"
        )


def _load_template(resource: Any, expected_name: str) -> SubtitleTemplate:
    data = _read_json(resource)
    context = f"Template '{resource.name}'"
    _expect_keys(
        data,
        {"schema_version", "name", "description", "style", "layout", "animation"},
        context=context,
    )
    _expect_schema_version(data["schema_version"], context=context)
    name = _expect_string(data["name"], context=f"{context}.name")
    if name != expected_name:
        raise TemplateError(
            f"{context}.name must match its indexed filename stem '{expected_name}'"
        )
    description = _expect_string(data["description"], context=f"{context}.description")

    style = _expect_object(data["style"], context=f"{context}.style")
    _expect_keys(
        style,
        {"typography", "backdrop", "shadow", "opacity"},
        context=f"{context}.style",
    )
    typography = _expect_object(
        style["typography"], context=f"{context}.style.typography"
    )
    _expect_keys(
        typography,
        {
            "font_family",
            "font_weight",
            "font_size",
            "italic",
            "letter_spacing",
            "line_height",
            "text_case",
            "color",
            "highlight_color",
        },
        context=f"{context}.style.typography",
    )
    for field in (
        "font_family",
        "font_weight",
        "font_size",
        "letter_spacing",
        "line_height",
        "text_case",
        "color",
    ):
        _expect_string(typography[field], context=f"{context}.style.typography.{field}")
    italic = _expect_boolean(
        typography["italic"], context=f"{context}.style.typography.italic"
    )
    highlight_color = _expect_nullable_string(
        typography["highlight_color"],
        context=f"{context}.style.typography.highlight_color",
    )

    backdrop = _expect_object(style["backdrop"], context=f"{context}.style.backdrop")
    _expect_keys(
        backdrop, {"type", "color", "size"}, context=f"{context}.style.backdrop"
    )
    for field in ("type", "color", "size"):
        _expect_string(backdrop[field], context=f"{context}.style.backdrop.{field}")

    shadow = _expect_object(style["shadow"], context=f"{context}.style.shadow")
    _expect_keys(shadow, {"size"}, context=f"{context}.style.shadow")
    _expect_string(shadow["size"], context=f"{context}.style.shadow.size")
    _expect_string(style["opacity"], context=f"{context}.style.opacity")

    layout = _expect_object(data["layout"], context=f"{context}.layout")
    _expect_keys(
        layout,
        {"position", "margins", "max_width", "max_height"},
        context=f"{context}.layout",
    )
    _expect_string(layout["position"], context=f"{context}.layout.position")
    margins = _expect_object(layout["margins"], context=f"{context}.layout.margins")
    _expect_keys(
        margins,
        {"left", "right", "top", "bottom"},
        context=f"{context}.layout.margins",
    )
    for field in ("left", "right", "top", "bottom"):
        _expect_string(margins[field], context=f"{context}.layout.margins.{field}")
    _expect_string(layout["max_width"], context=f"{context}.layout.max_width")
    _expect_string(layout["max_height"], context=f"{context}.layout.max_height")

    animation = _expect_object(data["animation"], context=f"{context}.animation")
    _expect_keys(animation, {"cue", "word"}, context=f"{context}.animation")
    cue = _expect_object(animation["cue"], context=f"{context}.animation.cue")
    _expect_keys(cue, {"entrance", "exit"}, context=f"{context}.animation.cue")
    for phase_name in ("entrance", "exit"):
        phase = _expect_object(
            cue[phase_name], context=f"{context}.animation.cue.{phase_name}"
        )
        _expect_keys(phase, {"type"}, context=f"{context}.animation.cue.{phase_name}")
        phase_type = _expect_string(
            phase["type"], context=f"{context}.animation.cue.{phase_name}.type"
        )
        if phase_type != "none":
            raise TemplateError(
                f"{context}.animation.cue.{phase_name}.type must be none in "
                f"schema version {_TEMPLATE_SCHEMA_VERSION}"
            )

    word = _expect_object(animation["word"], context=f"{context}.animation.word")
    _expect_keys(word, {"type", "mode"}, context=f"{context}.animation.word")
    word_type = _expect_string(word["type"], context=f"{context}.animation.word.type")
    word_mode = _expect_nullable_string(
        word["mode"], context=f"{context}.animation.word.mode"
    )
    if word_type not in {"none", "karaoke"}:
        raise TemplateError(f"{context}.animation.word.type must be none or karaoke")
    if word_type == "none" and word_mode is not None:
        raise TemplateError(f"{context}.animation.word.mode must be null for type none")
    if word_type == "karaoke" and word_mode is None:
        raise TemplateError(f"{context}.animation.word.mode is required for karaoke")
    if word_type == "none" and highlight_color is not None:
        raise TemplateError(
            f"{context}.style.typography.highlight_color must be null when word "
            "animation is none"
        )
    if word_type == "karaoke" and highlight_color is None:
        raise TemplateError(
            f"{context}.style.typography.highlight_color is required for karaoke"
        )

    appearance_values: dict[str, object] = {
        "font": typography["font_family"],
        "font_weight": typography["font_weight"],
        "italic": italic,
        "text_color": typography["color"],
        "text_case": typography["text_case"],
        "backdrop": backdrop["type"],
        "backdrop_color": backdrop["color"],
        "opacity": style["opacity"],
    }
    if name == DEFAULT_SUBTITLE_TEMPLATE and typography["font_weight"] == "regular":
        appearance_values.pop("font_weight")
    effects_values: dict[str, object] = {"karaoke": word_type == "karaoke"}
    if word_type == "karaoke":
        effects_values.update(
            karaoke_mode=word_mode,
            highlight_color=highlight_color,
        )
    relative_values = {
        "font_size": typography["font_size"],
        "letter_spacing": typography["letter_spacing"],
        "line_height": typography["line_height"],
        "outline_weight": backdrop["size"],
        "shadow_weight": shadow["size"],
        "margin_left": margins["left"],
        "margin_right": margins["right"],
        "margin_top": margins["top"],
        "margin_bottom": margins["bottom"],
        "max_width": layout["max_width"],
        "max_height": layout["max_height"],
    }
    position = str(layout["position"])
    if position.startswith("top-"):
        relative_values.pop("margin_bottom")
    elif position.startswith("bottom-"):
        relative_values.pop("margin_top")
    else:
        relative_values.pop("margin_top")
        relative_values.pop("margin_bottom")
    try:
        parsed_margins = {
            name: parse_relative_length(str(raw_value))
            for name, raw_value in margins.items()
        }
        config = validate_subtitle_config(
            None,
            appearance_values=appearance_values,
            position=position,
            relative_values=relative_values,
            effects_values=effects_values,
        )
        config = replace(
            config,
            layout=replace(
                config.layout,
                margin_left=parsed_margins["left"],
                margin_right=parsed_margins["right"],
                margin_top=parsed_margins["top"],
                margin_bottom=parsed_margins["bottom"],
            ),
        )
        config = validate_subtitle_config(config)
    except ValidationError as exc:
        raise TemplateError(f"{context} is semantically invalid: {exc}") from exc
    return SubtitleTemplate(name=name, description=description, config=config)


def _load_template_catalog(root: Any = None) -> tuple[SubtitleTemplate, ...]:
    if root is None:
        root = resources.files("multisubs").joinpath("assets").joinpath("templates")
    index = _read_json(root.joinpath(_INDEX_RESOURCE))
    _expect_keys(index, {"schema_version", "templates"}, context="Template index")
    _expect_schema_version(index["schema_version"], context="Template index")
    filenames = index["templates"]
    if type(filenames) is not list:
        raise TemplateError("Template index.templates must be a JSON array")
    if not filenames:
        raise TemplateError("Template index.templates must not be empty")
    checked_filenames: list[str] = []
    for position, filename in enumerate(filenames):
        if not isinstance(filename, str) or not _RESOURCE_NAME_PATTERN.fullmatch(
            filename
        ):
            raise TemplateError(
                f"Template index.templates[{position}] must be a safe kebab-case "
                "JSON filename"
            )
        if filename == _INDEX_RESOURCE:
            raise TemplateError("Template index cannot list itself")
        if filename in checked_filenames:
            raise TemplateError(f"Template index contains duplicate file '{filename}'")
        checked_filenames.append(filename)

    try:
        discovered = {
            item.name
            for item in root.iterdir()
            if item.is_file()
            and item.name.endswith(".json")
            and item.name != _INDEX_RESOURCE
        }
    except OSError as exc:
        raise TemplateError("Could not enumerate packaged subtitle templates") from exc
    indexed = set(checked_filenames)
    if discovered != indexed:
        missing = indexed - discovered
        unindexed = discovered - indexed
        details: list[str] = []
        if missing:
            details.append("missing: " + ", ".join(sorted(missing)))
        if unindexed:
            details.append("unindexed: " + ", ".join(sorted(unindexed)))
        raise TemplateError(
            "Template index does not match packaged resources ("
            + "; ".join(details)
            + ")"
        )

    templates = tuple(
        _load_template(root.joinpath(filename), filename.removesuffix(".json"))
        for filename in checked_filenames
    )
    names = tuple(template.name for template in templates)
    if len(names) != len(set(names)):
        raise TemplateError("Packaged subtitle templates contain duplicate names")
    if DEFAULT_SUBTITLE_TEMPLATE not in names:
        raise TemplateError("Template catalog must contain the default template")
    return templates


_CATALOG_ERROR: TemplateError | None = None
try:
    SUBTITLE_TEMPLATES = _load_template_catalog()
except TemplateError as exc:
    SUBTITLE_TEMPLATES = ()
    _CATALOG_ERROR = exc

TEMPLATE_CHOICES = tuple(template.name for template in SUBTITLE_TEMPLATES)
_TEMPLATE_BY_NAME = MappingProxyType(
    {template.name: template for template in SUBTITLE_TEMPLATES}
)


def require_template_catalog() -> None:
    """Raise the stored package-resource diagnostic when catalog loading failed."""
    if _CATALOG_ERROR is not None:
        raise _CATALOG_ERROR


def get_subtitle_template(name: str | None) -> SubtitleTemplate:
    """Return a stable built-in template, resolving omission to ``default``."""
    require_template_catalog()
    resolved_name = DEFAULT_SUBTITLE_TEMPLATE if name is None else name
    try:
        return _TEMPLATE_BY_NAME[resolved_name]
    except KeyError as exc:
        raise ValidationError(
            "subtitle-template must be one of: " + ", ".join(TEMPLATE_CHOICES)
        ) from exc
