# Generate SRT, ASS, and a subtitled video from timed-cue JSON

Status: Proposed

Depends on:

- Existing cue layout, source mapping, animation, ASS, FFmpeg, and
  artifact publication contracts in [architecture.md](../../architecture.md).

## Objective

Let a caller supply known cue and word times in a small public JSON format and
generate styled SRT and ASS files without transcribing, translating, or
loading an ASR runtime. The same invocation burns the generated ASS into a
copy of the required input video. The caller owns the timing; multisubs owns
validation, layout, encoding, and rendering.

## Scope

Included:

- A strict, versioned input document matching the example below.
- A supported Python function and an opt-in CLI mode for subtitle generation
  and video rendering.
- The current semantic style, template, font, layout, casing, and animation
  pipeline, including its documented shaping fallback.
- Collision-safe publication of the SRT/ASS pair and the video rendered
  from that generated ASS, all with the same stem.

Excluded:

- ASR, translation, creation of a transcription JSON, and inference of word
  times or cue boundaries.
- Reading the retained transcription JSON schema 3 as this schema 1 format.
  The development-only `scripts/replay_subtitle_layout.py` remains a separate
  diagnostic tool and is not promoted into the public input contract.
- Remote JSON, embedded file paths, per-cue styles, speaker tracks, arbitrary
  ASS tags, or a new template schema.

## Decisions and constraints

- Input `schema_version` is the exact JSON integer `1`; it is independent of
  retained transcription schema 3 and custom-template schema 1.
- `language` is a required language label, not an ASR capability request.
  Accept a 2- or 3-letter ASCII primary subtag with optional 2- through
  8-character ASCII alphanumeric subtags separated by hyphens (35 characters
  total at most). Preserve it for display, normalize it for safe file naming,
  and use its primary subtag for linguistic layout. Do not restrict it to any
  ASR backend language catalog.
- `cues` is a nonempty ordered array. Every cue has finite nonnegative numeric
  `start`/`end` seconds with `start < end`, nonempty `text`, and a nonempty
  `words` array. Every word has `start`, `end`, and nonempty `text` with
  `cue.start <= word.start < word.end <= cue.end`; words are chronological and
  do not overlap within one cue. Cue overlaps may remain valid and preserve
  input order; document how the renderer displays them.
- Word strings must map in order to exact, nonoverlapping spans of cue `text`.
  Intervening whitespace is preserved verbatim. Every non-whitespace source
  character, including punctuation, must belong to a word span. Reject an
  incomplete or ambiguous mapping with a cue/word index, rather than silently
  fabricating separators or timing. Preserve Unicode graphemes, NBSP, and
  source casing through the existing mapping and display rules.
- Preserve the supplied cue and word times. Layout may insert visual line
  breaks; it must not split one timed cue into new cues without corresponding
  supplied times. Reject an unfit cue with an actionable envelope diagnostic.
  SRT contains cue times and displayed text; ASS may use supplied word times
  for enabled effects. Quantization must never invent a positive word interval
  when the supplied timeline cannot represent one safely.
- Require a local input video. Probe its dimensions, rotation, sample aspect
  ratio, and display aspect ratio through the existing geometry boundary; use
  that same normalized geometry for ASS layout and final FFmpeg rendering.
  Do not accept separate canvas dimensions or infer geometry from JSON. Fail
  early if the known video duration ends before a cue.
- Limit JSON input to 16 MiB, nesting to 16 levels, cues to 20,000, words
  to 100,000, cumulative text to 1,000,000 characters, and times to 24 hours.
  Reject duplicate/unknown keys, booleans as numbers, NaN/Infinity, malformed
  UTF-8, and unsupported versions. Apply limits before expensive measurement
  or output creation. Never echo full input text in routine errors.

## Public interface and contracts

Example input:

```json
{
  "schema_version": 1,
  "language": "pt",
  "cues": [
    {
      "start": 0.4,
      "end": 1.8,
      "text": "Isso é importante",
      "words": [
        {"start": 0.4, "end": 0.7, "text": "Isso"},
        {"start": 0.8, "end": 1.0, "text": "é"},
        {"start": 1.1, "end": 1.8, "text": "importante"}
      ]
    }
  ]
}
```

Proposed Python API, exported lazily from `multisubs.__init__`:

```python
generate_subtitles_from_json(
    cues_json_path: str | Path,
    video_path: str | Path,
    output_dir: str | Path,
    *,
    subtitle_config: SubtitleConfig | None = None,
) -> GeneratedSubtitleArtifacts
```

`GeneratedSubtitleArtifacts` is a named, typed result with `srt_path`,
`ass_path`, and `video_path: Path`. The function probes the supplied video
once and renders it using the ASS file it just generated. It accepts a
validated semantic config; CLI template resolution stays at the CLI boundary.
Input JSON and video are never rewritten.

Proposed CLI examples:

```sh
multisubs -i video.mp4 --cues-json cues.json -o output --template amber-word
```

`--cues-json` selects the timed-cue mode and requires the existing `-i`
video input. It generates SRT/ASS and renders the video from the generated
ASS. Reject explicit ASR/model/task/language options,
`--keep-transcriptions`, preview options, and the external-subtitle-file mode
before probing or loading a model. Existing style, template, font, layout, and
animation options remain valid for this mode. Check explicit option presence,
not just values equal to defaults.

Publish `<video-stem>-<language>.srt`, `.ass`, and a rendered
`<video-stem>-<language><video-extension>`. Reserve one common numeric suffix
when any target collides, using the existing safe filename helper. Build
artifacts in an invocation-owned temporary area; render from the generated
ASS before publication, then publish the complete set with rollback if a
later publication fails. Return/print every published path. No JSON is
published, and `--keep-transcriptions` is inapplicable.

## Implementation

- Add a focused `multisubs/timed_cues.py` reader for the public JSON contract,
  typed cue/word values, bounded parsing, and exact source-span validation.
  Do not pass user-owned mappings or private compiler keys to `ass.py`.
- Extract or call the shared layout and SRT/ASS writer core below
  `write_transcription_artifacts()` without manufacturing a
  `TranscriptDocument` or ASR metadata. Keep the existing schema-3 writer and
  tuple-returning `generate_transcriptions()` compatible.
- Resolve geometry and wrapping metrics once; apply text case before measuring
  and keep source identity for each timed word. Reuse the production shaping
  decision and animation compiler. Call the existing ASS burn boundary with
  the newly generated ASS, resolved video geometry, and selected font
  directory. Keep FFmpeg probing and rendering in `subtitler.py`.
- Add a request type and early CLI dispatch. Validate mode conflicts before
  probing; validate parsed cues before output creation; preserve existing
  normal and preview paths. Use the established atomic/collision-safe helpers.

## Implementation tasks

- [ ] Implement bounded schema-1 parsing, exact word-to-cue mapping, immutable
  typed values, and precise validation errors with focused unit tests.
- [ ] Separate shared cue layout and SRT/ASS serialization from transcription
  metadata; implement the public API and named result without changing current
  ASR output or retained JSON schema.
- [ ] Add `--cues-json` dispatch, style/template reuse, mode conflicts,
  video rendering from generated ASS, and collision-safe three-artifact
  publication.
- [ ] Cover animation timing, Unicode text, wrapping, font resolution,
  malformed input, output failure, and no-ASR-import behavior.
- [ ] Update README, PRD, architecture, CLI help, public API docs, AGENTS map,
  and this package's plan status when implementation begins/completes.

## Verification

Unit tests in a new `tests/test_timed_cues.py` and affected existing suites
must cover the example, adjacent and overlapping cues, whitespace and
punctuation mapping, CJK/emoji/combining sequences, text-case changes,
quantization boundaries, malformed types/times/order, unknown or duplicate
keys, resource bounds, unsupported version, missing/invalid video, unfit
layout, collision naming, partial publication failure, and input
immutability. Prove SRT and ASS use the same logical cue text, preserve
supplied timing, and that video rendering consumes the newly generated ASS.
A fresh process must complete without importing WhisperX, PyTorch, or another ASR runtime.

Integration verification uses a small non-sensitive video and FFmpeg to
confirm the generated ASS canvas matches the video geometry, inspect the
rendered video during and outside a cue, and verify word effects, copied
audio, rotation, and sample aspect ratio. No full transcription or model
download is needed.

Run after implementation:

```sh
python -m pytest tests/test_timed_cues.py tests/test_transcriber.py tests/test_ass.py tests/test_cli.py tests/test_layout.py tests/test_text_segmentation.py
python -m pytest
python -m pytest -m integration tests/test_integration.py
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Record which FFmpeg and visual checks actually ran and any unavailable
integration evidence. Update the README command reference, examples, and
generated-files section; add a product requirement and acceptance criteria in
`docs/prd.md`; document the independent input schema, component boundary,
timing/layout semantics, and output lifecycle in `docs/architecture.md`.

## Commit and pull-request plan

Suggested branch: `feat/timed-cue-json-rendering` from updated `main`.

Suggested commits:

1. `feat: validate public timed cue JSON` — schema, typed values, and tests.
2. `feat: render timed cues without ASR` — shared writer, API, CLI,
   generated-ASS video rendering, publication, and behavioral tests.
3. `docs: document timed cue file generation` — public docs and plan status.

Suggested draft PR: `feat: generate subtitles from timed cue JSON`, base
`main`. Link this plan; explain schema, CLI/API/output effects, test commands
actually run, docs, and remaining risks. Finish verification before Git
delivery. After explicit delivery confirmation, stage only scoped files. In
the final pre-PR documentation commit, mark this plan/package `In review` and
record the branch as delivery reference; push before opening the PR. After an
authoritative merge, mark `Done` and replace the branch with the merged PR link.

## Acceptance criteria

- The supplied JSON and required input video generate valid SRT and ASS
  without ASR, then a copied video rendered from that same generated ASS.
  The ASS layout uses the video's normalized geometry.
- SRT preserves the cue timeline; ASS word effects follow the supplied word
  timeline or produce a documented safe fallback, never fabricated times.
- Invalid text/timing/schema/geometry fails before publication with a useful
  cue/word location, and repeated runs receive one collision-safe stem for
  all three outputs.
- Existing normal and preview behavior, retained schema-3 JSON, and existing
  public tuple returns remain compatible.
