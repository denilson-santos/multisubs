# Feature 2: named subtitle positions

Status: Done

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)

## Objective

Replace numeric ASS alignment with human-readable visual positions.

## Public interface

Add:

~~~
--position top-left
--position top-center
--position top-right
--position middle-left
--position center
--position middle-right
--position bottom-left
--position bottom-center
--position bottom-right
~~~

The default is bottom-center unless a selected preset provides another value.

Remove:

~~~
--style-alignment
~~~

## Internal mapping

| Public position | ASS alignment |
| --- | ---: |
| bottom-left | 1 |
| bottom-center | 2 |
| bottom-right | 3 |
| middle-left | 4 |
| center | 5 |
| middle-right | 6 |
| top-left | 7 |
| top-center | 8 |
| top-right | 9 |

The numeric value must be private to the ASS compiler.

## Margin behavior

- Left-aligned positions use margin-left as their edge inset.
- Right-aligned positions use margin-right.
- Bottom positions use margin-bottom.
- Top positions use margin-top.
- Middle positions follow native ASS alignment and are not moved vertically by
  MarginV.
- Equal left and right margins preserve geometric centering inside the native
  ASS layout region.
- Unequal margins intentionally shift that native layout region.

Left and right are physical screen directions. They are not language-relative
start and end values.

Pull request #33 temporarily changed named positions to safe-area `\an`/`\pos`
events. [Feature 7](07-placement-modes-and-maximum-height.md) supersedes that
untagged refinement and restores this plan's native ASS style alignment and
margin contract. The public `--position` interface and this plan's Done status
are unchanged.

## Implementation

- Add a SubtitlePosition enum or equivalent closed type.
- Parse positions through argparse choices.
- Map the position to an internal anchor and ASS alignment.
- Compile native ASS margins for the selected vertical alignment.
- Store the position on SubtitleLayout, not SubtitleAppearance.
- Keep per-event generated override support available for custom coordinates.
- Include requested and resolved position in rendering metadata.

## Validation

- Unknown names fail through argparse.
- --position cannot be combined with complete custom X/Y positioning.
- Horizontal margins that leave no usable native layout width fail before
  transcription.
- Position names are lowercase and hyphenated; do not accept numeric aliases.

## Implementation tasks

- [x] Define the public position choices.
- [x] Remove numeric alignment parsing.
- [x] Add position-to-anchor mapping.
- [x] Add safe-rectangle calculation.
- [x] Update ASS style compilation.
- [ ] Add cross-field conflict validation (deferred until Feature 5 adds custom coordinates).
- [x] Update progress and rendering metadata.
- [x] Replace CLI help and examples.

## Unit tests

- Exact mapping for all nine values.
- Default bottom-center.
- Each edge selects the correct margin.
- Unequal side margins affect the native ASS layout region predictably.
- Unknown and numeric inputs fail.
- Conflict with custom coordinates fails before runtime.
- Generated ASS contains the correct private numeric alignment.

Implemented in `tests/test_layout.py`, `tests/test_cli.py`,
`tests/test_config.py`, and `tests/test_ass.py`. Custom-coordinate conflict
coverage remains pending Feature 5 because those public options do not exist yet.

## Integration tests

Render one short two-line subtitle in all nine positions and verify:

- Its bounding box falls inside the expected third of the frame.
- It remains inside the native margin region.
- Top and bottom margins are measured from the correct edge.
- Text with right-to-left shaping does not reverse the physical position.

Implemented in `tests/test_integration.py` as an opt-in nine-position render
matrix. RTL-specific shaping remains covered when the integration font/runtime
fixture is expanded.

## Documentation

- Add a three-by-three position diagram to README.
- Remove all user-facing references to ASS alignment numbers.
- Document left/right as screen directions.
- Update the ASS style contract in architecture.md.
- Update FR-9 and acceptance criteria to name semantic positioning.

## Commit and pull-request plan

Suggested branch:

~~~
feat/named-subtitle-positions
~~~

Suggested commits:

1. feat: add named subtitle positions
   - Add the closed position type, CLI choices, mapping, and unit tests.
2. feat: apply position-aware safe margins
   - Resolve the safe rectangle and compile private ASS alignment values.
3. test: render the named position matrix
   - Add opt-in visual-bound checks for all nine positions.
4. docs: document named subtitle positions
   - Replace numeric alignment examples and add the position diagram.

Suggested pull request:

~~~
Title: feat: replace numeric subtitle alignment with named positions
Base: dev
~~~

The PR must show the public-name-to-private-ASS mapping, document conflicts with
custom coordinates, and include representative top, center, and bottom preview
evidence without committing generated media.

Before requesting review:

- Verify all nine mappings and margin directions.
- Run CLI parsing, layout, ASS, and relevant integration tests.
- Confirm no numeric alignment option remains in the new interface.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- Users can select every standard ASS anchor by name.
- No public error or help text requires numeric ASS alignment knowledge.
- The chosen position and edge margins are consistent across aspect ratios.
- Position conflicts are rejected before WhisperX loading.
