# Feature 1: video geometry and ASS canvas

Status: In review

Depends on: [shared foundation](00-foundation.md)

## Objective

Make ASS coordinates, margins, font sizes, outlines, and shadows predictable by
declaring an explicit script resolution based on the frames that FFmpeg will
render.

## Public behavior

This feature does not require a new positioning option. Geometry is detected
from the input video before transcription and used by every layout mode.

The user should see proportional results across resolutions instead of relying
on libass defaults for an ASS file without PlayResX and PlayResY.

## Geometry contract

VideoGeometry must distinguish:

- Coded dimensions reported by the video stream.
- Render dimensions seen by the subtitles filter.
- Rotation metadata.
- Sample aspect ratio.
- Display aspect ratio.
- Duration.

The first usable video stream is selected deterministically and its index is
recorded. Missing or multiple streams must never cause an arbitrary mapping.

## Probe implementation

Add probe_video_geometry() to multisubs/subtitler.py:

1. Locate ffprobe.
2. Request JSON output for streams and container duration.
3. Select the first supported video stream.
4. Validate width and height as positive bounded integers.
5. Parse rotation from tags or display-matrix side data.
6. Normalize right-angle rotation.
7. Calculate the frame dimensions seen by the render graph.
8. Parse sample aspect ratio without trusting malformed fractions.
9. Return a typed VideoGeometry.

Both ffmpeg and ffprobe availability must be checked before starting WhisperX.
FFprobe stderr should be bounded in user-facing errors.

## Rotation policy

The probe and render graph must agree about autorotation:

- For 0° and 180°, keep width and height.
- For 90° and 270°, swap render width and render height if FFmpeg autorotation is
  enabled.
- Integration tests must verify the actual filtered frame dimensions.
- If autorotation behavior is made explicit in the FFmpeg command, document and
  test that policy rather than relying on an executable default.

## ASS changes

Write the following Script Info fields:

~~~
ScriptType: v4.00+
PlayResX: <render width>
PlayResY: <render height>
ScaledBorderAndShadow: yes
WrapStyle: 0
~~~

Use the same resolved dimensions for all ASS margins and generated position
coordinates.

Until relative units are introduced, the temporary `--style-*` numeric values
are interpreted against the legacy 384x288 ASS design canvas and scaled to the
resolved render dimensions. This keeps the default `Roboto 14` appearance
proportional while preserving the raw option values for the later CLI cutover.

Pass original_size to the FFmpeg subtitles filter when required by the render
graph's aspect-ratio policy. Pass fontsdir only when the user supplied a
validated fonts directory.

## Validation and failures

Reject before transcription:

- No video stream.
- Zero, negative, non-numeric, or unreasonably large dimensions.
- Unsupported or contradictory rotation metadata.
- Invalid sample aspect ratio when it affects render geometry.
- ffprobe unavailable or returning invalid JSON.

Do not expose the complete ffprobe payload or unbounded stderr in diagnostics.

## Implementation tasks

- [x] Extend FFmpeg dependency validation to ffprobe.
- [x] Add VideoGeometry.
- [x] Add a narrow JSON probe parser.
- [x] Resolve autorotation and aspect-ratio policy.
- [x] Pass geometry through RunRequest execution.
- [x] Add PlayResX and PlayResY to ASS.
- [x] Add ScaledBorderAndShadow and WrapStyle.
- [x] Supply original_size where the render policy requires it.
- [x] Record resolved geometry in JSON rendering metadata.
- [x] Report detected layout dimensions in progress output.

## Unit tests

- Landscape coded and render dimensions.
- Stored portrait video.
- 90° and 270° display rotation.
- 180° rotation.
- Valid and invalid sample aspect ratios.
- Missing duration.
- Missing video stream.
- Multiple video streams.
- Malformed JSON and non-zero ffprobe exit.
- ASS header field order and values.
- FFmpeg filter receives matching original_size.

Mock the external commands in the default test suite.

## Integration tests

Use tiny generated, licensed fixtures:

- 1920x1080-equivalent landscape.
- 1080x1920-equivalent portrait.
- Square.
- Rotation metadata.
- Non-square pixels.

The fixtures may use smaller physical sizes as long as their aspect and rotation
properties exercise the same logic. Render a known subtitle and verify that its
pixel bounds are proportional.

## Documentation

- Add ffprobe to README requirements.
- Explain that positioning uses displayed frame dimensions.
- Document rotation and non-square-pixel handling.
- Update the architecture FFmpeg boundary and ASS contract.
- Update product acceptance criteria for cross-resolution consistency.

## Commit and pull-request plan

Suggested branch:

~~~
feat/video-geometry-ass-canvas
~~~

Suggested commits:

1. feat: probe normalized video geometry
   - Add ffprobe validation, parsing, rotation policy, and hermetic tests.
2. feat: define a video-aware ASS canvas
   - Add PlayRes fields, filter sizing, rendering metadata, and ASS tests.
3. test: cover rendered subtitle geometry
   - Add the opt-in rotation, aspect-ratio, and normalized-bound checks.
4. docs: document video-aware subtitle geometry
   - Update requirements, architecture, PRD, and user-facing limitations.

Suggested pull request:

~~~
Title: feat: make the ASS canvas follow video geometry
Base: dev
~~~

The PR description must include sample probe inputs and normalized outputs,
explain autorotation and sample-aspect-ratio policy, and state whether ffprobe is
a new user prerequisite. Attach generated preview evidence to the PR; do not
commit preview media.

Before requesting review:

- Run focused probe, ASS, subtitler, CLI, and integration tests.
- Verify absent ffprobe and malformed media failures occur before WhisperX.
- Confirm the rendered frame and PlayRes dimensions match.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- Every generated ASS declares positive PlayResX and PlayResY.
- The declared canvas equals the frame dimensions used for subtitle rendering.
- A relative test layout occupies equivalent frame proportions in landscape,
  portrait, square, 720p, 1080p, and 4K cases.
- Rotation metadata does not place subtitles against the wrong physical edge.
- Probe failures occur before model loading and produce actionable diagnostics.
