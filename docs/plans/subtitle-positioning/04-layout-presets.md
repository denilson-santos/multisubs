# Feature 4: layout presets

Status: Planned

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)
- [Named positions](02-named-positions.md)
- [Relative units](03-relative-units.md)

## Objective

Provide coherent, reusable position and safe-area configurations for common
video geometries without requiring a long list of flags.

## Public interface

~~~
--layout auto
--layout landscape
--layout portrait
--layout square
--layout vertical-social
--layout upper-third
--layout centered
~~~

The default is auto.

## Proposed preset baselines

| Preset | Position | Left/right | Vertical inset | Max width | Max lines |
| --- | --- | --- | --- | --- | ---: |
| landscape | bottom-center | 6% / 6% | bottom 6% | 88% | 2 |
| portrait | bottom-center | 8% / 8% | bottom 8% | 84% | 2 |
| square | bottom-center | 7% / 7% | bottom 7% | 86% | 2 |
| vertical-social | bottom-center | asymmetric safe area | larger bottom inset | remaining safe width | 2 |
| upper-third | top-center | 6% / 6% | top 8% | 88% | 2 |
| centered | center | 8% / 8% | centered | 84% | 2 |

The vertical-social values must be calibrated with documented generic overlay
guides. The preset must not claim compatibility guarantees for a named social
platform whose interface can change.

Presets own the resolved default line count. The public `--max-lines` override
is delivered by [Feature 7](07-maximum-lines.md) after adaptive wrapping can
enforce the value without losing text or inventing timestamps.

## Auto selection

Proposed aspect-ratio bands:

- Landscape when width / height is greater than 1.1.
- Portrait when width / height is less than 0.9.
- Square otherwise.

The exact boundary values become product constants with focused boundary tests.
Selection uses render dimensions after rotation handling.

## Merge semantics

Presets are complete immutable SubtitleLayout values. Resolution order:

1. Load the selected preset.
2. Resolve auto to a concrete base preset.
3. Apply every explicit layout override.
4. Resolve relative units.
5. Validate the resulting safe rectangle.

Explicit values win field by field. Do not copy mutable preset dictionaries or
modify global defaults during a run.

## Configuration ownership

- Define preset source values in multisubs/config.py.
- Resolve and merge them in multisubs/layout.py.
- Keep ASS numeric values out of preset definitions.
- Include a human-readable preset description for CLI help and documentation.
- Record requested and resolved preset names in rendering metadata.

## Implementation tasks

- [ ] Define immutable preset objects.
- [ ] Add --layout choices and descriptions.
- [ ] Implement aspect-ratio classification.
- [ ] Implement field-by-field explicit overrides.
- [ ] Add safe-area validation after merge.
- [ ] Add requested/resolved metadata.
- [ ] Print the resolved preset in progress output.
- [ ] Visually calibrate defaults before final acceptance.

## Unit tests

- Every preset resolves to a complete layout.
- auto selects landscape, portrait, and square.
- Exact aspect-ratio boundaries.
- Rotation is applied before classification.
- Each explicit option overrides only its field.
- One invocation cannot mutate a preset used by another.
- Invalid post-merge safe areas fail.
- Rendering metadata distinguishes requested auto from resolved portrait, square,
  or landscape.

## Integration tests

Create golden preview images for each preset using a licensed synthetic video.
Review:

- Edge distances.
- Maximum line width.
- One-line and two-line vertical anchoring.
- Appearance at small and large resolutions.
- The asymmetric vertical-social safe area.

Golden updates require explicit visual review.

## Documentation

- Add one command example per preset family.
- Add normalized safe-area diagrams.
- Explain auto classification and override precedence.
- Document that vertical-social is generic rather than platform-guaranteed.
- Update FR-9 and acceptance criteria for preset selection.
- Add preset immutability and centralization to conventions.md.

## Commit and pull-request plan

Suggested branch:

~~~
feat/subtitle-layout-presets
~~~

Suggested commits:

1. feat: define immutable subtitle layout presets
   - Add complete preset objects and immutability tests.
2. feat: select subtitle layouts by aspect ratio
   - Add auto classification, explicit override merging, and boundary tests.
3. test: add golden previews for subtitle presets
   - Add reviewed reference renders and integration assertions.
4. docs: document subtitle layout presets
   - Add commands, safe-area diagrams, precedence, and product requirements.

Suggested pull request:

~~~
Title: feat: add subtitle layout presets
Base: dev
~~~

The PR must include the proposed preset values, visual calibration rationale,
aspect-ratio boundaries, and explicit-override examples. Golden preview changes
require deliberate visual review and licensing confirmation for their fixtures.

Before requesting review:

- Run preset completeness, immutability, boundary, and merge tests.
- Attach landscape, portrait, square, and vertical-social previews.
- Confirm auto uses post-rotation render geometry.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- --layout alone produces a complete valid layout.
- auto selects the expected preset after rotation is resolved.
- Explicit flags consistently override preset fields.
- Presets render within their documented safe areas.
- Defaults are backed by approved golden previews for landscape, portrait, and
  square video.
