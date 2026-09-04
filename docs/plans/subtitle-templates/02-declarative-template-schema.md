# Declarative template schema

Status: In review

Depends on:

- [Built-in subtitle templates](01-built-in-subtitle-templates.md)

## Objective

Replace the hard-coded built-in template definitions with packaged, strictly
validated JSON resources organized into `style`, `layout`, and `animation`,
while preserving every current template name, CLI result, preview, retained
artifact, and rendered pixel contract.

This increment creates a stable internal boundary for adding cue animations in
the next plan. It is deliberately a behavior-preserving refactor rather than a
user-defined template feature.

## Scope

Included:

- Add one deterministic template index and one UTF-8 JSON resource for each of
  the eight current built-in templates.
- Give the internal resource format its own `schema_version`, independent from
  the retained transcription JSON schema.
- Organize static presentation values under `style` and `layout`, and current
  karaoke behavior under `animation.word`.
- Place text color and karaoke highlight color inside `style.typography`.
- Keep `shadow` as a sibling of `typography` and `backdrop` inside `style`.
- Parse resources through `importlib.resources`, reject malformed or unknown
  data, and compile valid definitions into immutable typed runtime values.
- Align runtime ownership around typed style, layout, and animation contracts
  so Plan 3 does not add a parallel effects path.
- Package and verify the complete resource catalog in wheel and sdist.
- Prove the migrated catalog resolves identically to the current Python
  registry before removing the hard-coded definitions.

Excluded:

- User-authored JSON, `--template-file`, filesystem discovery, remote catalogs,
  environment-variable templates, or editing/persisting templates.
- New template names, changed template values, cue motion, new CLI flags, or a
  changed default presentation.
- Reorganizing or removing fields from the public retained transcription JSON.
- Independent shadow color, blur, X/Y shadow offsets, gradients, or new style
  controls.
- Raw ASS tags, ASS field names, renderer-specific numeric codes, or video-
  geometry-resolved values in a template resource.

## Decisions and constraints

### Resource layout and ordering

Use package resources rather than paths relative to the source checkout:

~~~text
multisubs/assets/templates/
├── index.json
├── default.json
├── clean-outline.json
├── social-bold.json
├── classic-yellow.json
├── newsroom.json
├── editorial.json
├── high-contrast.json
└── neon-karaoke.json
~~~

`index.json` is the only ordering authority. Directory enumeration must not
define public CLI choice order. It declares template resource filenames once,
without duplicates or absolute paths. Every indexed file must exist, and every
template JSON file in the packaged directory must be indexed exactly once.

The loader must use `importlib.resources` and perform no writes, network calls,
FFmpeg execution, Pillow loading, or model imports. Loading may be cached for
the process after successful validation because the resources are immutable.

### Internal template schema

Each resource uses this complete high-level shape:

~~~json
{
  "schema_version": 1,
  "name": "neon-karaoke",
  "description": "High-energy captions with progressive word highlighting.",
  "style": {
    "typography": {
      "font_family": "Montserrat",
      "font_weight": "bold",
      "font_size": "5%",
      "italic": false,
      "letter_spacing": "0px",
      "line_height": "auto",
      "text_case": "original",
      "color": "#FFFFFF",
      "highlight_color": "#00F5D4"
    },
    "backdrop": {
      "type": "outline",
      "color": "#080012E6",
      "size": "7%"
    },
    "shadow": {
      "size": "5%"
    },
    "opacity": "100%"
  },
  "layout": {
    "position": "bottom-center",
    "margins": {
      "left": "8%",
      "right": "8%",
      "top": "0%",
      "bottom": "3%"
    },
    "max_width": "100%",
    "max_height": "20%"
  },
  "animation": {
    "cue": {
      "entrance": {
        "type": "none"
      },
      "exit": {
        "type": "none"
      }
    },
    "word": {
      "type": "karaoke",
      "mode": "progressive"
    }
  }
}
~~~

All current built-ins use native named placement, so version 1 of the internal
schema does not admit X/Y coordinates or media-specific pixels calculated from
geometry. A future internal explicit-placement template requires a separate
schema and product decision. Cue animation is represented directly by explicit
`entrance` and `exit` phase objects; there is no aggregate preset field.
Concrete renderer tags and geometry-resolved values never appear in a template
resource.

`typography.color` and optional `typography.highlight_color` are semantic
conventional RGBA colors. `highlight_color` is required only when
`animation.word.type` is `karaoke` and must be null otherwise. Shadow remains a
separate style component but continues inheriting the backdrop color because
independent shadow color is not a current public or renderer contract.

Every template is a complete presentation rather than a sparse patch. The
`default.json` values intentionally duplicate the authoritative defaults in
`multisubs/config.py`; an exact equivalence test is mandatory so either side
cannot drift silently. Omitted `--template` and explicit `--template default`
must continue resolving through the same validated runtime object.

### Validation and failure behavior

Validate in two stages:

1. The catalog boundary validates UTF-8 JSON structure, schema versions,
   expected keys, field types, unique kebab-case names, index/name agreement,
   and absence of unknown keys.
2. The existing semantic configuration boundary validates colors, units,
   font weights, text case, backdrop kind, placement, margins, dimensions, and
   karaoke combinations.

Do not silently ignore unknown keys, coerce booleans into numbers, accept
non-finite values, merge partial definitions with hidden defaults, or fall back
to another template after a catalog error. Add a focused project error such as
`TemplateError` for damaged packaged resources. The CLI must report a concise
installation/catalog diagnostic and exit before probing or model loading; the
original exception remains chained for tests or debugging.

### Typed runtime ownership

Refactor the private runtime configuration so one `SubtitleConfig` owns three
immutable branches:

- `style`, containing typed typography, backdrop, shadow, and opacity values;
- `layout`, retaining the existing placement and envelope contract;
- `animation`, containing cue and word animation values. In this plan both cue
  phases have type `none`, while the word branch represents the
  already-supported karaoke modes. The runtime owns entrance and exit as
  separate phases so Plan 3 can select or override them independently.

The resource parser produces a typed template definition and then uses the
normal semantic configuration validation path. `templates.py` owns catalog
lookup, stable choices, and immutable `SubtitleTemplate` values; it must not
contain a second hard-coded registry or compile ASS. `config.py` remains the
authority for scalar defaults and semantic validation. Geometry stays in
`layout.py`, font resolution in `font_catalog.py` and `text_measurement.py`, and
serialization in `ass.py`.

These classes and parser helpers remain private implementation contracts unless
they are deliberately exported later. Existing callable artifact APIs and the
console interface remain compatible.

## Public interface and contracts

No CLI spelling, choice, default, or precedence changes. These remain
equivalent:

~~~text
multisubs -i video.mp4
multisubs -i video.mp4 --template default
~~~

The same eight template names remain accepted in the same order. Explicit
appearance, layout, and current karaoke flags keep replacing only their current
fields. As a temporary behavior-preserving bridge, those karaoke flags compile
into the new internal `animation.word` branch. Plan 3 removes them in favor of
the unified animation flag hierarchy. Translation restrictions, preview
behavior, output paths, cleanup, and collision handling are unchanged.

Retained JSON stays at `schema_version: 2` with its current documented shape,
including `metadata.rendering.template` and `effects.karaoke`. The internal
template resource schema is not a supported integration surface and is not
copied into retained output. SRT and ASS must be byte-for-byte compatible for
equivalent deterministic inputs after the refactor.

## Implementation

- Add strict resource decoding and immutable template-definition models in
  `multisubs/templates.py` or a small private catalog module if keeping parsing
  separate makes the boundary clearer.
- Add the index and eight complete JSON resources under
  `multisubs/assets/templates`, then declare them as setuptools package data.
- Introduce the typed style/animation runtime taxonomy in
  `multisubs/models.py` and migrate config, layout, wrapping, measurement,
  preview, transcription, ASS, and test references without behavioral changes.
- Compile template resource values through `validate_subtitle_config()` rather
  than duplicating color, length, weight, or placement parsers.
- Keep CLI explicit-presence tracking separate from template-provided defaults,
  preserving the existing placement and karaoke conflict diagnostics.
- Remove hard-coded template literals only after snapshot, ASS, JSON, preview,
  and resolved-layout equivalence tests pass.

## Implementation tasks

- [x] Add the versioned template index and strict JSON catalog parser.
- [x] Add complete JSON definitions for all eight existing templates.
- [x] Add immutable template style, layout, cue-animation, and word-animation
  definition models.
- [x] Refactor runtime configuration ownership to `style`, `layout`, and
  `animation` without changing the public CLI or artifact contracts.
- [x] Preserve config.py as the default authority and enforce exact
  `default.json` equivalence.
- [x] Compile resources through the existing semantic validators and add a
  dedicated damaged-catalog diagnostic.
- [x] Preserve explicit CLI override precedence and early conflict validation.
- [x] Package and audit the resource index and every template file in wheel and
  sdist.
- [x] Add source-tree, clean-wheel, equivalence, error, and regression tests.
- [x] Update docs/architecture.md and applicable package/convention references
  for the new internal boundary; keep README behavior unchanged.
- [x] Move the plan and package to `In review` only after delivery is
  explicitly authorized.

## Unit tests

- Index schema version, stable order, unique files, relative safe filenames,
  existence, complete directory coverage, and exact name/file agreement.
- Template schema version, required and unknown keys, nested types, duplicate
  names, valid descriptions, full style/layout/animation presence, and valid
  JSON numbers.
- Invalid UTF-8, malformed JSON, unsupported versions, missing resources,
  traversal-like filenames, invalid semantic colors/units/enums, and illegal
  highlight/word-animation combinations produce the catalog diagnostic without
  fallback.
- All parsed definitions and runtime templates are immutable and do not share
  mutable nested state between requests.
- Exact snapshots of all eight resource definitions match the currently
  documented baselines.
- `default.json`, config.py defaults, omitted selection, and explicit `default`
  are equal before and after geometry resolution.
- Every existing template produces the same resolved style, layout, wrapping,
  placement, preview ASS, normal ASS, SRT display text, and retained JSON as the
  pre-migration golden fixtures.
- Every explicit CLI override still changes only its corresponding field, and
  existing inactive-margin, coordinate, translation, and karaoke errors retain
  their early boundary.
- Importing the catalog performs no write, subprocess, network, Pillow,
  FFmpeg, WhisperX, or PyTorch work.

## Integration and manual verification

- Render or preview all eight templates on controlled 1920x1080 and 1080x1920
  fixtures and compare the results with pre-refactor reference frames within
  the existing deterministic tolerance.
- Exercise `default`, `neon-karaoke`, an explicit style override, and an
  explicit position override from a clean wheel installation with no source
  tree on `PYTHONPATH`.
- Remove `dist/` immediately before building, inspect wheel and sdist contents,
  and confirm the index plus all eight JSON resources appear exactly once.
- Confirm no generated media, preview image, transcription artifact, or
  unpacked temporary resource is committed.

## Documentation

- Update docs/architecture.md component ownership, configuration composition,
  package-resource loading, and internal template schema descriptions.
- Update docs/conventions.md only if strict internal resource validation and
  template package auditing become reusable engineering rules.
- Keep README.md and docs/prd.md describing the current eight-template public
  behavior; do not advertise internal JSON as a user extension mechanism.
- Update this plan, its package dashboard, and the top-level catalog through the
  normal lifecycle states.

## Commit and pull-request plan

Suggested branch:

~~~text
refactor/declarative-template-schema
~~~

Suggested commits:

1. `refactor: organize subtitle configuration contracts`
   - Add typed style/layout/animation ownership and migrate runtime references
     with behavior-preserving tests.
2. `refactor: load built-in templates from packaged json`
   - Add strict resource parsing, migrate the eight templates, remove the
     hard-coded registry values, and add catalog/equivalence tests.
3. `build: package subtitle template resources`
   - Add package-data and clean-wheel/sdist inventory checks.
4. `docs: document the declarative template boundary`
   - Update architecture, any adopted convention, and plan lifecycle status.

Suggested pull request:

~~~text
Title: refactor: load built-in templates from declarative resources
Base: main
~~~

Before opening the pull request:

~~~text
python -m pytest tests/test_templates.py tests/test_config.py tests/test_cli.py tests/test_layout.py tests/test_ass.py tests/test_preview.py tests/test_transcriber.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
rm -rf dist
python -m build
python -m twine check dist/*
git diff --check
git status --short
~~~

Audit both archives and perform the clean-wheel template/preview smoke check
after the build. Record the exact equivalence and package inventory results in
the pull-request description.

In the final pre-PR documentation commit, move Plan 2 and the package to
`In review`, record `refactor/declarative-template-schema` as the delivery
reference, and push the complete branch before opening the PR. Do not add a
post-open commit solely to record its number or URL.

After merge, mark Plan 2 `Done`, replace its branch reference with the merged
pull-request link, recalculate package/catalog progress, and identify Plan 3 as
the next unblocked increment.

## Acceptance criteria

- The source tree, wheel, and sdist contain one deterministic index and exactly
  one validated JSON resource for each of the eight current templates.
- Every resource uses schema version 1 and complete `style`, `layout`, and
  `animation` branches; text/highlight colors are under typography and shadow
  is a separate style component, while cue entrance and exit are explicit
  phase objects with no aggregate preset.
- Unknown, missing, malformed, unsafe, or semantically invalid packaged data
  fails clearly before probing or model loading and never falls back silently.
- No user-facing template-file or discovery mechanism is introduced.
- Existing template names, order, CLI defaults, override precedence,
  validation, preview, JSON schema, SRT, ASS, output lifecycle, and rendered
  results remain compatible.
- Omitted template selection, explicit `default`, config.py defaults, and the
  packaged default definition resolve identically without silent drift.
- The internal runtime has one typed style/layout/animation configuration path;
  no parallel raw mapping or raw ASS template path remains.
- Focused tests, the hermetic suite, controlled render comparisons, clean
  package builds, archive audits, clean-wheel smoke checks, Ruff, Pyright,
  compileall, CLI help, and documentation checks pass.
