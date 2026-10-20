# Preview real synchronized video excerpts

Status: In review

Delivery: `feat/reusable-subtitle-runs`

Depends on: [source reuse](00-source-speech-cache.md),
[artifact preparation](01-subtitle-export.md), and the existing FFmpeg boundary.

## Objective and public contract

`--preview-clip --preview-at HH:MM:SS --preview-duration 8s` renders moving
source video and available source audio with the production transcript/styles.
Duration defaults to 10 seconds and accepts whole milliseconds from 1 through
15 seconds, using the same duration grammar as existing previews. Start is
required, finite, nonnegative, and earlier than a known media end. Clamp the
requested end to that end; validate the range before recognition.
The CLI timestamp has exactly two ASCII digits per field and whole seconds;
fractional inputs are rejected. Internal numeric rendering timestamps retain
their existing precision.

All preview selectors and controls share the `Subtitle preview` CLI help panel.
`--preview-at` remains optional for PNG and simulated-animation backgrounds;
omission selects the first source frame (0 seconds). It is required for a real
excerpt. `--preview-duration` sets the simulated cue duration (default 4 seconds)
or the real excerpt duration (default 10 seconds); PNG rejects duration. Sample
text/guides are available only for PNG and simulated animation. These shared
controls replace the initially proposed separate clip timing flags.
PNG previews also accept valid video encoding settings while ignoring them
without initializing a video encoder, so video settings can stay in the command
when switching to `--preview-layout`.

Reuse full-source speech through `<output-dir>/.multisubs-cache` by default;
`--cache-dir DIR` selects a shared or custom location. A miss recognizes the full
input, not just the excerpt, so subsequent previews/full renders share one
source transcript. This increment supports `transcribe` only. Sample previews,
external subtitles, subtitle-only mode, `--keep-transcriptions`, and existing
sample-preview-only options cannot be combined with this mode.

Publish one collision-safe `video-subtitle-clip-preview.mp4`, with H.264 video
(libx264 by default or the explicit supported encoder), source geometry and
autorotation, and available source audio re-encoded as AAC for arbitrary cuts.
No audio is synthesized for silent input. No subtitle/JSON artifacts are
published. Empty-speech intervals remain valid excerpts.

## Implementation tasks

- [x] Add CLI range parsers/validation and typed request fields.
- [x] Verify shared timing flags, preview help grouping, first-frame defaults,
  optional sample frame selection, and renamed cache controls after the follow-up.
- [x] Accept validated video encoding options in PNG previews without changing
  the image or initializing a video encoder.
- [x] Prepare complete production ASS on the original timeline. Never restart
  an existing cue's animation or discard words at the excerpt boundary.
- [x] Keep seeking, timestamp restoration before libass, output clock reset,
  codec/pixel format, audio, temporary output, and errors in `subtitler.py`.
- [x] Seek to the excerpt rather than decode a long prefix; test timing against
  the equivalent original-timeline render, including non-keyframe boundaries.
- [x] Cover invalid/near-end ranges, optional audio, subtitles spanning a cut,
  real animation phase, media failures, collision safety, and cleanup.
- [x] Document full-input recognition on cache miss and distinguish this mode
  from the existing silent frozen-background simulated animation preview.

## Verification and acceptance

Run `.venv/bin/python -m pytest tests/test_rerun_cli.py tests/test_subtitler.py` and
`.venv/bin/python -m pytest -m integration tests/test_rerun_integration.py`.
Use small synthetic moving media, deterministic source speech (no real ASR),
and audio to verify duration, source frame selection, geometry, subtitle clock,
animation phase, and audio presence/synchronization. Preview must retain source
text and observed times. Inspect representative animated output visually when
automated frame comparisons cannot establish readability.

## Commit and pull-request plan

Use the package branch and shared draft PR against `main`. Suggested commits:
`feat: preview synchronized subtitle excerpts` and
`docs: document reusable transcription and visual iteration`.
Run full hermetic checks, targeted synthetic FFmpeg integration, compileall,
CLI help, and the link/diff checks. Record only commands actually run in the PR.
Follow explicit Git approval and final pre-PR status rules in the dashboard.
