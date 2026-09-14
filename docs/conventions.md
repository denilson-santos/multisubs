# Engineering Conventions

## Scope and status

This document defines engineering conventions for multisubs, a Python 3.10–3.13 CLI. It applies to code, tests, packaging, documentation, automation, and releases. Follow it for new or materially changed work; do not rewrite existing code solely for conformance when the improvement is broad or risky.

The terms below communicate the strength of a convention:

- **Must**: an invariant, compatibility promise, or safety requirement.
- **Should**: the default choice; deviate only with a documented reason.
- **May**: an optional practice that is useful in the stated circumstances.

The `dev` extra configures local quality tools. CI and artifact promotion follow
the [delivery workflow](delivery.md).

## Convention hierarchy

When guidance conflicts, use this order:

1. User requirements and security constraints.
2. The product contract in [prd.md](prd.md).
3. The public behavior documented in [README.md](../README.md).
4. The design and data contracts in [architecture.md](architecture.md).
5. This document.
6. Local conventions already established in the file being changed.

Update a higher-level document when a proposed change intentionally modifies the contract it describes. See [AGENTS.md](../AGENTS.md) for the documentation update matrix.

## Supported environment and dependencies

### Python and virtual environments

- Must support Python 3.10 through 3.13, as declared by requires-python. The
  upper bound follows WhisperX 3.8.6 and must be reviewed with any WhisperX
  upgrade.
- Must use an isolated virtual environment for development. Invoke package-management commands through python -m pip so they target the active interpreter.
- Should develop and test against the oldest supported Python version as well as the current development version. The oldest version catches accidental use of newer syntax and standard-library APIs.
- Should keep runtime imports free of development-only dependencies.
- Must not commit virtual environments, Python bytecode, model caches, generated media, or generated transcription artifacts.

### Packaging

- Must keep runtime dependencies and the multisubs console-script entry point in pyproject.toml.
- Must use PEP 621 project metadata rather than introducing a second packaging configuration unless there is a compelling limitation.
- Should keep release metadata complete: description, README reference, license, classifiers, project URLs, and supported Python versions.
- Must use one authoritative package version. `multisubs.__version__` is the source of truth and `pyproject.toml` derives its version dynamically.
- Should build and install a wheel from a clean environment before publishing a release.
- Must remove the existing `dist/` directory immediately before every
  distribution build. Artifact validation, checksums, attestation, upload, and
  clean-install smoke checks must consume only files created by that build.
- Must declare bundled font binaries, their per-family `OFL.txt` files, and the
  font manifest as package data. A clean-wheel smoke check must explicitly
  verify the complete manifest inventory instead of relying on source-tree
  availability.
- Must declare built-in template JSON resources as package data. Their
  deterministic index and complete resource inventory must be audited in the
  source tree, wheel, and sdist, then exercised from a clean wheel install.

### Dependency changes

- Must justify every new runtime dependency: the capability it provides, why the standard library or an existing dependency is insufficient, its license, its maintenance status, and its installation-size impact.
- Must treat torch, torchaudio, and torchvision as a compatible set. Update and test them together rather than changing one package in isolation.
- Must validate a WhisperX upgrade against the selected PyTorch set, CPU inference, and CUDA inference when the project claims CUDA support.
- Must document FFmpeg as a system dependency. Installing ffmpeg-python does not install the FFmpeg executable or its subtitle-rendering libraries.
- Should use a lock file or platform-specific constraints files for reproducible development and CI environments. Torch wheels often differ by operating system, Python version, CUDA version, and CPU/GPU build, so one universal lock file may not be sufficient.
- Should audit dependency updates for release notes, known vulnerabilities, wheel availability, and model/runtime compatibility before merging.
- Must not use unpinned Git URLs, arbitrary download scripts, or implicit latest-version installs in CI or release instructions.
- Must treat Pillow as the text-measurement boundary rather than reimplementing
  TrueType/OpenType parsing. Font resolution must remain bounded and must not
  serialize machine-specific font paths or persist transcript text in caches.
- Must keep fontTools 4.63 or a reviewed compatible 4.x release as the runtime
  cmap-coverage reader. Use it only for bounded TrueType/OpenType coverage
  inspection; Pillow/RAQM remains the shaping and advance-measurement boundary.
  Bound file size, collection faces, candidate count, and fontconfig runtime;
  reject malformed resources without automatic downloads. Record the effective
  family and fallback reason without local paths in JSON.
- Must keep `uniseg` at the selected `0.10.1` compatibility line for the shared
  Unicode boundary adapter. Its pinned Unicode 16.0.0 data supplies grapheme,
  word, line, and sentence boundaries; it does not provide linguistic
  dictionary segmentation. Do not replace it with ad-hoc combining-mark,
  East-Asian-width, or UTF-16 indexing logic without updating the multilingual
  plan and its fixture evidence.
- Must keep Japanese and Chinese lexical grouping behind the shared text
  adapter with the reviewed pins SudachiPy 0.6.11,
  SudachiDict-small 20260723, and jieba 0.42.1. Load dictionaries lazily and
  offline, reconcile every provider boundary with complete uniseg graphemes,
  and preserve source offsets and alignment records. jieba must use a bounded
  invocation-local temporary cache that is removed afterwards; never use its
  shared host cache or persist transcript text. These Apache-2.0/MIT
  dependencies add about 164 MB installed in the evaluated Python 3.10
  environment; version, license, wheel, hash, and platform evidence lives in
  the multilingual backend decision plan.
- Must normalize public font-weight names, aliases, and supported numeric input
  to one canonical OpenType rank. Face selection ranks absolute weight distance
  before italic mismatch and uses stable provider order as the final tie
  breaker; diagnostics must distinguish the requested rank from the inferred
  resolved face rank.
- Must obtain bundled font binaries unchanged from an authoritative tagged
  release, pinned commit, or versioned Google Fonts API response over HTTPS.
  Record the full catalog or upstream revision, exact binary source URL,
  internal family/style metadata, byte size, and SHA-256 in the committed
  manifest; keep the matching OFL 1.1 text beside each family.
- Must not subset, convert, rename internally, synthesize static instances, or
  download a bundled font at runtime. Add or update font assets and their
  manifest entries together, then audit both wheel and sdist inventories.

## Project structure and module boundaries

- Follow the [architecture component map](architecture.md#components) for
  module ownership and interfaces. Add a focused module when a responsibility
  no longer fits instead of growing `cli.py` into a second pipeline.
- Must avoid circular imports and import-time model loading, filesystem writes, network access, or FFmpeg execution.
- Should make a new public API explicit through multisubs/__init__.py only when it is intentionally supported. Leave implementation helpers module-private with a leading underscore.
- Should return a named dataclass or typed mapping from a new public function that has several related outputs. Preserve an existing tuple-returning API unless a migration plan and compatibility decision are documented.

## Python code style

### General style

- Must write code compatible with Python 3.10.
- Should follow PEP 8 with an 88-character preferred line length, matching common Black and Ruff defaults.
- Should use four spaces for indentation, UTF-8 source files, Unix line endings, and a final newline.
- Should use snake_case for functions, variables, modules, and CLI-internal names; PascalCase for classes; and UPPER_SNAKE_CASE for constants.
- Should use clear, domain-specific names such as aligned_segments, subtitle_path, and compute_type instead of unexplained abbreviations.
- Should prefer f-strings for readable interpolation and avoid constructing shell command strings.
- Must preserve the surrounding file's style during a small change. Do not mix a broad formatting rewrite with a behavioral change.

### Imports and dependencies

- Should order imports as standard library, third-party packages, then local packages, with a blank line between groups.
- Must avoid wildcard imports.
- Should import a dependency at module scope only if importing it is cheap and required for that module's normal use. Use a deliberate lazy import when it materially improves CLI startup, optional-dependency behavior, or test isolation.
- Must not add an import whose sole effect is to alter global PyTorch, WhisperX, or FFmpeg behavior without documenting it.

### Types, interfaces, and docstrings

- Should add type annotations to new public functions, return values, data containers, and non-obvious internal boundaries.
- Should use Path or str only at external boundaries when both are truly supported; normalize once inside the function. Avoid passing a mixture of path types throughout a call graph.
- Should use TypedDict, dataclass, or a small dedicated model for structured data whose shape is controlled by this project.
- Must treat data returned by WhisperX and FFmpeg wrappers as external input: access optional fields defensively and validate the subset relied on by the project.
- Should write docstrings for public functions and non-obvious algorithms. Explain assumptions, input/output contracts, failure behavior, and units where relevant.
- Must keep docstrings and type hints aligned with actual behavior.

### Paths, files, and resources

- Should use pathlib.Path for new path-heavy code. Existing os.path code may remain consistent within its module; do not mix the two styles indiscriminately in one function.
- Must normalize and validate input and output paths before expensive model work begins.
- Must never overwrite a user-provided input file or an existing output artifact silently. Preserve the collision-safe naming contract described in [architecture.md](architecture.md#output-layouts).
- Should create outputs in a temporary file or directory adjacent to their final destination and move them into place only after successful completion. This avoids presenting a partial video or subtitle file as finished.
- Must delete temporary artifacts only after the step that consumes them succeeds, and must not delete artifacts outside the current invocation's output scope.
- Should preserve the original exception context when a filesystem operation fails and tell the user which path and operation failed.
- Must write JSON, SRT, and ASS text as UTF-8.
- Load packaged declarative resources through `importlib.resources` and
  validate them before use. Treat custom templates as bounded, untrusted data:
  never execute, fetch, install, or persist them, and do not serialize local
  paths or raw contents. See [architecture template contracts](architecture.md#internal-template-resources).

## Command-line interface conventions

### Compatibility and arguments

- Must treat documented flags, defaults, output layout, and exit behavior as a public API. Review the [README command reference](../README.md#command-reference) before changing them.
- Should add new options in a backward-compatible way and prefer an opt-in flag over changing existing default behavior.
- Must use kebab-case long flags and a concise, non-conflicting short flag only when it materially improves common usage.
- Must keep argument help text accurate, include units and defaults where useful, and avoid jargon that users cannot act on.
- Should use argparse validation for invalid choices and missing required values. Perform validation that depends on the filesystem or a combination of options before model loading.
- Must reject unsupported translation/model combinations before expensive
  work starts; see [translation requirements](prd.md#functional-requirements).
- Should offer a dry-run or validation-only mode before adding an operation with expensive processing or destructive potential.

### Dimension and unit options

- Public layout inputs must be explicit, bounded, and validated before model
  loading. Resolve geometry-dependent values only after probing, in the typed
  layout boundary; never pass unresolved units to ASS serialization.
- Relative-unit bases, rounding, native/explicit placement, margin validation,
  and envelope rules are defined in the
  [architecture layout and ASS contract](architecture.md#srt-and-ass)
  and [product requirements](prd.md#functional-requirements). Keep this file
  focused on validation timing and ownership rather than duplicating those
  values.

### Exit status, output, and diagnostics

- Must return a non-zero exit status for invalid arguments, missing dependencies, model failures, media-processing failures, and failed output writes.
- Should write normal progress and successful result paths to standard output. Should write diagnostics and actionable errors to standard error.
- Should use stable, human-readable messages that identify the failed operation and relevant path or dependency without dumping an opaque traceback by default.
- Must preserve a traceback or exception chain for a debug mode, test failure, or structured logging path.
- Should introduce standard logging with named loggers and a verbose or log-level option before the CLI grows beyond simple progress messages. Library modules should not depend on CLI-only logging configuration.
- Must not print access tokens, environment secrets, full private transcript contents, or sensitive media metadata in routine logs.

## WhisperX, PyTorch, and model conventions

### Hardware and model lifecycle

- Keep compute-device, precision, and model-loading behavior aligned with the
  [architecture execution flow](architecture.md#execution-flow).
- Should provide a deliberate device override before adding more hardware modes, so users can choose CPU or a specific accelerator deterministically.
- Must not silently fall back from a user-requested model, language, task, or precision to a different semantic behavior. A safe fallback must be visible in logs and documentation.
- Should load models once per invocation and pass the loaded instance through the pipeline. Do not reload a model for each small pipeline step.
- Should release large references promptly after processing in future batch workflows. Only use GPU-cache clearing when there is measured benefit; indiscriminate cache clearing can reduce throughput.
- Must keep model downloads, caches, and credentials out of the repository and out of normal project output directories.
- Should report the selected model, device, precision, detected language, and dependency versions in debug logs or reproducibility metadata, subject to privacy considerations.

### Transcription and alignment

- Keep language, task, translation, and model behavior aligned with the
  [product requirements](prd.md#functional-requirements); reject unsupported
  combinations before expensive work and never silently change semantics.
- Treat WhisperX results as external input: validate used fields and timestamps
  and do not turn undocumented upstream metadata into a stable contract.
- Change language handling, VAD, alignment models, or model defaults only with
  targeted tests and a documentation update. Describe network-dependent setup
  so offline users know why an initial run may fail.

### Performance and memory

- Should measure representative CPU and GPU runs before changing default models, precision, VAD, or cue-generation algorithms.
- Should use short, licensed, non-sensitive fixtures for performance checks; do not commit production media.
- Should expose performance-affecting choices as explicit configuration rather than hidden environment-dependent heuristics when users need reproducibility.
- Must fail clearly on out-of-memory conditions and explain the most relevant remedies, such as choosing a smaller model or a different device, when they are known.

## Subtitle data and formatting conventions

### Cue construction

- Cue boundaries, source mapping, Unicode grouping, wrapping, timing, and
  fallback behavior are specified in [architecture](architecture.md#subtitle-cue-construction)
  and [PRD FR-7/FR-17](prd.md#functional-requirements). Preserve source text and
  validated timestamps; never invent content or word timing to satisfy layout.
- Keep layout work bounded and thresholds centralized. Add language-specific
  fixtures before claiming new segmentation support; see the testing strategy
  below.

### SRT, ASS, and JSON

- Use [SRT and ASS](architecture.md#srt-and-ass),
  [JSON](architecture.md#json), and [output layouts](architecture.md#output-layouts)
  as the authoritative artifact contracts. Preserve JSON compatibility within
  a release line unless an explicit versioned migration is approved.
- SRT cue indices must be sequential and timestamps must use
  HH:MM:SS,mmm. Normalize embedded line endings and test rounding at
  millisecond, minute, and hour boundaries.
- Treat transcript fragments as untrusted text. Keep semantic style, layout,
  and animation values typed; escape display text separately from generated
  ASS overrides. Update the architecture contract and tests when changing this
  boundary.
- Serialize JSON-compatible finite values only. Treat source paths and
  transcripts as sensitive; do not publish generated JSON by default.

### Typography and renderer

- The shared typography, measurement, geometry, animation, and preview behavior
  is defined in [subtitle-cue construction](architecture.md#subtitle-cue-construction)
  and [SRT and ASS](architecture.md#srt-and-ass). Do not create a separate
  preview-only implementation of these contracts.
- Add opt-in FFmpeg/libass rendering coverage for changes that affect ASS
  output; the testing section below defines integration-test requirements.

## FFmpeg and media-processing conventions

- Use an argument-based API such as ffmpeg-python or subprocess argument lists;
  never interpolate user-controlled paths or options into shell commands.
- Treat filter paths as untrusted input. Escape them for FFmpeg filter syntax and
  test spaces, quotes, colons, commas, backslashes, and non-ASCII characters.
- Keep codec, quality, stream mapping, audio, container, metadata, and overwrite
  policy explicit. Update the [README](../README.md) and
  [architecture](architecture.md) if rendering behavior changes.
- Follow the [FFmpeg boundary](architecture.md#ffmpeg) for preflight, selected
  stream, geometry, and autorotation. Use temporary output and publish it only
  after success.
- Bound work on malformed media, avoid recursively processing user paths, and
  report failures with enough stage/path context to diagnose them without
  exposing sensitive contents.

## Error handling and observability

- Must catch only exceptions that the code can handle or enrich. Never use a bare except or silently swallow an exception.
- Should use domain-specific exceptions at module boundaries when callers need to distinguish validation, dependency, transcription, alignment, serialization, and rendering failures.
- Must preserve the original exception as the cause when re-raising a more useful error.
- Should make cleanup failure non-destructive: report it separately without hiding a primary successful result or primary processing failure.
- Should include an invocation identifier in structured logs if batch or concurrent processing is introduced.
- Must ensure diagnostic output never contains raw credentials or a complete transcript unless the user explicitly requests debug output and accepts that exposure.

## Testing conventions

### Test layers

- Must create or update tests for every new feature and every change to an existing feature. The tests must cover its expected behavior, relevant validation and failure paths, and any public output or compatibility contract it changes.
- Must keep tests current with the implementation, CLI, output formats, and documented behavior. Do not merge a feature change that knowingly leaves obsolete, skipped, or contradictory tests behind.
- Must keep default tests hermetic: no model download, GPU requirement, network call, long transcription, or installed system FFmpeg dependency.
- Should unit-test pure functions first, especially cue boundaries, text wrapping, timestamp formatting, JSON construction, and collision-safe path generation.
- Should mock WhisperX and FFmpeg wrapper calls in unit tests. Assert the project contract passed to those integrations rather than their internal behavior.
- Should add opt-in integration tests for real FFmpeg/libass rendering and, separately, WhisperX transcription/alignment. Mark them clearly and skip them when dependencies, media fixtures, or hardware are unavailable.
- Should use golden JSON/SRT/ASS fixtures for output contracts. Review golden-file changes as carefully as code changes.
- Should add regression tests before fixing a reported subtitle segmentation or rendering defect.
- May use property-based tests for timestamp ordering, unique-path generation, and word/cue boundary invariants.

### Fixtures and test data

- Must use small, licensed, non-sensitive media fixtures. Do not commit production videos, voices, transcripts, or identifying metadata.
- Should keep fixture duration short enough for CI and test only the behavior needed by the case.
- Must store expected output text in UTF-8 and include Unicode coverage.
- Should test the pinned Unicode adapter with combining marks, Hangul Jamo,
  Indic conjuncts, flags, modifiers, variation selectors, ZWJ sequences,
  supplementary-plane characters, repeated records, NBSP, and incomplete
  alignment. Tests must assert exact source reconstruction rather than removing
  all spaces before comparison.
- Should include tests for no audio stream, corrupt media, absent FFmpeg, unsupported filters, missing alignment timestamps, nonexistent paths, output collisions, and cleanup failures.
- Must verify both artifact modes: default cleanup and keep-transcriptions.

The completed multilingual gate permits no package-owned `xfail` marker.
Unexpected errors must fail rather than being swallowed by an expected
assertion failure. Required CI render evidence must fail when its provisioned
font inventory is missing; an ordinary developer integration run may skip with
an explanation when the external fixture is unavailable.
Synthetic UTF-8 fixtures live under `tests/fixtures/multilingual`; local replay
outputs and dependency evaluation environments remain temporary or ignored.
The exact evaluation environment remains in
`scripts/multilingual-spike-requirements.txt`; production-adopted pins also live
in `pyproject.toml`. Run backend evaluation in a separate virtual environment.

### Recommended quality tooling

When the project adopts a test/tooling baseline, configure it in pyproject.toml and document exact installation commands. The recommended baseline is:

| Concern | Recommended tool | Purpose |
| --- | --- | --- |
| Tests | pytest | Unit tests, fixtures, markers, and readable failure reporting. |
| Coverage | pytest-cov | Coverage measurement with focused thresholds after the suite is established. |
| Formatting and linting | Ruff | Fast formatting checks, import organization, and lint rules. |
| Type checking | Pyright or mypy | Static validation of public interfaces and external-data boundaries. |
| Hooks | pre-commit | Repeatable local formatting, linting, and whitespace checks. |
| Packaging | build and twine check | Build a distributable artifact and validate its metadata. |
| Security | pip-audit or Dependabot/Renovate | Identify vulnerable or stale Python dependencies. |

Once those tools are configured, the expected local quality gate should be equivalent to:

~~~
python -m compileall multisubs
ruff format --check .
ruff check .
pyright
python -m pytest
rm -rf dist
python -m build
twine check dist/*
~~~

Do not run a command from this list merely because it appears here if the corresponding tool is not installed or configured yet.

## Documentation conventions

- Must update [README.md](../README.md) for changes users need to install, invoke, understand, or troubleshoot.
- Must update [prd.md](prd.md) for changes to goals, scope, functional requirements, non-functional requirements, exclusions, or acceptance criteria.
- Must update [architecture.md](architecture.md) for changes to execution flow, module ownership, cue policy, output contracts, output layouts, or external boundaries.
- Must update this document when the team adopts, changes, or removes an engineering convention.
- Must update [AGENTS.md](../AGENTS.md) when a documentation file becomes required reading for a class of agent work.
- Should write documentation in English to match the source code and existing project documentation.
- Should use descriptive headings, relative Markdown links, fenced examples, and language that distinguishes current behavior from planned behavior.
- Must not document a capability as supported until it is implemented, verified, and exposed through the intended user interface.

## Security, privacy, and supply chain

- Must treat all media files, subtitle text, paths, and metadata as potentially untrusted or sensitive.
- Must avoid shell execution with interpolated user-controlled values.
- Must not send media, transcripts, telemetry, or model credentials to third parties without an explicit user-facing feature and consent model.
- Should provide a documented data-retention policy before adding caches, logs, telemetry, batch histories, or cloud features.
- Must keep tokens, private package indexes, Hugging Face credentials, and local configuration outside the repository. Use environment variables or a user-specific secure configuration mechanism.
- Should set practical limits or warnings for enormous files, excessive duration, malformed media, and resource-intensive model selections before exposing the tool to untrusted batch inputs.
- Must review package provenance, hashes or locks where available, and release artifacts before publishing.

## CI, releases, and change management

### Continuous integration

- Must run compile checks, Ruff formatting and linting, Pyright, hermetic tests,
  a package build, and package-metadata checks on every pull request to `main`.
- Must test Python 3.10 and 3.13. Use the pinned CPU PyTorch set in hosted CI so
  validation does not depend on GPU runners or CUDA wheel downloads.
- Must keep GPU and real-model integration tests outside the default pull-request
  path unless GPU runners are intentionally funded and maintained.
- Must run the opt-in FFmpeg/libass suite in the manually approved staging
  environment before a commit is eligible for release.
- Must pin every referenced GitHub Action to a reviewed full commit SHA and use
  Dependabot to propose controlled updates.
- Must grant `GITHUB_TOKEN` only the permissions required by each workflow or
  job. Pull-request validation remains read-only; attestation writes belong only
  to staging and release writes belong only to production publication.
- Must not use `pull_request_target` for code validation or expose environment
  secrets to untrusted pull-request code.
- Must fail CI on generated-file drift only when those files are intentional, reviewable project artifacts.
- Should run documentation link checks once the documentation set grows or is published.

### Releases

- Should follow semantic versioning: patch for backward-compatible fixes, minor for backward-compatible features, and major for breaking public CLI, output-contract, or supported-environment changes.
- Must keep the README focused on the current interface and current defaults.
  Document breaking changes and legacy migration details in release notes or a
  changelog instead of retaining recipes for removed interfaces in the README.
- Should maintain a changelog when releases become externally consumed.
- Must build from a clean checkout, install the built artifact in a clean environment, invoke multisubs --help, and perform the appropriate smoke checks before publishing.
- Should publish reproducible source distributions and wheels with provenance or signed artifacts when the distribution channel supports them.
- Must build wheel and source artifacts once in staging, record SHA-256 checksums,
  attest their provenance, and promote those exact files without rebuilding.
- Must publish production only from a stable `vX.Y.Z` tag that matches
  `multisubs.__version__`, points to a commit in `main`, and has a non-expired
  successful staging artifact for the same SHA.
- Must create or resume a matching draft before publication. Never alter an
  already published release or move an existing release tag; issue a new patch
  version for a correction.
- GitHub Releases are the distribution channel for this workflow. Publishing to
  PyPI or another registry requires a separate product and credential decision.

### Commits and pull requests

- Must follow GitHub Flow: branch from `main`, open the pull request against
  `main`, satisfy `Development / development-gate`, merge with one of the
  repository's enabled methods, and remove the merged remote branch. Long-lived
  environment branches are not used.
- Must name short-lived branches `<type>/<short-kebab-case-description>`, using
  `feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `build`, or `chore` according
  to the primary purpose of the change.
- Should keep a change focused on one user-visible behavior or one maintainability concern.
- Must use clear imperative Conventional Commit-style subjects with the same
  allowed type vocabulary, for example `fix: handle missing rotation metadata`.
- Should keep each commit coherent and independently reviewable. Separate
  mechanical formatting, structural refactors, behavior, and documentation
  when combining them would obscure the review.
- Must use a pull-request title that summarizes the full change and a body that
  explains the scope, reason, user or developer impact, verification actually
  performed, documentation changes, and remaining risks.
- Plan-backed changes must record their task branch and `In review` status in
  the final pre-PR documentation commit. Do not push a metadata-only commit
  after opening the PR solely to add its number; the post-merge status update
  marks the plan `Done` and replaces the branch with the merged PR link.
- Should choose the merge method deliberately: merge commits preserve branch
  topology, squash merges collapse the pull request into one commit, and rebase
  merges preserve individual commits on a linear path.
- Must include tests or explain why tests are not applicable.
- Must include documentation updates or explain why no documented behavior changed.
- Should describe performance, hardware, dependency, and output-contract impact in the pull request when relevant.
- Must not combine generated media, model artifacts, broad reformatting, and functional changes in a single review unless they are inseparable.

## Pre-change and pre-merge checklists

### Before changing code

- [ ] Read the relevant product, user, architecture, and convention documents.
- [ ] Identify whether the change affects public CLI behavior, output files, JSON shape, subtitle timing, model behavior, or FFmpeg rendering.
- [ ] Identify the smallest appropriate module boundary.
- [ ] Decide the expected failure behavior and user-visible diagnostic.
- [ ] Decide which unit and optional integration tests cover the change.

### Before merging

- [ ] Verify the code against the available local quality checks.
- [ ] Run focused tests and explain any checks not run.
- [ ] Confirm no source media, model cache, virtual environment, secrets, or generated artifacts were added.
- [ ] Confirm paths are collision-safe and cleanup cannot delete unrelated files.
- [ ] Confirm user-visible changes are reflected in the README.
- [ ] Confirm product-scope changes are reflected in the PRD.
- [ ] Confirm pipeline, data-contract, or dependency changes are reflected in the architecture document.
- [ ] Confirm a new or changed engineering rule is reflected in this document and surfaced through AGENTS.md when agents need to follow it.
