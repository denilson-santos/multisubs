# Shared foundation for subtitle layout

Status: In progress

## Objective

Replace the raw ASS-oriented style dictionary with typed appearance and layout
contracts. Reorder the pipeline so video geometry is known before ASS layout is
resolved, without weakening artifact safety or forcing heavy runtime imports
during CLI validation.

This foundation is a prerequisite for the seven positioning features. It should
land as a behavior-preserving refactor and retain a temporary adapter for the
existing --style-* inputs. Their approved removal belongs to the package cutover
after the replacement interface is complete.

## Current constraints

- multisubs/config.py stores ASS field names directly in DEFAULT_STYLE.
- multisubs/cli.py generates every --style-* argument by iterating over that
  dictionary.
- RunRequest transports an unstructured Mapping of style values.
- generate_transcriptions() transcribes and immediately writes JSON, SRT, and ASS.
- The ASS writer has no neutral layout model and receives no video geometry.
- The same cue text currently represents semantic text and visual line wrapping.

These couplings make percentage units, previews, and geometry-dependent wrapping
difficult to add safely.

## Target data model

The foundation adds the typed objects needed immediately and reserves the
remaining contracts for the feature that can validate them correctly. Do not add
unused placeholder types merely to satisfy the roadmap.

### RelativeLength

Added by Feature 3 after its syntax and resolution bases are implemented.

- Numeric value.
- Unit: percent or pixel.
- Resolution basis supplied by the field that consumes it.
- Original user representation retained for actionable diagnostics.

### VideoGeometry

Added by Feature 1 together with the FFprobe boundary.

- coded_width and coded_height.
- render_width and render_height.
- sample_aspect_ratio.
- display_aspect_ratio when available.
- rotation.
- duration when available.
- selected video stream index.

### SubtitleAppearance

- font.
- font_size.
- text_color.
- bold.
- italic.
- backdrop kind: none, outline, or box.
- backdrop_color.
- backdrop_size.
- shadow_size.
- optional fonts_dir.

### SubtitleLayout

- selected preset.
- named position or custom-coordinate mode.
- optional position_x and position_y.
- anchor.
- margins for all four edges.
- maximum width.
- maximum visual lines.

### ResolvedSubtitleConfig

Added incrementally as geometry and relative units become available.

- Appearance converted into ASS-safe scalar values.
- Layout converted into PlayRes coordinates and margins.
- Original preset and explicit-override information for reproducibility.
- No unresolved percentages.

### TranscriptDocument and SubtitleCue

The foundation adds TranscriptDocument and separates semantic transcription from
artifact writing. CuePlacement and the final visual cue type are added by the
coordinate and wrapping features.

- Transcript metadata and unwrapped semantic cue text.
- Word timings retained separately.
- Visual text produced only after layout resolution.
- Optional generated ASS overrides stored outside user/transcription text.

## Target CLI redesign

Remove the loop that exposes every DEFAULT_STYLE key. Define explicit argument
groups and help text:

### Appearance

~~~
--font
--font-size
--text-color
--bold / --no-bold
--italic / --no-italic
--backdrop
--backdrop-color
--backdrop-size
--shadow-size
--fonts-dir
~~~

### Layout

~~~
--layout
--position
--margin-left
--margin-right
--margin-top
--margin-bottom
--max-width
--max-lines
--position-x
--position-y
--anchor
~~~

### Preview

~~~
--preview-layout
--preview-at
--preview-text
--preview-guides
~~~

Remove these public ASS details:

- Numeric alignment.
- BorderStyle codes.
- ASS color syntax.
- SecondaryColour.
- Encoding.
- ScaleX and ScaleY.
- Angle.
- Spacing.
- Underline and StrikeOut.

Internally, the ASS compiler still supplies every required style field in the
correct order.

## User-facing color format

Accept:

- #RRGGBB for an opaque color.
- #RRGGBBAA for a color with conventional alpha.

Convert to ASS BGR color order and inverted ASS alpha only inside the ASS
serializer. Validate the original value before model loading. Keep shell quoting
examples in the README because # can start a shell comment.

## Pipeline split

Refactor the current generate_transcriptions() responsibilities into:

1. transcribe_video(): model loading, transcription, alignment, and semantic cues.
2. resolve_subtitle_config(): presets, geometry, units, and validation.
3. layout_subtitle_cues(): visual wrapping and generated placement data.
4. write_transcription_artifacts(): JSON, SRT, and ASS.
5. embed_subtitles(): final FFmpeg render.

Keep generate_transcriptions() as a programmatic compatibility wrapper unless a
separate major API change is explicitly approved. The CLI should use the split
pipeline directly.

## Module responsibilities

### multisubs/config.py

- Supported language and model choices.
- Built-in appearance defaults.
- Immutable layout preset definitions.
- No generic ASS-style validation.

### multisubs/layout.py

Introduced by the first dependent feature that needs geometry or unit resolution.

- RelativeLength parsing.
- Preset merge and precedence.
- Resolution-dependent validation.
- Named-position mapping.
- Safe-area calculations.
- Cue layout calculations.

### multisubs/ass.py

- ASS header and style field ordering.
- User color conversion.
- Generated override tags.
- Transcript text escaping.
- ASS timestamp formatting.

Generated tags and escaped transcript text must be separate function arguments so
untrusted text cannot become an override.

### multisubs/subtitler.py

The foundation preserves its current behavior. Feature 1 adds probing and Feature
7 adds preview rendering.

- FFmpeg and FFprobe discovery.
- Video probing.
- Video rendering.
- Preview-frame rendering.
- Filter arguments, stream mapping, temporary media, and diagnostics.

### multisubs/transcriber.py

- WhisperX/PyTorch boundary.
- Transcription and word alignment.
- Semantic cue construction.
- No FFmpeg probing or ASS-specific position calculations.

### multisubs/cli.py

- Parsing and direct validation.
- Pipeline orchestration.
- Output publication and cleanup.
- A split transcription/artifact pipeline. Feature 7 adds the early preview
  branch.

## JSON metadata

Prepare the artifact writer to accept rendering metadata without changing the
current JSON output in this behavior-preserving refactor. The geometry feature
will introduce a documented schema_version before adding a rendering object
containing:

- source video geometry used for layout;
- requested and resolved preset;
- resolved position or coordinates;
- resolved margins and maximum width;
- appearance values used to compile ASS.

Do not put generated ASS strings or raw command lines in JSON. The existing
transcription text and segment contract must remain documented.

## Error model

- Syntax and independent range errors: argparse error before FFmpeg and WhisperX.
- Geometry-dependent range errors: ValidationError after FFprobe and before
  WhisperX.
- Probe executable missing: DependencyError.
- Malformed or unsupported media geometry: RenderingError or a dedicated
  MediaProbeError if callers need to distinguish it.
- Artifact serialization failures: ArtifactError.

Diagnostics should name the public option, original value, valid range, and
relevant video dimension.

## Implementation checklist

- [x] Add the typed SubtitleAppearance, SubtitleLayout, SubtitleConfig, and
  TranscriptDocument value objects.
- [x] Preserve the current CLI through a typed temporary adapter.
- [x] Document explicit CLI groups and color conversion for the package cutover.
- [x] Replace RunRequest.style_options with subtitle_config.
- [x] Split transcription from artifact writing.
- [x] Move ASS serialization into a focused module.
- [x] Keep heavy imports behind runtime boundaries.
- [x] Preserve atomic artifact writes.
- [x] Preserve collision-safe stems and publication.
- [x] Preserve failed-run work directories.
- [x] Leave the JSON output unchanged until rendering metadata has a concrete
  geometry contract.
- [x] Mark obsolete --style-* documentation and tests for the package cutover.

## Tests

Add focused test modules:

- tests/test_layout.py for pure configuration logic.
- tests/test_ass.py for serialization and injection safety.
- tests/test_media_probe.py for geometry mapping.

Update:

- tests/test_cli.py for the new request object and early validation.
- tests/test_transcriber.py for the split transcript/artifact flow.
- tests/test_subtitler.py for new FFmpeg/FFprobe boundaries.
- tests/test_integration.py for real libass output.

Required regression cases:

- Colors with and without alpha.
- Empty and malicious font names.
- Unknown presets and positions.
- Conflicting layout modes.
- ASS text containing braces and backslashes.
- Paths containing spaces, quotes, commas, colons, backslashes, and Unicode.
- Failed publication and cleanup behavior.

## Documentation

- Replace the README style-options table with appearance and layout groups.
- Update FR-9 in docs/prd.md to describe user-facing appearance and layout
  control, not ASS style overrides.
- Update the architecture component map and execution flow.
- Replace the DEFAULT_STYLE convention with typed configuration and preset
  requirements.
- Add release notes calling the CLI redesign a breaking change.

## Commit and pull-request plan

Suggested branch:

~~~
refactor/subtitle-layout-foundation
~~~

Suggested commits:

1. refactor: add typed subtitle configuration contracts
   - Add immutable configuration and cue models with focused tests.
   - Keep the current CLI mapped through a temporary adapter.
2. refactor: split transcription from artifact generation
   - Separate semantic transcription, layout, serialization, and publication.
   - Preserve the public wrapper and artifact lifecycle.
3. refactor: isolate ASS serialization
   - Move ASS compilation and escaping behind a focused boundary.
   - Add injection and golden-output tests.
4. docs: document the subtitle layout foundation
   - Update architecture and conventions without claiming unfinished features.

Suggested pull request:

~~~
Title: refactor: establish the typed subtitle layout pipeline
Base: dev
~~~

The PR must remain behavior-preserving, identify the temporary compatibility
adapter, and demonstrate that existing CLI, output, cleanup, and transcription
tests still pass. Do not remove --style-* in this PR.

Before requesting review:

- Run the full hermetic suite because this changes central orchestration.
- Show the old and new internal execution flow in the PR description.
- Call out any public Python signature retained by a wrapper.
- Update the package dashboard to In review and add the PR link.

## Acceptance criteria

- The current public CLI continues to work through a documented temporary
  adapter until the package cutover.
- Invalid appearance/layout values fail before WhisperX loading.
- The orchestration layer has a dedicated point between semantic transcription
  and artifact writing where Feature 1 can resolve video geometry.
- Programmatic transcription can produce semantic cues without writing files.
- Generated ASS remains valid and safely escapes transcription text.
- Existing collision, cleanup, translation, and artifact-retention behavior
  continues to pass its tests.
