# Feature 8: layout preview

Status: Done

Pull request: [#37](https://github.com/denilson-santos/multisubs/pull/37)

Depends on:

- [Shared foundation](00-foundation.md)
- [Video geometry and ASS canvas](01-video-geometry-and-ass-canvas.md)
- [Named positions](02-named-positions.md)
- [Relative units](03-relative-units.md)
- [Layout presets](04-layout-presets.md)
- [Custom coordinates](05-custom-coordinates.md)
- [Adaptive line wrapping](06-adaptive-line-wrapping.md)
- [Placement modes and maximum height](07-placement-modes-and-maximum-height.md)

## Objective

Let a user inspect subtitle position, native ASS margins or the explicit
maximum envelope, font, colors, and wrapping on a real video frame without
loading WhisperX or running a complete transcription.

## Public interface

~~~
--preview-layout
--preview-at 00:00:10.500
--preview-text "Example subtitle preview text that demonstrates a readable two-line caption"
--preview-guides
~~~

Proposed defaults:

- preview-at: midpoint of the video when duration is known, otherwise zero.
- preview-text: a documented two-line sample suitable for evaluating alignment.
- preview-guides: off.

## Mode behavior

When --preview-layout is present:

1. Perform normal argument validation.
2. Validate FFmpeg and FFprobe.
3. Probe video geometry and duration.
4. Resolve appearance and layout.
5. Generate a temporary ASS with the sample cue.
6. Render one PNG at the selected timestamp.
7. Publish it collision-safely.
8. Remove temporary files.
9. Exit without importing PyTorch or WhisperX.

Do not create JSON, SRT, a final subtitle video, or a retained transcription
directory.

## Output contract

Default name:

~~~
<video-stem>-subtitle-preview.png
~~~

Use the existing collision-safe naming policy:

~~~
video-subtitle-preview.png
video-subtitle-preview (1).png
~~~

The CLI success message must identify the exact preview path.

## Timestamp parsing

Accept one documented format:

~~~
HH:MM:SS.mmm
~~~

Optionally also accept non-negative seconds if doing so remains unambiguous.
Normalize internally to finite seconds.

Validation:

- Non-negative.
- Not later than duration when duration is available.
- Finite and bounded.
- Frame extraction failure produces a rendering diagnostic.

## Preview text

- Treat preview text as untrusted user content.
- Normalize physical newlines consistently.
- Apply the same adaptive wrapping as real cues.
- Honor the same resolved maximum envelope and derived line capacity as final
  subtitle rendering.
- If the complete sample would require more than one timed cue, render only the
  first lexical group selected by the normal cue-boundary calculation. Omit the
  remaining groups because they represent later scenes in a real render.
- Preserve the calculated line breaks in the preview ASS so libass cannot add
  visual lines beyond the capacity derived from maximum height.
- Escape it with the same ASS dialogue serializer.
- Give the sample cue a duration that includes the requested frame timestamp.

## Guide overlay

When --preview-guides is active, render non-production diagnostics appropriate
to the selected placement mode:

- Native ASS margin region and active vertical margin for named placement.
- Maximum-width and maximum-height boundaries.
- Explicit envelope and anchor point for custom coordinates.
- Position or preset name.
- PlayRes dimensions.

Implement guides as generated ASS drawing events or a controlled FFmpeg overlay;
never combine raw user content into filter expressions. Guide style must be
visibly distinct and excluded from normal output.

## FFmpeg implementation

Add render_subtitle_preview() to multisubs/subtitler.py:

- Use structured ffmpeg-python arguments.
- Apply the same subtitles filter options as final rendering.
- Seek to the validated timestamp.
- Produce exactly one PNG frame.
- Capture bounded stderr.
- Write to a temporary path next to the final preview.
- Publish only after FFmpeg succeeds.
- Remove the partial image on both success and failure.

## CLI design

- Keep preview as a mode flag so the existing command shape remains valid.
- Reject transcription-only options only if their presence would be misleading;
  otherwise document that language, task, and model are ignored in preview mode.
- Prefer explicit conflict errors over silently ignoring output-affecting options.
- --keep-transcriptions is invalid in preview mode.
- Preview honors every appearance and deterministic layout option.

## Implementation tasks

- [x] Add preview CLI options.
- [x] Add preview mode with a dedicated PreviewRequest.
- [x] Branch before transcriber imports.
- [x] Parse and validate preview timestamp.
- [x] Generate the sample cue and temporary ASS.
- [x] Add guide generation.
- [x] Render and publish one PNG safely.
- [x] Add preview-specific success and failure messages.
- [x] Document which normal options are invalid or ignored.

## Unit tests

- PreviewRequest construction.
- Default midpoint and explicit timestamp.
- Unknown duration fallback.
- Timestamp before zero and beyond duration.
- Preview text escaping.
- Resolved maximum-height and derived-line-capacity propagation into preview cue
  layout.
- Width- and height-driven first-cue segmentation when the complete sample does
  not fit.
- Preservation of calculated ASS line breaks without renderer rewrapping.
- Guide event serialization.
- Collision-safe output.
- --keep-transcriptions conflict.
- FFmpeg failure preserves no published partial image.
- Monkeypatch import boundaries to prove WhisperX/PyTorch are not imported.

## Integration tests

- Render a preview for named placement.
- Render custom X/Y and anchor.
- Render one-line and two-line sample text.
- Render guides and verify they are present.
- Use paths containing spaces and Unicode.
- Verify the output is a valid PNG with the probed frame dimensions.

## Documentation

- Add a preview quick-start example.
- Document output naming and collision behavior.
- Explain that preview skips transcription.
- Include a guide-overlay example image if a small generated fixture is suitable.
- Update architecture execution flow with the early preview branch.
- Add preview behavior to product requirements and acceptance criteria.

## Commit and pull-request plan

Suggested branch:

~~~
feat/subtitle-layout-preview
~~~

Suggested commits:

1. feat: add a transcription-free layout preview request
   - Add CLI mode, timestamp validation, and import-boundary tests.
2. feat: render collision-safe subtitle preview frames
   - Add temporary ASS/PNG lifecycle, FFmpeg diagnostics, and publication tests.
3. feat: draw subtitle layout preview guides
   - Add native margin, explicit envelope, anchor, width/height, and canvas
     diagnostics.
4. docs: document subtitle layout previews
   - Add usage, output contract, conflicts, and troubleshooting.

Suggested pull request:

~~~
Title: feat: add fast subtitle layout previews
Base: main
~~~

The PR must prove that preview mode does not import WhisperX/PyTorch, document
its output lifecycle, and include generated examples as PR attachments rather
than repository artifacts.

Before requesting review:

- Run CLI, preview request, ASS, publication, and cleanup tests.
- Run the real FFmpeg PNG integration test.
- Verify failure cannot publish a partial preview.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- Preview completes without importing or loading WhisperX/PyTorch.
- The PNG uses the same resolved ASS and filter configuration as final rendering.
- Position, wrapping, and appearance match the eventual rendered video.
- An oversized sample shows only the first cue-sized lexical group and never
  gains renderer-created lines beyond the resolved maximum-height capacity.
- Failure never publishes a partial preview.
- Output naming remains collision-safe.
