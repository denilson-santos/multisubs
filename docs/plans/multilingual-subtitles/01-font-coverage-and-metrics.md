# Resolve covering fonts before measuring subtitle geometry

Status: Planned

Depends on: [Plan 0](00-regressions-and-decisions.md).

## Objective and scope

Eliminate the Japanese overlap by measuring and rendering a verified font face
that contains the displayed characters. Apply the same rule to every supported
script, including previews, outlines, boxes, and line-height calculations.

This increment changes font resolution and diagnostics; it does not yet change
lexical grouping or speech times. Keep semantic font-size, spacing, color,
weight, and template defaults. Do not compensate by shrinking text, adding
arbitrary tracking, changing the video codec, or hardcoding a Japanese width.

## Font and failure contract

Plan 0 selected fontTools 4.63.0 for Unicode cmap/TTC coverage inspection.
Pillow remains responsible for measurement; libass remains the render authority.
Adopt the reader as a declared runtime dependency in this increment, with the
bounded parsing and variation-sequence checks below. Its evaluation is recorded
in [Plan 0](00-regressions-and-decisions.md#selected-backends-and-evidence).

1. Resolve the requested face with current custom → bundled → system precedence.
   Validate its coverage against the display-cased text, not the language code
   alone. `--lang ja` does not prove every character is Japanese; translation
   measures its English output. Preserve the requested face when it covers the
   text, including an explicit custom face.
2. For missing glyphs, select a covering local face in a bounded, deterministic
   candidate search: custom directory, available packaged faces, then the
   supported system provider. Use language/script preference and existing
   weight/slant ranking within the selected provider. Do not pick a Chinese
   regional face as a verified Japanese typographic match merely because it
   contains the same code points; report any unavoidable regional substitution.
3. Select one covering face for the entire semantic cue before visual splitting.
   All child cues inherit it, avoiding circular font/wrapping decisions. Measure
   the entire shaped line using that face. Mixed-script text must be covered by
   that face; arbitrary per-character font mixing is outside this increment.
4. Keep the original font request as configuration and record the effective
   face separately. Compile that effective family/face into ASS rather than
   leaving Inter in an event that was measured with a replacement. Pass the
   selected resources to FFmpeg for the entire invocation lifetime.
5. If no covering face can be established for positioned rendering, fail with
   an actionable font/shaping message before artifact serialization or final
   media publication. Suggest existing `--font`/`--fonts-dir` controls without
   automatic downloads. An unresolved simple native-text legacy path may keep
   its documented `unicode-estimate` behavior only when it uses no measured
   fragment/box placement; it must not claim this package's geometry guarantee.
6. Missing glyphs in a resolved face must never count as successful
   `font-metrics`. Cmap coverage is necessary but not sufficient: variation
   sequences, complex shaping, and glyph selection require the render checks.

This deliberately tightens fallback for positioned effects. Record that change
in README/PRD and release notes; do not silently convert every failure into a
successful corrupted render. This policy is selected for implementation based
on Plan 0's local evaluation; production validation belongs to this plan.

## Ordered implementation tasks

- [ ] Add an immutable internal resolved-font contract in `models.py` or the
  measurement boundary: requested/effective identity, face index, coverage
  result, provider, fallback reason, and private resource lifetime reference.
- [ ] Implement coverage queries in `text_measurement.py` using the Plan 0
  selected reader. Bound candidate count, file size, collection faces, and
  subprocess runtime; close fonts and reject malformed tables cleanly.
- [ ] Exempt only legitimate non-rendering controls from ordinary glyph checks;
  handle combining marks, variation selectors, and joiners as sequences rather
  than dropping them. Keep glyph coverage distinct from shaping capability.
- [ ] Extend the resolver to evaluate fallback candidates against actual text.
  A family name or `fc-match` response alone is not evidence of coverage.
  Retain deterministic requested-weight and slant diagnostics.
- [ ] Refactor orchestration in `transcriber.py`, `layout.py`, `cli.py`, and
  `preview.py`: validate scalar requests early, resolve geometry once, and
  resolve actual content fonts after transcription/preview text is available.
  Content-dependent failures cannot always happen before model loading.
- [ ] Recompute natural ascent/descent, automatic/explicit line height, capacity,
  width, and decorations from the selected face. Preserve original relative
  lengths until resolution; avoid reusing an Inter-resolved numeric line height
  after selecting a different font. Revalidate explicit line-height/envelope
  constraints using the actual face.
- [ ] Replace the assumption of one run-global `WrappingMetrics` with an
  explicit per-cue layout context while retaining a run-level cache. Update
  `_append_display_cue`, `write_ass`, preview guides, boxes, and fragment
  placements to consume that same context.
- [ ] Extend `font_catalog.py` only for selected-resource lifetime/materialization
  as needed; keep measurement and system font search outside catalog loading.
  Extend `subtitler.py` to receive the resolved font set/directory without
  discovering fonts independently. Materialize only selected assets, never
  install globally or scan arbitrary directory trees.
- [ ] Ensure libass actually selects the intended face, including TTC index,
  same-named custom fonts, and weight substitution. If an exact identity cannot
  be guaranteed, do not advertise it as verified.
- [ ] Add per-cue font/layout metadata under the existing schema-3 segment
  objects and an additive run summary of requested font and substitutions.
  Preserve current required fields and meanings for homogeneous-font runs.
  For heterogeneous runs, retain the run defaults explicitly as defaults and
  document per-cue metadata as authoritative; never label one face as covering
  all cues. Do not serialize font paths or generated ASS markup.
- [ ] Aggregate coverage/substitution diagnostics once per run, with counts and
  actionable advice but no transcript text. Remove Plan 0 font `xfail` marks.

## Verification and acceptance

Unit tests cover a found font with absent glyphs, valid custom precedence,
unsupported TTC faces, missing providers, fallback ordering, transformed text,
mixed scripts, malformed resources, cache identity, and resource cleanup.
Assert font changes propagate to *both* horizontal and vertical geometry.

Use pinned Japanese/Chinese/Korean and representative RTL/Indic fixture fonts
from Plan 0. Render full lines and individual glyphs at the same size, weight,
outline, and coordinates. Compare placement advances with the matching native
libass whole-line reference; distinguish glyph ink bounds from advance width.
For the Japanese plain/highlight fixture require no neighbor collision and no
unintended overlap between lines; include the actual 1080×1920 envelope.
Record explicit pixel tolerances before evaluating output and never enlarge
them merely to hide a systematic mismatch. Exercise heavy/italic substitution,
auto/explicit line height, nonzero spacing, boxes, and mixed Latin/CJK.

Acceptance requires the old approximately 41px missing-glyph measurement to be
rejected for the Japanese sample, the replacement's real metrics to drive ASS,
and all fitting reference cues to stay within their declared geometry. A failed
coverage resolution must not publish a final video or claim `font-metrics`.
SRT/JSON text and word times remain intact even when improved widths change
line/cue distribution. Latin text covered by its requested face keeps its
existing presentation within established renderer tolerances.

```sh
python -m pytest tests/test_text_measurement.py tests/test_font_catalog.py tests/test_layout.py tests/test_ass.py tests/test_transcriber.py tests/test_preview.py tests/test_cli.py tests/test_subtitler.py
python -m pytest -m integration tests/test_integration.py tests/test_preview_integration.py tests/test_karaoke.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Because dependency/resource resolution changes, also run the clean-build and
wheel-install gate in [Plan 5](05-verification-and-rollout.md). A first-font-only
smoke test is insufficient for a multi-font run.

## Documentation, delivery, and risks

Update README font recipes, requirements, fallback troubleshooting, and JSON
metadata; PRD FR-7/FR-9 and readability/error criteria; architecture font
providers, pipeline, per-cue geometry, JSON and ASS; conventions for the adopted
coverage reader, fallback guarantees, resource bounds, and dependency review.

Suggested branch: `fix/subtitle-font-coverage`.
Suggested commits: `fix: validate subtitle font coverage`,
`fix: share resolved cue fonts with measurement and rendering`,
`docs: document multilingual font fallback`.
Draft PR title: `fix: measure subtitles with their rendered fonts`.
Follow the [shared delivery lifecycle](README.md#delivery-strategy).

Main risks are font-name collisions, different shaping/weight choices in
libass, larger resource sets, and explicit heights becoming invalid after a
correct substitution. Document these failures rather than clamping user
geometry. Rollback through a focused revert, keeping retained source assets
untouched; do not change font binaries or published tags.
