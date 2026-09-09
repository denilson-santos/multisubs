# Establish regressions and select multilingual backends

Status: In review

Delivery branch: `test/multilingual-regressions`.
Local implementation is verified and ready for pull-request review; `Done`
requires merge evidence.

Depends on: the completed foundations linked in the [dashboard](README.md).

## Objective

Turn the reported failures into reproducible acceptance evidence and settle the
few backend choices that affect installation and architecture before broad
implementation. Keep confirmed observations separate from extrapolations.

## Baseline and scope

The local report concerns `multisubs/data/test-jp (7)/test-jp-ja.mp4` and its
adjacent `subtitles` assets: 1080×1920, 30 fps, approximately 38 seconds,
Japanese transcription, `turbo`, centered `amber-word`. The retained JSON
records Inter SemiBold, ASS size 89, Pillow metric size 62, a 684px text budget,
and a 76px natural line height. The reported 254 aligned records each contain
one character, including four intervals of approximately 20ms. These values
are historical observations to reproduce, not constants for production code.

Confirmed observations:

- The local Inter measures sampled Japanese characters as the missing glyph
  at 40.6875px. ASS fragment centers advance approximately 41px; a local libass
  replay selects WenQuanYi Zen Hei for Japanese. The original MP4 does not
  embed an authoritative record of the renderer's fallback font.
- `なかった`, `デフォルト`, and `使用` cross cue boundaries at 11.832s,
  34.288s, and 36.210s respectively. Japanese line breaking can legitimately
  occur inside some lexical words; arbitrary *timed cue/highlight* cuts are a
  separate readability issue and must not be conflated with every line break.
- `。！？`, `、`, and selected Arabic/Indic marks are not recognized by the
  current sentence/clause detectors. This transcript contains no sentence
  punctuation, so punctuation support alone cannot fix its grouping.
- Joining aligned Korean words removes required spaces. Mixed Japanese and
  ASCII records can acquire spaces absent from their source text.

RTL ordering, Indic shaping, and other fonts/scripts are risks to investigate;
the Japanese video does not prove those render failures. Lexical recognition
accuracy against the audio was not evaluated. Do not substitute on-screen text
outside the central subtitle for an audio ground truth.

## Ordered implementation tasks

- [x] Record implementation-base SHA, Python/Pillow/WhisperX/FFmpeg/libass
  versions, font hashes, exact effective configuration, and artifact hashes in
  a local evidence manifest. Check the current plan dependencies on `main`.
- [x] Add authored synthetic UTF-8 fixtures under
  `tests/fixtures/multilingual/` directory, with logical text, source spans,
  aligned times, expected legal/prohibited boundaries, and expected script.
  Do not copy the user's entire transcript or video into tests.
- [x] Reproduce font fallback independently with a synthetic background and
  Japanese text using Inter. Capture bounded font-selection diagnostics and
  individual glyph/whole-line masks, not only a valid ASS string.
- [x] Add regressions for Korean spaces, mixed `第1回`/Latin text, punctuation,
  repeated characters, zero/missing times, combining sequences, and lexical
  groups crossing duration/width limits. Keep new expected failures explicitly
  marked `xfail(strict=True)` only while the corresponding fix is pending;
  Plans 1–4 must remove their marks, and Plan 5 permits none to remain.
- [x] Add a developer-only replay helper under
  `scripts/replay_subtitle_layout.py`. Accept explicit local retained JSON and
  an original uncaptioned input or synthetic background, validate bounded data,
  and call the public artifact-writing/renderer boundaries. Never burn a second
  subtitle onto the already-captioned output. This is not a new public CLI.
- [x] Label replay fidelity: retained segments have already undergone cue
  construction and filtering. They cannot reconstruct discarded ASR boundaries,
  punctuation, or missing alignments. Use synthetic raw-alignment fixtures for
  these cases and record that limitation in replay output.
- [x] Evaluate and record the backend decisions below in this document, then
  update dependent plans to the selected versions, interfaces, and resource
  inventory. Complete this gate before their production implementation.

## Initial backend decision gate

The following criteria guided the evaluation. The selected route and actual
results are recorded below; production adoption belongs to Plans 1–3.

| Decision | Preferred direction | Required evidence before selection |
| --- | --- | --- |
| Glyph coverage | A maintained font-table reader, with fontTools as the first candidate; Pillow remains the shaping/measurement owner | Unicode cmap/TTC handling, malformed-file bounds, variation-selector limitations, Python 3.10–3.13 compatibility, license and size; no new handwritten SFNT parser |
| Text segmentation | One adapter exposing grapheme, word, sentence, and line boundaries; evaluate ICU dictionary boundaries for Japanese/Chinese first | Actual Japanese/Chinese fixture quality, offset conversion, offline dictionaries, deterministic versions, Python installation/native dependency cost |
| Rendering | Keep FFmpeg/libass and use a verified covering face per semantic cue, with whole-line rendering where shaping requires it | Measured versus rendered glyph/line geometry and font-face identity; no claim that cmap coverage alone proves shaping |

The [fontTools API](https://fonttools.readthedocs.io/en/stable/ttLib/ttFont.html)
provides Unicode cmap lookup. [ICU boundary analysis](https://unicode-org.github.io/icu/userguide/boundaryanalysis/)
provides dictionary-assisted boundaries for Japanese/Chinese and Unicode-based
line/grapheme boundaries. These capabilities make them evaluation candidates,
not already accepted dependencies or proof of suitability on every host.

Compare the preferred segmentation adapter with a maintained pure-Python
Unicode implementation plus local Japanese/Chinese tokenizers if ICU packaging
is unsuitable. Select one production route, not two divergent default engines.
No regex-only approximation may be labeled linguistic segmentation. No runtime
font/dictionary download or cloud text processing is allowed. Report exact
dependency/resource versions, licenses, installed/distribution size deltas,
supported platforms, and clean-install results. If neither route satisfies the
contract, retain `Proposed` and record the concrete unmet requirement instead
of claiming the downstream language fix is ready.

The proposed font policy uses available custom/bundled/system fonts without
adding a large bundled CJK catalog in this package. An offline fixture font
inventory for integration must nevertheless be pinned and reproducibly
provisioned; missing fixture fonts cannot silently skip a required release gate.

## Selected backends and evidence

Evaluation performed on 2026-09-09 using a fresh temporary CPython 3.10.12
environment. No evaluation dependency was added to production or the normal
development environment. Exact pins are in
[multilingual-spike-requirements.txt](../../../scripts/multilingual-spike-requirements.txt).

| Component | Selected version | License | Download size observed | Installed bytes observed |
| --- | --- | --- | ---: | ---: |
| fontTools | 4.63.0 | MIT | 4.9 MB wheel | 24,160,749 |
| uniseg | 0.10.1; Unicode 16.0.0 | MIT | 8.2 MB wheel | 11,103,303 |
| SudachiPy | 0.6.11 | Apache-2.0 | 1.6 MB wheel | 4,466,689 |
| SudachiDict-small | 20260723 | Apache-2.0 | 41.8 MB wheel | 122,968,845 |
| jieba | 0.42.1 | MIT | 19.2 MB source archive | 38,261,173 |

Installed sizes include the files observed in this environment and may vary
with bytecode/platform. The combined dependency installation is about 201 MB;
these are separate dependency distributions, not fonts/dictionaries copied into
the multisubs wheel. The current project's distribution size is unchanged by
runtime assets in this increment. Packaging and fresh offline wheel installation
remain mandatory when adopting the dependencies in Plans 1–3 and in Plan 5.

PyICU 2.16.2 was rejected as the default integration route: its source build
failed before installation because `pkg-config`/ICU development setup was
absent. The upstream [installation guide](https://pypi.org/project/pyicu/)
confirms the native build requirements. No system packages were installed.
Use the selected single adapter route, with language-specific providers beneath
it, rather than two environment-dependent implementations of the same language.

Actual offline evaluation and limitations:

- fontTools detected missing Japanese glyphs in bundled Inter and covering
  glyphs in face 0 of the local WenQuanYi TTC. Cmap lookup does not certify
  shaping, variation sequences, or libass's final selection. Plan 1 owns those
  production checks and malformed-font bounds.
- uniseg preserves the tested Indic vowel, flag, skin tone, accent, and ZWJ
  clusters. Its versioned line-break rules avoid the tested closing punctuation;
  they are not a linguistic dictionary.
- Sudachi mode B preserves `デフォルト` and `使用` with source offsets. Raw
  morphology splits `なかっ`/`た`; the evaluation prototype joins auxiliary and
  non-independent predicate tails. Plan 3 must implement and test this as a
  general presentation rule, never a string-specific repair.
- jieba with `HMM=False` split traditional `學習` into individual characters.
  With the packaged HMM enabled, both simplified and traditional fixture words
  are grouped correctly. It still splits emoji/ZWJ records; the prototype
  intersects its boundaries with complete grapheme boundaries. No text is
  normalized, translated, or rewritten to simplify segmentation.
- Evaluation disables socket creation while loading/using dictionaries and
  removes jieba's invocation-specific temporary cache. It verifies exact token
  offsets/reconstruction and the protected display groups of all synthetic
  fixtures. These samples establish feasibility, not universal linguistic
  correctness. The old jieba release warrants a bounded adapter and continued
  compatibility tests; do not treat age as evidence of current maintenance.
- fontTools and SudachiPy CPython 3.13 manylinux2014 x86-64 wheels were downloaded
  successfully. They were not executed under Python 3.13 on this host. Full
  interpreter/platform and product offline-install gates stay with adoption/CI.

Resource hashes (SHA-256):

- Sudachi small `system.dic`:
  `f872a878c3c5e8a0df4ae8c548e1d7a754f58cdb37eb660ba22f6514457ad8cc`.
- jieba `dict.txt`:
  `7197c3211ddd98962b036cdf40324d1ea2bfaa12bd028e68faa70111a88e12a8`.
- Bundled Inter SemiBold:
  `334bb2c51aeba5f566abac8d03a7e75ab3234d6926b52e92a85dc704129258b5`.
- Local integration fixture WenQuanYi Zen Hei TTC:
  `79c18ebe7b811951e8311bad7103ebeae8c337ed9988ea69e8a78a66cfe029b9`.
  Provisioned by distro package `fonts-wqy-zenhei=0.9.45-8`, face 0; license is
  GPL-2 with font-embedding exception and M+ font terms (not a bundled OFL font).
  The test skips when this exact external fixture is unavailable; this is not
  permission to skip the required multilingual release gate in Plan 5.

Reproduce the evaluation from the checkout in a separate temporary environment:

```sh
python -m venv /tmp/multisubs-backend-evaluation
/tmp/multisubs-backend-evaluation/bin/python -m pip install -r scripts/multilingual-spike-requirements.txt
/tmp/multisubs-backend-evaluation/bin/python -m scripts.evaluate_multilingual_backends
```

Use a fresh location when that path already contains unrelated work. Install
requires package access; the evaluation itself checks offline operation.
Upstream interfaces: [SudachiPy](https://worksapplications.github.io/sudachi.rs/python/api/sudachipy.html),
[uniseg](https://uniseg-py.readthedocs.io/en/stable/),
[jieba](https://github.com/fxsjy/jieba), and the fontTools link above.

## Local implementation evidence

Base: `9841330e94d4f72ae111548f5d1f18b9468a98e1`. Python 3.10.12, Pillow 12.2.0,
WhisperX 3.8.6 (metadata only; never imported by replay), FFmpeg
4.4.2-0ubuntu0.22.04.1. The local libass probe from the original diagnosis is
0.15.2; the integration test also captures current libass/font selection through
pytest record properties. The saved artifact's reported font is not proof of
the original video's fallback face.

The synthetic integration test measures a **63px glyph ink width against a
40px minimum positioned advance**. Running that test with `--runxfail` fails
at exactly the collision assertion, confirming the defect rather than masking
an unrelated exception. The normal suite marks it strictly as Plan 1's owned
regression. Eighteen additional hermetic expected failures belong to Plans 1–3;
they are not fixed by this foundation work.

Local replay used:

```sh
python -m scripts.replay_subtitle_layout \
  'multisubs/data/test-jp (7)/subtitles/test-jp-ja.json' \
  --output-dir /tmp/multisubs-ja-plan0 --render
```

It produced JSON/SRT/ASS, a SHA-256/version manifest, a synthetic background,
and a rendered replay under a unique directory. The central frame at 1s was
visually inspected and reproduces the overlap. Original files were preserved;
the local JSON input hash is
`ebe11740efde4f15eae4032143fc215d91e90ba86d9acab3ca189461c3dd2cb7`.
The generated JSON records the current effective configuration; saved rendering
settings are not imported. An interrupted render leaves `pending` evidence and
diagnostic artifacts; only successful rendering records `complete`.

## Acceptance and verification

Local verification on 2026-09-09: the hermetic suite completed with 916 passed,
56 deselected integration tests, and 18 strict expected failures. The selected
integration suite (`test_multilingual_integration.py`, `test_integration.py`,
and `test_karaoke.py`) completed with 40 passed, 26 deselected, and one strict
expected failure for the confirmed glyph collision. Ruff lint/format, project
and developer-script Pyright checks, compileall, CLI help, and `git diff --check`
passed. The isolated backend evaluation also completed successfully. Expected
failures document outstanding corrections; they are not passing fixes.

- Synthetic tests reproduce the confirmed failure categories independently of
  Whisper model loading or the user's private file paths.
- A local replay emits reviewable central-subtitle frames without modifying
  existing artifacts; malformed input and collisions have coverage.
- Backend selection records concrete install and render evidence, dependency
  impact, and safe failure policy; downstream plan decisions are synchronized.
- Existing tests stay green and known-failure marks have an explicit owner.

Run in the isolated development environment:

```sh
python -m pytest tests/test_multilingual_regressions.py tests/test_replay_subtitle_layout.py tests/test_text_measurement.py tests/test_wrapping.py tests/test_transcriber.py tests/test_karaoke.py
python -m pytest -m integration tests/test_multilingual_integration.py tests/test_integration.py tests/test_karaoke.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff check .
python -m ruff format --check .
python -m pyright
git diff --check
```

Record the exact replay command and font manifest used. No full transcription is a
routine check; a small local transcription is only needed if original alignment
data unavailable in retained artifacts must be investigated.

## Documentation and delivery

Record decisions/evidence here; update conventions for any adopted fixture or
dependency process, and installation docs when dependencies actually change.
Keep runtime capability claims out of README until their fixes ship.

Suggested branch: `test/multilingual-regressions`.
Suggested commits: `test: reproduce multilingual subtitle failures`,
`test: add local subtitle replay tooling`,
`docs: record multilingual backend decisions`.
Draft PR title: `test: establish multilingual subtitle regressions`.
Follow the [shared delivery lifecycle](README.md#delivery-strategy), target
`main`, and attach only synthetic public evidence. Rollback removes test/tool
scaffolding; production output is not changed by this increment.
