# Bundled OFL font catalog

Status: In review

Delivery: `feat/bundled-font-catalog`

Depends on:

- [Completed subtitle positioning roadmap](../subtitle-positioning/README.md)
- [Completed subtitle typography roadmap](../subtitle-typography/README.md)

## Objective

Ship a deterministic, offline font catalog containing every static weight and
italic face that the current CLI can select for six useful Google Fonts OFL
families, then make font measurement and FFmpeg/libass rendering resolve the
same bundled face without requiring system installation.

This foundation lets templates and direct `--font` usage render consistently
across clean machines while preserving explicit custom-font behavior.

## Scope

Included:

- Bundle 82 unmodified official Google Fonts TTF desktop files for Roboto,
  Inter, Montserrat, Oswald, Lora, and Atkinson Hyperlegible Next.
- Keep the original family-specific `OFL.txt` beside each family.
- Add a machine-readable manifest containing source, pinned version or commit,
  upstream URL, filename, internal family, weight, italic state, format, byte
  size, and SHA-256 for every binary.
- Include the assets and licenses in both wheel and sdist.
- Resolve explicitly supplied custom fonts first, bundled faces second, and
  fontconfig third, using the existing deterministic nearest-weight policy.
- Give Pillow/RAQM and FFmpeg/libass the same provider directory for the
  selected face.
- Make all bundled families available to direct `--font` usage without
  `--fonts-dir`.
- Use bundled Roboto for the existing default appearance.
- Add a complete README recipe for supplying a new local font family through
  `--fonts-dir`, including directory shape, supported formats, internal family
  naming, weight/italic selection, precedence, and current limitations.

Excluded:

- Modifying, subsetting, converting, renaming, regenerating, or repairing a
  font binary.
- Bundling variable font files or exposing width, optical-size, grade, or other
  OpenType axes. The API-generated static files keep unexposed axes at their
  Google Fonts defaults.
- Bundling webfonts, language subsets, sources, build tools, historical
  releases, or separate families such as Roboto Condensed or Montserrat
  Alternates.
- Downloading fonts at application runtime, installing them globally, or
  writing to a host font cache.
- Adding a font-download runtime dependency or a `THIRD_PARTY_NOTICES.md` file.
- Changing the public weight, italic, `--font`, or `--fonts-dir` syntax.

## Decisions and constraints

### Exact face inventory

The implementation must obtain final desktop binaries from the official Google
Fonts CSS API using its static TTF response. The manifest pins one Google Fonts
catalog commit, the returned family version, the complete stylesheet request,
and each versioned `fonts.gstatic.com` binary URL; mixing arbitrary versions
within a family is not allowed.

| Family | Required faces | Expected count |
| --- | --- | ---: |
| Roboto | 100 through 900 in 100-step ranks; upright and italic; normal width | 18 |
| Inter | 100 through 900 in 100-step ranks; upright and italic; default optical size | 18 |
| Montserrat | 100 through 900 in 100-step ranks; upright and italic | 18 |
| Oswald | 200, 300, 400, 500, 600, and 700; upright | 6 |
| Lora | 400, 500, 600, and 700; upright and italic | 8 |
| Atkinson Hyperlegible Next | 200 through 800 in 100-step ranks; upright and italic | 14 |

These 82 faces are every static desktop variation served by Google Fonts within
the weight and italic dimensions users can currently alter. Google Fonts
generates these static TTF instances from the canonical variable fonts, so
Roboto includes 200, 600, and 800 and Atkinson Hyperlegible Next replaces the
two-weight classic family. Width and optical-size axes remain at their service
defaults until a future feature defines their CLI, measurement, JSON, and ASS
contracts.

Authoritative references are the pinned
[Google Fonts catalog](https://github.com/google/fonts) and the Google Fonts
[static-font distribution contract](https://github.com/googlefonts/googlefonts.github.io/blob/main/gf-guide/statics.md).
The committed manifest, not a floating specimen page, is the release inventory.

### Asset and license layout

Use one package resource directory per family so the chosen directory can be
passed directly to the current non-recursive custom-font matcher and to
FFmpeg/libass:

~~~
multisubs/assets/fonts/
├── manifest.json
├── roboto/
│   ├── Roboto-Thin.ttf
│   ├── ...
│   ├── Roboto-BlackItalic.ttf
│   └── OFL.txt
├── inter/
├── montserrat/
├── oswald/
├── lora/
└── atkinson-hyperlegible-next/
~~~

Keep `LICENSE` at the repository root as the MIT license for multisubs. Each
font family remains under its own copied OFL text. README may summarize that
split but is not a substitute for the packaged family license.

The manifest is a technical provenance and integrity contract, not an
additional legal notice. Hashes are verified in tests and release preparation,
not recalculated during every normal invocation.

### Resource and provider behavior

Add a focused `multisubs/font_catalog.py` boundary. It owns manifest loading,
bounded family lookup, package-resource access, and the renderer directory for
a bundled selection. It must not import Pillow, execute FFmpeg, or perform
network access.

Provider order is deterministic:

1. A valid explicit `--fonts-dir`, including a same-named family override.
2. The bundled family catalog.
3. Fontconfig when available.
4. The existing Unicode-width estimate when no concrete face resolves.

The resolved face contract must carry its provider kind and a private renderer
directory. `text_measurement.py` uses that selection for Pillow/RAQM and the
CLI passes the same directory to preview or final FFmpeg rendering. Absolute
paths stay internal and must not appear in retained JSON or routine output.

Installed wheels are normally unpacked. Resource access must nevertheless use
`importlib.resources`; if a family directory is not available as an ordinary
filesystem directory, materialize only the selected family into an
invocation-scoped temporary directory and keep its lifetime open through
measurement and rendering. Do not copy all six families for every run.

### Packaging and supply chain

Declare the font binaries, manifest, and OFL texts as setuptools package data.
Do not broaden the PEP 621 project `license = "MIT"` declaration to imply that
font binaries are MIT licensed.

Before committing an asset, verify:

- the download uses HTTPS and an authoritative tagged release, pinned commit,
  or versioned Google Fonts static API URL;
- the original license identifies OFL 1.1 and belongs to that family release;
- Pillow reports the expected family, weight, and italic metadata;
- the binary SHA-256, size, source URL, and upstream revision match the
  manifest;
- no file was converted, subsetted, renamed internally, or regenerated.

The increased distribution size is an accepted consequence of shipping every
selectable face. The implementation pull request must report before/after wheel
and sdist sizes so the release impact is explicit.

Every distribution build must remove the existing `dist/` directory
immediately before invoking the builder. Inventory audits, Twine checks,
checksums, attestations, smoke installs, and uploads then operate only on the
wheel and sdist produced by that invocation rather than stale versions.

## Public interface and contracts

No new CLI option is added in this plan. Existing commands gain bundled family
resolution:

~~~
multisubs -i video.mp4 --font Inter --font-weight black --italic
multisubs -i video.mp4 --font Lora --font-weight 500
~~~

`--fonts-dir` remains an additional custom provider and keeps highest
precedence. Unknown font families retain the current fontconfig or Unicode
estimate behavior. Missing exact weights still use the current nearest-weight
diagnostic.

### Custom font workflow

The README must contain a dedicated "Use a custom font" recipe. It explains
that users add fonts for one invocation rather than installing them into or
modifying the multisubs package. The documented directory is flat because the
current resolver examines supported files directly inside `--fonts-dir` and
does not recurse into family subdirectories:

~~~
fonts/
├── MyFont-Regular.ttf
├── MyFont-SemiBold.ttf
├── MyFont-Bold.ttf
└── MyFont-BoldItalic.ttf
~~~

The recipe must include a complete command:

~~~
multisubs -i video.mp4 \
  --fonts-dir ./fonts \
  --font "My Font" \
  --font-weight bold \
  --italic
~~~

It must state all of these user-visible rules:

- `.ttf`, `.otf`, and `.ttc` files are accepted.
- Files must be directly inside the supplied directory; nested directories are
  ignored unless recursive discovery is introduced by a separate feature.
- `--font` matches the font's internal family metadata, which may differ from
  the filename.
- Multiple families and all their weight/italic faces may share the same flat
  directory.
- `--font-weight` and `--italic` select the closest matching face through the
  existing deterministic ranking; an unavailable exact weight produces the
  existing substitution diagnostic.
- The directory is used for both Pillow/RAQM measurement and FFmpeg/libass
  rendering and does not install fonts globally.
- An explicit custom face has priority over a same-named bundled face; bundled
  families then precede fontconfig.
- Users are responsible for ensuring that fonts they supply may be used and
  distributed for their intended output.

SRT text, timing, cue segmentation, CLI validation, output names, and cleanup
are unaffected. ASS style values are unaffected except that a bundled face is
now available to libass. JSON keeps the current requested/resolved font fields,
records `bundled` as the source when applicable, and never records a package or
temporary asset path. The JSON schema version remains unchanged because the
provider value is an additive resolution result within the existing field.

The current semantic default values remain unchanged. Default Roboto will now
resolve to the pinned bundled Regular face rather than an environment-specific
installation or fallback.

## Implementation

- Add the six resource directories, 82 font files, original OFL texts, and one
  deterministic JSON manifest under `multisubs/assets/fonts`.
- Add `multisubs/font_catalog.py` with immutable manifest models, bounded
  resource lookup, provider metadata, and temporary materialization fallback.
- Refactor `multisubs/text_measurement.py` so custom, bundled, and fontconfig
  candidates use one ranking contract and return the renderer provider
  directory with the selected face.
- Update CLI preview and normal-render orchestration to preserve the provider
  resource lifetime and pass the selected directory into `subtitler.py`.
- Keep FFmpeg-specific filter construction in `subtitler.py`; it accepts the
  already selected directory and does not discover package resources itself.
- Add setuptools package-data configuration and artifact-content checks.

## Implementation tasks

- [x] Pin one Google Fonts catalog revision and record each API family version,
  stylesheet, and exact binary URL, then download and verify the 82 unmodified
  static TTFs and six matching OFL texts.
- [x] Add the package asset tree and complete deterministic manifest.
- [x] Implement manifest parsing, family/face lookup, resource lifetime, and
  selected-family materialization fallback in `font_catalog.py`.
- [x] Integrate custom-first, bundled-second, fontconfig-third face resolution
  with the existing nearest-weight and italic ranking.
- [x] Pass the exact selected provider directory through preview and final
  rendering without serializing its path.
- [x] Configure wheel and sdist package data, clean `dist/` before each build,
  and add artifact inventory checks.
- [x] Add focused unit, packaging, clean-install, and FFmpeg/libass integration
  tests.
- [x] Add the complete custom-font README recipe and update README.md,
  docs/prd.md, docs/architecture.md, conventions where needed, and roadmap
  status.

## Unit tests

- Manifest syntax, unique family identifiers, unique filenames, exact face
  count, declared weight/italic matrix, supported file extensions, relative
  paths, SHA-256 format, and family-license presence.
- Hash and byte-size agreement for all 82 committed binaries.
- Pillow metadata agreement for every family, weight, and italic declaration.
- Case-insensitive family lookup, exact-weight behavior within every published
  family range, and deterministic nearest-weight behavior outside incomplete
  ranges such as Oswald and Lora.
- Custom-directory precedence over a same-named bundled family, bundled
  precedence over fontconfig, fontconfig fallback for an unbundled family, and
  Unicode estimate fallback when no provider resolves.
- Selected-family resource lifetime and materialization cleanup, including
  paths containing spaces and non-ASCII characters.
- Requested/resolved JSON source metadata says `bundled` without exposing
  package or temporary paths.
- Existing current-default values remain unchanged and resolve bundled Roboto
  Regular.

## Integration and manual verification

- Remove `dist/`, build wheel and sdist, list their contents, and prove every
  manifest entry and each family `OFL.txt` exists exactly once in both
  artifacts.
- Install the wheel into a clean environment without the six families installed
  system-wide; run `multisubs --help` and a focused preview for every family.
- Render representative regular, heavy, and italic faces through real
  FFmpeg/libass and compare their bounds with Pillow/RAQM within the established
  tolerance.
- Confirm an explicit custom directory containing a same-named test family is
  used by both measurement and libass instead of the bundled family.
- Record the wheel and sdist size delta and verify no runtime network request or
  global font installation occurs.

## Documentation

- Update README requirements and appearance reference with the bundled family
  inventory, selectable faces, offline behavior, custom-provider precedence,
  package-size implication, and per-family OFL licensing note.
- Add a dedicated README custom-font recipe containing the flat directory
  example, complete invocation, supported extensions, internal-family-name
  rule, multiple-face selection, nearest-weight behavior, non-installing
  behavior, provider precedence, and user-supplied licensing responsibility.
- Extend FR-9 and acceptance criteria in docs/prd.md for deterministic bundled
  font availability and provider precedence.
- Update docs/architecture.md with the asset manifest, `font_catalog.py`,
  provider order, resource lifetime, measurement/render directory sharing, and
  packaging boundary.
- Update docs/conventions.md with the font provenance, unmodified-binary,
  manifest/hash, per-family license, and artifact-audit rules if they become
  reusable release requirements.

## Implementation evidence

- The pinned inventory contains 82 static faces served from Google Fonts
  catalog commit `f6b2b7e8545e086ad3f821af21895d732b6485cf`: Roboto v51,
  Inter v20, Montserrat v31, Oswald v57, Lora v37, and Atkinson Hyperlegible
  Next v7.
- Pillow metadata, byte size, SHA-256, and the six OFL texts agree for all
  packaged resources.
- The hermetic suite passes with 514 tests. All 39 controlled integration tests
  pass, including real FFmpeg/libass bounds checks for Roboto 200, 600, and 800.
- A temporary FFmpeg/libass smoke render resolves and renders one representative
  static face from each of the six bundled families, including Atkinson
  Hyperlegible Next ExtraBold and Portuguese diacritics.
- Wheel and sdist build, pass Twine metadata checks, pass the archive inventory
  audit, and a dependency-free clean-wheel install verifies all 82 hashes and
  runs `multisubs --help`.
- The shared builder removes `dist/` immediately before `python -m build`, and a
  regression test preserves that order so stale artifacts cannot enter later
  validation or promotion steps.
- Compared with the pre-change 3.0.0 artifacts, the wheel grows from 72,388 to
  6,777,513 bytes (+6,705,125) and the sdist grows from 115,903 to 6,818,894
  bytes (+6,702,991).

## Commit and pull-request plan

Suggested branch:

~~~
feat/bundled-font-catalog
~~~

Suggested commits:

1. `build: bundle verified OFL font families`
   - Font binaries, family licenses, manifest, and package-data configuration.
2. `feat: resolve bundled subtitle fonts`
   - Resource/provider boundary, measurement/render integration, and focused
     tests.
3. `docs: document bundled subtitle fonts`
   - README, PRD, architecture, conventions if needed, and roadmap status.

Suggested pull request:

~~~
Title: feat: add a bundled OFL font catalog
Base: main
~~~

Before opening the pull request:

- Run `python -m pytest tests/test_config.py tests/test_text_measurement.py tests/test_cli.py tests/test_subtitler.py` plus the new font-catalog and packaging tests.
- Run controlled font checks with `python -m pytest -m integration -k font` when
  FFmpeg/libass is available.
- Run `python -m compileall multisubs`, `multisubs --help`,
  `python -m pytest`, `python -m ruff format --check .`,
  `python -m ruff check .`, and `python -m pyright`. Then run `rm -rf dist`
  immediately before `python -m build`, followed by
  `python -m twine check dist/*`.
- Install the built wheel in a clean environment and verify its font and license
  inventory against the manifest.
- In the final pre-PR documentation commit, move Plan 0 and the package to
  `In review` and record `feat/bundled-font-catalog` as the delivery reference.
- Push the complete branch before opening the PR; do not add a post-open commit
  solely for its number or URL.

After merge:

- Mark Plan 0 `Done`, replace the branch with the merged PR link, recalculate
  package/catalog progress, and identify Plan 1 as the next unblocked plan.

## Acceptance criteria

- A clean wheel installation contains and can render all 82 declared static
  faces and all six original family OFL texts without network access or system
  font installation.
- Every committed font is byte-for-byte represented by the exact source URL,
  size, and SHA-256 recorded in the manifest.
- Direct `--font` plus supported `--font-weight` and `--italic` selections use
  the expected bundled face when an exact face exists.
- An explicit custom face wins over the bundled same-named family; an unbundled
  family can still use fontconfig or the current estimate fallback.
- Pillow/RAQM and FFmpeg/libass consume the same selected provider directory in
  preview and normal rendering.
- Default appearance values remain unchanged and default Roboto resolves to the
  bundled Regular face.
- README gives a user enough information to add a new family without inspecting
  source code: where to place files, which formats work, how `--font` identifies
  the family, how to select weight/italic variants, the non-recursive directory
  limitation, and how custom precedence works.
- JSON reports the provider without exposing any local, package, or temporary
  path; SRT, timing, artifacts, and cleanup remain unchanged.
- Every build starts with a removed `dist/`; wheel/sdist audits, clean-install
  smoke checks, hermetic tests, controlled render tests, and required
  documentation pass.
