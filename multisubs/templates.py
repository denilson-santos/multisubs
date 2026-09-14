"""Strict loader for immutable built-in subtitle presentation templates."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from importlib import resources
from types import MappingProxyType
from typing import Any, cast

from .config import parse_relative_length, validate_subtitle_config
from .errors import TemplateError, ValidationError
from .models import (
    CueAnimationType,
    SubtitleAnimationPhase,
    SubtitleConfig,
    SubtitleElementAnimation,
    SubtitleWordElementAnimation,
    WordAnimationMode,
)

DEFAULT_SUBTITLE_TEMPLATE = "default"
_TEMPLATE_SCHEMA_VERSION = 5
_LEGACY_TEMPLATE_SCHEMA_VERSION = 4
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


def _expect_schema_version(
    value: Any, *, context: str, expected: int = _TEMPLATE_SCHEMA_VERSION
) -> None:
    if type(value) is not int or value != expected:
        raise TemplateError(f"{context} must use schema_version {expected}")


def _load_complete_template(
    resource: Any,
    expected_name: str,
    *,
    schema_version: int,
    data: dict[str, Any] | None = None,
) -> SubtitleTemplate:
    if data is None:
        data = _read_json(resource)
    context = f"Template '{resource.name}'"
    _expect_keys(
        data,
        {"schema_version", "name", "description", "style", "layout", "animation"},
        context=context,
    )
    _expect_schema_version(
        data["schema_version"], context=context, expected=schema_version
    )
    name = _expect_string(data["name"], context=f"{context}.name")
    if name != expected_name:
        raise TemplateError(
            f"{context}.name must match its indexed filename stem '{expected_name}'"
        )
    description = _expect_string(data["description"], context=f"{context}.description")

    appearance_values, style_relative_values, highlight_color = _read_complete_style(
        data["style"], context=context, name=expected_name
    )

    position, margins, layout_values = _read_complete_layout(
        data["layout"], context=context
    )
    animation_values = _read_complete_animation(data["animation"], context=context)

    word_text_highlighted = (
        animation_values["word_text_emphasis"] == CueAnimationType.HIGHLIGHT.value
    )
    if not word_text_highlighted and highlight_color is not None:
        raise TemplateError(
            f"{context}.style.typography.highlight_color must be null when word "
            "text emphasis is not highlight"
        )
    if word_text_highlighted and highlight_color is None:
        raise TemplateError(
            f"{context}.style.typography.highlight_color is required for highlight"
        )

    if word_text_highlighted:
        animation_values["word_text_highlight_color"] = highlight_color
    relative_values = {
        **style_relative_values,
        **layout_values,
    }
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
            animation_values=animation_values,
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


def _read_complete_style(
    value: Any,
    *,
    context: str,
    name: str,
) -> tuple[dict[str, object], dict[str, str], str | None]:
    """Validate a complete template style and map it to config overrides."""
    style = _expect_object(value, context=f"{context}.style")
    _expect_keys(
        style,
        {"typography", "backdrop", "word_backdrop", "shadow", "opacity"},
        context=f"{context}.style",
    )
    typography = _expect_object(
        style["typography"], context=f"{context}.style.typography"
    )
    typography_context = f"{context}.style.typography"
    typography_fields = (
        "font_family",
        "font_weight",
        "font_size",
        "letter_spacing",
        "line_height",
        "text_case",
        "color",
    )
    _expect_keys(
        typography,
        {*typography_fields, "italic", "highlight_color"},
        context=typography_context,
    )
    text_values = {
        field: _expect_string(
            typography[field], context=f"{typography_context}.{field}"
        )
        for field in typography_fields
    }
    italic = _expect_boolean(
        typography["italic"], context=f"{typography_context}.italic"
    )
    highlight_color = _expect_nullable_string(
        typography["highlight_color"],
        context=f"{typography_context}.highlight_color",
    )
    backdrop = _read_complete_backdrop(
        style["backdrop"], context=f"{context}.style.backdrop"
    )
    word_backdrop = _read_complete_backdrop(
        style["word_backdrop"], context=f"{context}.style.word_backdrop"
    )
    shadow = _expect_object(style["shadow"], context=f"{context}.style.shadow")
    _expect_keys(shadow, {"size"}, context=f"{context}.style.shadow")
    shadow_size = _expect_string(shadow["size"], context=f"{context}.style.shadow.size")
    opacity = _expect_string(style["opacity"], context=f"{context}.style.opacity")

    appearance_values: dict[str, object] = {
        "font": text_values["font_family"],
        "font_weight": text_values["font_weight"],
        "italic": italic,
        "text_color": text_values["color"],
        "text_case": text_values["text_case"],
        "backdrop": backdrop["type"],
        "backdrop_color": backdrop["color"],
        "word_backdrop": word_backdrop["type"],
        "word_backdrop_color": word_backdrop["color"],
        "opacity": opacity,
    }
    if name == DEFAULT_SUBTITLE_TEMPLATE and text_values["font_weight"] == "regular":
        appearance_values.pop("font_weight")
    relative_values = {
        "font_size": text_values["font_size"],
        "letter_spacing": text_values["letter_spacing"],
        "line_height": text_values["line_height"],
        "outline_weight": backdrop["size"],
        "word_backdrop_size": word_backdrop["size"],
        "shadow_weight": shadow_size,
    }
    return appearance_values, relative_values, highlight_color


def _read_complete_layout(
    value: Any,
    *,
    context: str,
) -> tuple[str, dict[str, str], dict[str, str]]:
    """Validate layout data and translate its keys to configuration names."""
    layout = _expect_object(value, context=f"{context}.layout")
    layout_context = f"{context}.layout"
    _expect_keys(
        layout,
        {"position", "margins", "max_width", "max_height"},
        context=layout_context,
    )
    position = _expect_string(layout["position"], context=f"{layout_context}.position")
    margins = _expect_object(layout["margins"], context=f"{layout_context}.margins")
    _expect_keys(
        margins,
        {"left", "right", "top", "bottom"},
        context=f"{layout_context}.margins",
    )
    parsed_margins = {
        field: _expect_string(
            margins[field], context=f"{layout_context}.margins.{field}"
        )
        for field in ("left", "right", "top", "bottom")
    }
    width = _expect_string(layout["max_width"], context=f"{layout_context}.max_width")
    height = _expect_string(
        layout["max_height"], context=f"{layout_context}.max_height"
    )
    layout_values = {
        f"margin_{field}": margin for field, margin in parsed_margins.items()
    }
    layout_values.update(max_width=width, max_height=height)
    return position, parsed_margins, layout_values


def _read_complete_animation(
    value: Any,
    *,
    context: str,
) -> dict[str, object]:
    """Validate complete cue and word animation tracks."""
    animation = _expect_object(value, context=f"{context}.animation")
    _expect_keys(animation, {"cue", "word"}, context=f"{context}.animation")
    groups = {
        scope: _expect_object(animation[scope], context=f"{context}.animation.{scope}")
        for scope in ("cue", "word")
    }
    for scope, group in groups.items():
        _expect_keys(
            group,
            {"text", "backdrop"},
            context=f"{context}.animation.{scope}",
        )

    values: dict[str, object] = {}
    for scope, group in groups.items():
        for element in ("text", "backdrop"):
            track_context = f"{context}.animation.{scope}.{element}"
            track = _expect_object(group[element], context=track_context)
            expected_fields = {"entrance", "emphasis", "exit"}
            if scope == "word":
                expected_fields.add("mode")
            _expect_keys(track, expected_fields, context=track_context)
            prefix = f"{scope}_{element}"
            for phase_name in ("entrance", "emphasis", "exit"):
                phase_type, duration_ms = _load_animation_phase(
                    track[phase_name],
                    context=f"{track_context}.{phase_name}",
                )
                values[f"{prefix}_{phase_name}"] = phase_type
                if duration_ms is not None:
                    values[f"{prefix}_{phase_name}_duration"] = f"{duration_ms}ms"
            if scope == "word":
                mode_name = _expect_string(
                    track["mode"], context=f"{track_context}.mode"
                )
                try:
                    values[f"{prefix}_mode"] = WordAnimationMode(mode_name)
                except ValueError as exc:
                    raise TemplateError(
                        f"{track_context}.mode is not supported"
                    ) from exc
    return values


def _read_complete_backdrop(value: Any, *, context: str) -> dict[str, str]:
    backdrop = _expect_object(value, context=context)
    fields = ("type", "color", "size")
    _expect_keys(backdrop, set(fields), context=context)
    return {
        field: _expect_string(backdrop[field], context=f"{context}.{field}")
        for field in fields
    }


def _expect_allowed_keys(
    value: Mapping[str, Any], allowed: set[str], *, context: str
) -> None:
    unknown = set(value).difference(allowed)
    if unknown:
        raise TemplateError(
            f"{context} contains unknown field(s): {', '.join(sorted(unknown))}"
        )


def _relative_text(value: object) -> str:
    """Return the source token for one validated relative length."""
    return getattr(value, "original", str(value))


def _template_data_from_config(
    config: SubtitleConfig,
    *,
    name: str,
    description: str,
) -> dict[str, Any]:
    """Serialize a complete semantic configuration to the internal schema."""
    typography = config.style.typography

    def phase_data(phase: SubtitleAnimationPhase) -> dict[str, Any]:
        value: dict[str, Any] = {"type": phase.type.value}
        if phase.duration_ms:
            value["duration_ms"] = phase.duration_ms
        return value

    def track_data(
        track: SubtitleElementAnimation, *, include_mode: bool = False
    ) -> dict[str, Any]:
        value: dict[str, Any] = {
            "entrance": phase_data(track.entrance),
            "emphasis": phase_data(track.emphasis),
            "exit": phase_data(track.exit),
        }
        if include_mode:
            word_track = cast(SubtitleWordElementAnimation, track)
            value["mode"] = word_track.mode.value
            value = {
                "mode": value.pop("mode"),
                **value,
            }
        return value

    return {
        "schema_version": _TEMPLATE_SCHEMA_VERSION,
        "name": name,
        "description": description,
        "style": {
            "typography": {
                "font_family": typography.font,
                "font_weight": typography.font_weight.canonical_name,
                "font_size": _relative_text(typography.font_size),
                "italic": typography.italic,
                "letter_spacing": _relative_text(typography.letter_spacing),
                "line_height": _relative_text(typography.line_height),
                "text_case": typography.text_case.value,
                "color": typography.color,
                "highlight_color": typography.highlight_color,
            },
            "backdrop": {
                "type": config.style.backdrop.kind.value,
                "color": config.style.backdrop.color,
                "size": _relative_text(config.style.backdrop.size),
            },
            "word_backdrop": {
                "type": config.style.word_backdrop.kind.value,
                "color": config.style.word_backdrop.color,
                "size": _relative_text(config.style.word_backdrop.size),
            },
            "shadow": {"size": _relative_text(config.style.shadow.size)},
            "opacity": config.style.opacity.original,
        },
        "layout": {
            "position": config.layout.position.value,
            "margins": {
                "left": _relative_text(config.layout.margin_left),
                "right": _relative_text(config.layout.margin_right),
                "top": _relative_text(config.layout.margin_top),
                "bottom": _relative_text(config.layout.margin_bottom),
            },
            "max_width": _relative_text(config.layout.max_width),
            "max_height": _relative_text(config.layout.max_height),
        },
        "animation": {
            "cue": {
                "text": track_data(config.animation.cue.text),
                "backdrop": track_data(config.animation.cue.backdrop),
            },
            "word": {
                "text": track_data(config.animation.word.text, include_mode=True),
                "backdrop": track_data(
                    config.animation.word.backdrop, include_mode=True
                ),
            },
        },
    }


def _default_template_data() -> dict[str, Any]:
    """Build the sparse-schema inheritance base from semantic config defaults."""
    return _template_data_from_config(
        validate_subtitle_config(None),
        name=DEFAULT_SUBTITLE_TEMPLATE,
        description="General-purpose subtitle presentation.",
    )


def _merge_sparse_object(
    base: Mapping[str, Any],
    value: Any,
    *,
    allowed: set[str],
    context: str,
) -> dict[str, Any]:
    override = _expect_object(value, context=context)
    _expect_allowed_keys(override, allowed, context=context)
    merged = deepcopy(dict(base))
    merged.update(override)
    return merged


def _merge_sparse_phase(
    base: Mapping[str, Any],
    value: Any,
    *,
    context: str,
    reset_duration_on_type_change: bool = False,
) -> dict[str, Any]:
    phase = _expect_object(value, context=context)
    _expect_allowed_keys(phase, {"type", "duration_ms"}, context=context)
    if "type" not in phase:
        raise TemplateError(f"{context} is missing field(s): type")
    merged = deepcopy(dict(base))
    merged.update(phase)
    if reset_duration_on_type_change and phase["type"] != base.get("type"):
        if "duration_ms" not in phase:
            merged.pop("duration_ms", None)
    if reset_duration_on_type_change and phase["type"] in {"none", "highlight"}:
        if "duration_ms" not in phase:
            merged.pop("duration_ms", None)
    return merged


def _expand_sparse_template_data(
    data: dict[str, Any],
    *,
    expected_name: str,
    base_data: Mapping[str, Any] | None = None,
    reset_animation_duration: bool = False,
) -> dict[str, Any]:
    """Expand schema-5 omissions while rejecting unknown authored fields."""
    context = "Template"
    _expect_allowed_keys(
        data,
        {"schema_version", "name", "description", "style", "layout", "animation"},
        context=context,
    )
    for field in ("schema_version", "name", "description"):
        if field not in data:
            raise TemplateError(f"{context} is missing field(s): {field}")
    _expect_schema_version(data["schema_version"], context=context)
    name = _expect_string(data["name"], context=f"{context}.name")
    if name != expected_name:
        raise TemplateError(
            f"{context}.name must match its indexed filename stem '{expected_name}'"
        )
    _expect_string(data["description"], context=f"{context}.description")

    expanded = (
        deepcopy(dict(base_data)) if base_data is not None else _default_template_data()
    )
    expanded["name"] = name
    expanded["description"] = data["description"]

    if "style" in data:
        expanded["style"] = _expand_sparse_style_data(expanded["style"], data["style"])

    if "layout" in data:
        expanded["layout"] = _expand_sparse_layout_data(
            expanded["layout"], data["layout"]
        )

    if "animation" in data:
        expanded["animation"] = _expand_sparse_animation_data(
            expanded["animation"],
            data["animation"],
            reset_animation_duration=reset_animation_duration,
        )
    return expanded


def _expand_sparse_style_data(base: Mapping[str, Any], value: Any) -> dict[str, Any]:
    style = _merge_sparse_object(
        base,
        value,
        allowed={"typography", "backdrop", "word_backdrop", "shadow", "opacity"},
        context="Template.style",
    )
    if "typography" in value:
        style["typography"] = _merge_sparse_object(
            base["typography"],
            value["typography"],
            allowed={
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
            context="Template.style.typography",
        )
    for element, allowed in (
        ("backdrop", {"type", "color", "size"}),
        ("word_backdrop", {"type", "color", "size"}),
        ("shadow", {"size"}),
    ):
        if element in value:
            style[element] = _merge_sparse_object(
                base[element],
                value[element],
                allowed=allowed,
                context=f"Template.style.{element}",
            )
    return style


def _expand_sparse_layout_data(base: Mapping[str, Any], value: Any) -> dict[str, Any]:
    layout = _merge_sparse_object(
        base,
        value,
        allowed={"position", "margins", "max_width", "max_height"},
        context="Template.layout",
    )
    if "margins" in value:
        layout["margins"] = _merge_sparse_object(
            base["margins"],
            value["margins"],
            allowed={"left", "right", "top", "bottom"},
            context="Template.layout.margins",
        )
    return layout


def _expand_sparse_animation_data(
    base: Mapping[str, Any],
    value: Any,
    *,
    reset_animation_duration: bool,
) -> dict[str, Any]:
    animation = _merge_sparse_object(
        base,
        value,
        allowed={"cue", "word"},
        context="Template.animation",
    )
    for scope in ("cue", "word"):
        if scope not in value:
            continue
        group = _merge_sparse_object(
            base[scope],
            value[scope],
            allowed={"text", "backdrop"},
            context=f"Template.animation.{scope}",
        )
        for element in ("text", "backdrop"):
            if element not in value[scope]:
                continue
            track_base = base[scope][element]
            track = _merge_sparse_object(
                track_base,
                value[scope][element],
                allowed=(
                    {"mode", "entrance", "emphasis", "exit"}
                    if scope == "word"
                    else {"entrance", "emphasis", "exit"}
                ),
                context=f"Template.animation.{scope}.{element}",
            )
            for phase_name in ("entrance", "emphasis", "exit"):
                if phase_name in value[scope][element]:
                    track[phase_name] = _merge_sparse_phase(
                        track_base[phase_name],
                        value[scope][element][phase_name],
                        context=f"Template.animation.{scope}.{element}.{phase_name}",
                        reset_duration_on_type_change=reset_animation_duration,
                    )
            group[element] = track
        animation[scope] = group
    return animation


def _load_sparse_template(
    resource: Any, expected_name: str, *, data: dict[str, Any] | None = None
) -> SubtitleTemplate:
    if data is None:
        data = _read_json(resource)
    expanded = _expand_sparse_template_data(data, expected_name=expected_name)
    return _load_complete_template(
        resource,
        expected_name,
        schema_version=_TEMPLATE_SCHEMA_VERSION,
        data=expanded,
    )


def _load_template(
    resource: Any, expected_name: str, *, schema_version: int | None = None
) -> SubtitleTemplate:
    """Load a legacy complete resource or a schema-5 sparse resource."""
    data = _read_json(resource)
    version = data.get("schema_version") if schema_version is None else schema_version
    if schema_version is not None:
        _expect_schema_version(
            data.get("schema_version"),
            context=f"Template '{resource.name}'",
            expected=schema_version,
        )
    if version == _TEMPLATE_SCHEMA_VERSION:
        return _load_sparse_template(resource, expected_name, data=data)
    if version == _LEGACY_TEMPLATE_SCHEMA_VERSION:
        return _load_complete_template(
            resource,
            expected_name,
            schema_version=_LEGACY_TEMPLATE_SCHEMA_VERSION,
            data=data,
        )
    _expect_schema_version(
        data.get("schema_version"), context=f"Template '{resource.name}'"
    )
    raise AssertionError("unreachable")


def _load_animation_phase(value: Any, *, context: str) -> tuple[str, int | None]:
    phase = _expect_object(value, context=context)
    phase_type_name = _expect_string(phase.get("type"), context=f"{context}.type")
    try:
        phase_type = CueAnimationType(phase_type_name)
    except ValueError as exc:
        raise TemplateError(f"{context}.type is not supported") from exc
    if phase_type is CueAnimationType.NONE:
        _expect_keys(phase, {"type"}, context=context)
        return phase_type.value, None
    if phase_type is CueAnimationType.HIGHLIGHT:
        _expect_keys(phase, {"type"}, context=context)
        return phase_type.value, None
    unknown = set(phase).difference({"type", "duration_ms"})
    if unknown:
        raise TemplateError(
            f"{context} contains unknown field(s): {', '.join(sorted(unknown))}"
        )
    duration_ms = phase.get("duration_ms")
    if duration_ms is not None and (
        type(duration_ms) is not int or duration_ms < 10 or duration_ms > 5000
    ):
        raise TemplateError(f"{context}.duration_ms must be from 10 through 5000")
    return phase_type.value, duration_ms


def _load_template_catalog(root: Any = None) -> tuple[SubtitleTemplate, ...]:
    if root is None:
        root = resources.files("multisubs").joinpath("assets").joinpath("templates")
    index_version, filenames = _read_template_index(root)
    _validate_template_inventory(root, filenames)

    templates = tuple(
        _load_template(
            root.joinpath(filename),
            filename.removesuffix(".json"),
            schema_version=index_version,
        )
        for filename in filenames
    )
    names = tuple(template.name for template in templates)
    if len(names) != len(set(names)):
        raise TemplateError("Packaged subtitle templates contain duplicate names")
    if DEFAULT_SUBTITLE_TEMPLATE not in names:
        raise TemplateError("Template catalog must contain the default template")
    return templates


def _read_template_index(root: Any) -> tuple[int, list[str]]:
    """Read and validate the packaged template inventory and its stable order."""
    index = _read_json(root.joinpath(_INDEX_RESOURCE))
    _expect_keys(index, {"schema_version", "templates"}, context="Template index")
    index_version = index["schema_version"]
    if type(index_version) is not int or index_version not in (
        _LEGACY_TEMPLATE_SCHEMA_VERSION,
        _TEMPLATE_SCHEMA_VERSION,
    ):
        raise TemplateError(
            "Template index must use schema_version "
            f"{_LEGACY_TEMPLATE_SCHEMA_VERSION} or {_TEMPLATE_SCHEMA_VERSION}"
        )
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
    return index_version, checked_filenames


def _validate_template_inventory(root: Any, filenames: list[str]) -> None:
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
    indexed = set(filenames)
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
