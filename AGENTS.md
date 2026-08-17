# AGENTS.md

## Project purpose

multisubs is a Python 3.10+ CLI for transcribing a local video with WhisperX, producing JSON/SRT/ASS subtitle assets, and rendering hard subtitles into a copied video with FFmpeg.

Read the relevant project documentation before changing behavior:

- [README.md](README.md) is the user-facing source for installation, CLI usage, output layout, and current limitations.
- [docs/prd.md](docs/prd.md) defines the product problem, scope, requirements, acceptance criteria, and intentional exclusions.
- [docs/architecture.md](docs/architecture.md) describes the pipeline, component boundaries, subtitle-cue rules, output contracts, and external integrations.
- [docs/conventions.md](docs/conventions.md) defines engineering, testing, dependency, security, and release conventions for this stack.

## Repository map

| Path | Responsibility |
| --- | --- |
| multisubs/cli.py | Argument parsing, user-facing validation, output-directory selection, and artifact cleanup. |
| multisubs/transcriber.py | WhisperX loading, transcription, word alignment, subtitle-cue construction, and JSON/SRT/ASS generation. |
| multisubs/ass.py | ASS header, style, timestamp, dialogue escaping, and serialization. |
| multisubs/subtitler.py | ffprobe geometry detection and FFmpeg invocation that burns an ASS file into the output video. |
| multisubs/config.py | Default ASS style values. |
| multisubs/utils.py | Collision-safe file and directory naming. |
| multisubs/errors.py | User-actionable error types at module boundaries. |
| multisubs/models.py | Typed internal request and artifact contracts. |
| pyproject.toml | Package metadata, dependencies, and the multisubs console-script entry point. |
| tests/ | Hermetic unit tests plus opt-in integration tests for external boundaries. |
| README.md | User documentation; consult it for public CLI and installation behavior. |
| docs/prd.md | Product requirements and scope; consult it before changing user-facing behavior or priorities. |
| docs/architecture.md | Technical design; consult it before changing the pipeline, data shape, output lifecycle, or external boundaries. |
| docs/conventions.md | Engineering standards; consult it before modifying code, dependencies, tests, FFmpeg integration, or release automation. |

## Setup and verification

Install in an isolated environment:

~~~
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
~~~

Install development checks with `python -m pip install -e '.[dev]'`.

For code-only changes, run:

~~~
python -m compileall multisubs
multisubs --help
~~~

Run the hermetic suite with `python -m pytest`. Do not run a full transcription as a routine smoke test: model loading may download assets and use substantial CPU, GPU, memory, and time. Run it only when the change needs end-to-end validation and a small non-sensitive video is available.

## Change guidelines

- Follow [docs/conventions.md](docs/conventions.md) for Python style, dependency changes, external-tool boundaries, error handling, test design, privacy, and release work.
- Preserve the public CLI flags and their defaults unless a breaking change is explicitly intended. Check the [README command reference](README.md#command-reference) and the functional requirements in [docs/prd.md](docs/prd.md#functional-requirements) first.
- Keep translation restrictions aligned with Whisper capabilities: turbo and models ending in .en cannot translate, and translation output is English. This is a product constraint in [docs/prd.md](docs/prd.md#functional-requirements) and a pipeline constraint in [docs/architecture.md](docs/architecture.md#design-constraints).
- Preserve collision-safe output behavior through get_unique_path and get_unique_dir_path. Do not silently overwrite user media or subtitle files. See [output layouts](docs/architecture.md#output-layouts) and FR-12 in [docs/prd.md](docs/prd.md#functional-requirements).
- Keep the --keep-transcriptions lifecycle consistent: retained runs keep JSON/SRT/ASS under a subtitles directory; non-retained successful runs remove only the transient SRT and ASS files. Consult [generated files](README.md#generated-files) and [output layouts](docs/architecture.md#output-layouts).
- When adding or changing a style value, update DEFAULT_STYLE, ensure the generated --style-* argument has the correct type, and keep the ASS Style field order correct. Update the [style options](README.md#style-options), the architecture's [SRT and ASS contract](docs/architecture.md#srt-and-ass), and the relevant product requirement.
- Keep subtitle-cue logic readable. It intentionally favors sentence punctuation and pauses before character and duration limits; word-timestamp-free segments have a fallback path. Refer to [subtitle-cue construction](docs/architecture.md#subtitle-cue-construction) and FR-7 in [docs/prd.md](docs/prd.md#functional-requirements).
- Keep FFmpeg-specific behavior isolated in multisubs/subtitler.py. Follow the [FFmpeg boundary](docs/architecture.md#ffmpeg) and keep user prerequisites accurate in the [README requirements](README.md#requirements).
- Do not commit virtual environments, model caches, generated videos, or generated subtitle artifacts. The repository ignores data/ and common build outputs for this reason.
- Avoid unrelated reformatting. Follow the surrounding file's style when modifying it.

## Implementation-plan delivery approval

- When an explicit plan specifies a Git branch, that instruction authorizes
  creating and switching to the named branch before implementation without a
  separate confirmation. First verify the intended base branch and preserve
  all existing working-tree changes.
- Apart from that authorized branch setup, complete the local implementation
  and relevant verification before starting the plan's Git delivery workflow.
- Always stop and ask the user for explicit confirmation before staging,
  committing, pushing, or opening or updating a pull request for plan work.
- Treat commit and pull-request instructions written in a plan as the delivery
  template, not as authorization to stage, commit, push, or publish changes.
- After the user confirms delivery, follow the plan's branch, commit, and
  pull-request instructions and include only the changes belonging to that plan.

## Documentation expectations

Documentation is part of the definition of done for behavior changes. Use this matrix to decide what to read and update:

| Change | Read before changing | Update when the change is made |
| --- | --- | --- |
| Installation, dependencies, supported environments, or user commands | [README.md](README.md#requirements) and [docs/prd.md](docs/prd.md#non-functional-requirements) | [README.md](README.md) |
| CLI flags, defaults, validation, translation behavior, or user-visible errors | [README command reference](README.md#command-reference) and [functional requirements](docs/prd.md#functional-requirements) | [README.md](README.md); update [docs/prd.md](docs/prd.md) if scope or a requirement changes |
| Output names, artifact retention, JSON shape, SRT/ASS generation, or collision handling | [generated files](README.md#generated-files) and [architecture output data and layouts](docs/architecture.md#output-data) | [README.md](README.md) and [docs/architecture.md](docs/architecture.md); update [docs/prd.md](docs/prd.md) if a functional requirement changes |
| Cue segmentation, wrapping, timing, or alignment behavior | [subtitle-cue construction](docs/architecture.md#subtitle-cue-construction) and FR-7 in [docs/prd.md](docs/prd.md#functional-requirements) | [docs/architecture.md](docs/architecture.md); update [docs/prd.md](docs/prd.md) if the expected user outcome changes |
| Module boundaries, execution flow, data contracts, or external integrations | [docs/architecture.md](docs/architecture.md) | [docs/architecture.md](docs/architecture.md); also update [README.md](README.md) for changed user prerequisites or limitations |
| Product goals, audience, scope, exclusions, or acceptance criteria | [docs/prd.md](docs/prd.md) | [docs/prd.md](docs/prd.md), then align [README.md](README.md) and [docs/architecture.md](docs/architecture.md) where they describe the same behavior |
| Python style, dependencies, test strategy, privacy, security, CI, or releases | [docs/conventions.md](docs/conventions.md) | [docs/conventions.md](docs/conventions.md), plus the relevant README, PRD, or architecture document |

## External dependencies

WhisperX depends on PyTorch and can use CUDA when available. FFmpeg and ffprobe must be installed as system executables, and FFmpeg's subtitles filter needs appropriate ASS/libass support. Treat these integrations as runtime dependencies even though only their Python packages appear in pyproject.toml. See [external boundaries](docs/architecture.md#external-boundaries) for ownership and behavior, [README requirements](README.md#requirements) for the user-facing prerequisites, and [the dependency conventions](docs/conventions.md#supported-environment-and-dependencies) before changing them.
