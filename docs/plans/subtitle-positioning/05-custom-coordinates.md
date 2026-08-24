# Feature 5: custom subtitle coordinates

Status: Done

Pull request: [#15](https://github.com/denilson-santos/multisubs/pull/15)

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)
- [Named positions](02-named-positions.md)
- [Relative units](03-relative-units.md)

## Objective

Allow an advanced user to place a chosen point of the subtitle box at an exact
X/Y coordinate.

## Public interface

~~~
--position-x 50%
--position-y 86%
--anchor bottom-center
~~~

Both coordinates accept percent or pixel units. The initial implementation
defaulted the custom anchor to bottom-center;
[Feature 7](07-placement-modes-and-maximum-height.md) makes it explicit together
with max-width and max-height so the envelope contract has no hidden inputs.

## Coordinate meaning

- position-x is measured from the PlayRes canvas left edge.
- position-y is measured from the PlayRes canvas top edge.
- anchor identifies the point on the subtitle box attached to that coordinate.
- The anchor uses the same nine public names as --position.

Example:

~~~
--position-x 50% --position-y 86% --anchor bottom-center
~~~

This places the bottom-center of the subtitle box at 50% of PlayRes width and
86% of PlayRes height.

Feature 6 temporarily changed these values to safe-area-local offsets.
[Feature 7](07-placement-modes-and-maximum-height.md) supersedes that untagged
amendment and restores this plan's original global PlayRes coordinate contract.
Margins are ignored for explicit `\pos` placement, matching ASS behavior.

## CLI conflict rules

- position-x and position-y must be supplied together.
- --position is incompatible with custom coordinates.
- --layout may still provide appearance and a preset for native mode, but its
  margins and maximum dimensions do not define explicit placement.
- --anchor without custom coordinates is rejected to avoid a no-op option.
- [Feature 7](07-placement-modes-and-maximum-height.md) requires users to supply
  max-width and max-height with explicit coordinates so the complete subtitle
  envelope can be validated.

All syntax conflicts fail before FFprobe. Canvas-bound checks happen after
FFprobe and before WhisperX.

## ASS implementation

Generate an internal event override directly in the PlayRes canvas. For a
1920x1080 canvas, `50%`/`86%` resolves to:

~~~
{\an2\pos(960,929)}
~~~

Rules:

- Convert public anchor to private ASS alignment.
- Resolve coordinates directly against the PlayRes canvas axes.
- Build generated tags in a dedicated serializer.
- Escape transcription text separately.
- Concatenate generated tags only after both pieces are independently valid.
- Never accept raw ASS override text from the CLI.

Although the first implementation applies one coordinate to every cue, represent
placement per cue internally so later features do not require another ASS event
contract change.

## Explicit envelope behavior

- max-width and max-height define the complete maximum subtitle envelope around
  the anchor.
- Margins do not affect explicit placement or its available space.
- Percentage maximum dimensions resolve against full render width/height.
- Reject an envelope that crosses any canvas edge; do not shrink it to anchor
  capacity or move its coordinate.
- Reject an anchor outside the PlayRes canvas.
- An explicit future allow-offscreen switch would require a separate product
  decision; do not silently permit clipping.
- Measure the subtitle box before rendering and reject a maximum height that
  cannot fit one line with its decorations.

## Implementation tasks

- [x] Add X/Y and anchor arguments.
- [x] Add pair and conflict validation.
- [x] Resolve coordinates against PlayRes.
- [x] Add CuePlacement to the internal cue contract.
- [x] Implement safe generated override serialization.
- [x] Integrate generated tags with escaped dialogue text.
- [x] Record requested and resolved coordinates.
- [ ] Add custom placement to preview mode; the preview CLI is delivered by
      [Feature 8](08-layout-preview.md), so this branch only exposes the
      reusable per-cue placement contract.

## Unit tests

- Percent and pixel X/Y conversion.
- Required coordinate pair.
- Default and explicit anchors.
- All nine anchors.
- Coordinates at 0% and 100%.
- Coordinates outside the PlayRes width or height.
- Conflict with named position.
- Anchor without coordinates.
- Text containing braces, backslashes, commas, newlines, Unicode, and fake ASS
  overrides.
- Generated tags appear before escaped text exactly once.

## Integration tests

Render known coordinates and measure the subtitle alpha bounds:

- Center anchor at frame center.
- Bottom-center anchor near the lower canvas edge with a valid envelope.
- Top-left at an explicit pixel position.
- One-line and two-line cues using the same anchor.
- Landscape, portrait, and square canvases.

Allow only the documented rounding tolerance.

## Documentation

- Add a coordinate-system diagram.
- Explain that Y grows downward.
- Document anchor semantics and conflicts.
- Include percent and pixel examples.
- State that SRT cannot preserve these coordinates; positioning is represented in
  ASS and the rendered video.
- Update the ASS event contract in architecture.md.

## Commit and pull-request plan

Suggested branch:

~~~
feat/custom-subtitle-coordinates
~~~

Suggested commits:

1. feat: add custom subtitle coordinates and anchors
   - Add CLI validation, coordinate resolution, and anchor tests.
2. feat: serialize safe ASS position overrides
   - Add CuePlacement, generated-tag isolation, and injection regressions.
3. test: verify exact rendered subtitle anchors
   - Add alpha-bound integration checks for representative anchors.
4. docs: document custom subtitle coordinates
   - Add diagrams, examples, conflicts, and SRT limitations.

Suggested pull request:

~~~
Title: feat: support exact subtitle coordinates
Base: dev
~~~

The PR description must state the coordinate origin, Y direction, anchor
semantics, clipping policy, and rounding tolerance. Security review must focus on
the boundary between generated ASS tags and escaped transcript text.

Before requesting review:

- Run all ASS escaping and injection regression tests.
- Measure representative rendered anchor positions.
- Verify every invalid option combination fails before transcription.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- The selected subtitle anchor lands on the requested global PlayRes coordinate
  within one ASS coordinate of rounding tolerance.
- Custom placement remains stable between one-line and two-line cues.
- Transcript content cannot inject or alter generated position tags.
- Invalid or clipped placements fail before transcription.
