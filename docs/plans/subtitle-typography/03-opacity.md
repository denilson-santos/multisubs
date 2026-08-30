# Subtitle opacity

Status: Done

Delivery: [#46](https://github.com/denilson-santos/multisubs/pull/46)

Depends on:

- [Font weight](00-font-weight.md)
- [Letter spacing](01-letter-spacing.md)
- [Line height](02-line-height.md)

## Objective

Let users adjust the opacity of the complete subtitle composition with one
predictable percentage while preserving the relative transparency already
encoded in text, karaoke, backdrop or outline, and shadow colors.

## Scope

Included:

- Add `--opacity PERCENT`, defaulting to `100%`.
- Accept percentages from `0%` through `100%`, including decimal percentages.
- Multiply every visual component's existing conventional alpha by the global
  opacity exactly once.
- Apply the same resolved colors in preview, retained ASS, and final rendering.
- Record requested opacity and effective component colors in JSON diagnostics.

Excluded:

- Separate opacity flags for text, karaoke, box, outline, or shadow.
- Changing the existing `#RRGGBB` and `#RRGGBBAA` color syntax.
- Animating opacity, fades, transitions, or cue-specific opacity.
- Altering video opacity or compositing an additional video layer.

## Decisions and constraints

- The public value must include `%`; bare numbers are rejected to avoid
  ambiguity between a percentage, a zero-to-one scalar, and an alpha byte.
- `100%` is neutral and preserves the current output byte-for-byte wherever the
  serializer is otherwise unchanged. `0%` is valid and makes every subtitle
  layer fully transparent without removing cues or changing timing.
- Opacity composes with each color's conventional alpha rather than replacing
  it. For a base alpha `A` in the inclusive range 0 through 255 and an opacity
  percentage `P`, the effective alpha is
  `round_half_up(A * P / 100)`, clamped to 0 through 255.
- Conventional alpha remains `00` transparent and `FF` opaque. Conversion to
  ASS inverted alpha occurs only after multiplication through the common color
  compiler.
- The multiplier is applied at one compiler boundary. Appearance resolution,
  karaoke overrides, line-height box drawing, and preview must consume the same
  effective palette rather than applying opacity independently.
- The option affects pixels only. Measurement, wrapping, cue segmentation,
  placement, timestamps, and artifact lifecycle do not change.
- This is additive and default-compatible and therefore does not require a
  major release.

## Public interface and contracts

~~~
--opacity 100%
--opacity 75%
--opacity 32.5%
--opacity 0%
~~~

Missing percent signs, negative values, values above `100%`, non-finite values,
and malformed units fail through CLI/configuration validation before ffprobe or
WhisperX. Typed configuration stores a normalized finite percentage or an
equivalent zero-to-one scalar chosen once for the internal contract.

For example, `--text-color #FFFFFFFF --opacity 50%` produces an effective text
alpha near 128, while `--text-color #FFFFFF80 --opacity 50%` produces an
effective alpha near 64. A backdrop whose configured opacity is 60% remains
less opaque than fully opaque text after both are multiplied by the same global
value.

SRT text, cue timing, and output paths are unaffected. JSON records the
requested percentage, normalized opacity, base component colors, and effective
component colors in conventional RGBA notation without exposing generated ASS
markup. These additive fields keep `schema_version` unchanged.

## Implementation

- Add the opacity value and percentage parser to the typed appearance contract
  in `multisubs/models.py` and `multisubs/config.py`, with `100%` as the default.
- Add `--opacity` to `multisubs/cli.py` and validate syntax and range before
  video probing or model loading.
- Add one pure alpha-composition helper to `multisubs/ass.py` or a shared color
  module. Reuse the existing conventional-RGBA validation and perform ASS alpha
  inversion only after composition.
- Resolve one effective palette for primary text, karaoke secondary/highlight
  color, backdrop or outline, and shadow. Ensure progressive and active-word
  karaoke overrides use the effective palette rather than raw configuration.
- Pass the same effective palette to preview generation, including explicit
  line-height events and any layered background rectangles.
- Extend `multisubs/transcriber.py` JSON rendering diagnostics with requested
  opacity and base/effective colors, avoiding local paths and ASS tags.

## Implementation tasks

- [x] Add the default, strict percentage parser, typed field, and revalidation.
- [x] Wire `--opacity` into CLI help and request construction.
- [x] Implement conventional-alpha multiplication with documented rounding.
- [x] Apply the effective palette once across ordinary ASS, karaoke overrides,
  boxes or outlines, shadows, explicit line-height events, and preview.
- [x] Add opacity and base/effective palette diagnostics to JSON.
- [x] Add focused configuration, CLI, color, ASS, karaoke, preview, metadata,
  and default-output tests.
- [x] Update README.md, docs/prd.md, docs/architecture.md, and package status.

## Unit tests

- Parsing and normalization of `0%`, integer percentages, decimal percentages,
  and `100%`.
- Rejection of bare numbers, empty values, negative or over-100 values,
  unsupported units, NaN, infinity, and malformed percentages.
- Alpha multiplication at transparent, half-transparent, and opaque base
  values, including explicit half-up rounding and clamping.
- `100%` identity, `0%` full transparency, and proof that alpha is not
  multiplied twice.
- Primary text, karaoke highlight/secondary color, backdrop or outline, and
  shadow all use their own base alpha with the common multiplier.
- Conventional RGBA-to-ASS BGR/inverted-alpha conversion remains correct after
  composition, including override tags.
- Default-output regression confirming that omitted opacity preserves current
  ASS and preview behavior.

## Integration and manual verification

- Render ordinary, progressive karaoke, and active-word karaoke samples at
  `100%`, `50%`, and `0%`; compare preview and final frames at the same cue.
- Repeat with a semi-transparent text color and the default translucent box to
  confirm relative alpha is preserved rather than overwritten.
- Verify outline and shadow variants, explicit line height, native placement,
  and explicit coordinates without changing bounds or wrapping.
- Inspect retained ASS to confirm style colors and generated overrides contain
  the effective alpha and transcript text remains escaped separately.

## Documentation

- Add `--opacity`, accepted syntax, default, examples, composition formula, and
  interaction with RGBA colors to the README command and appearance references.
- Explain that opacity applies to the complete subtitle composition and that
  component-specific alpha remains available through color values.
- Extend FR-9 and appearance acceptance criteria in docs/prd.md.
- Update the typed appearance, palette compilation, preview, karaoke, ASS, and
  JSON contracts in docs/architecture.md.
- Update docs/conventions.md only if the color-composition helper establishes a
  reusable rounding or color-space convention.

## Commit and pull-request plan

Suggested branch:

~~~
feat/subtitle-opacity
~~~

Suggested commits:

1. `feat: add global subtitle opacity`
   - Typed configuration, CLI, alpha composition, ASS/preview/JSON integration,
     and focused tests.
2. `docs: document subtitle opacity`
   - README, PRD, architecture, and roadmap status.

Suggested pull request:

~~~
Title: feat: add global subtitle opacity
Base: main
~~~

Before opening the pull request:

- Run `python -m pytest tests/test_config.py tests/test_cli.py tests/test_ass.py tests/test_preview.py tests/test_karaoke.py tests/test_transcriber.py`.
- Run the relevant controlled FFmpeg checks with
  `python -m pytest -m integration tests/test_integration.py -k subtitle` when
  their prerequisites are available.
- Run `python -m compileall multisubs`, `multisubs --help`,
  `python -m pytest`, `python -m ruff check .`, and `python -m pyright`.
- In the final pre-PR documentation commit, move the plan and package to
  `In review` and record `feat/subtitle-opacity` as the delivery reference.
- Push the complete branch before opening the PR; do not add a post-open commit
  solely for its number or URL.

After merge:

- Mark Plan 3 `Done`, replace the branch with the merged PR link, recalculate
  package/catalog progress, and identify Plan 4 as the next unblocked plan.

## Acceptance criteria

- `--opacity` accepts only an explicit percentage from `0%` through `100%` and
  invalid input fails before video or model loading.
- Effective alpha equals each component's existing alpha multiplied by the
  global opacity with one documented rounding rule.
- Preview, ordinary ASS, progressive karaoke, active-word karaoke, boxes or
  outlines, shadows, retained ASS, and final rendering agree.
- `100%` preserves current appearance, and `0%` changes no text, geometry,
  timing, or output lifecycle despite producing transparent subtitle pixels.
- JSON records requested opacity and base/effective colors without ASS markup
  or machine-specific data.
- SRT text, transcript text, cue timing, wrapping, placement, and artifact
  lifecycle remain unchanged.
