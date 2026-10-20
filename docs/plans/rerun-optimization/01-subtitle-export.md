# Generate subtitle files without video encoding

Status: In review

Delivery: `feat/reusable-subtitle-runs`

Depends on: [Plan 0](00-source-speech-cache.md) for source reuse and the
existing schema-3/SRT/ASS artifact compiler.

## Objective and public contract

`--subtitles-only` publishes one styled ASS and one plain SRT without rendering
a video. The input video remains required to resolve actual geometry. It uses
normal speech recognition on the first run and reuses the output-local cache
by default; `--cache-dir DIR` selects another location.
Presentation overrides, fonts, templates, real timing, and shaping fallbacks
use the production pipeline. This increment supports `transcribe` only.

Publish `output/video-pt.srt` and `output/video-pt.ass` under one collision-safe
stem; unknown language omits the suffix. Private schema-3 JSON remains transient.
Reject `--keep-transcriptions`, video encoding options, external subtitle input,
and either sample preview or real preview mode. Validate before expensive work.
No public Python API or existing result-dataclass contract changes are required.

## Implementation tasks

- [x] Add validated request mode and CLI help, preserving normal artifact output.
- [x] Use the existing normal/cache recognition and complete artifact pipeline.
- [x] Bypass FFmpeg rendering capability and encoder preflight in this mode;
  ffprobe remains necessary and ASR may require FFmpeg for audio extraction.
- [x] Atomically publish the SRT/ASS pair with shared collision suffix and clean
  invocation-owned intermediates after success. Preserve diagnostics on failure.
- [x] Cover output text/timing/style, collisions on either suffix, failed
  publication rollback, invalid combinations, and zero encoder/render calls.
- [x] Update README outputs/options, PRD requirements, and architecture flow.

## Verification and acceptance

Run `.venv/bin/python -m pytest tests/test_rerun_cli.py tests/test_cli.py tests/test_transcriber.py`.
Export with two templates against one cache must recognize once and produce
different styled ASS without any rendered media or published JSON. Existing
files remain untouched. Display output matches an ordinary run's subtitles for
equal source/configuration. A complete cache must work without an ASR runtime.

## Commit and pull-request plan

Use the package branch and shared draft PR against `main`. Suggested commit:
`feat: export styled subtitles without rendering video`, with focused tests.
Run repository checks described in Plan 0 and the package's delivery lifecycle;
complete local verification before requesting Git delivery confirmation.
