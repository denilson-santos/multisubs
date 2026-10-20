# Reusable transcription and visual iteration

Status: Done

## Objective and scope

Recognize one video's speech once, export alternative subtitle presentations,
and evaluate synchronized excerpts before rendering the complete video.
The three increments share an automatic output-local speech cache with an
optional custom location. Multiple
template exports in one invocation and persistent layout caches are deferred.

## Plans and progress

Progress: 3/3 plans merged into `main` in
[PR #115](https://github.com/denilson-santos/multisubs/pull/115) on 2026-10-20.
Development and staging workflows passed, including Python 3.10 and 3.13.
Local verification passed:
1,450 hermetic tests and 20 synthetic FFmpeg integration cases, including the
automatic output-local cache, `transcriptions/v1` with legacy reuse, optional
sample-frame selection, first-frame defaults, and PNG previews accepting video
encoding options without initializing an encoder. Three opt-in NVENC cases were
skipped. Ruff formatting/lint, Pyright, compileall, CLI help, wheel/source builds,
package metadata checks, and bundled-font artifact audits also passed.
CI-specific regression checks also passed with forced terminal colors and
Pyright 1.1.414, covering ANSI-normalized option errors and typed RGB pixels.

| Plan | Status | Dependencies | Implementation delivery |
| --- | --- | --- | --- |
| [0 — Source speech cache](00-source-speech-cache.md) | Done | Existing source-speech API and ASR catalog | [PR #115](https://github.com/denilson-santos/multisubs/pull/115) |
| [1 — Subtitle export](01-subtitle-export.md) | Done | Plan 0 for source reuse; existing artifact pipeline | [PR #115](https://github.com/denilson-santos/multisubs/pull/115) |
| [2 — Real excerpt preview](02-real-excerpt-preview.md) | Done | Plans 0–1; existing FFmpeg and geometry boundaries | [PR #115](https://github.com/denilson-santos/multisubs/pull/115) |

## Delivery order and strategy

The implementation proceeded through cache, subtitle export, and real previews
on `feat/reusable-subtitle-runs`, delivered together in PR #115. Focused feature,
documentation, and CI portability commits formed one shared review candidate.
All three plans and this package were marked `In review` before opening the PR,
with the task branch retained as the delivery reference.

After the confirmed merge and successful staging run, the version-bump update
marks the plans/package `Done`, records the merged PR, and synchronizes the
[catalog](../README.md). Git delivery follows the explicit approval rules in
[AGENTS.md](../../../AGENTS.md).

## Shared definition of done

- Translation restrictions, source-speech schema 1, retained schema 3, and
  observed source timings remain intact. Sample previews remain ASR-free;
  their first-frame defaults and whole-second CLI notation are documented.
- CLI transcription reuses `<output-dir>/.multisubs-cache` by default;
  `--cache-dir` overrides the location and `--refresh-cache` works with either.
  Cache retention is independent of generated artifact retention. Translation,
  sample previews, external subtitles, and Python rendering remain uncached.
- Changing presentation reuses source text and observed times while rebuilding
  cues/layout; no timestamp simulation enters production speech.
- Outputs are collision-safe and published after the selected operation succeeds.
- Hermetic tests forbid real model loading; media checks use synthetic fixtures.
- README, PRD, architecture, conventions, and CLI help describe actual behavior.
