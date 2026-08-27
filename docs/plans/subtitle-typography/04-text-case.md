# Text case

Status: Planned

Depends on:

- [Font weight](00-font-weight.md)
- [Letter spacing](01-letter-spacing.md)
- [Line height](02-line-height.md)
- [Subtitle opacity](03-opacity.md)

## Objective

Let users preserve the original transcription case or display subtitle text in
uppercase or lowercase while keeping measurement, wrapping, karaoke timing,
preview, retained artifacts, and final rendering consistent.

## Scope

Included:

- Add `--text-case {original,uppercase,lowercase}`, defaulting to `original`.
- Apply Unicode-aware Python case conversion to display fragments before width
  measurement, wrapping, line-height capacity, SRT, and ASS serialization.
- Preserve original transcription text and aligned-word metadata in JSON.
- Keep each transformed karaoke fragment associated with its original timed
  word rather than reconstructing timing from transformed strings.

Excluded:

- Title case, sentence case, small caps, per-word custom casing, and custom
  transformation rules.
- Locale-specific casing selection or a `--locale` option.
- Modifying WhisperX transcription output, language detection, timestamps, or
  alignment confidence.
- Transliteration, accent removal, normalization, spell correction, or
  punctuation rewriting.

## Decisions and constraints

- Canonical values are `original`, `uppercase`, and `lowercase`; input is
  case-insensitive and normalizes to one typed enum.
- `original` is a no-op and preserves current output. `uppercase` uses
  `str.upper()` and `lowercase` uses `str.lower()` on each display fragment.
- Python's Unicode default casing is deterministic but not locale-sensitive.
  Language-specific rules such as Turkish dotted/dotless I are an explicit
  initial limitation and must be documented rather than guessed from the
  transcription language.
- Conversion happens before measurement and wrapping because character count
  and glyph width can change, for example German `ß` becoming `SS`.
- Conversion is performed on trusted plain-text fragments before ASS escaping
  and tag assembly. User text can never become trusted ASS markup.
- Karaoke timing remains attached by fragment/word identity. Implementations
  must not split or retokenize transformed strings to recover timestamps.
- SRT and ASS are display artifacts and therefore contain the selected case.
  The original full transcript, original segment text, and aligned words remain
  available in JSON; additive display fields and rendering metadata show the
  transformed cue text.
- This is additive and default-compatible and therefore does not require a
  major release.

## Public interface and contracts

~~~
--text-case original
--text-case uppercase
--text-case lowercase
~~~

Unknown or empty values fail through CLI/configuration validation before
ffprobe or WhisperX. Typed configuration stores a `TextCase` enum.

For `--text-case uppercase`, an original fragment such as `Olá, Straße!` is
measured, wrapped, and displayed as `OLÁ, STRASSE!`. Its original transcript
and word timing remain intact in JSON. If expansion causes the text to exceed
the resolved width or height, the normal wrapping and segment-capacity logic
creates the same next-cue behavior used for untransformed text.

JSON records the requested text-case mode and transformed display text at the
same cue or rendering-diagnostic boundary used by wrapping. It must distinguish
original transcription data from display data clearly enough that consumers do
not mistake transformed captions for WhisperX output. These additive fields
keep `schema_version` unchanged unless implementation discovers that an
existing field must change meaning; that case requires an explicit schema and
migration decision before coding.

## Implementation

- Add `TextCase` and its parser/default to `multisubs/models.py` and
  `multisubs/config.py`, then expose `--text-case` through `multisubs/cli.py`.
- Introduce one plain-text display transformation at the earliest shared point
  after transcription/alignment data is preserved but before cue measurement
  and wrapping.
- Keep transformed fragments associated with source segment and aligned-word
  identities. Preserve whitespace and punctuation exactly except for Unicode
  characters changed by the selected case operation.
- Ensure both font-aware Pillow measurement and Unicode fallback estimation
  consume transformed display text, including letter spacing and line height.
- Serialize transformed display fragments into SRT and escaped ASS text. Build
  karaoke tags around already-transformed, separately escaped word fragments.
- Reuse the same transformed cue path in preview; do not maintain a separate
  preview-only sample transformation.
- Audit `multisubs/transcriber.py` JSON fields and add explicit original versus
  display text fields or rendering metadata without silently changing the
  semantics of existing transcription fields.

## Implementation tasks

- [ ] Add the `TextCase` enum, default, strict parser, and typed revalidation.
- [ ] Wire `--text-case` into CLI help and request construction.
- [ ] Add one shared Unicode display-fragment transformer before measurement
  and wrapping while preserving original source data.
- [ ] Use transformed fragments in normal cues, both karaoke modes, SRT, ASS,
  preview, width measurement, and height capacity.
- [ ] Record selected mode and transformed display text in JSON without
  replacing original transcript and alignment fields.
- [ ] Add focused configuration, CLI, Unicode, wrapping, SRT, ASS, preview,
  karaoke, metadata, and default-output tests.
- [ ] Update README.md, docs/prd.md, docs/architecture.md, and package status.

## Unit tests

- Parsing of all canonical modes, case-insensitive values, the original
  default, and rejection of empty or unknown values.
- Portuguese and Latin-script uppercase/lowercase behavior with accents and
  punctuation.
- Length-changing conversion such as German `ß` to `SS`, Greek sigma forms,
  combining marks, CJK characters, emoji, and RTL text.
- Documented locale-independent behavior for Turkish dotted and dotless I.
- Width measurement and wrapping use transformed glyphs, including a fixture
  where uppercase text creates an additional line or cue.
- Height capacity clips/splits the transformed preview sample exactly like
  normal cue generation.
- Progressive and active-word karaoke preserve word timing and highlighting
  when a transformed word changes code-point count.
- Braces, backslashes, line breaks, and ASS-like input remain escaped after
  transformation and never become generated tags.
- JSON preserves original full text, segments, aligned words, timestamps, and
  confidence while recording transformed display text separately.
- Default-output regression confirming `original` preserves existing SRT, ASS,
  preview, and JSON behavior apart from documented additive metadata.

## Integration and manual verification

- Render ordinary, progressive karaoke, and active-word karaoke captions in all
  three modes and compare preview and final frames at equivalent cue times.
- Use a sample containing Portuguese accents, German `ß`, mixed scripts, emoji,
  punctuation, and an ASS-like brace sequence.
- Verify that uppercase expansion can change wrapping or cue capacity without
  changing original timestamps or losing words.
- Inspect retained JSON, SRT, and ASS to confirm original data is preserved in
  JSON while display artifacts use the selected case and safe escaping.

## Documentation

- Add `--text-case`, accepted values, default, examples, Unicode behavior, and
  locale-sensitive limitation to README command and appearance references.
- Explain that SRT and ASS are transformed display artifacts while JSON retains
  original transcription and alignment data.
- Extend FR-7 and FR-9 plus related acceptance criteria in docs/prd.md because
  case conversion can affect both cue capacity and appearance.
- Update the display-fragment, measurement, wrapping, SRT/ASS, karaoke, preview,
  and JSON contracts in docs/architecture.md.
- Update docs/conventions.md only if a reusable Unicode transformation/testing
  convention is introduced.

## Commit and pull-request plan

Suggested branch:

~~~
feat/subtitle-text-case
~~~

Suggested commits:

1. `feat: add subtitle text case controls`
   - Typed configuration, CLI, transformation pipeline, artifact/preview/JSON
     integration, and focused tests.
2. `docs: document subtitle text case`
   - README, PRD, architecture, and roadmap status.

Suggested pull request:

~~~
Title: feat: add subtitle text case controls
Base: main
~~~

Before opening the pull request:

- Run `python -m pytest tests/test_config.py tests/test_cli.py tests/test_wrapping.py tests/test_ass.py tests/test_preview.py tests/test_karaoke.py tests/test_transcriber.py`.
- Run the relevant controlled FFmpeg checks with
  `python -m pytest -m integration tests/test_integration.py -k subtitle` when
  their prerequisites are available.
- Run `python -m compileall multisubs`, `multisubs --help`,
  `python -m pytest`, `python -m ruff check .`, and `python -m pyright`.
- In the final pre-PR documentation commit, move the plan and package to
  `In review` and record `feat/subtitle-text-case` as the delivery reference.
- Push the complete branch before opening the PR; do not add a post-open commit
  solely for its number or URL.

After merge:

- Mark Plan 4 `Done`, replace the branch with the merged PR link, recalculate
  package/catalog progress, and mark the package complete if no new plan has
  been accepted.

## Acceptance criteria

- `--text-case` accepts only `original`, `uppercase`, or `lowercase`, defaults
  to `original`, and invalid input fails before video or model loading.
- Selected case is applied before measurement, wrapping, height capacity, SRT,
  ASS, preview, and final rendering.
- Length-changing Unicode conversion does not lose, duplicate, retime, or
  mis-highlight karaoke words.
- Original transcription and aligned-word data remain unchanged in JSON, while
  transformed display text and the selected mode are explicitly recorded.
- Plain text is transformed before escaping, and generated ASS tags remain
  structurally separate from user content.
- Default commands remain visually and behaviorally unchanged.
