# Plan 0: word-timed karaoke highlighting

Status: Planned

Depends on:

- [Shared subtitle-layout foundation](../subtitle-positioning/00-foundation.md)
- [Adaptive line wrapping](../subtitle-positioning/06-adaptive-line-wrapping.md)
- [Breaking CLI cutover](../subtitle-positioning/README.md#breaking-cli-cutover)

## Objective

Let users opt into subtitles that progressively highlight complete words at
their WhisperX alignment times while preserving readable multiword cues,
ordinary subtitle positioning, and portable plain-text artifacts.

## Scope

Included:

- An opt-in word-level karaoke effect for transcription runs.
- One configurable highlight color; the resolved normal text color is the
  inactive color.
- Deterministic ASS `\k` timing compiled from validated word start times.
- A plain-cue fallback with a visible warning when an individual cue cannot be
  mapped losslessly to usable word timings.
- Additive JSON rendering metadata that records the resolved effect and fallback
  count.
- Hermetic serializer and timing tests plus opt-in FFmpeg/libass render checks.

Excluded:

- Syllable-, phoneme-, or character-level alignment.
- Smooth left-to-right `\kf` sweeps, bouncing or scaling words, fades, scrolling
  lyrics, current-word-only overlays, and multiple simultaneous karaoke styles.
- Karaoke on translated output in the first version.
- A manual timing editor, lyrics import, audio-only workflow, or correction UI.
- Karaoke markup in SRT or user-authored raw ASS override tags.

## Decisions and constraints

- Plain subtitles remain the default; `--karaoke` is explicit and opt-in.
- The first effect uses ASS `\k`, which displays a syllable or word with the
  secondary color before its interval and switches it immediately to the primary
  color when that interval begins. Durations are centiseconds, as specified by
  the [Aegisub ASS karaoke tag reference](https://aeg-dev.github.io/AegiSite/docs/3.0/ASS_Tags/#karaoke-effect).
- A complete aligned word is the smallest highlighted unit. The implementation
  must not claim syllable timing that WhisperX did not supply.
- Translation is rejected with `--karaoke` before model loading. The current
  translation path does not guarantee that source-language alignment timestamps
  map losslessly onto the English display words.
- Generated ASS tags are trusted compiler output. Transcript text, punctuation,
  and separators remain untrusted data and are escaped independently before
  composition.
- No word timestamp is synthesized. A cue that lacks a complete, chronological,
  lossless word mapping renders as an ordinary cue, increments the fallback
  count, and contributes to one concise user-facing warning for the run.
- The feature adds no runtime dependency. FFmpeg with libass remains the render
  boundary and must be exercised by an opt-in integration test.
- Effect preparation and serialization must be linear in the number of displayed
  words. Avoid one ASS Dialogue event per word and avoid duplicating the full cue
  text in layered events.

## Public interface and contracts

### CLI and validation

Add these options after the subtitle-positioning CLI cutover:

~~~
--karaoke
--karaoke-highlight-color '#FFD54F'
~~~

- `--karaoke` enables the effect.
- `--karaoke-highlight-color` accepts the same semantic `#RRGGBB` or
  `#RRGGBBAA` color form as the post-cutover `--text-color` option. Its default
  is resolved only when karaoke is enabled.
- Supplying a karaoke-specific color without `--karaoke` is an argument error.
- Combining `--karaoke` with `--task translate` is an argument error in this
  increment.
- Direct option errors must be reported before video probing, WhisperX imports,
  model loading, or output-directory mutation.
- Do not add `--style-karaoke-*` compatibility flags.

### Python configuration

- Add an immutable `SubtitleEffects` contract to `SubtitleConfig` and represent
  the resolved karaoke configuration as typed values rather than an ASS tag or
  free-form mapping.
- Keep effect configuration flowing through `RunRequest`, artifact preparation,
  JSON metadata, and `write_ass()` without adding parallel boolean parameters.
- Preserve the existing public artifact-writing return value and output paths.
- Keep new compiler helpers private unless a supported programmatic effects API
  is intentionally documented.

### Cue and timing contract

Extend the display-cue result introduced by adaptive wrapping so it preserves:

- unwrapped semantic text;
- escaped-independent display fragments and intentional line separators;
- the ordered source word records that produced each displayed word fragment;
- cue start and end timestamps;
- generated placement data, independently from text and effects.

Karaoke preparation must map displayed words back to source word records without
re-tokenizing the final string. Punctuation already attached to a WhisperX word
stays highlighted with that word. Untimed separators, spaces, and intentional
line breaks retain their exact layout representation and receive no independent
timing.

For each eligible cue:

1. Quantize the cue start, each word start, and cue end to absolute ASS
   centiseconds using the serializer's established rounding rule.
2. Require the first displayed word to start at the quantized cue start. A cue
   with a leading untimed interval uses the plain fallback rather than receiving
   an invisible or invented timing token.
3. Convert the ordered absolute boundaries to non-negative relative durations.
   Each word's duration ends at the next word's start; the last ends at the cue
   end. This preserves inter-word pauses without inventing an activation time.
4. Allow a zero-centisecond duration caused by legitimate quantization instead
   of shifting later boundaries or lengthening the event.
5. Prove that durations are monotonic and sum exactly to the quantized Dialogue
   duration. Fall back to a plain cue if the proof fails.
6. Compose trusted color and `\kN` override blocks around independently escaped
   display fragments. Never run the completed tagged line through the ordinary
   text-escaping function.

The display mapping must preserve CJK text without adding spaces, retain RTL
logical order, and keep combining marks and emoji in their original fragment.
Support claims for complex scripts require a real libass render with the chosen
controlled font; an unsafe or lossy mapping must use the documented fallback.

### JSON, SRT, ASS, and output layout

- JSON retains plain semantic/display text and original aligned-word metadata;
  it never stores generated ASS strings. Add an `effects.karaoke` object under
  rendering metadata with `enabled`, resolved mode (`word`), normal color,
  highlight color, and `fallback_cues`. This is an additive schema-version 1
  change.
- SRT remains plain text with the same cue times and intentional visual line
  breaks. It cannot reproduce the effect and must contain no braces or `\k`
  markup generated by this feature.
- ASS remains the authoritative effect artifact. When karaoke is disabled, its
  dialogue serialization must remain byte-for-byte compatible for equivalent
  configuration. When enabled, one Dialogue event per cue contains validated
  color overrides and one `\k` duration per displayed timed word.
- Retained ASS files contain editable karaoke tags. Temporary SRT and ASS cleanup
  and collision-safe publication remain unchanged.
- Rendered video names, directories, codec policy, stream mapping, and FFmpeg
  invocation are unaffected.

### Diagnostics and privacy

- Report one aggregate warning after effect preparation when one or more cues
  use the plain fallback; do not print transcript contents in the warning.
- The warning identifies the count and explains that timestamps were not
  invented. It does not turn an otherwise valid transcription into a failed run.
- No new transcript, media, model, or path data is sent to an external service.

## Implementation

### Typed effects and CLI

- Extend `multisubs/models.py` with the immutable effects contract and add it to
  `SubtitleConfig`.
- Resolve defaults and validate semantic colors in `multisubs/config.py`; ASS
  BGR and inverted-alpha conversion remains private to the ASS compiler.
- Add the two CLI options and cross-option validation in `multisubs/cli.py`.
  Update request fixtures and prove invalid combinations fail before expensive
  boundaries.

### Display-word mapping

- Build on the semantic/display cue separation from adaptive wrapping rather
  than parsing `display_text` after wrapping.
- Introduce a small typed display fragment or token model that can distinguish
  timed words, spaces, punctuation/separators, and intentional line breaks while
  reconstructing the exact plain display text.
- Preserve original usable word metadata in JSON, but expose only validated
  start/end values to the effect compiler.
- Prepare all display cues and an immutable effect report before writing JSON,
  SRT, or ASS so the three serializers observe one resolved outcome.

### ASS compilation

- Keep karaoke timing and override compilation in `multisubs/ass.py` or a focused
  ASS compiler module if `ass.py` would otherwise mix validation, token mapping,
  and serialization responsibilities.
- Add a pure absolute-boundary-to-duration function and test centisecond rollover,
  rounding, zero durations, pauses, overlaps, and long cues.
- Emit validated primary/secondary color overrides once per eligible Dialogue
  event, followed by generated `\k` blocks at timed word boundaries.
- Escape each transcript-derived fragment before composition. Ensure literal
  braces, backslashes, text resembling `\k`, commas, and newlines cannot create
  or terminate an override block.
- Keep plain fallback Dialogue events on the same style, placement, timing, and
  display text as non-karaoke output.

### Failure and compatibility behavior

- Treat missing words, invalid timestamps, non-lossless display mapping, or an
  impossible quantized duration sequence as per-cue fallback conditions.
- Keep true artifact I/O failures and invalid typed configuration as fatal
  project errors with their existing exception boundaries.
- Do not change WhisperX model selection, alignment calls, cue-boundary
  priorities, geometry probing, or FFmpeg rendering policy for this feature.

## Implementation tasks

- [ ] Add typed subtitle-effects and karaoke configuration models.
- [ ] Add CLI parsing, semantic color validation, and translation/color
  cross-option errors before expensive work.
- [ ] Extend display cues with a lossless word-to-fragment mapping.
- [ ] Prepare karaoke eligibility and aggregate fallback metadata once per run.
- [ ] Implement deterministic centisecond duration allocation.
- [ ] Compile trusted ASS color and `\k` tags around separately escaped text.
- [ ] Preserve byte-for-byte plain ASS output when the feature is disabled.
- [ ] Keep SRT plain and add resolved effect metadata to JSON.
- [ ] Add hermetic CLI, model, timing, escaping, JSON, SRT, and ASS tests.
- [ ] Add controlled-font FFmpeg/libass rendering coverage.
- [ ] Update README.md, docs/prd.md, docs/architecture.md, and relevant
  conventions.
- [ ] Update this dashboard to In review and add the pull-request link before
  requesting final review.

## Unit tests

### CLI and configuration

- Defaults leave karaoke disabled and preserve current artifact output.
- `--karaoke` resolves word mode, normal text color, and default highlight color.
- Six- and eight-digit highlight colors convert correctly at the ASS boundary.
- Invalid color, a color without `--karaoke`, and karaoke with translation are
  parser errors before probing or model loading.
- Typed configurations are immutable, independently validated, and represented
  consistently in request and JSON metadata.

### Timing and token mapping

- One word, several words, exact centiseconds, fractional centiseconds, minute
  rollover, long pauses, a leading untimed interval, overlapping word ends,
  equal starts, and a zero-length quantized interval.
- The sum of emitted durations equals the quantized cue duration with no
  cumulative rounding drift.
- Word activation boundaries equal quantized aligned starts; word end timestamps
  are validated but never used to invent the next activation boundary.
- Punctuation attached to a word, explicit line breaks, multiple scripts,
  combining marks, emoji, RTL logical order, and CJK text without inserted spaces.
- Reconstructing the plain text from display fragments exactly matches the SRT
  display text and the ASS dialogue after generated markup is removed.

### Serialization and fallback

- Eligible cues receive exactly one generated timing block per displayed timed
  word and one validated color setup.
- Braces, backslashes, literal `\k20`, commas, CRLF, and Unicode remain literal
  subtitle content and cannot inject an ASS override.
- Missing, partial, non-chronological, non-finite, or lossy word mappings produce
  plain cues, one aggregate warning, and the correct JSON fallback count.
- Mixed runs can contain eligible and fallback cues without changing cue IDs,
  timestamps, order, text, placement, or cleanup behavior.
- SRT and JSON contain no generated ASS override text.
- Disabled karaoke matches the existing plain ASS golden fixture exactly.

Property checks should generate chronological word starts and prove duration
conservation, non-negative durations, exact text reconstruction, and absence of
unescaped override syntax across arbitrary Unicode fragments.

## Integration and manual verification

Add an opt-in FFmpeg/libass test with a short synthetic video and a controlled,
redistributable font. Render frames:

- before the first word activates;
- during at least two different word intervals;
- after the final word activates;
- from an equivalent run without karaoke.

Assert that only the expected word regions change from normal to highlight
color, prior words remain highlighted, positioning and line breaks stay stable,
and the non-karaoke reference remains unchanged. Exercise at least landscape and
portrait canvases, one two-line cue, a meaningful pause, and literal ASS-like
text.

Manually inspect Portuguese, CJK, RTL, combining-mark, and emoji fixtures with a
font that covers each script. Record unsupported shaping/font coverage as a
limitation rather than approving a rendering claim from ASS text inspection
alone. Attach representative before/during/after frames and the small retained
ASS excerpt to the pull request; do not commit generated media.

## Documentation

- Add the two options, quoting example, translation restriction, fallback
  behavior, and retained-ASS behavior to README.md.
- Add a functional requirement and acceptance criterion for opt-in word-timed
  highlighting to docs/prd.md; keep richer animated karaoke styles out of scope.
- Update docs/architecture.md with the effects configuration, display-fragment
  mapping, duration allocation, JSON metadata, plain SRT contract, and ASS
  compilation boundary.
- Update docs/conventions.md with the reusable rule that generated ASS overrides
  and untrusted transcript fragments must be composed through separate typed
  paths, if that rule is not already sufficiently explicit.
- Keep `multisubs --help` wording user-facing: describe highlighted words and
  color formats without requiring knowledge of `\k`, primary color, or secondary
  color.

## Commit and pull-request plan

Suggested branch:

~~~
feat/karaoke-subtitles
~~~

Suggested commits:

1. `refactor: preserve timed words through subtitle layout`
   - Add the typed display-fragment mapping and exact reconstruction tests
     without changing plain output.
2. `feat: compile word-timed karaoke subtitles`
   - Add effects configuration, duration allocation, safe ASS compilation,
     metadata, fallback behavior, and focused unit tests.
3. `feat: expose karaoke subtitle controls`
   - Add CLI options, early cross-option validation, help text, and orchestration
     coverage.
4. `test: render word-timed karaoke subtitles`
   - Add opt-in controlled-font FFmpeg/libass verification and visual fixtures
     that remain untracked.
5. `docs: document word-timed karaoke subtitles`
   - Update user, product, architecture, convention, and roadmap documentation.

Suggested pull request:

~~~
Title: feat: add word-timed karaoke subtitles
Base: main
~~~

The pull request must link this plan, state that translation and richer
animations are excluded, show the plain-output compatibility result, describe
the per-cue fallback policy, and include before/during/after render evidence.

Before requesting review:

~~~
python -m pytest tests/test_ass.py tests/test_config.py tests/test_cli.py tests/test_transcriber.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff check .
python -m pyright
git diff --check
git status --short
~~~

Run the repository's opt-in FFmpeg/libass integration marker separately and
record the exact command, FFmpeg/libass versions, font, operating system, and
result in the pull-request description. Build and inspect a wheel if the CLI
cutover or package metadata changes in the implementation branch.

Before staging each commit, inspect `git status --short`, `git diff --check`, and
the relevant diff. Stage only the logical files for that commit. Before opening
the pull request, inspect `git log --oneline origin/main..HEAD` and
`git diff --stat origin/main...HEAD`; do not use an unreviewed generated PR body.

## Acceptance criteria

- A transcription run with `--karaoke` highlights each eligible displayed word
  at its quantized aligned start time and keeps prior words highlighted.
- Plain subtitles remain the default and equivalent non-karaoke ASS output is
  byte-for-byte unchanged.
- Users can select a validated semantic highlight color without using ASS color
  syntax or `--style-*` flags.
- Karaoke translation and meaningless option combinations fail before video
  probing or model loading with actionable messages.
- Generated word durations are non-negative, conserve the quantized cue
  duration, and never rely on invented word timestamps.
- Ineligible cues render as ordinary subtitles, the run reports one aggregate
  warning, and JSON records the exact fallback count.
- SRT contains only plain display text; JSON contains no generated ASS tags; ASS
  contains only trusted generated tags around independently escaped text.
- Text, punctuation, word order, cue IDs, cue times, line breaks, placement,
  output names, retention, and cleanup remain consistent across artifacts.
- Controlled FFmpeg/libass tests demonstrate the expected color transition and
  stable layout in landscape and portrait output.
- README.md, docs/prd.md, docs/architecture.md, relevant conventions, and both
  plan dashboards describe the shipped behavior and final status.
