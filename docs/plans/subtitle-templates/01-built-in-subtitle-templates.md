# Built-in subtitle templates

Status: Planned

Depends on:

- [Bundled OFL font catalog](00-bundled-ofl-font-catalog.md)
- [Completed subtitle positioning roadmap](../subtitle-positioning/README.md)
- [Completed karaoke subtitles roadmap](../karaoke-subtitles/README.md)
- [Completed subtitle typography roadmap](../subtitle-typography/README.md)

## Objective

Let users select one of eight useful, reproducible subtitle presentations with
one semantic CLI option, preview the result without transcription, and refine
it through explicit appearance, layout, and effect flags. Templates may include
effects when the effect is intrinsic to their documented purpose;
`neon-karaoke` therefore enables progressive karaoke by default.

The default template must be the exact current presentation: Roboto Regular,
white text, translucent black box, current shadow, current relative dimensions,
and bottom-center placement.

## Scope

Included:

- Add `--subtitle-template NAME` with eight stable, kebab-case names.
- Treat the selected template as a complete immutable baseline and apply
  explicit CLI values as field-level overrides.
- Resolve omitted selection to `default` without changing current semantic
  default values.
- Use only the bundled font families delivered by Plan 0.
- Support templates in preview and normal transcription/rendering paths.
- Make the existing `--karaoke` option symmetric through `--no-karaoke`, so a
  template-provided karaoke effect can be explicitly disabled.
- Allow a template to define whether karaoke is enabled, its mode, and its
  highlight color through the existing typed effects contract.
- Record requested and resolved template identity in JSON diagnostics.
- Document the intent, full settings, font, suitable use, and override examples
  for every template.
- Visually verify each template in representative 16:9 and 9:16 videos.

Excluded:

- User-defined template files, configuration discovery, environment-variable
  templates, remote catalogs, plugin templates, or persistence of edited
  templates.
- Restoring `--layout`, aspect-ratio auto-selection, hidden safe areas, or
  automatic platform-specific placement.
- Automatically changing templates based on video geometry, language, media
  content, or transcription result.
- Creating a new effect type, changing karaoke timing, or enabling an effect in
  a template whose name and documented purpose do not imply it.
- Exposing raw ASS fields or allowing arbitrary ASS override syntax.
- Adding variable-font axis controls.

## Decisions and constraints

### Template names and exact baselines

Every value uses the existing semantic configuration and validation paths.
Unlisted fields use the current defaults in `multisubs/config.py`; the registry
must not contain raw ASS field names or numeric alignment codes.

#### `default`

Current general-purpose presentation; this is the resolved template when the
option is omitted.

| Field | Value |
| --- | --- |
| Font | Roboto, regular 400, upright, `4%` |
| Text | `#FFFFFF`, original case, `100%` opacity |
| Backdrop | box, `#00000099`, `0px` padding, `4%` shadow |
| Typography | `0px` letter spacing, `auto` line height |
| Placement | bottom-center; left/right `18%`, top `0%`, bottom `5%` |
| Envelope | max width `100%`, max height `10%` |

#### `clean-outline`

Neutral, modern captions for interviews, courses, and product demonstrations.

| Field | Value |
| --- | --- |
| Font | Inter, medium 500, upright, `4%` |
| Text | `#FFFFFF`, original case, `100%` opacity |
| Backdrop | outline, `#000000CC`, `5%` thickness, `0px` shadow |
| Typography | `0px` letter spacing, `auto` line height |
| Placement | bottom-center; left/right `14%`, top `0%`, bottom `5%` |
| Envelope | max width `100%`, max height `14%` |

#### `social-bold`

Large, energetic mobile-first captions for short-form video.

| Field | Value |
| --- | --- |
| Font | Montserrat, extra-bold 800, upright, `5%` |
| Text | `#FFFFFF`, uppercase, `100%` opacity |
| Backdrop | outline, `#000000E6`, `8%` thickness, `3%` shadow |
| Typography | `0px` letter spacing, `auto` line height |
| Placement | bottom-center; left/right `8%`, top `0%`, bottom `8%` |
| Envelope | max width `100%`, max height `22%` |

#### `classic-yellow`

Familiar yellow captions with a strong dark edge for interviews, archives,
documentaries, and general-purpose video.

| Field | Value |
| --- | --- |
| Font | Roboto, bold 700, upright, `4.2%` |
| Text | `#FFD54F`, original case, `100%` opacity |
| Backdrop | outline, `#000000E6`, `6%` thickness, `3%` shadow |
| Typography | `0px` letter spacing, `auto` line height |
| Placement | bottom-center; left/right `12%`, top `0%`, bottom `6%` |
| Envelope | max width `100%`, max height `16%` |

#### `newsroom`

Compact left-aligned treatment for reports, explainers, and factual updates.

| Field | Value |
| --- | --- |
| Font | Oswald, semi-bold 600, upright, `4.2%` |
| Text | `#FFFFFF`, uppercase, `100%` opacity |
| Backdrop | box, `#0B1F3ACC`, `8%` padding, `0px` shadow |
| Typography | `1%` letter spacing, `auto` line height |
| Placement | bottom-left; left `5%`, right `35%`, top `0%`, bottom `6%` |
| Envelope | max width `100%`, max height `16%` |

#### `editorial`

Quiet serif styling for documentary, cultural, and cinematic material.

| Field | Value |
| --- | --- |
| Font | Lora, semi-bold 600, italic, `4%` |
| Text | `#FFF8E7`, original case, `95%` opacity |
| Backdrop | outline, `#111111CC`, `4%` thickness, `3%` shadow |
| Typography | `0px` letter spacing, `auto` line height |
| Placement | bottom-center; left/right `16%`, top `0%`, bottom `7%` |
| Envelope | max width `100%`, max height `15%` |

#### `high-contrast`

Strong letter differentiation and an opaque contrast surface for maximum
legibility.

| Field | Value |
| --- | --- |
| Font | Atkinson Hyperlegible Next, bold 700, upright, `4.3%` |
| Text | `#000000`, original case, `100%` opacity |
| Backdrop | box, `#FFD600FF`, `10%` padding, `0px` shadow |
| Typography | `0px` letter spacing, `auto` line height |
| Placement | bottom-center; left/right `10%`, top `0%`, bottom `5%` |
| Envelope | max width `100%`, max height `18%` |

The name describes visual contrast, not a formal accessibility conformance
claim. Documentation must not claim WCAG compliance for rendered video without
a separate measured standard and test protocol.

#### `neon-karaoke`

High-energy outlined captions that enable word-timed progressive karaoke with
a vivid highlight palette.

| Field | Value |
| --- | --- |
| Font | Montserrat, bold 700, upright, `5%` |
| Text | `#FFFFFF`, original case, `100%` opacity |
| Backdrop | outline, `#080012E6`, `7%` thickness, `5%` shadow |
| Typography | `0px` letter spacing, `auto` line height |
| Placement | bottom-center; left/right `8%`, top `0%`, bottom `7%` |
| Envelope | max width `100%`, max height `20%` |
| Karaoke effect | enabled, progressive mode, highlight `#00F5D4` |

Selecting this template is equivalent to an explicit request for karaoke.
Consequently, translation and layout preview reject it through the existing
karaoke restrictions unless the user supplies `--no-karaoke`. Disabling the
effect retains every other `neon-karaoke` template value.

### Default compatibility

The `default` template must be assembled from the same authoritative constants
used by the no-option path. Do not duplicate a second set of literals that can
drift from `multisubs/config.py`.

The following must resolve identically at the semantic configuration, ASS,
wrapping, and placement boundaries:

~~~
multisubs -i video.mp4
multisubs -i video.mp4 --subtitle-template default
~~~

Rendered glyph pixels may become more reproducible because Plan 0 supplies a
pinned Roboto face; the documented style values themselves do not change.

### Override precedence and validation

The parser keeps explicit values distinguishable from omitted ones. Resolution
applies one template baseline, overlays only explicitly supplied fields, then
runs the existing typed validation and geometry resolution once.

Examples:

~~~
multisubs -i video.mp4 --subtitle-template social-bold --text-color '#FFFFFF'
multisubs -i video.mp4 --subtitle-template editorial --no-italic
multisubs -i video.mp4 --subtitle-template newsroom --position top-left --margin-top 6%
multisubs -i video.mp4 --subtitle-template neon-karaoke --karaoke-mode active-word
multisubs -i video.mp4 --preview-layout --subtitle-template neon-karaoke --no-karaoke
~~~

An explicit override changes only its named field. It does not import values
from another template. Existing conflicts remain errors, including an explicit
inactive vertical margin, custom coordinates without their required envelope,
translation with resolved karaoke, and preview with resolved karaoke.

`--karaoke` becomes an `argparse.BooleanOptionalAction` whose parser default is
`None`, preserving the existing `--karaoke` spelling while adding
`--no-karaoke` and allowing omission to inherit the template baseline. A final
disabled effect combined with an explicit karaoke mode or highlight color is
still invalid. `neon-karaoke --no-karaoke` is valid; adding
`--karaoke-mode` or `--karaoke-highlight-color` to that disabled composition is
not.

Effect validation moves after template/override composition but remains before
ffprobe, WhisperX import, model loading, or output mutation. Translation and
preview checks consume the final typed effect state rather than raw argument
presence.

Template-provided fields are defaults rather than explicit CLI presence for
conflict diagnostics. For example, overriding `newsroom` to a top position does
not make its template bottom margin an explicitly invalid user option; an
explicit `--margin-bottom` with that top position still fails.

### Registry and typed ownership

Add an immutable `SubtitleTemplate` typed contract and a focused
`multisubs/templates.py` registry. A template contains semantic appearance,
native layout, and typed effects values; it never contains raw ASS syntax,
media-specific geometry, or mutable dictionaries shared across runs.

`multisubs/config.py` remains the authority for primitive defaults, parsing,
and validation. `templates.py` composes already supported values into named
baselines. `cli.py` owns option parsing, explicit-field tracking, baseline plus
override composition, and user-facing progress. Geometry remains in
`layout.py`; ASS remains in `ass.py`; font resources remain in
`font_catalog.py`; FFmpeg behavior remains in `subtitler.py`.

## Public interface and contracts

CLI help lists every stable template name and identifies `default` as the
default. Unknown names fail through argparse before ffprobe or WhisperX. No
short template option is added. The existing `--karaoke` flag remains valid and
`--no-karaoke` is added as its explicit negative form.

Preview accepts the same option and renders the same final configuration:

~~~
multisubs -i video.mp4 --preview-layout --subtitle-template high-contrast
multisubs -i video.mp4 --preview-layout --subtitle-template neon-karaoke --no-karaoke
~~~

Preview does not synthesize word timings. A karaoke-enabled final composition,
whether enabled by a template or `--karaoke`, remains invalid with
`--preview-layout`. Explicit `--no-karaoke` previews only the static appearance
of `neon-karaoke` and does not claim to preview its timed effect.

SRT text and timing are unaffected except when a selected template's existing
`text-case` baseline changes the displayed text, such as `social-bold` and
`newsroom`. Original transcript and aligned words remain preserved in JSON.
ASS uses the existing semantic compiler and receives no template-specific raw
fields.

JSON adds template diagnostics under rendering metadata:

~~~json
"template": {
  "requested": "social-bold",
  "resolved": "social-bold"
}
~~~

When omitted, `requested` is null and `resolved` is `default`. Existing
requested/resolved appearance, layout, font, wrapping, and karaoke metadata
continues to record the effective values, so consumers do not need the registry
to interpret a retained run. This additive field does not change
`schema_version`.

Output paths, artifact retention, collision handling, model selection,
translation constraints, transcription, and cue timing are unchanged.

## Implementation

- Add the immutable template model and ordered registry in
  `multisubs/templates.py`, sourcing `default` from current config constants.
- Add `--subtitle-template` to `multisubs/cli.py` with stable choices and no
  short alias.
- Convert `--karaoke` to `argparse.BooleanOptionalAction` with `None` as the
  omitted value, preserving `--karaoke` and adding `--no-karaoke`.
- Compose template baseline plus explicit CLI overrides before the existing
  `validate_subtitle_config()` boundary, while retaining explicit-field
  presence for actionable placement errors.
- Validate karaoke mode/color presence, translation, and preview restrictions
  against the final composed effect rather than raw argparse values.
- Report the selected template in preview and normal progress without changing
  error-stream behavior.
- Add requested/resolved template diagnostics to retained JSON while keeping
  all effective values explicit.
- Reuse the Plan 0 bundled provider for each template font; no registry code
  handles file paths.

## Implementation tasks

- [ ] Add the typed immutable template model, registry, stable choices, and
  exact eight baseline definitions.
- [ ] Add symmetric `--karaoke`/`--no-karaoke` parsing and final-state effect
  validation without weakening early failure timing.
- [ ] Implement CLI parsing and field-level template/override composition with
  existing presence-sensitive validation.
- [ ] Integrate selection into preview and normal render progress and JSON
  diagnostics.
- [ ] Add default-equivalence, per-template, override-precedence, invalid-name,
  placement-conflict, preview, effect, and serialization tests.
- [ ] Add controlled 16:9 and 9:16 FFmpeg/libass visual verification for all
  templates without committing generated media.
- [ ] Update README.md, docs/prd.md, docs/architecture.md, and roadmap status.

## Unit tests

- Registry order, exact names, unique identifiers, immutable configs, supported
  semantic values, and one valid bundled family/face for each template.
- Complete field assertions for all eight templates, including colors, alpha,
  units, case, weight, italic, backdrop, placement, maximum dimensions, and
  effect defaults.
- No-option and explicit `default` equivalence before and after geometry
  resolution, including ASS style/events and wrapping metrics.
- One explicit override per appearance, typography, layout, and effect
  field, proving unrelated template fields remain unchanged.
- `--bold`/`--no-bold`, `--italic`/`--no-italic`, explicit font weight, and
  explicit custom font directory compatibility.
- Unknown names, template plus invalid inactive margin, template plus incomplete
  explicit coordinates, and resolved karaoke/translation and karaoke/preview
  conflicts all fail at their current early boundaries.
- `neon-karaoke` enables progressive karaoke and its highlight color; explicit
  mode/color overrides win, and `--no-karaoke` disables the effect without
  changing unrelated template fields.
- `--no-karaoke` plus an explicit karaoke mode or highlight color is rejected,
  while translation and preview become valid with `neon-karaoke` only after
  the effect is explicitly disabled.
- JSON requested null/resolved default behavior, explicit selection, effective
  values, and absence of raw template mappings or asset paths.

## Integration and manual verification

- Render the same licensed test text with every static template on one
  1920x1080 and one 1080x1920 fixture; verify legibility, intended alignment,
  no envelope crossing, and no avoidable clipping. Preview the static
  `neon-karaoke` appearance with `--no-karaoke` on both geometries.
- Use preview and normal transcription paths with the same template and compare
  font provider, resolved dimensions, wrapping, placement, palette, and ASS
  compiler strategy.
- Render representative Portuguese diacritics and punctuation with all six
  families; include a controlled non-Latin sample for each family only where
  its declared upstream coverage supports it.
- Verify `social-bold` and `newsroom` casing, `classic-yellow` text color,
  `editorial` italic face, `high-contrast` opaque palette, and both karaoke
  modes with `neon-karaoke`.
- Confirm generated previews, videos, and subtitle artifacts remain untracked
  and are not committed.

## Documentation

- Add a README template gallery table with name, intended use, font, main
  visual traits, command examples, preview recipe, and override precedence.
- Add `--subtitle-template` to the command reference and clarify that the
  default is the current presentation.
- Document template-provided effects, `--no-karaoke`, final-state validation,
  and the static-preview recipe for `neon-karaoke`.
- Document the bundled family/variation table and per-family OFL files in the
  README license section; do not add removed-layout migration history.
- Extend FR-9 and product acceptance criteria in docs/prd.md with template
  selection, default equivalence, explicit override precedence, offline bundled
  fonts, and preview/final agreement.
- Update docs/architecture.md with template registry ownership, configuration
  composition order, JSON metadata, and unchanged ASS/layout boundaries.

## Commit and pull-request plan

Suggested branch:

~~~
feat/subtitle-templates
~~~

Suggested commits:

1. `feat: add built-in subtitle templates`
   - Typed registry, CLI composition, JSON metadata, and focused tests.
2. `test: verify subtitle template rendering`
   - Controlled preview and FFmpeg/libass integration coverage.
3. `docs: document built-in subtitle templates`
   - README, PRD, architecture, and roadmap status.

Suggested pull request:

~~~
Title: feat: add built-in subtitle templates
Base: main
~~~

Before opening the pull request:

- Run `python -m pytest tests/test_config.py tests/test_cli.py tests/test_layout.py tests/test_ass.py tests/test_preview.py tests/test_karaoke.py tests/test_transcriber.py` plus the new template tests.
- Run controlled rendering with
  `python -m pytest -m integration -k 'template or font or preview'` when
  FFmpeg/libass is available.
- Run `python -m compileall multisubs`, `multisubs --help`,
  `python -m pytest`, `python -m ruff format --check .`,
  `python -m ruff check .`, and `python -m pyright`. Then run `rm -rf dist`
  immediately before `python -m build`, followed by
  `python -m twine check dist/*`.
- Install the wheel in a clean environment and render at least `default`,
  `classic-yellow`, `social-bold`, `editorial`, and `high-contrast` previews
  without host copies of their fonts, plus the `neon-karaoke` static appearance
  with `--no-karaoke`.
- Attach or describe temporary 16:9 and 9:16 visual evidence in the pull-request
  body without committing generated media.
- In the final pre-PR documentation commit, move Plan 1 and the package to
  `In review` and record `feat/subtitle-templates` as the delivery reference.
- Push the complete branch before opening the PR; do not add a post-open commit
  solely for its number or URL.

After merge:

- Mark Plan 1 and the package `Done`, replace the branch with the merged PR
  link, recalculate package/catalog progress, and evaluate the accumulated
  backward-compatible feature set for a minor release.

## Acceptance criteria

- `--subtitle-template` accepts exactly the eight documented names and rejects
  unknown names before probing or model loading.
- Omitting the option and selecting `default` produce identical current
  semantic appearance, wrapping, ASS, and placement values.
- Every non-default template resolves its documented bundled face and exact
  baseline values without requiring a system font or network connection.
- An explicit supported CLI field overrides only that field, while invalid
  final combinations still produce the existing actionable errors.
- `classic-yellow` renders Roboto Bold text in the documented yellow color
  with its dark outline and preserves original casing.
- `neon-karaoke` enables progressive karaoke by default, explicit effect
  fields override its mode and color, and `--no-karaoke` disables only the
  effect.
- Resolved karaoke remains incompatible with translation and preview before
  expensive work; `neon-karaoke --no-karaoke` is valid for those paths, while
  disabled karaoke plus mode/color options is rejected.
- Preview and normal rendering agree for every static template's font provider,
  typography, palette, wrapping, and placement on controlled 16:9 and 9:16
  fixtures. `neon-karaoke` timed behavior is verified through controlled
  transcription/ASS fixtures, not simulated in preview.
- JSON records requested/resolved template identity and complete effective
  configuration without changing schema version or exposing asset paths.
- SRT/ASS safety, timing, output lifecycle, collision handling, translation
  constraints, and custom-font precedence remain compatible.
- User documentation describes only the delivered templates and current
  features; package status, tests, and quality gates pass.
