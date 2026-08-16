# Feature 3: relative layout units

Status: In review

Pull request: [#12](https://github.com/denilson-santos/multisubs/pull/12)

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)

## Objective

Allow resolution-independent font sizes, margins, maximum widths, and coordinates
while preserving explicit pixel control for advanced users.

## Public syntax

Accepted forms:

~~~
8%
4.5%
72px
0px
~~~

Bare numbers are rejected so the coordinate system is never ambiguous.

The current staged implementation wires unit-bearing options for the dimensions
already present in the typed configuration: font size, backdrop/outline size,
shadow size, and four margins. `--position-x`/`--position-y` are introduced by
[Feature 5](05-custom-coordinates.md), and `--max-width` is introduced by
[Feature 6](06-adaptive-line-wrapping.md); both consume the same parser and
resolution helpers rather than being duplicated in this feature.

## Resolution bases

| Field | Percent basis |
| --- | --- |
| margin-left, margin-right, max-width, position-x | Render width |
| margin-top, margin-bottom, position-y | Render height |
| font-size | Shorter render edge |
| backdrop-size, shadow-size | Resolved font size |

Pixel values refer to the PlayRes canvas, which is defined to match render
geometry.

## Defaults

Proposed appearance baseline:

- font-size: 4.5% of the shorter edge;
- backdrop-size: 6% of the resolved font size;
- shadow-size: 4% of the resolved font size.

Layout defaults come from presets. Values must be visually calibrated in the
integration matrix before being frozen as the public defaults.

## Parser and data model

RelativeLength stores:

- A finite decimal value.
- Unit.
- Original string.

Parsing must:

- Trim surrounding whitespace.
- Require an exact % or px suffix.
- Reject NaN, infinity, exponent abuse, signs where not supported, and trailing
  content.
- Bound the number of digits and decimal places.
- Avoid oversized integer conversion failures.

Resolution converts RelativeLength into a non-negative integer ASS coordinate.
Use one documented rounding function consistently.

## Field validation

### Percent coordinates

- position-x and position-y: 0% through 100%.

### Pixel coordinates

- X: 0 through render width.
- Y: 0 through render height.

### Margins

- Non-negative.
- left + right must leave positive width.
- top + bottom must leave positive height.

### Maximum width

- Greater than zero.
- Cannot exceed the safe rectangle width.

### Font size

- Greater than zero.
- Enforce an upper bound that prevents a single line from consuming an
  unreasonable portion of the frame.

### Backdrop and shadow

- Non-negative.
- Bound relative to resolved font size.

All geometry-dependent validation happens after FFprobe and before WhisperX.

## Implementation

- Add parse_relative_length().
- Add axis-specific resolution helpers instead of one ambiguous conversion.
- Add safe integer bounds before ASS serialization.
- Resolve the complete layout once; never convert units independently in the ASS
  writer.
- Retain both requested and resolved values in rendering metadata.
- Make CLI diagnostics identify the option and its percentage basis.

## Implementation tasks

- [x] Implement strict syntax parsing.
- [x] Define per-field percentage bases.
- [x] Define rounding and bounds.
- [x] Convert appearance values.
- [x] Convert layout values.
- [x] Validate combined safe-area dimensions.
- [x] Add requested/resolved JSON metadata.
- [x] Add unit syntax to CLI help.

## Unit tests

- Integer and decimal percentages.
- Integer and decimal pixels.
- Whitespace.
- Missing unit.
- Negative values.
- NaN, infinity, oversized numbers, and excessive precision.
- 0%, 100%, and exact canvas-edge coordinates.
- Landscape, portrait, square, 720p, 1080p, and 4K conversion.
- Margin sums that eliminate the safe rectangle.
- Maximum width larger than the safe area.
- Deterministic rounding.

Property-oriented tests should verify that valid percentages remain monotonic as
video dimensions increase.

## Integration tests

Render the same relative layout at multiple resolutions and compare normalized
subtitle bounds. Also render a fixed-pixel layout to verify that pixel values do
not scale unexpectedly.

## Documentation

- Add a units section to README with the percentage-basis table.
- Include examples using both % and px.
- Explain why bare numbers are invalid.
- Document rounding and safe-area validation in architecture.md.
- Add cross-resolution behavior to product acceptance criteria.

## Commit and pull-request plan

Suggested branch:

~~~
feat/relative-subtitle-units
~~~

Suggested commits:

1. feat: parse explicit subtitle length units
   - Add RelativeLength, strict syntax validation, bounds, and parser tests.
2. feat: resolve subtitle units against video geometry
   - Add field-specific bases, rounding, cross-field validation, and metadata.
3. test: verify subtitle scaling across resolutions
   - Add normalized-bound coverage for percent and fixed-pixel layouts.
4. docs: document subtitle layout units
   - Add unit syntax, bases, validation, and migration examples.

Suggested pull request:

~~~
Title: feat: add relative units for subtitle layout
Base: dev
~~~

The PR description must list the percentage basis for every public field, show
rounding examples, and explain the decision to reject bare numbers. Include
before/after normalized measurements rather than relying only on screenshots.

Before requesting review:

- Run parser boundary and oversized-number tests.
- Verify geometry-dependent errors precede WhisperX loading.
- Run the multi-resolution integration matrix.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- Every public dimension has an unambiguous unit.
- Percentage values resolve against the documented axis.
- Invalid combinations fail before transcription.
- Equivalent relative values produce equivalent normalized placement across the
  supported resolution matrix.
