# Verify multilingual output and prepare rollout

Status: Planned

Depends on Plans [0](00-regressions-and-decisions.md),
[1](01-font-coverage-and-metrics.md), [2](02-text-and-alignment-mapping.md),
[3](03-linguistic-cues-and-timing.md), and
[4](04-shaping-effects-and-previews.md).

## Objective and scope

Close the original report with reviewed central-subtitle evidence, verify the
same corrections across supported scripts, and document exactly which outputs
are supported, substituted, or intentionally rendered without word effects.
This gate assembles prior evidence and covers remaining cross-component risks;
each behavior PR must already contain its own tests.

## Language and evidence matrix

All rows below are verification targets, not claims of completed fixes. Include
every code in `config.py::SUPPORTED_LANGUAGES` in a synthetic smoke matrix, with
deeper tests by writing system and real rendered checks for high-risk groups.

| Group/codes | Required cases | Evidence needed |
| --- | --- | --- |
| Japanese `ja` | Kana/kanji, no punctuation, closing punctuation, small kana, Latin/digits, all reported defects | Controlled font metrics, legal cue boundaries, group transitions, local central-subtitle replay |
| Chinese `zh` | Simplified/traditional text, fullwidth punctuation, Latin/digits | Character-to-group mapping, locale/font distinction, real renders |
| Korean `ko` | Word spaces, punctuation, Hangul/Jamo | Exact separators, graphemes, font coverage, real renders |
| RTL `ar fa ur he` | Joining scripts where applicable, numbers, brackets, mixed Latin | Whole-line visual order, verified effects or explicit static fallback |
| Indic `hi te ml` | Vowel marks, conjuncts, punctuation | Grapheme conservation, shaping, mark placement, verified effects/fallback |
| Georgian `ka` | Covering and non-covering fonts | Correct coverage selection, legible render or actionable missing-font error |
| Latin `ca cs da de en es eu fi fr gl hr hu id it lv nl nn no pl pt ro sk sl sv tl tr vi` | Accents, long words, punctuation, casing, decomposed marks | Smoke coverage for each code; deeper Portuguese/English/Vietnamese and casing regressions |
| Greek/Cyrillic `el ru uk` | Alphabet, marks, punctuation, mixed digits | Coverage, source preservation, baseline render regressions |

Thai, Lao, Khmer, and Burmese are future segmentation considerations and must
not enter the supported-language list as part of this fix. Font coverage is
content-dependent: no sample proves coverage of every possible character in a
language. Likewise, correct subtitle rendering does not prove ASR accuracy.

## Ordered implementation tasks

- [ ] Check every confirmed failure from Plan 0 has a passing regression and
  remove all temporary known-failure markers owned by this package. Classify
  remaining risks as verified support, tested fallback, or an explicit blocker.
- [ ] Add a parameterized smoke fixture for every current language code and
  assert its code set equals `SUPPORTED_LANGUAGES`, avoiding a stale test list.
  Keep representative fonts and synthetic text provenance explicit.
- [ ] Run real font/shape tests in a controlled environment with a pinned font
  inventory. Configure the required integration job to fail on missing fixture
  fonts while ordinary developer integration runs may explain unavailable
  prerequisites. No runtime font downloads; provision test assets beforehand
  from reviewed immutable sources with licenses/hashes.
- [ ] Extend `tests/test_multilingual_integration.py`, introduced by Plan 0,
  with focused tests marked `integration`, reusing current
  frame/mask helpers rather than a second production renderer. Validate glyph
  spacing, line height, active-group color, boxes, and fallback metadata.
- [ ] Cover 9:16, 16:9, and square; retain rotation/non-square-pixel regressions.
  Use `default`, `amber-word`, `mint-progress`, and `focus-marker`, plus a cue
  motion case, custom template overrides, and native/explicit placement.
- [ ] Verify retained and non-retained runs, malformed/missing fonts,
  partial alignment, missing shaper/dictionary, absent ffmpeg, renderer failure,
  filename collisions, Unicode/quoted paths, and temporary-resource cleanup.
- [ ] Replay the original local Japanese example with its existing timestamps
  onto the original uncaptioned input when available, or a synthetic background.
  Use unique output paths under ignored `data/` or a temporary directory. Never
  modify the original video/JSON/SRT/ASS or publish them by default.
- [ ] Inspect only the central generated subtitle at representative frames
  across the whole clip and immediately around the historical 11.832s,
  34.288s, and 36.210s cuts. Those old times are observation points, not required
  new cue boundaries. Confirm no overlap, content loss, or avoidable lexical
  cuts, and inspect playback of word-group transitions.
- [ ] State replay limits: corrected source mapping cannot recover source text
  already removed before the retained JSON. Validate that behavior with raw
  synthetic alignment fixtures; perform a small local ASR run only if needed
  to check the actual WhisperX boundary. Do not attribute spelling errors to
  the font fix or promise transcription accuracy without audio review.
- [ ] Verify actual automatic/explicit language resolution and English
  translation paths on the implementation base. Preserve the current rejection
  of translation with word animation, `turbo`, or `.en` as applicable.
- [ ] Audit additive JSON metadata across mixed-font/group/fallback runs,
  unchanged required schema-3 fields, original word identities/times, plain SRT,
  safe ASS escaping, and no private resource paths in new fields.
- [ ] Complete the clean-build/offline smoke and performance gates below; update
  current docs and the language matrix with exact evidence and limitations.

## Exact verification commands

Use the project's isolated environment with development tools installed. These
are implementation verification instructions; none has been claimed as run by
creating this plan.

```sh
python -m pytest tests/test_text_measurement.py tests/test_font_catalog.py tests/test_wrapping.py tests/test_transcriber.py tests/test_layout.py tests/test_karaoke.py tests/test_ass.py tests/test_animation.py tests/test_preview.py tests/test_cli.py tests/test_subtitler.py tests/test_language.py
python -m pytest -m integration tests/test_multilingual_integration.py tests/test_integration.py tests/test_karaoke.py tests/test_preview_integration.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

The new integration file must exist before its command runs. Include any new
text-adapter/replay tests in focused runs; the full suite must discover them.
Exercise supported Python 3.10 and 3.13 in CI and compatibility smoke checks
for 3.11/3.12 when new native dependencies/resources are adopted.

For distribution validation, remove only the repository build-output `dist/`
immediately before building, as required by delivery conventions:

```sh
rm -rf dist
python -m build
python -m twine check dist/*
```

Audit wheel/sdist contents against the existing font/template manifests and any
new dependency resource inventories. Record wheel/sdist size deltas. Install
the single resulting wheel outside the checkout into a fresh environment from
a prepared dependency wheelhouse, then disable networking for `multisubs
--help`, import, PNG/MP4 preview, and synthetic artifact/render smoke checks.
Record the exact installation and preview commands with the selected wheel,
font fixtures, and media paths. Ensure dictionaries load offline, no model is
imported by previews, and selected font resources survive through rendering.

Benchmark the same 250-/1000-record cases from Plan 3 plus many short cues
using repeated fonts. Check bounded caches, candidate search, dictionary
initialization, and ASS event growth; investigate >2× same-host regressions.
Do not establish performance from transcription/model loading time.

## Measurable release acceptance

- The central Japanese subtitle renders without unintended glyph/line overlap
  and without missing-glyph measurements driving positioned geometry.
- The controlled lexical examples stay whole across timed cues whenever the
  envelope/duration permits them; emergency cases are explicitly diagnosed.
- Korean spaces, mixed-script adjacency, punctuation, and source timestamps
  survive all artifacts and previews under the defined normalization contract.
- Japanese/Chinese highlight groups follow derived source intervals, with no
  artificial duration floor, and previews clearly retain simulated timing.
- Every high-risk script has a passed real render or a tested, documented
  legible fallback; missing evidence prevents claiming that capability shipped.
- The supported-language matrix is exhaustive, ordinary Latin regressions
  pass, and template/custom font/geometry/lifecycle behavior remains coherent.
- Build, clean-install, offline, performance, privacy, and documentation gates
  pass with no generated/user media committed and no runtime network dependency.

## Documentation, delivery, and rollback

Update README installation, font coverage, multilingual behavior, preview
examples, generated files, and limitations; PRD FR-7/9/16/17/18 and acceptance;
architecture text/font/group/render flow and output contracts; conventions
and delivery only where new fixture/dependency/CI requirements apply. Do not
change environment promotion rules merely to add a regression suite.

Suggested branch: `test/multilingual-render-validation`.
Suggested commits: `test: verify multilingual subtitle rendering`,
`test: verify offline multilingual artifact installation`,
`docs: document verified multilingual subtitle behavior`.
Draft PR title: `test: validate multilingual subtitle corrections`.
Follow the [shared delivery lifecycle](README.md#delivery-strategy); record exact
checks, skips, frame evidence, resource versions, and unresolved limitations.

These PRs do not authorize a tag or release. After merges, promote through the
existing staging gate and review accumulated compatibility changes, especially
new positioned-render errors and per-cue metadata, before selecting SemVer.
Prepare release notes explaining that existing burned-in videos and saved ASS
files remain unchanged and must be regenerated to benefit from corrections.
Retained source timestamps permit a layout replay only to the extent described
above; there is no automatic migration or new public replay/import command.

Rollback with a focused fix/revert PR and a new release through the normal
workflow. Revert dependent grouping/render contracts together when necessary;
do not leave a new producer paired with an old consumer, delete user artifacts,
or move published tags. Mark this package `Done` only after authoritative merge
signals for all six plans and completed acceptance evidence.
