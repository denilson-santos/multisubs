# Custom template directory with built-in inheritance

Status: In review

Delivery: `feat/custom-template-files`

Depends on:

- [Curated social templates](04-curated-social-templates.md), including its
  sparse normalization and complete immutable configuration contract.

## Objective and scope

Let users supply a local directory with `--template-dir PATH` and select a
presentation by name through the existing `--template NAME`,
optionally deriving style, layout, and animation from one built-in template
through `base`. Implementation is active on the delivery branch after Plan 4's
merge.

Include transcription, static preview, animated preview, existing CLI overrides,
custom fonts through `--fonts-dir`, early validation, and retained provenance.
Keep the final sixteen built-in choices and their private JSON resources
consistent with the current catalog. The follow-up catalog reduction removes
nine redundant Plan 4 presets while preserving the default and the remaining
fifteen curated styles.

Exclude remote URLs, recursive directory discovery, multiple template directories,
installation into the packaged catalog,
inheritance from other user files, multiple bases, recursive includes, variables,
executable expressions, raw ASS, new renderer effects, and embedded font files.
No migration-guide file or new runtime dependency is required.

## Public interface

```sh
multisubs -i video.mp4 -l pt --template-dir ./templates --template my-yellow-captions
multisubs -i video.mp4 --preview-layout --template-dir ./templates --template my-yellow-captions
multisubs -i video.mp4 --preview-animation --template-dir ./templates --template=my-yellow-captions \
  --fonts-dir ./fonts --font-size 3.6%
```

`--template-dir` accepts one flat directory, analogous to `--fonts-dir`.
`--template` selects a name from the combined custom and built-in catalog;
both flags work together and support argparse's `--option=value` syntax.
Without a directory, retain existing selection and default behavior. With a
directory and omitted `--template`, select `default` through the same lookup.
Resolve relative directories against the working directory, expand `~`, accept
spaces and Unicode, and reject missing, unreadable, or non-directory inputs.

Discover immediate regular `*.json` files in deterministic filename order;
ignore subdirectories and non-JSON files. No index file is required or reserved.
Validate all discovered documents once per invocation before selecting a name;
malformed or duplicate custom definitions fail even when not selected. Empty
directories are valid and leave the built-in choices available. Selection uses
the JSON `name`, independent of filename. Reject duplicate names within the
directory and identify both filenames; never choose by discovery order.

Custom names take precedence over equal built-in names, including `default`,
only when the directory is explicitly supplied. Otherwise fall back to the
built-in catalog. An invalid matching custom definition must never fall back
silently. Unknown selections list the available combined names deterministically
and suggest `--template-dir` when appropriate. Remove the parser's static
`choices=TEMPLATE_CHOICES` restriction and validate names after directory loading
in `_build_request`; parser acceptance is deferred until directory resolution.
`--help` documents built-ins and directory lookup without reading user files.

Never install, copy, modify, or delete custom files or alter the global packaged
registry. No `--template-file` flag or compatibility alias will be implemented.

### Public custom JSON version 1

```json
{
  "schema_version": 1,
  "name": "my-yellow-captions",
  "description": "Yellow word emphasis with my preferred spacing.",
  "base": "yellow-pop",
  "style": {
    "typography": {
      "font_size": "3.6%"
    }
  },
  "layout": {
    "margins": {
      "bottom": "15%"
    }
  }
}
```

Require integer `schema_version: 1` and a nonempty kebab-case `name`.
`description` is optional and must be nonempty when supplied. The name is a
label independent of the filename. It is registered only in the invocation's
custom catalog and takes precedence over a matching built-in selection.
Source provenance distinguishes a custom label matching a built-in name.
`base`, `style`, `layout`, and `animation` are optional. The minimal document
contains only version and name and resolves to the default presentation.

`base` accepts exactly one current built-in name from `TEMPLATE_CHOICES`,
including `default`. Omission means `default`. Reject null, empty strings,
arrays, unknown/removed names, URLs, and filenames as bases; explain the valid
choices without silently substituting another template. Private files remain
private; their existing public catalog names are the inheritance interface.
Resolve `base` exclusively against the built-in registry, bypassing the custom
directory. Thus a custom `yellow-pop` can use `"base": "yellow-pop"`, and a
custom `default` without base inherits the internal default without recursion.
Custom names are never valid bases unless that same name exists internally.

Version 1 exposes the recognized semantic fields of private schema 5 under
`style`, `layout`, and `animation`, with the same units, enums, independent
tracks, and validation. Explicitly document the allowed field tree during
implementation, rather than accepting whatever a future internal reader accepts.
Coordinates and font-directory paths remain CLI-only. The public version is
independent of private template schema 5 and transcription artifact schema 3;
do not accept private versions 4/5 through the new public loader.

Maintain canonical order: version, name, description, base, style, layout,
animation, followed by Plan 4's nested field order. Use UTF-8 and two-space
indentation in examples. Reject duplicate keys, unknown properties, non-finite
numbers, invalid types, and unsupported versions with contextual diagnostics.

## Inheritance and override semantics

Resolve in this order: built-in baseline (default if omitted), custom JSON,
explicit CLI flags, then existing geometry-dependent resolution. Inherit the
complete semantic baseline, including layout and animation; never mutate the
cached catalog or derive behavior by merging only authored sparse base files.

Merge recognized objects by field, preserving omitted siblings. Empty objects
are no-ops. Explicit false, zero, and supported `none` values override inherited
values; null is not a general reset mechanism. Reject null except for the
existing nullable typography `highlight_color` contract.

Animation phases need deliberate merging:

- An omitted phase retains the base phase and duration.
- A supplied phase requires `type`. If its type matches the inherited type,
  retain its duration unless explicitly overridden.
- Changing type starts with the new effect's default duration; never retain a
  duration from a different effect. An explicit duration takes precedence.
- `{"type": "none"}` disables that phase and removes its inherited duration.
  `highlight` is also durationless. Explicit duration on either is invalid.
- Disabling word text highlighting clears an inherited highlight color unless
  the custom document explicitly supplies a value. A supplied non-null color
  with inactive highlighting is invalid; null clears it. Enabling highlighting
  requires an effective non-null color from the base or custom document.
- Each track remains independent: disabling text emphasis keeps word decoration
  and its timing active. Disabling `word_backdrop.type` does not disable text
  highlighting. Inactive backdrop motion keeps existing renderer semantics.

Validate the custom baseline before CLI overlays so flags cannot repair an
invalid file. Then apply CLI flags through the existing validator, retaining its
effect-aware duration/disable rules and placement-presence behavior. Custom
layout fields are baseline values, not explicit CLI argument presence. Preserve
inherited inactive margins when changing native position and enforce current
coordinate-mode conflicts only for explicitly supplied CLI arguments.

Base names refer to the installed catalog version. Upgrading that catalog can
change inherited visuals; schema compatibility alone does not freeze appearance.
Document pinning the package version or explicitly specifying the full semantic
presentation for users who require stable styling. Future removal of a supported
base is a public compatibility change; never silently redirect removed names.

## Boundaries, validation, and persistence

Add a dedicated `multisubs/custom_templates.py` reader for the public format.
Reuse typed configuration validation and narrowly extracted normalization helpers
from `templates.py` where appropriate. Keep the built-in directory/index audit,
schema checks, and filename/name rules strict and separate from external files.
The helper is an internal Python API; do not promise a new supported Python SDK.

The CLI loads the directory into an invocation-local immutable catalog and
resolves the selected name once during `_build_request`, before ffprobe, output
creation, font materialization, or model loading. Shape and semantic validation
happen there; geometry and font-metric checks still follow probing. Carry an
immutable config and source identity through `RunRequest` and `PreviewRequest`;
preview, transcriber, and ASS rendering must not reread the user file.

Read at most 1 MiB plus one byte per file and reject oversized input before parsing.
Bound the custom catalog to 256 JSON files and 16 MiB total bytes, with actionable
errors at the first exceeded limit. Do not follow symlink entries in discovery;
reject matching JSON symlinks and non-regular JSON entries explicitly, while
ignoring subdirectories. A directory path itself may resolve through a symlink
as with existing local path options. Cache only for the current request.
Reject non-regular files and handle I/O, decoding, JSON, excessive nesting, and
semantic failures as actionable domain errors. Include the failing field or
line/column, without echoing the complete file. No shell execution, network
retrieval, recursive resolution, or import-time external-file loading.

Keep built-in `metadata.rendering.template` output byte-compatible in shape
(`requested` and `resolved`). For custom runs, keep these keys with the custom
name as `resolved`, the explicit selected name or null as `requested`, and add
`source: "custom"`, `schema_version: 1`, and the
resolved built-in `base` name. Do not serialize directory or file paths, raw JSON,
description, or font paths. Existing rendering metadata continues recording the
resolved configuration. Treat the custom-only metadata extension as additive
within artifact schema 3 and document it explicitly; do not change existing key
types or the metadata emitted for built-ins. Identify custom selection and its
base in progress output without implying permanent catalog registration.

Preserve output naming, cleanup, retained artifact lifecycle, SRT text and
timing, font provider precedence, and ASS compilation. Word animation inherited
from a base must trigger the same transcription translation rejection and
missing-alignment fallback. Preview modes retain simulated/static timing and
their existing speech-validation exemptions.

## Implementation tasks

- [x] Add the public version-1 reader, flat directory discovery, invocation-local
  name registry, duplicate detection, field contract, bounded local loading,
  base lookup, immutable merge, and error translation with focused unit tests.
- [x] Cover every inherited phase transition and dependent highlight-color rule,
  plus sparse objects, explicit disabling, and unchanged cached base configs.
- [x] Wire `--template-dir` and deferred `--template` name validation into all modes;
  implement custom-first selection and built-in-only base resolution;
  preserve baseline-versus-explicit option semantics and custom font resolution.
- [x] Carry source identity to progress and retained JSON without storing paths;
  preserve exact built-in output fixtures and old request construction defaults.
- [x] Add real ASS/preview coverage for a derived yellow-pop, a custom panel,
  a template without base, and a custom font directory. Verify equivalence to
  the same fully explicit typed config on 16:9 and 9:16 fixtures.
- [x] Document the public field tree, examples, inheritance and disabling rules,
  schema compatibility, errors, and upgrade behavior. Synchronize dashboards.

## Verification and acceptance

Unit cases must cover minimal input; every catalog name as base; deep sibling
inheritance; immutable baselines across successive loads; phase type changes,
same-type durations, explicit none/false/zero; highlight enabling/disabling;
missing files, directories, invalid UTF-8/JSON, duplicate/unknown keys, booleans
as versions, non-finite numbers, over-size/deep input, unsupported versions,
and invalid bases. Confirm malformed files fail before probing or model imports.
Exercise combined selectors, both equals/separate flag syntax, CLI overrides,
filename/name independence,
native position and explicit coordinates, and both preview modes.
Cover empty directories, ignored subdirectories/non-JSON entries, duplicate
custom names, invalid unselected documents, custom/built-in collisions,
custom `default` with omitted selection, built-in-only base lookup, symlink and
catalog limits, deterministic diagnostics, help without directory reads, and
isolation between consecutive requests using different directories.

Retained-JSON tests must prove source/base identification, no custom path leaks,
unchanged built-in snapshots, and fully resolved rendering values. Delete or
modify a file after request construction to prove rendering uses its snapshot.
Use existing fake transcription fixtures for retention and fallback checks;
routine verification must not download or run speech models.

Run these commands after implementation:

```sh
python -m pytest tests/test_custom_templates.py tests/test_templates.py tests/test_cli.py tests/test_config.py tests/test_preview.py tests/test_transcriber.py
python -m pytest
python -m pytest -m integration tests/test_integration.py tests/test_preview_integration.py tests/test_animation.py
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Build wheel/sdist under the existing clean-build conventions, run `python -m
build` and `python -m twine check dist/*`, audit the 17 template JSON resources
(index plus sixteen choices) and 82 font binaries, and install the wheel outside
the checkout. Load a local
custom file and render with packaged fonts there. Inspect stable and animated
frames on light/dark/busy fixtures for retained padding, word placement, and
equality with explicit-config renders. Record actual commands, results, and
any unavailable integration evidence before claiming acceptance.

Acceptance requires all three CLI modes to accept the documented example;
optional base/default behavior and precedence to match this plan; invalid input
to fail early; independent inherited effects to behave correctly; all 16
built-ins and current default output without custom overrides to remain unchanged;
custom-first selection and built-in-only inheritance to work; and no permanent registration,
source-file mutation, path leak, or renderer-specific custom-template branch.

Implementation verification on 2026-09-08:

- python3 -m pytest tests/test_custom_templates.py tests/test_templates.py tests/test_cli.py -q — 148 passed.
- python3 -m pytest -q — 783 passed, 54 deselected.
- python3 -m pytest -m integration tests/test_integration.py
  tests/test_preview_integration.py tests/test_animation.py -q — 50 passed,
  124 deselected.
- python3 -m ruff check ., python3 -m ruff format --check ., and
  python3 -m pyright — passed.
- python3 -m compileall -q multisubs, multisubs --help, and git diff --check — passed.

## Documentation and delivery

During implementation update README recipes and command reference, PRD FR-9
and custom-template acceptance, architecture flow/module ownership/public input
and artifact metadata contracts, and conventions for maintaining the public
schema. Update the AGENTS.md repository map for the new module. Keep existing
completed plans as history; this plan extends Plan 4's private-only scope without
adding custom-file support to Plan 4's delivery requirements.

Implementation branch: `feat/custom-template-files`, created from the merged
Plan 4 baseline. Suggested focused commits:

1. `feat: load custom templates with built-in inheritance`
2. `feat: expose custom templates across CLI rendering modes`
3. `docs: document custom template format and inheritance`

Keep behavior tests with each implementation commit. Draft PR title:
`feat!: support custom templates and streamline built-in catalog`; base `main`.
Link this plan and describe scope, public schema/provenance effects, validation
actually run, documentation, and catalog-upgrade limitations.

Follow [AGENTS.md](../../../AGENTS.md) and [delivery](../../delivery.md).
Finish implementation and verification before requesting Git delivery approval.
The implementation branch is `feat/custom-template-files`.
The final pre-PR documentation commit moves the plan and package to In review
with that branch; push the complete branch before opening the PR. After an
authoritative merge signal, mark the plan/package Done, record the merged PR,
and update progress to 6/6. Rollback the reader, CLI integration, metadata, and
documentation together through a normal revert or fix; user JSON remains intact.
