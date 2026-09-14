# Simplify pipeline orchestration and artifact ownership

Status: In progress

Depends on: [Plan 0](00-configuration-and-requests.md),
[Plan 1](01-text-and-layout.md), and
[Plan 2](02-ass-and-animation-rendering.md).

## Objective

Make normal transcription and both preview modes read as short workflows with
clear runtime, cue, artifact, publication, and cleanup boundaries.

## Scope

Included: `transcriber.py`, `preview.py`, `subtitler.py`, `utils.py`,
`errors.py`, their tests, and focused integration tests.

Excluded: asynchronous/batch processing, new media codecs, changes to model
selection, full transcription smoke tests, and new public Python APIs.

## Decisions and implementation

- Keep WhisperX/PyTorch imports and model lifetime behind the transcription
  runtime boundary; previews remain transcription-free.
- Separate cue construction, metadata/JSON projection, SRT/ASS writing, and
  public artifact orchestration. Preserve `generate_transcriptions()` and other
  documented/imported call points through thin facades.
- Keep all ffprobe/FFmpeg policy in `subtitler.py`; factor common probing,
  filter, temporary-output, and error translation steps without hiding command
  arguments behind a general media framework.
- Represent publication and cleanup as explicit state transitions using the
  existing collision-safe/atomic utilities. Never broaden cleanup targets.

## Tasks and verification

- [x] Retain model-call, language, cue/artifact, preview-dispatch, FFmpeg,
  publication, and cleanup contract tests.
- [x] Decompose JSON projection and display-cue layout by responsibility while
  preserving compatibility entry points and schema 3.
- [x] Keep transcription and preview orchestration separate where contracts
  differ; share repeated FFmpeg preview error translation without obscuring the
  commands or lifecycle.
- [x] Run hermetic orchestration tests and focused opt-in media tests without
  loading a real speech model.

Run:

~~~
.venv/bin/python -m pytest tests/test_transcriber.py tests/test_language.py tests/test_preview.py tests/test_subtitler.py tests/test_cli.py tests/test_utils.py
.venv/bin/python -m pytest -m integration tests/test_preview_integration.py tests/test_integration.py
.venv/bin/python -m pytest
~~~

## Delivery

Included on the shared branch: `refactor/simplify-codebase`.
Suggested commits: `test: characterize pipeline ownership`,
`refactor: separate transcription and artifact stages`, and
`refactor: simplify preview and media orchestration`; these are commits within
the shared refactor, not a separate pull request.
Use the standard plan status and explicit Git delivery approval lifecycle.

## Acceptance criteria

- Normal, retained, static-preview, and animation-preview workflows publish the
  same collision-safe paths and clean only invocation-owned temporary files.
- Translation restrictions, language selection, model calls, ffprobe geometry,
  FFmpeg stream/filter policy, and actionable errors are unchanged.
- JSON schema 3, SRT text/timing, ASS inputs, and aggregate diagnostics remain
  equivalent for characterized fixtures.
- Public orchestration functions are short facades over cohesive internal
  stages and preview imports do not load WhisperX or PyTorch.
