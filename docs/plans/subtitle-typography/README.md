# Subtitle typography roadmap

Status: In review

This package adds semantic typography controls without exposing raw ASS field
names. It owns font weight, letter spacing, line height, global opacity, and
text case. Subtitle placement and available dimensions remain owned by the
[subtitle-positioning roadmap](../subtitle-positioning/README.md), while timed
color changes remain owned by the
[karaoke-subtitles roadmap](../karaoke-subtitles/README.md).

## Product outcome

Users can select a weight using familiar font-face names or numeric weight
values, tune horizontal letter spacing and vertical line rhythm, control the
opacity of the complete subtitle composition, and choose whether displayed
text preserves or changes its case. Preview, adaptive wrapping, retained ASS,
rendered video, and JSON diagnostics must agree about the resolved typography.
Existing commands keep their current appearance because the defaults remain
regular weight, zero additional letter spacing, the font's automatic line
height, full opacity, and original text case.

## Shared public contract

The package introduces these options incrementally:

~~~
--font-weight WEIGHT
--letter-spacing LENGTH
--line-height auto|LENGTH
--opacity PERCENT
--text-case {original,uppercase,lowercase}
~~~

`--font-weight` accepts case-insensitive names such as `regular`, `light`,
`medium`, `semi-bold`, `bold`, and `black`, plus documented aliases commonly
used by fonts such as `book`, `demi-bold`, and `heavy`. It also accepts the
numeric ranks `100` through `900` in increments of 100. Both forms normalize to
the same semantic rank, and the default is `regular`/`400`. The existing
`--bold` and `--no-bold` options remain compatibility shorthands for `bold`/`700`
and `regular`/`400`; combining either shorthand with `--font-weight` is rejected
as ambiguous.

Letter spacing accepts a non-negative `%` or `px` length. Percentages use the
resolved font size as their basis, and the default remains `0px`.

Line height defaults to `auto`, which preserves the measured font metrics. An
explicit percentage scales the measured natural line height, while pixels set
the baseline advance in PlayRes space. Explicit values smaller than the
natural line height are rejected so lines cannot overlap silently.

Opacity accepts an explicit percentage from `0%` through `100%` and defaults to
`100%`. It multiplies each component's existing alpha instead of replacing it,
so text, karaoke highlight, box or outline, and shadow preserve their relative
transparency.

Text case accepts `original`, `uppercase`, or `lowercase` and defaults to
`original`. Case conversion affects displayed SRT/ASS text and is performed
before measurement and wrapping, while original transcription and aligned-word
data remain preserved in JSON.

## Plan status

This table is the source of truth for the package. Status values follow the
[plan catalog vocabulary](../README.md#status-vocabulary).

| Order | Plan | Status | Depends on | Delivery |
| --- | --- | --- | --- | --- |
| 0 | [Font weight](00-font-weight.md) | Done | Subtitle positioning and karaoke packages | [#42](https://github.com/denilson-santos/multisubs/pull/42) |
| 1 | [Letter spacing](01-letter-spacing.md) | In review | 0 | `feat/subtitle-letter-spacing` |
| 2 | [Line height](02-line-height.md) | Planned | 0, 1 | — |
| 3 | [Subtitle opacity](03-opacity.md) | Planned | 0, 1, 2 | — |
| 4 | [Text case](04-text-case.md) | Planned | 0, 1, 2, 3 | — |

Package progress: 1 of 5 plans done. Plan 1 is in review.

## Dependencies and delivery order

All completed subtitle-positioning and karaoke work is a prerequisite because
the typography controls must share the existing typed configuration, font-aware
wrapping, preview, ASS compiler, and generated-tag safety contracts.

Recommended delivery order:

1. Add named and numeric font weight resolution and retain the current bold
   shorthands.
2. Add renderer-aware letter spacing to the common measurement path.
3. Add line-height-aware capacity and multi-line ASS rendering after the final
   font metrics are available.
4. Add compositional opacity after every visual layer has a stable compiler.
5. Add text-case conversion to the shared display-fragment pipeline.

Do not combine the five plans into one pull request. Each increment must leave
default output unchanged and the complete test suite passing.

## Commit strategy

Use one short-lived implementation branch and pull request per numbered plan.
Follow [docs/conventions.md](../../conventions.md), keep behavior with its focused
tests, and use a separate documentation commit when that makes the user-facing
contract easier to review.

Do not commit preview images, videos, retained subtitle artifacts, font files,
model caches, or machine-specific font paths. Every commit must leave the
package importable and its focused tests passing.

## Pull-request strategy

Each implementation pull request targets `main` and must link its individual
plan. The body must describe defaults, compatibility, CLI and JSON changes, ASS
serialization, measurement and wrapping effects, preview behavior, exact tests
run, visual evidence, and remaining renderer/font limitations.

Before opening a pull request:

1. Complete the plan's focused and repository-wide verification.
2. In the final pre-PR documentation commit, move the plan and package to
   `In review` and record the task branch in the Delivery column.
3. Push the complete branch before opening the pull request.
4. Do not create a post-open commit solely to record the PR number or URL.

After an authoritative merge signal, update the plan and package to `Done`,
replace the branch reference with the merged pull-request link, recalculate
progress, and identify the next unblocked plan.

## Release and rollback

The five options are additive and their defaults preserve current behavior, so
the package is expected to qualify for a minor `2.x` release unless an
implementation pull request changes an existing contract. Do not create a tag
automatically when the last plan merges; first verify the exact accumulated
diff, approve the staged artifact, and follow
[docs/delivery.md](../../delivery.md).

No persisted-data migration is required. Each numbered plan is independently
revertible before release. After a published release, recover through a normal
revert pull request and a new SemVer patch release; never move an existing tag.

## Shared definition of done

- Defaults preserve the current wrapping and rendered appearance; internal ASS
  fields may use the new semantic representation needed by a delivered option.
- CLI validation rejects invalid and conflicting values before model loading
  whenever geometry is not required.
- Preview and normal transcription use the same resolved typography,
  measurement, wrapping, serialization, and placement contracts.
- Font-aware and Unicode-estimate measurement account for letter spacing and
  explicit line height; fallback limitations remain visible in progress and
  JSON.
- Opacity multiplies existing component alpha exactly once and treats preview,
  ordinary cues, karaoke, boxes or outlines, and shadows consistently.
- Text-case conversion occurs before measurement and wrapping. SRT and ASS use
  transformed display text when requested, while JSON preserves the original
  transcript and aligned words. Generated ASS tags remain separate from escaped
  transcript fragments.
- Karaoke progressive, karaoke active-word, ordinary cues, boxes, outlines,
  shadows, native placement, and explicit placement remain compatible.
- JSON records requested and resolved typography without exposing local font
  paths or generated ASS markup.
- Hermetic unit tests, controlled FFmpeg/libass integration tests, compile and
  CLI smoke checks, Ruff, and Pyright pass.
- README.md, docs/prd.md, and docs/architecture.md describe every delivered
  option and its limitations.
