# Animated preview clip with simulated word timing

Status: Planned

Depends on:

- [Multiline capacity](00-multiline-capacity.md).
- [Independent animations](../subtitle-templates/03-cue-animations-and-animated-templates.md).
- [Unified vector box](../subtitle-backdrops/00-unified-vector-box.md).

## Objective and scope

Export a short silent MP4 showing one subtitle's cue and word animations using
the selected template, overrides, and sample text. Use deterministic simulated
word times without WhisperX, PyTorch, speech synthesis, or network access.

Keep `--preview-layout` as the static PNG mode. Exclude GUI/player controls,
GIF, real transcript import, multiple cues, moving-background excerpts,
audio, and per-frame image export from this increment.

The user accepted clips, simulated times, and one cue. The numeric defaults
and frozen-background policy below are initial implementation assumptions,
chosen to make the first version concrete and reproducible.

## Public interface and compatibility

```sh
multisubs -i video.mp4 --template word-focus --preview-animation \
  --preview-text "Example subtitle animation, with simulated timing." \
  --preview-duration 4s --preview-at 00:00:10.500
```

- `--preview-animation`: mutually exclusive with `--preview-layout`.
- `--preview-duration`: cue duration, default `4s`; accept `ms`/`s`, whole
  milliseconds, 1–15 seconds inclusive. Reject bare/nonfinite/negative values.
  This is separate from animation-phase duration limits. Require clip mode.
- Reuse `--preview-text`, `--preview-at`, and `--preview-guides` in both modes.
  Reject these without a preview mode, as today. Keep existing PNG defaults.
- Capture one uncaptioned source frame at `--preview-at` (existing midpoint or
  zero default), then freeze it for the clip. This timestamp selects background
  only; the animation clock starts at zero. Fail clearly if no frame is decoded.
- Add 500ms before and after the cue. Default total duration: 5 seconds;
  cue interval: [500ms, 4500ms). No automatic loop or repetition.
- Output `<video-stem>-subtitle-animation-preview.mp4`, collision-safe in the
  requested output directory. One video stream, no audio, 30fps, H.264,
  yuv420p, faststart. Duration tolerance: one output frame.
- Preserve autorotated geometry; for odd dimensions use a documented compatible
  pixel format/encoder path (yuv444p) without stretching or changing ASS canvas.
  Check encoder availability and fail with actionable guidance if unavailable.
- Reject `--keep-transcriptions` in either preview mode. Treat language/model/
  task as preview-ignored options consistently with PNG; do not trigger speech
  validation/imports, including word-animation translation restrictions here.
- Success/progress output identifies the MP4 and explicitly says timings are
  simulated, not synchronized to source speech. Guides also identify simulation
  when enabled; do not add mandatory text overlays to the clip itself.

No retained JSON/SRT/ASS, template schema change, or change to public
`generate_transcriptions`/`embed_subtitles` signatures. Extend preview request
types with backward-compatible defaults or use a dedicated typed clip request.

## Text and deterministic timing contract

1. Normalize and apply display casing before measurement. Select the same first
   fitting cue as PNG using Plan 0. Report when a sample was shortened without
   logging its private contents. Simulate only the selected display text.
2. Preserve fragment reconstruction and word identity across line breaks.
   Reuse Unicode-aware lexical/grapheme helpers; punctuation attaches to its
   word, CJK without spaces uses grapheme units, combining/ZWJ clusters remain
   intact, and punctuation-only nonempty text remains renderable.
3. Give each unit weight `max(1, non-punctuation grapheme count)`. Reserve gaps
   after nonfinal units: 150ms for sentence endings, 80ms for clause endings,
   otherwise 40ms. If total gaps exceed 20% of cue duration, scale them down
   proportionally. No gap after the last unit.
4. Allocate the remaining duration by weights with integer largest-remainder
   rounding and source-order tie breaks. Work in ASS centiseconds after
   deterministic duration quantization; allocate at least one centisecond per
   unit. If that is impossible, fail with guidance to increase duration or
   shorten text rather than silently dropping units or extending the clip.
5. First word starts at cue start; final word ends at cue end. Intervals are
   positive, ordered, nonoverlapping, and contained in the cue. Same selected
   text and duration produce identical timing, independent of machine speed.
   Document rounding between millisecond CLI input and ASS centiseconds.
6. Pass typed `KaraokeCue`/display fragments into the production ASS compiler
   with animation enabled. Preserve independent active-word/progressive modes
   and existing phase shortening; do not stretch effects to fill the clip.

Simulation is confined to this preview mode. Missing real alignment in normal
transcription must still fall back without invented timestamps. PNG keeps its
first-word/half-cue representative state with animation suppressed. Historical
plans excluding video preview remain historical; current docs must distinguish
these two modes when this feature is delivered.

## Component responsibilities and tasks

- [ ] `config.py`/`models.py`: typed preview mode, duration defaults/validation,
  and a pure simulated timeline contract distinct from speech alignment.
- [ ] `cli.py`: explicit mode conflicts, early preview dispatch, progress,
  collision-safe output lifecycle, and no transcription-runtime imports.
- [ ] `preview.py`: share text preparation with PNG; build the selected cue's
  simulated timing and clip ASS without `_karaoke_preview_cue` static behavior.
- [ ] Reuse `animation.py` normalization and `ass.py` events unchanged where
  possible. Extract pure helpers if needed; do not import model runtime to
  synthesize a demonstration timeline or create a second effects renderer.
- [ ] `subtitler.py`: extract an uncaptioned frame, generate a zero-based
  repeated-frame timeline, then apply production subtitles/font/geometry options
  and encode MP4. Freezing must happen before subtitles so effects still move.
- [ ] Validate scalar errors before probing; validate geometry/frame/encoder
  prerequisites before rendering. Keep structured FFmpeg arguments, bounded
  diagnostics, and actionable RenderingError/ArtifactError boundaries.
- [ ] Publish only a complete clip, retry collision naming at publication,
  preserve existing media, and clean temporary frame/ASS/partial MP4 on all
  success/failure paths. Keep filenames and transcript text out of filter code.
- [ ] Bound input/timeline/event work with existing renderer budgets and the
  duration limit; no per-frame ASS events or model/cache downloads.
- [ ] Add tests and update current docs and roadmap before Git delivery.

## Verification and acceptance criteria

Unit coverage in `test_preview.py`, `test_cli.py`, `test_animation.py`, and
`test_subtitler.py` must prove mode conflicts, duration limits, frozen-frame
timestamp independence, positive exact-sum intervals, repeatability, punctuation
gaps, short/long/Unicode samples, both independent word modes, shortened phases,
no speech imports, collision handling, and cleanup after every failing stage.
PNG remains one motion-suppressed image with its existing naming and semantics.

Real FFmpeg tests in `test_preview_integration.py` must probe duration, stream
count, codec, frame rate, geometry, and no audio. Use synthetic non-sensitive
backgrounds with bundled fonts; test landscape, portrait, odd dimensions,
rotation, and paths containing spaces/Unicode. Check pre/post cue frames have
no added subtitles, and compare frames at cue entrance, word changes, gaps,
emphasis, and exit to production ASS rendering with the identical synthetic
timeline. Use pixel tolerances for lossy encoding, not byte equality.

Manually inspect `default`, `cinematic-fade`, `lower-third-slide`, `impact-yellow`,
`soft-zoom`, `neon-karaoke`, and `word-focus`, including text-only/box-only
motion, glyph outlines, translucent surfaces, and mixed word modes. Record
font/FFmpeg versions, timing, event counts, and frames showing transitions.
Keep review clips temporary/ignored; skipped integrations are missing evidence.

Run:

```sh
python -m pytest tests/test_preview.py tests/test_cli.py tests/test_animation.py tests/test_ass.py tests/test_subtitler.py
python -m pytest -m integration tests/test_preview_integration.py tests/test_integration.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Also perform clean build/Twine/artifact audits from the delivery gate and a
wheel-installed clip smoke test outside the checkout. No full transcription.

## Documentation and delivery

Update README commands, duration/background semantics, output naming, encoder
requirements, simulation limitations, and PNG versus MP4 examples. Extend PRD
FR-16 and preview acceptance criteria; explicitly scope the synthetic-time
exception. Update architecture request flow, timeline ownership, output lifecycle,
and FFmpeg boundary; conventions must distinguish simulated demonstrations from
real alignment without weakening normal fallback rules.

Branch: `feat/animation-preview-clip`, from updated main after Plan 0 merges.
Suggested commits: `feat: add deterministic animation preview timelines`,
`feat: render silent animation preview clips`, and
`docs: document animated subtitle previews` (each behavior commit includes tests).
Draft PR title: `feat: add animation preview clips with simulated word timing`.
Link this plan and report interfaces, exclusions, evidence, actual checks,
encoder compatibility and simulation limitations. Follow the
[dashboard delivery lifecycle](README.md); no merge/release is implied.

Main risks are confusing simulated timing with speech sync, differing Unicode
unit mapping, heavy effect expansion, and encoder/player compatibility for odd
dimensions. Address these with explicit messaging, reconstruction checks, event
budgets, and media probes. Roll back via a focused revert PR; no persistent
data migration is introduced.
