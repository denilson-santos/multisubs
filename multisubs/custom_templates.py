"""Loader and resolver for user-provided subtitle template directories."""

from __future__ import annotations

import json
import re
import stat
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .errors import TemplateError, ValidationError
from .templates import (
    DEFAULT_SUBTITLE_TEMPLATE,
    TEMPLATE_CHOICES,
    SubtitleTemplate,
    _DuplicateKeyError,
    _expand_sparse_template_data,
    _expect_allowed_keys,
    _expect_schema_version,
    _expect_string,
    _load_sparse_template,
    _reject_duplicate_keys,
    _template_data_from_config,
    get_subtitle_template,
)

CUSTOM_TEMPLATE_SCHEMA_VERSION = 1
MAX_CUSTOM_TEMPLATE_BYTES = 1 * 1024 * 1024
MAX_CUSTOM_TEMPLATE_COUNT = 256
MAX_CUSTOM_TEMPLATE_TOTAL_BYTES = 16 * 1024 * 1024
MAX_CUSTOM_TEMPLATE_JSON_DEPTH = 32

_CUSTOM_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CUSTOM_TOP_LEVEL_KEYS = {
    "schema_version",
    "name",
    "description",
    "base",
    "style",
    "layout",
    "animation",
}


@dataclass(frozen=True)
class ResolvedSubtitleTemplate:
    """A selected template plus the source information needed for metadata."""

    template: SubtitleTemplate
    source: str = "builtin"
    base: str | None = None


class _CustomTemplateResource:
    """Small resource adapter used by the strict packaged-template loader."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = path.name

    def read_text(self, *, encoding: str) -> str:
        return self.path.read_text(encoding=encoding)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not supported")


def _check_json_depth(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_CUSTOM_TEMPLATE_JSON_DEPTH:
        raise TemplateError(
            "Custom subtitle template JSON exceeds the maximum nesting depth "
            f"of {MAX_CUSTOM_TEMPLATE_JSON_DEPTH}"
        )
    if isinstance(value, dict):
        for child in value.values():
            _check_json_depth(child, depth=depth + 1)
    elif isinstance(value, list):
        for child in value:
            _check_json_depth(child, depth=depth + 1)


def _read_custom_json(path: Path, raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        ValueError,
        _DuplicateKeyError,
    ) as exc:
        raise TemplateError(
            f"Could not read custom subtitle template '{path}': {exc}"
        ) from exc
    _check_json_depth(value)
    if type(value) is not dict:
        raise TemplateError(
            f"Custom subtitle template '{path}' must contain a JSON object"
        )
    return value


def _reject_custom_nulls(
    value: Any,
    *,
    context: str,
    path: tuple[str, ...] = (),
) -> None:
    if value is None:
        if path == ("style", "typography", "highlight_color"):
            return
        raise TemplateError(f"{context}.{'.'.join(path)} must not be null")
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_custom_nulls(
                child,
                context=context,
                path=path + (str(key),),
            )
    elif isinstance(value, list):
        for position, child in enumerate(value):
            _reject_custom_nulls(
                child,
                context=context,
                path=path + (str(position),),
            )


def _read_custom_template_files(directory: Path) -> list[tuple[Path, dict[str, Any]]]:
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        raise TemplateError(
            f"Could not enumerate custom subtitle template directory '{directory}'"
        ) from exc

    json_entries: list[Path] = []
    for entry in entries:
        if entry.suffix != ".json":
            continue
        if entry.is_symlink():
            raise TemplateError(
                f"Custom subtitle template '{entry}' must not be a symbolic link"
            )
        try:
            info = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise TemplateError(
                f"Could not inspect custom subtitle template '{entry}'"
            ) from exc
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise TemplateError(
                f"Custom subtitle template '{entry}' must be a regular file"
            )
        json_entries.append(entry)
    if len(json_entries) > MAX_CUSTOM_TEMPLATE_COUNT:
        raise TemplateError(
            "Custom subtitle template directory contains more than "
            f"{MAX_CUSTOM_TEMPLATE_COUNT} JSON files"
        )

    total_bytes = 0
    loaded: list[tuple[Path, dict[str, Any]]] = []
    for entry in json_entries:
        try:
            info = entry.stat(follow_symlinks=False)
        except OSError as exc:
            raise TemplateError(
                f"Could not inspect custom subtitle template '{entry}'"
            ) from exc
        if not stat.S_ISREG(info.st_mode):
            raise TemplateError(
                f"Custom subtitle template '{entry}' must be a regular file"
            )
        if info.st_size > MAX_CUSTOM_TEMPLATE_BYTES:
            raise TemplateError(
                f"Custom subtitle template '{entry}' exceeds the maximum size of "
                f"{MAX_CUSTOM_TEMPLATE_BYTES} bytes"
            )
        total_bytes += info.st_size
        if total_bytes > MAX_CUSTOM_TEMPLATE_TOTAL_BYTES:
            raise TemplateError(
                "Custom subtitle templates exceed the total size limit of "
                f"{MAX_CUSTOM_TEMPLATE_TOTAL_BYTES} bytes"
            )
        try:
            with entry.open("rb") as stream:
                raw = stream.read(MAX_CUSTOM_TEMPLATE_BYTES + 1)
        except OSError as exc:
            raise TemplateError(
                f"Could not read custom subtitle template '{entry}'"
            ) from exc
        if len(raw) > MAX_CUSTOM_TEMPLATE_BYTES:
            raise TemplateError(
                f"Custom subtitle template '{entry}' exceeds the maximum size of "
                f"{MAX_CUSTOM_TEMPLATE_BYTES} bytes"
            )
        loaded.append((entry, _read_custom_json(entry, raw)))
    return loaded


def _parse_custom_template(
    path: Path,
    data: dict[str, Any],
    *,
    builtins: dict[str, SubtitleTemplate],
) -> tuple[str, SubtitleTemplate, str]:
    context = f"Custom subtitle template '{path}'"
    _expect_allowed_keys(data, _CUSTOM_TOP_LEVEL_KEYS, context=context)
    _reject_custom_nulls(data, context=context)
    if "schema_version" not in data:
        raise TemplateError(f"{context} is missing field(s): schema_version")
    _expect_schema_version(
        data["schema_version"],
        context=f"{context}.schema_version",
        expected=CUSTOM_TEMPLATE_SCHEMA_VERSION,
    )
    if "name" not in data:
        raise TemplateError(f"{context} is missing field(s): name")
    name = _expect_string(data["name"], context=f"{context}.name")
    if _CUSTOM_NAME_PATTERN.fullmatch(name) is None:
        raise TemplateError(
            f"{context}.name must use lowercase kebab-case (for example, 'my-template')"
        )

    description = data.get("description", f"Custom subtitle template '{name}'.")
    description = _expect_string(description, context=f"{context}.description")

    base_name = data.get("base", DEFAULT_SUBTITLE_TEMPLATE)
    base_name = _expect_string(base_name, context=f"{context}.base")
    if base_name not in builtins:
        raise TemplateError(
            f"{context}.base must name a built-in subtitle template; "
            f"supported values are: {', '.join(TEMPLATE_CHOICES)}"
        )

    sparse_data: dict[str, Any] = {
        "schema_version": 5,
        "name": name,
        "description": description,
    }
    for field in ("style", "layout", "animation"):
        if field in data:
            sparse_data[field] = deepcopy(data[field])

    base_template = builtins[base_name]
    animation_value = data.get("animation")
    word_value = (
        animation_value.get("word") if isinstance(animation_value, dict) else None
    )
    word_text_value = word_value.get("text") if isinstance(word_value, dict) else None
    emphasis_value = (
        word_text_value.get("emphasis") if isinstance(word_text_value, dict) else None
    )
    if (
        base_template.config.animation.word.text.emphasis.type.value == "highlight"
        and isinstance(emphasis_value, dict)
        and emphasis_value.get("type") != "highlight"
    ):
        style_value = sparse_data.get("style")
        if style_value is None:
            sparse_data["style"] = {
                "typography": {"highlight_color": None},
            }
        elif isinstance(style_value, dict):
            typography_value = style_value.setdefault("typography", {})
            if isinstance(typography_value, dict):
                typography_value.setdefault("highlight_color", None)

    base_data = _template_data_from_config(
        base_template.config,
        name=base_template.name,
        description=base_template.description,
    )
    expanded = _expand_sparse_template_data(
        sparse_data,
        expected_name=name,
        base_data=base_data,
        reset_animation_duration=True,
    )
    resource = _CustomTemplateResource(path)
    template = _load_sparse_template(resource, name, data=expanded)
    if base_name == DEFAULT_SUBTITLE_TEMPLATE:
        typography_override = data.get("style", {}).get("typography", {})
        if "font_weight" not in typography_override:
            base_typography = base_template.config.style.typography
            typography = replace(
                template.config.style.typography,
                font_weight_input=base_typography.font_weight_input,
                font_weight_input_form=base_typography.font_weight_input_form,
            )
            style = replace(template.config.style, typography=typography)
            template = replace(template, config=replace(template.config, style=style))
    return name, template, base_name


def load_custom_template_directory(
    directory: str | Path,
) -> dict[str, tuple[SubtitleTemplate, str]]:
    """Validate every immediate JSON template in a user directory."""
    try:
        path = Path(directory).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise TemplateError(
            f"Could not resolve custom subtitle template directory '{directory}'"
        ) from exc
    if not path.exists():
        raise TemplateError(
            f"Custom subtitle template directory not found: '{directory}'"
        )
    if not path.is_dir():
        raise TemplateError(
            f"Custom subtitle template path '{directory}' is not a directory"
        )

    builtins = {template.name: template for template in _builtin_templates()}
    parsed: dict[str, tuple[SubtitleTemplate, str]] = {}
    seen_files: dict[str, Path] = {}
    for file_path, data in _read_custom_template_files(path):
        name, template, base_name = _parse_custom_template(
            file_path,
            data,
            builtins=builtins,
        )
        if name in parsed:
            previous = seen_files[name]
            raise TemplateError(
                f"Custom subtitle templates contain duplicate name '{name}' "
                f"(files '{previous.name}' and '{file_path.name}')"
            )
        parsed[name] = (template, base_name)
        seen_files[name] = file_path
    return parsed


def _builtin_templates() -> tuple[SubtitleTemplate, ...]:
    # Imported lazily so a damaged packaged catalog reports through its existing API.
    from .templates import SUBTITLE_TEMPLATES, require_template_catalog

    require_template_catalog()
    return SUBTITLE_TEMPLATES


def resolve_subtitle_template(
    name: str | None,
    template_dir: str | Path | None = None,
) -> ResolvedSubtitleTemplate:
    """Resolve a built-in or directory-provided template by its JSON name."""
    custom: dict[str, tuple[SubtitleTemplate, str]] = {}
    if template_dir is not None:
        custom = load_custom_template_directory(template_dir)

    resolved_name = DEFAULT_SUBTITLE_TEMPLATE if name is None else name
    if resolved_name in custom:
        template, base_name = custom[resolved_name]
        return ResolvedSubtitleTemplate(template, source="custom", base=base_name)
    if resolved_name in TEMPLATE_CHOICES:
        return ResolvedSubtitleTemplate(get_subtitle_template(resolved_name))

    available_names = tuple(dict.fromkeys((*TEMPLATE_CHOICES, *sorted(custom))))
    available_custom = ", ".join(sorted(custom))
    suffix = (
        f" Available custom templates from --template-dir: {available_custom}."
        if available_custom
        else " Use --template-dir to load custom templates."
    )
    raise ValidationError(
        "subtitle-template must be one of: " + ", ".join(available_names) + "." + suffix
    )
