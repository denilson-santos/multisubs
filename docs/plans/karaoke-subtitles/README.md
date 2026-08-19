# Karaoke subtitles roadmap

Status: Planned

This directory contains the implementation plan for adding an optional
word-timed karaoke effect to rendered subtitles. The package owns effect timing
and ASS compilation; subtitle geometry, cue wrapping, and maximum-line policy
remain in the [subtitle-positioning roadmap](../subtitle-positioning/README.md).

## Product outcome

Users can request subtitles whose words change from the normal text color to a
highlight color as their aligned timestamps are reached. Plain subtitles remain
the default, SRT stays portable and free of ASS markup, and unsupported timing
data degrades visibly and safely instead of receiving invented timestamps.

## Plan status

This table is the source of truth for the package. Status values follow the
[plan catalog vocabulary](../README.md#status-vocabulary).

| Order | Plan | Status | Depends on | Pull request |
| --- | --- | --- | --- | --- |
| 0 | [Word-timed highlighting](00-word-timed-highlighting.md) | Planned | Subtitle positioning 0, 6, and CLI cutover | — |

Package progress: 0 of 1 plans done; Plan 0 awaits its cross-package
dependencies before implementation starts.

## Cross-package dependencies

Implementation starts after:

- [Shared subtitle-layout foundation](../subtitle-positioning/00-foundation.md),
  which is already complete.
- [Adaptive line wrapping](../subtitle-positioning/06-adaptive-line-wrapping.md),
  which separates semantic words from display text and intentional line breaks.
- The [breaking CLI cutover](../subtitle-positioning/README.md#breaking-cli-cutover),
  so the new effect uses semantic color controls rather than extending the
  temporary `--style-*` interface.

Maximum-line overrides and layout preview are not prerequisites. They must,
however, continue consuming the same display-cue contract when implemented.

## Delivery order

1. Merge the cross-package dependencies above into `main`.
2. Implement [Plan 0](00-word-timed-highlighting.md) in one focused branch and
   pull request.
3. After merge, mark the plan and package Done in the next planning-status
   update and update the top-level catalog.

## Commit strategy

Use one implementation branch for this package and keep each commit importable
and covered by the focused test subset. Separate the typed display-token
refactor, ASS effect compilation, public CLI wiring, real-render coverage, and
documentation when those changes remain independently reviewable.

Follow [docs/conventions.md](../../conventions.md) for commit subjects. Do not
commit generated videos, subtitle artifacts, model caches, fixup commits, or
unrelated formatting changes.

## Pull-request strategy

The implementation pull request targets `main` after all dependencies are
merged. It must link the individual plan, describe the CLI and artifact
contracts, include exact verification results, and attach representative
before/during/after render frames produced with a controlled font.

Before final review:

1. Change the plan row to In review and add the pull-request link.
2. Complete every acceptance criterion or document an explicit exception.
3. Run the focused, repository-wide, and opt-in FFmpeg/libass checks named in
   the plan.
4. Confirm that the default non-karaoke output remains unchanged.
5. Confirm no generated media or retained transcription artifact is staged.

After merge, change the row to Done, set package progress to 1 of 1, and update
the package row in [the plan catalog](../README.md).

## Definition of done

- Karaoke is opt-in and unavailable combinations fail before model loading.
- Highlight timing is derived only from validated aligned-word timestamps.
- Cues without a lossless word-to-display mapping fall back to plain rendering
  with a user-visible warning and machine-readable count.
- Generated ASS control tags are compiled separately from escaped transcript
  text, and SRT never receives those tags.
- Plain and karaoke JSON, SRT, ASS, retained-artifact, cleanup, and rendered-video
  contracts are documented and tested.
- Hermetic unit tests, controlled FFmpeg/libass integration tests, compile and
  CLI smoke checks, Ruff, and Pyright pass.
- README.md, docs/prd.md, docs/architecture.md, and any new reusable convention
  are updated in the implementation pull request.
