# Font weight

Status: Planned

Depends on:

- [Completed subtitle positioning roadmap](../subtitle-positioning/README.md)
- [Completed karaoke subtitles roadmap](../karaoke-subtitles/README.md)

## Objective

Let users request a font weight by a familiar face name such as `regular`,
`light`, `semi-bold`, or `bold`, or by its numeric rank from `100` through
`900`, then resolve the closest face actually available in the selected font
family for consistent measurement and libass rendering.

## Scope

Included:

- Add `--font-weight WEIGHT`, defaulting to `regular`.
- Accept case-insensitive canonical names, documented aliases, and numeric
  ranks from `100` through `900` in increments of 100.
- Keep `--bold` and `--no-bold` as compatibility shorthands for `bold` and
  `regular`.
- Match the requested weight against faces in `--fonts-dir` or fontconfig and
  report the face that was actually selected.
- Compile the resolved semantic weight for preview and normal ASS output.

Excluded:

- Accepting arbitrary numeric values between the supported 100-step ranks.
- Treating an arbitrary font filename or full style name as a weight.
- Downloading fonts, synthesizing missing faces, editing font files, or
  guaranteeing that every family supplies every named weight.
- Directly selecting or interpolating OpenType variable-font axes.

## Decisions and constraints

- Canonical public values are the names `thin`, `extra-light`, `light`,
  `regular`, `medium`, `semi-bold`, `bold`, `extra-bold`, and `black`, plus the
  corresponding numeric ranks `100`, `200`, `300`, `400`, `500`, `600`, `700`,
  `800`, and `900`.
- Named and numeric forms are equivalent inputs: `thin` = `100`,
  `extra-light` = `200`, `light` = `300`, `regular` = `400`, `medium` = `500`,
  `semi-bold` = `600`, `bold` = `700`, `extra-bold` = `800`, and `black` =
  `900`.
- Input is case-insensitive. Spaces and underscores normalize to hyphens, so
  `Semi Bold`, `semi_bold`, and `semi-bold` identify the same request.
- Common font metadata aliases normalize as follows: `hairline` to `thin`,
  `ultra-light` to `extra-light`, `normal` and `book` to `regular`, `demi-bold`
  to `semi-bold`, `ultra-bold` to `extra-bold`, and `heavy` to `black`.
- These names are semantic ranks, not a promise that the font contains a face
  with the same label. The resolver chooses the nearest available rank, keeps
  italic independent, and emits one substitution diagnostic when the match is
  not exact.
- `--font-weight` and either bold shorthand are mutually exclusive even when
  they would resolve to the same weight; silent precedence is not allowed.
- The typed appearance contract replaces boolean `bold` with a `FontWeight`
  enum whose values carry both a canonical name and numeric rank.
  Compatibility adaptation remains at CLI/configuration input boundaries, not
  throughout the pipeline.
- Face resolution and libass compilation operate on the normalized numeric
  rank, while diagnostics retain whether the user requested a name, alias, or
  number.
- This is additive and default-compatible and therefore does not require a
  major release.

## Public interface and contracts

~~~
--font-weight regular
--font-weight light
--font-weight "Semi Bold"
--font-weight bold
--font-weight 300
--font-weight 700
~~~

Unknown names, empty values, numeric values outside `100` through `900`,
numeric values not divisible by 100, and conflicts with `--bold` or `--no-bold`
fail through CLI/configuration validation before ffprobe or WhisperX. `--help`
lists canonical names, numeric ranks, their mapping, and alias normalization.

The typed Python configuration stores the canonical enum and not the raw input
token. SRT, cue timing, output paths, and cleanup are unaffected. ASS stores the
renderer weight needed to select the face. JSON records the requested token,
normalized canonical name and numeric rank, resolved family/style, inferred
resolved canonical name and numeric rank, input form, and whether a
substitution occurred. These additive fields keep `schema_version` unchanged.

## Implementation

- Add `FontWeight`, the name/rank table, and named, alias, and numeric parsing in
  `multisubs/models.py` and `multisubs/config.py`, including the regular default
  and compatibility translation from the existing bold boolean input.
- Update `multisubs/cli.py` so argparse distinguishes omitted bold shorthand
  from explicit `--no-bold`, detects conflicts, and constructs one canonical
  weight.
- Replace boolean style matching in `multisubs/text_measurement.py` with the
  shared deterministic rank table. Infer weight from face metadata, rank exact
  weight before nearest weight and exact italic before fallback, and use a
  stable tie breaker.
- Request the corresponding weight from fontconfig while still validating the
  loaded face's actual metadata. Do not infer exact success only from the
  fontconfig query.
- Update `multisubs/ass.py` to compile the canonical weight through one private
  mapping without changing ASS field order or user text.
- Add requested/resolved weight details to `multisubs/transcriber.py` JSON and
  existing font-substitution diagnostics without recording local paths.

## Implementation tasks

- [ ] Add the `FontWeight` enum, canonical name/rank table, alias parser,
  numeric parser, default, and typed revalidation.
- [ ] Wire named and numeric `--font-weight` plus bold-shorthand conflict
  handling into the CLI.
- [ ] Make custom-directory and fontconfig face selection weight-aware with
  deterministic nearest-face behavior.
- [ ] Compile the resolved weight into ASS for preview and normal rendering.
- [ ] Record requested and resolved weight diagnostics in JSON.
- [ ] Add focused configuration, CLI, font-resolution, ASS, preview, karaoke,
  metadata, and default-output tests.
- [ ] Update README.md, docs/prd.md, docs/architecture.md, and package status.

## Unit tests

- Every canonical name and numeric rank, case variation,
  spaces/hyphens/underscores, equivalent named/numeric pairs, and each
  documented alias.
- Default regular weight and `--bold`/`--no-bold` compatibility mappings.
- Conflicts between `--font-weight` and either shorthand.
- Rejection of unknown names, empty input, values below 100 or above 900,
  unsupported steps such as `350`, decimal and signed values, booleans,
  arbitrary style names, and malformed separators.
- Face-ranking fixtures for Thin, ExtraLight, Light, Book, Regular, Medium,
  DemiBold, SemiBold, Bold, ExtraBold, Heavy, Black, italic variants, ties, and
  missing exact faces.
- Fontconfig substitutions and diagnostics that distinguish requested from
  resolved weight.
- Exact ASS weight mapping and style-field order for all canonical weights.
- Default-output regression confirming regular non-italic rendering.

## Integration and manual verification

- Extend the controlled-font integration coverage with a family containing at
  least Regular, Light, SemiBold, and Bold faces; compare measured and libass
  bounds within the existing tolerance.
- Request a missing named weight and confirm preview and final rendering select
  the same nearest face and emit one actionable substitution diagnostic.
- Verify ordinary, progressive karaoke, and active-word cues retain identical
  text, timing, wrapping, and placement while changing only the font face.
- Test one `--fonts-dir` family and one fontconfig-provided family without
  committing font files or generated frames.

## Documentation

- Add `--font-weight`, canonical names and ranks, aliases, named and numeric
  examples, shorthand conflicts, and missing-face behavior to README command
  and appearance references.
- Update the old `--style-bold` migration mapping to `--font-weight bold` or
  `--font-weight 700` while retaining the compatibility shorthand note.
- Extend FR-9 and appearance acceptance criteria in docs/prd.md.
- Update the typed appearance, font-provider ranking, ASS adapter, JSON, and
  measurement contracts in docs/architecture.md.
- Update docs/conventions.md only if a reusable font-face ranking or fixture
  convention is introduced.

## Commit and pull-request plan

Suggested branch:

~~~
feat/subtitle-font-weight
~~~

Suggested commits:

1. `feat: add flexible subtitle font weights`
   - Typed configuration, CLI, face resolution, ASS/JSON output, and focused
     tests.
2. `docs: document subtitle font weights`
   - README, PRD, architecture, and roadmap status.

Suggested pull request:

~~~
Title: feat: add flexible subtitle font weights
Base: main
~~~

Before opening the pull request:

- Run `python -m pytest tests/test_config.py tests/test_cli.py tests/test_text_measurement.py tests/test_ass.py tests/test_preview.py tests/test_karaoke.py tests/test_transcriber.py`.
- Run the relevant controlled-font checks with
  `python -m pytest -m integration tests/test_integration.py -k font` when their
  prerequisites are available.
- Run `python -m compileall multisubs`, `multisubs --help`,
  `python -m pytest`, `python -m ruff check .`, and `python -m pyright`.
- In the final pre-PR documentation commit, move the plan and package to
  `In review` and record `feat/subtitle-font-weight` as the delivery reference.
- Push the complete branch before opening the PR; do not add a post-open commit
  solely for its number or URL.

After merge:

- Mark Plan 0 `Done`, replace the branch with the merged PR link, recalculate
  package/catalog progress, and identify Plan 1 as the next unblocked plan.

## Acceptance criteria

- A canonical name, documented alias, or supported numeric rank resolves to one
  canonical weight across CLI, configuration, measurement, JSON, ASS, preview,
  and final rendering.
- Existing commands using `--bold` or `--no-bold` retain their behavior.
- Unknown or conflicting input fails before video or model loading.
- Missing exact faces produce a deterministic, measured, recorded substitution
  rather than a false exact-match claim.
- Default commands remain regular weight and visually unchanged.
- Named and numeric equivalents select the same face and render identically,
  while JSON preserves the requested form for diagnostics.
- SRT text, transcript text, timing, placement, and artifact lifecycle remain
  unchanged.
