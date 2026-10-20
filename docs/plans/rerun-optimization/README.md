# Reusable transcription and visual iteration

Status: In review

## Objective and scope

Recognize one video's speech once, export alternative subtitle presentations,
and evaluate synchronized excerpts before rendering the complete video.
The three increments share an automatic output-local speech cache with an
optional custom location. Multiple
template exports in one invocation and persistent layout caches are deferred.

## Plans and progress

Progress: 0/3 plans merged. Plans 0–2 are implemented, verified, and prepared
for review on `feat/reusable-subtitle-runs`, the delivery reference for the
shared draft pull request against `main`. Verification passed:
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
| [0 — Source speech cache](00-source-speech-cache.md) | In review | Existing source-speech API and ASR catalog | `feat/reusable-subtitle-runs` |
| [1 — Subtitle export](01-subtitle-export.md) | In review | Plan 0 for source reuse; existing artifact pipeline | `feat/reusable-subtitle-runs` |
| [2 — Real excerpt preview](02-real-excerpt-preview.md) | In review | Plans 0–1; existing FFmpeg and geometry boundaries | `feat/reusable-subtitle-runs` |

## Delivery order and strategy

Implement cache, subtitle export, then real previews. Review the shared workflow
in one draft pull request against `main`, with focused commits for each behavior
and a final documentation commit. Git staging, commits, pushing, and PR creation
require separate explicit delivery confirmation under [AGENTS.md](../../../AGENTS.md).

Before opening that PR, change all three plans and this package to `In review`
in the final documentation commit and retain the task branch as the delivery
reference. Push the complete branch first. After an authoritative merge signal,
mark the plans/package `Done`, record the merged PR link, and update the
[catalog](../README.md). No post-open metadata-only commit is required.

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
