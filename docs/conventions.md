# Engineering Conventions

## Scope and status

This document defines engineering conventions for multisubs: a Python 3.10–3.13 command-line application built with setuptools, PyTorch, WhisperX, ffmpeg-python, FFmpeg, and JSON/SRT/ASS subtitle outputs.

It applies to production code, tests, packaging, documentation, automation, and releases. Follow it for all new or materially modified code. Existing code does not need a broad rewrite solely for conformance; improve it when the change is local, low risk, and verified.

The terms below communicate the strength of a convention:

- **Must**: an invariant, compatibility promise, or safety requirement.
- **Should**: the default choice; deviate only with a documented reason.
- **May**: an optional practice that is useful in the stated circumstances.

The repository's `dev` extra configures the recommended local quality tools.
GitHub Actions applies the same checks and promotes immutable distribution
artifacts through the environments documented in [delivery.md](delivery.md).

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
- Must normalize public font-weight names, aliases, and supported numeric input
  to one canonical OpenType rank. Face selection ranks absolute weight distance
  before italic mismatch and uses stable provider order as the final tie
  breaker; diagnostics must distinguish the requested rank from the inferred
  resolved face rank.

## Project structure and module boundaries

- Must keep command-line orchestration in multisubs/cli.py.
- Must keep model loading, transcription, alignment, cue construction, and subtitle-file writing in multisubs/transcriber.py.
- Must keep FFmpeg rendering concerns in multisubs/subtitler.py.
- Must keep semantic subtitle appearance defaults in multisubs/config.py.
- Must keep generic collision-safe path helpers in multisubs/utils.py.
- Should add a focused module when a responsibility no longer fits these boundaries instead of growing cli.py into a second pipeline implementation.
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

## Command-line interface conventions

### Compatibility and arguments

- Must treat documented flags, defaults, output layout, and exit behavior as a public API. Review the [README command reference](../README.md#command-reference) before changing them.
- Should add new options in a backward-compatible way and prefer an opt-in flag over changing existing default behavior.
- Must use kebab-case long flags and a concise, non-conflicting short flag only when it materially improves common usage.
- Must keep argument help text accurate, include units and defaults where useful, and avoid jargon that users cannot act on.
- Should use argparse validation for invalid choices and missing required values. Perform validation that depends on the filesystem or a combination of options before model loading.
- Must reject unsupported translation/model combinations before expensive work starts. Translation target and model restrictions are product requirements, not merely UI hints.
- Should offer a dry-run or validation-only mode before adding an operation with expensive processing or destructive potential.

### Dimension and unit options

- Must require an explicit `%` or `px` suffix for public layout lengths; bare
  numbers are ambiguous and must be rejected.
- Must parse bounded decimal input before model loading, reject signs and
  exponent notation, and preserve the original requested string for metadata.
- Must resolve percentages only after normalized video geometry is available,
  using the field's documented axis or reference value.
- Must resolve margins against the render axes first. In native ASS placement,
  resolve percentage maximum width against the width after left/right margins
  and maximum height against the alignment-specific available height. In
  explicit placement, resolve X/Y and both maximum dimensions against the full
  PlayRes axes and ignore margins.
- Must treat explicit pixel coordinates as absolute PlayRes coordinates and
  reject any complete anchored maximum-width/maximum-height envelope that leaves
  the canvas. Do not silently clamp, move, or shrink an invalid placement.
- Must use one deterministic rounding policy for every relative length and
  perform combined mode-specific validation after all fields are resolved.
- Must keep unresolved unit values out of ASS serialization; the ASS writer
  receives a geometry-resolved typed configuration.
- Must define layout preset sources centrally as immutable typed values in
  `config.py`; preset selection, field-by-field override merging, and
  geometry-dependent resolution belong in `layout.py`.

### Exit status, output, and diagnostics

- Must return a non-zero exit status for invalid arguments, missing dependencies, model failures, media-processing failures, and failed output writes.
- Should write normal progress and successful result paths to standard output. Should write diagnostics and actionable errors to standard error.
- Should use stable, human-readable messages that identify the failed operation and relevant path or dependency without dumping an opaque traceback by default.
- Must preserve a traceback or exception chain for a debug mode, test failure, or structured logging path.
- Should introduce standard logging with named loggers and a verbose or log-level option before the CLI grows beyond simple progress messages. Library modules should not depend on CLI-only logging configuration.
- Must not print access tokens, environment secrets, full private transcript contents, or sensitive media metadata in routine logs.

## WhisperX, PyTorch, and model conventions

### Hardware and model lifecycle

- Must select a supported compute configuration explicitly. The current behavior is CUDA with float16 when available and CPU with int8 otherwise; document any change to that policy in [architecture.md](architecture.md#execution-flow).
- Should provide a deliberate device override before adding more hardware modes, so users can choose CPU or a specific accelerator deterministically.
- Must not silently fall back from a user-requested model, language, task, or precision to a different semantic behavior. A safe fallback must be visible in logs and documentation.
- Should load models once per invocation and pass the loaded instance through the pipeline. Do not reload a model for each small pipeline step.
- Should release large references promptly after processing in future batch workflows. Only use GPU-cache clearing when there is measured benefit; indiscriminate cache clearing can reduce throughput.
- Must keep model downloads, caches, and credentials out of the repository and out of normal project output directories.
- Should report the selected model, device, precision, detected language, and dependency versions in debug logs or reproducibility metadata, subject to privacy considerations.

### Transcription and alignment

- Must distinguish transcription from translation. Translation output is English, and the CLI must reject models that do not support it.
- Must handle an alignment result without usable word timings. The fallback cue path must produce valid, chronologically ordered subtitle entries rather than crashing or inventing timestamps.
- Should validate that segment times are finite, non-negative, and monotonic before serializing them.
- Should preserve original WhisperX word metadata when it is useful for downstream consumers, but must not make undocumented upstream fields a stable project contract.
- Should make changes to language handling, VAD behavior, alignment models, or model defaults only with targeted tests and a documentation update.
- Must keep any network-dependent model setup explicit in documentation so offline users understand why an initial run may fail.

### Performance and memory

- Should measure representative CPU and GPU runs before changing default models, precision, VAD, or cue-generation algorithms.
- Should use short, licensed, non-sensitive fixtures for performance checks; do not commit production media.
- Should expose performance-affecting choices as explicit configuration rather than hidden environment-dependent heuristics when users need reproducibility.
- Must fail clearly on out-of-memory conditions and explain the most relevant remedies, such as choosing a smaller model or a different device, when they are known.

## Subtitle data and formatting conventions

### Cue construction

- Must preserve the product's readability policy: semantic boundaries such as sentence endings and meaningful pauses take priority over arbitrary hard splits. See [architecture.md](architecture.md#subtitle-cue-construction).
- Must derive visual wrapping from maximum width, maximum height, measured font
  line height, decorative bounds, and Unicode display-width estimates rather
  than a fixed character or line count. The estimator is approximate; libass
  remains authoritative for final font shaping and indivisible tokens may
  overflow.
- Must keep partition search bounded by both derived line capacity and available
  text units so unusually large height values cannot create unbounded work.
- Must keep cue timestamps in chronological order, with end at or after start; a rendered cue should normally have a strictly positive duration.
- Should keep thresholds, such as maximum duration and line length, centralized as named constants or documented configuration rather than scattering literal values.
- Should test punctuation, long sentences, pauses, one-word overflow, missing word timings, and exact threshold boundaries whenever cue logic changes.
- Should consider language-specific behavior before assuming space-delimited words, Latin punctuation, or left-to-right text. Add representative fixtures before claiming support for a new writing system or segmentation strategy.
- Must not mutate or discard transcript content solely to satisfy visual line-length targets. Prefer a well-timed overflow or a new cue over damaging words.

### SRT

- Must use UTF-8 and standard HH:MM:SS,mmm timestamps.
- Must number cues sequentially from one in output order.
- Should round timestamps consistently and test rollover at milliseconds, minutes, and hours.
- Must escape or normalize embedded line endings so the generated file remains structurally valid.

### ASS

- Must keep the ASS header, style field order, event field order, and dialogue line-break syntax compatible with the ASS format.
- Must ensure every transcription-derived value is safe in an ASS dialogue field. Escape or neutralize ASS override syntax and format-control characters according to the ASS specification, then test literal braces, backslashes, commas, newlines, and Unicode text.
- Must convert a visual line break to ASS \N in dialogue text rather than emitting a physical newline in the event.
- Must keep generated ASS overrides (placement, colors, and karaoke timing) on a trusted compiler path separate from independently escaped transcript fragments. Never parse or re-escape a completed generated override string as ordinary user text.
- Word-timed effects must preserve exact display-fragment reconstruction and use only validated aligned timestamps; missing or lossy mappings must fall back without inventing timing tokens.
- When a word-timed effect expands one cue into multiple ASS events, those events must be adjacent and non-overlapping, retain the complete cue text and placement, and never layer duplicate full-cue glyphs at the same timestamp.
- Must pass subtitle appearance and layout through typed configuration objects.
  Public inputs use semantic names and conventional color notation; ASS field
  ordering, fixed internal defaults, color conversion, and numeric codes belong
  only in the ASS serializer.
- Must keep the ASS style Bold field neutral and compile canonical font weights
  as trusted event-level `\\b100` through `\\b900` overrides so older libass
  style parsers receive the same exact OpenType rank used by font measurement.
  Compatibility bold shorthands may map to 400 or 700 only at configuration
  boundaries.
- Must not mutate a layout preset during a run. Preset definitions and their
  nested layout values must remain immutable so separate invocations cannot
  influence one another.
- Must compile named positions through native ASS style Alignment and actual
  margins without adding a synthetic event `\\pos`. Explicit coordinate mode
  must use event `\\an`/`\\pos`, neutral style margins, and a previously validated
  PlayRes envelope.
- Must validate appearance and layout values that can produce invalid ASS or unsafe filter input. Treat colors, font names, positions, margins, and numeric values as user input.
- Should use a documented style preset mechanism rather than duplicating long lists of CLI flags if several coherent styles are added.
- Should test generated ASS with a real FFmpeg/libass render in opt-in integration tests, because syntactically plausible ASS can still render unexpectedly.

### Typography measurement

- Must apply letter spacing in the shared measurement layer used by both
  concrete-font and Unicode-estimate modes before wrapping or cue splitting.
- Must count one tracking gap between consecutive rendered grapheme clusters on
  each visual line. Combining marks and zero-width joiner sequences stay with
  their base cluster, while spaces and punctuation remain measurable clusters.
  Explicit line breaks reset the gap count; raw code-point or byte counts are
  not valid substitutes.

### JSON contract

- Must keep the documented JSON top-level shape and required metadata fields backward compatible within a release line. See [architecture.md](architecture.md#json).
- Should add an explicit schema version before making the JSON a supported integration surface or changing its shape.
- Must serialize only JSON-compatible values and must not emit NaN or infinity.
- Should record timestamps in an unambiguous form. Use timezone-aware ISO 8601 values, preferably UTC, for new metadata fields.
- Should distinguish source language, detected language, requested task, selected model, and output language when they can differ.
- Must treat original_path and transcript text as potentially sensitive metadata. Avoid publishing generated JSON by default.

## FFmpeg and media-processing conventions

- Must use a maintained argument-based integration such as ffmpeg-python or subprocess.run with an argument list and check enabled; never concatenate untrusted paths or option values into a shell command.
- Must validate that the FFmpeg executable is available and that the required subtitle filter is supported before beginning a long run when practical.
- Must safely escape or pass subtitle-file paths for the FFmpeg filter syntax. Paths with spaces, quotes, colons, commas, backslashes, and non-ASCII characters require dedicated coverage.
- Must keep video-rendering policy explicit: subtitle filter, video codec, audio-stream policy, container compatibility, metadata preservation, and overwrite policy.
- Must avoid accidental re-encoding policy changes. If a change modifies codec, quality, stream mapping, audio-copy behavior, or container handling, document it in [README.md](../README.md) and [architecture.md](architecture.md).
- Must inspect the selected input video stream with ffprobe before model loading. The ASS canvas, rendering metadata, and FFmpeg subtitles filter must share the same normalized geometry and explicit autorotation policy.
- Should write rendered media to a temporary destination and publish it atomically after FFmpeg succeeds.
- Must surface FFmpeg failures with enough context to diagnose the command stage, input, output, and relevant stderr without leaking sensitive file contents.
- Should treat malformed media as untrusted input. Bound resource use where possible and avoid recursively processing paths supplied by a user.

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
- Should include tests for no audio stream, corrupt media, absent FFmpeg, unsupported filters, missing alignment timestamps, nonexistent paths, output collisions, and cleanup failures.
- Must verify both artifact modes: default cleanup and keep-transcriptions.

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
- Must document breaking changes, migration steps, and changed defaults in the README and release notes.
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
