# Burn an external SRT or ASS file into a video

Status: Planned

Depends on:

- The existing FFmpeg subtitle renderer and collision-safe video publication
  contract in [architecture.md](../../architecture.md). This plan does not
  depend on [Plan 0](00-compile-timed-cue-json.md).

## Objective

Let a caller supply a local SRT or ASS file and render its subtitles onto a
copy of a local video without invoking ASR or rebuilding the subtitle timeline.
This is hard-subtitle rendering, consistent with the current product; muxing a
selectable subtitle track is a different capability.

## Scope

Included:

- A public Python function and opt-in CLI mode that accept one existing `.srt`
  or `.ass` file and one video.
- Direct FFmpeg/libass ingestion of the subtitle file, preserving its cue
  content and timing. ASS retains its authored styles and override tags; SRT
  uses FFmpeg/libass default presentation.
- Optional local `--fonts-dir` for external ASS fonts, existing autorotation,
  stream selection, copied audio, collision-safe output, and actionable errors.

Excluded:

- Transcription, JSON compilation, translation, source subtitle rewriting,
  template or appearance overrides, forced restyling, and output SRT/ASS copies.
- Soft subtitle tracks, subtitle editing, automatic language detection,
  remote subtitle URLs, or conversion into the schema-1 timed-cue contract.
- Guaranteed cross-platform pixel-identical appearance for external SRT or
  ASS that relies on system fonts or FFmpeg/libass defaults.

## Decisions and constraints

- Accept `.srt` and `.ass` extensions case-insensitively. Validate a regular,
  readable, nonempty local file and video path before probing or creating
  output. FFmpeg is the format parser; its rejection of malformed content must
  become a concise rendering error naming the supplied subtitle path, without
  printing full dialogue or leaking unrelated file contents.
- Pass ASS through to FFmpeg unchanged. Do not parse, normalize, rewrite, or
  interpret its styles, tags, timing, script resolution, or font references.
  `--fonts-dir` may help resolve referenced local fonts. The user remains
  responsible for external ASS styling and font availability.
- Pass SRT to FFmpeg's `subtitles` filter unchanged. It receives the filter's
  default libass styling; templates and `SubtitleConfig` are not applied in
  this mode. Document that appearance can vary with installed FFmpeg/fonts.
  If deterministic project styling of imported SRT is desired later, specify
  that separately with a parser/conversion and explicit opt-in option.
- Keep the current `embed_subtitles(input_path, ass_path, ...)` positional API
  working for existing callers. Generalize only its internal FFmpeg file
  argument or add a narrowly shared renderer. Do not silently broaden that
  established API's documented ASS contract.
- Preserve the lowest-index usable video stream, normalized autorotation,
  `original_size` filter argument, optional copied audio, and existing FFmpeg
  dependency checks. No ASR backend, template catalog, font measurer, or cue
  layout is needed for this mode.

## Public interface and output

Proposed Python API, exported lazily from `multisubs.__init__`:

```python
render_subtitle_file(
    video_path: str | Path,
    subtitle_path: str | Path,
    output_dir: str | Path,
    *,
    fonts_dir: str | Path | None = None,
) -> Path
```

Proposed CLI examples:

```sh
multisubs -i video.mp4 --subtitle-file captions.srt -o output
multisubs -i video.mp4 --subtitle-file styled.ass --fonts-dir ./fonts -o output
```

`--subtitle-file` selects direct-render mode and requires `-i`. Reject
`--cues-json`, ASR/model/task/language options,
`--keep-transcriptions`, preview options, template selection, and every
appearance/layout/animation override. Permit `-o`, `--verbose`, and
`--fonts-dir`. Detect explicit conflicting flags even when they repeat a
default. Validate conflicts and subtitle path before FFmpeg probing.

Publish only `<video-stem>-subtitled<video-extension>` in the output directory,
with a numeric suffix on collision. Preserve the existing video codec policy
and copied audio behavior. Render to an invocation-owned temporary path and
atomically publish only after success; never overwrite the input video,
subtitle file, or existing output. Clean up only invocation-owned temporary
files on failure. Do not create a `subtitles` directory or a transcript JSON.

## Implementation

- Add early CLI mode selection before normal template/config/ASR validation.
  Keep the existing single-command invocation and ordinary `-i` requirement
  unchanged for existing users. Represent the direct-render request separately
  from `RunRequest`/`PreviewRequest` to avoid fake transcription fields.
- Add `render_subtitle_file()` in the FFmpeg boundary or a thin public facade
  around it. Rename private `ass_path` parameters to `subtitle_path` where
  appropriate while preserving the public `embed_subtitles()` signature.
- Reuse `probe_video_geometry()`, `validate_ffmpeg_support()`, the existing
  `subtitles` filter graph, and atomic/collision-safe video publication.
  Ensure paths with spaces, quotes, colons, Unicode, and backslashes are passed
  as data through the current FFmpeg wrapper, not through shell strings.
- Surface missing FFmpeg/libass, invalid media, missing fonts directory,
  malformed subtitles, and output write failures as actionable domain errors.
  Retain the original exception chain for debugging.

## Implementation tasks

- [ ] Add validated external subtitle file and video inputs plus a dedicated
  request/public API; preserve the existing ASS-only positional API.
- [ ] Generalize the private FFmpeg subtitle-file path and add CLI dispatch,
  conflicts, output naming, and failure cleanup.
- [ ] Cover real SRT and ASS rendering, authored ASS style preservation, audio
  copying, geometry, no-ASR-import behavior, and collisions.
- [ ] Update README, PRD, architecture, CLI help, AGENTS map if module
  ownership changes, and this package's plan status during implementation.

## Verification

Hermetic tests in `tests/test_subtitler.py` and `tests/test_cli.py` must cover
supported/unsupported extensions, case-insensitive suffixes, empty/missing
files, directories, invalid video, mode conflicts, default-valued explicit
ASR/style flags, optional fonts directory, FFmpeg command construction,
quoted/Unicode paths, copied audio selection, unique output names, atomic
publish failure, input immutability, and cleanup. In a fresh process, this
mode must not import WhisperX, PyTorch, or another ASR runtime.

Opt-in integration tests should burn short non-sensitive SRT and ASS fixtures
into a video with and without audio. Probe the result for expected stream,
dimensions, duration, and copied audio; inspect frames during and outside a
cue. For ASS, use a distinctive color or placement and verify that the
authored style remains visible. Include a malformed-file FFmpeg failure and
confirm no finished output appears. No transcription or model download is
required.

Run after implementation:

```sh
python -m pytest tests/test_subtitler.py tests/test_cli.py tests/test_integration.py
python -m pytest
python -m pytest -m integration tests/test_integration.py
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Record actual FFmpeg/libass version and visual checks. Update README examples,
command reference, requirements, output layout, and limitations; add a PRD
requirement and acceptance criteria; document the new FFmpeg boundary path,
style ownership, errors, and artifact lifecycle in architecture. No dependency
change is expected.

## Commit and pull-request plan

Suggested branch: `feat/external-subtitle-rendering` from updated `main`.

Suggested commits:

1. `feat: render external SRT and ASS files` — API, FFmpeg boundary, and tests.
2. `feat: expose external subtitle rendering in CLI` — mode dispatch and tests.
3. `docs: document external subtitle rendering` — public docs and plan status.

Suggested draft PR: `feat: render external SRT and ASS subtitles`, base `main`.
Link this plan; explain input/style/output contracts, verification commands
actually run, documentation, and remaining platform/font risks. Finish local
verification before Git delivery. After explicit delivery confirmation, stage
only scoped files. In the final pre-PR documentation commit, mark this
plan/package `In review` and record the branch as delivery reference; push
before opening the PR. After an authoritative merge, mark `Done` and replace
the branch with the merged PR link.

## Acceptance criteria

- A valid SRT and a valid ASS each render onto a copied video without ASR;
  existing input files remain byte-for-byte unchanged.
- External ASS styling remains authored; SRT follows documented FFmpeg/libass
  default presentation. Existing normal rendering and previews are unchanged.
- Invalid paths, extensions, conflicts, malformed content, missing FFmpeg, and
  output failures produce actionable errors without a published partial video.
- Repeated runs publish distinct video paths, preserve copied audio and
  autorotated geometry, and never delete unrelated files.
