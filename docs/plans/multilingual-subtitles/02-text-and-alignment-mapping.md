# Preserve source text independently of alignment units

Status: Done

Delivery: [PR #77](https://github.com/denilson-santos/multisubs/pull/77), merged.

Depends on: [Plan 0](00-regressions-and-decisions.md).

## Objective and scope

Preserve Korean spaces, Japanese/Latin adjacency, punctuation, combining
sequences, and original alignment records throughout subtitle generation.
Introduce a lossless mapping that later grouping and effects can consume.
This increment does not choose linguistic boundaries or alter Whisper models.

## Internal and public contracts

Use uniseg 0.10.1 (Unicode 16.0.0) behind the shared boundary adapter, as selected
in [Plan 0](00-regressions-and-decisions.md#selected-backends-and-evidence).
Its offsets use Python code-point positions. Adopt it as a declared dependency
here; Japanese/Chinese linguistic providers are integrated by Plan 3.

The existing `words` array is alignment data, not proof of lexical words.
Keep original records and metadata unchanged in retained JSON. Introduce
immutable internal source spans with a stable source-record identity, logical
text offsets, optional validated times, and alignment granularity. Distinguish
separators/untimed text from timed spans. A later display group may reference
several source records without rewriting them into one fake WhisperX word.

Source text is the aligned segment's text with a narrowly documented whitespace
normalization map. Preserve meaningful separators, NBSP/nonbreaking behavior,
joiners, punctuation, and Unicode normalization form. Physical line endings
may normalize for display; preserve raw text and an offset map. No blanket
`.split()`/`.strip()` reconstruction may erase source information. Existing
`full_text` and segment field meanings stay documented; any corrected joining
behavior must be identified as a bug fix rather than a schema reinterpretation.

Display casing remains optional and runs after source mapping. Length-changing
case conversions retain source span identity; do not retokenize uppercase text
to recover timing. Public artifact-writing return values, language detection,
translation restrictions, names, and lifecycle remain unchanged.

## Ordered implementation tasks

- [x] Audit `_full_text`, `build_subtitle_cues`, `_timed_words`,
  `_append_words_cue`, `layout_subtitle_cues`, and `_transform_display_words`
  in `transcriber.py`, plus `words_to_text`, `join_text_parts`,
  `normalise_display_text`, and `build_display_fragments` in `wrapping.py`.
  Identify where source separators, untimed punctuation, and ASR boundaries
  are discarded before artifacts exist.
- [x] Add the source-span types in `models.py` and a focused text-boundary
  adapter (proposed `multisubs/text_segmentation.py`). Keep it independent of
  WhisperX/PyTorch imports so previews remain lightweight.
- [x] Map aligned text to records monotonically within its original segment;
  handle repeated tokens by cursor/offset, never an unconstrained global match.
  Retain unmatched source spans and invalid/missing-time records as data.
  Do not simply filter away their textual content.
- [x] Preserve original segment boundaries as hints when adjoining streams;
  they are neither automatically mandatory cue breaks nor permission to insert
  spaces. Use retained text adjacency and explicit source separators first.
- [x] For direct Python callers with word records but no source string, keep a
  documented compatibility adapter: space-separated words by default, explicit
  Japanese/Chinese character alignment when known, and conservative script
  handling otherwise. Do not infer whitespace omission from East Asian width.
  Keep existing call signatures or add only optional keyword parameters.
- [x] Replace the CJK/emoji-width separator heuristic on the production path.
  Korean words such as `안녕하세요 세계` retain the original space; source
  `第1回`, `字幕AI`, punctuation, and emoji keep their original adjacency.
- [x] Make grapheme handling use the selected Unicode adapter instead of the
  current partial combining-mark/ZWJ algorithm in multiple modules. Cover
  spacing combining marks, flags, modifiers, variation selectors, Hangul Jamo,
  and Indic conjuncts. Convert external UTF-16 offsets to Python offsets when
  applicable and test supplementary-plane characters explicitly.
- [x] Build display fragments from the span map before line wrapping. Every
  fragment reconstructs the display string, with explicit generated line-break
  provenance so tests can reverse wrapping without deleting meaningful spaces.
- [x] On incomplete alignment mapping, keep complete source text at coarse
  segment times and suppress timing-dependent effects for that cue. Record one
  reason/count rather than assigning missing punctuation or words fabricated
  start/end values. Ensure callers can distinguish missing alignment from a
  genuine empty transcript.
- [x] Preserve existing chronology validation for usable timed records. Do not
  shift neighboring times to conceal invalid order or overlaps; apply current
  timing eligibility/fallback rules to the derived mapping.
- [x] Add additive mapping/fallback diagnostics without serializing internal
  font objects, paths, or ASS tags. Remove Plan 0 text-preservation `xfail`s.

## Unit and integration verification

Test exact reconstruction with Korean spaces, Japanese/Chinese without spaces,
mixed ASCII digits/Latin/CJK, punctuation-only records, Arabic/Hebrew logical
order, nonbreaking separators, repeated words/characters, missing record times,
and records whose text does not match the segment. Include `ß` casing expansion,
precomposed/decomposed accents, Devanagari vowel marks, flags, skin-tone/ZWJ emoji,
and Hangul sequences. Capture a fixture's expected normalized text explicitly;
do not compare strings after removing all spaces, which hides the reported bug.

Property-style tests must reconstruct source content after reversing only
generated wrapping/casing through the recorded mapping, preserve record order
and count, and prove no source start/end field changes. Golden JSON/SRT changes
must be reviewed for content conservation, not approved wholesale.

```sh
python -m pytest tests/test_wrapping.py tests/test_transcriber.py tests/test_karaoke.py tests/test_preview.py tests/test_text_measurement.py tests/test_language.py
python -m pytest -m integration tests/test_integration.py tests/test_karaoke.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Add the adapter's focused tests when introduced. Inspect Korean and mixed-script
renders with controlled fonts, but do not claim shaping is fixed until Plan 4.

## Implementation evidence

The implementation is complete on `fix/lossless-subtitle-text`. It adds the
pure `text_segmentation.py` adapter, immutable source-map/display-unit models,
lossless mapped wrapping, coarse fallback diagnostics, and regressions for
repeated records, Korean spacing, CJK/Latin adjacency, NBSP, case expansion,
line-ending offsets, and extended grapheme clusters. Plan 0 text-preservation
`xfail`s are removed; remaining multilingual `xfail`s belong to Plans 3–5.

Local verification:

```text
Focused text-segmentation, transcriber, wrapping, and preview regressions pass
ruff check passed; ruff format --check passed; pyright passed
Full hermetic suite: 943 passed, 56 deselected, 10 expected Plan 3–5 xfailed
FFmpeg/Karaoke integration: 39 passed, 26 deselected
Multilingual renderer integration: 2 passed
```

## Acceptance criteria

- Korean spaces and source CJK/ASCII adjacency survive JSON, SRT, ASS, and
  preview text preparation.
- Every original text span survives incomplete alignment; affected cues render
  complete static text with an explicit fallback count and no invented times.
- Every derived fragment has stable source provenance through case conversion
  and wrapping; original aligned records are not repurposed as lexical tokens.
- No new public flags, model downloads, translation behavior, or output-lifecycle
  changes are introduced.

## Documentation and delivery

Update architecture cue construction, source/display mapping, and JSON/SRT/ASS
contracts; README generated text and incomplete-alignment fallback; PRD FR-7
and FR-17; conventions for lossless Unicode and source-timing identity.

Suggested branch: `fix/lossless-subtitle-text`.
Suggested commits: `refactor: retain source spans through subtitle layout`,
`fix: preserve multilingual subtitle separators and untimed text`,
`docs: define lossless subtitle alignment mapping`.
Draft PR title: `fix: preserve multilingual subtitle text and alignment`.
Follow the [shared delivery lifecycle](README.md#delivery-strategy).

Risks: repeated text can cause false matches; raw segments already normalized
by WhisperX cannot recover lost source audio distinctions; schema consumers may
have depended on erroneous spacing. Keep replay limitations explicit and use
additive metadata. Roll back via a focused revert without rewriting old files.
