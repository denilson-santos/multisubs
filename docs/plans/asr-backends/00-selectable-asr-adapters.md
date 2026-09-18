# Add selectable ASR adapters

Status: In review

Depends on: the current transcription, cue-layout, artifact, and CLI contracts.

Delivery branch: `feat/translation-fallback-animation-controls`

## Objective

Allow one local-video workflow to use WhisperX, Faster-Whisper, NVIDIA
Parakeet, or Qwen3-ASR through a stable internal adapter contract. Users choose
the runtime explicitly, while the default remains WhisperX.

## Scope

Included:

- A public `--asr` option and backend-specific default model resolution.
- Lazy adapters that normalize language, text, segments, and word timestamps.
- Optional installation extras for every ASR backend and an all-backends extra.
- Backend-aware validation, progress, JSON metadata, tests, and documentation.

Excluded:

- Cloud ASR APIs, diarization, streaming, batching, custom inference tuning,
  selectable Qwen inference engines, or automatic runtime benchmarking.
- Translation in Parakeet or Qwen3-ASR.
- Fabricated word timestamps when an adapter or language cannot provide them.

## Decisions and constraints

- `whisperx` is the default adapter and keeps `turbo` as its default model.
- `faster-whisper` uses native word timestamps and supports the same
  transcription/English-translation task policy as Whisper models. Translation
  uses a six-second `chunk_length`, matching WhisperX's six-second
  `chunk_size`; both then share the artifact-level measured-font fallback for
  translated envelope overflow.
- `parakeet` defaults to `nvidia/parakeet-tdt-0.6b-v3`, accepts transcription
  only, and recognizes supported languages without a prompt. Because its normal
  NeMo result does not expose the recognized code, omitted `--lang` produces
  null language metadata and filenames without a language suffix; an explicit
  code labels artifacts without conditioning inference.
- `qwen` uses only `Qwen/Qwen3-ASR-1.7B-hf`. It uses native Transformers
  inference with quiet-boundary chunks capped at 180 seconds and
  `Qwen/Qwen3-ForcedAligner-0.6B-hf` when
  an explicit or automatically detected source code is supported by the
  aligner. Other supported languages enter the existing coarse-timing fallback.
- Runtime packages stay optional and are imported only by the selected adapter.
  The core package and Faster-Whisper CPU path do not require PyTorch; CPU-only
  PyTorch installation uses its dedicated wheel index. CUDA guidance covers
  the matching PyTorch wheel index and Faster-Whisper's CTranslate2 libraries
  without treating the NVIDIA driver as a package dependency. Model downloads
  remain local runtime actions initiated by the user's command.

## Public interface and contracts

`--asr {whisperx,faster-whisper,parakeet,qwen}` defaults to `whisperx`.
Omitted `--model` resolves to the selected adapter's documented default;
explicit models are validated against its supported catalog. The public
`generate_transcriptions` and `transcribe_video` functions gain an optional ASR
selector without changing existing positional calls or tuple results.

Retained JSON keeps schema version 3 and adds the selected ASR identifier to
metadata. Its language is nullable when a backend cannot expose detection.
Unknown-language filenames omit the language suffix; collision handling and
cleanup are unchanged.

The subtitle CLI also exposes scoped presentation suppression for translation
compatibility: `--disable-cue-animations` and `--disable-word-animations` remove
all animation phases from text and backdrop tracks in their scope. Cue
suppression preserves its static backdrop; word suppression also removes the
dependent word decoration fields. A translation request that retains word
requirements reports the active category, recommends the word-scope flag, and
lists compatible built-in templates; cue-level presentation remains available.

## Implementation tasks

- [x] Add the adapter protocol, catalog, shared validation, and normalized
      result types.
- [x] Move WhisperX model interaction behind its adapter without changing
      inference, alignment, retry, or translation behavior.
- [x] Add hermetic Faster-Whisper, Parakeet, and Qwen3-ASR adapters with native
      timestamp normalization and actionable missing-extra errors.
- [x] Wire ASR/model resolution through CLI and programmatic orchestration.
- [x] Record the selected backend in retained metadata and preserve preview
      runtime isolation.
- [x] Add unit and regression coverage for every adapter and invalid
      backend/task/language/model combination.
- [x] Add scoped cue/word animation and effect suppression flags, with explicit
      translation diagnostics and compatibility-template guidance.
- [x] Update package metadata, README, PRD, architecture, conventions, and plan
      status.

## Verification

Run focused adapter, language, CLI, transcription, and preview tests, then:

~~~
python -m compileall multisubs
ruff format --check .
ruff check .
pyright
python -m pytest
multisubs --help
python -m build
twine check dist/*
~~~

Real model downloads are excluded from the default gate. Optional manual smoke
tests should use short, licensed, non-sensitive audio and the separately
installed backend extra.

## Commit and pull-request plan

Suggested branch: `feat/asr-backends`.

Suggested commits:

1. `refactor: isolate WhisperX behind an ASR adapter`
2. `feat: add selectable local ASR backends`
3. `docs: document selectable ASR runtimes`

The implementation was delivered as `feat: add selectable ASR backends` in
[PR #88](https://github.com/denilson-santos/multisubs/pull/88), merged into
`main` after the complete gate passed.

## Acceptance criteria

- Omitting both ASR and model produces the existing WhisperX `turbo` behavior.
- Each selectable backend normalizes valid output into ordered subtitle cues,
  preserves real word timestamps when available, and never imports another
  unselected runtime.
- Missing optional dependencies and unsupported task, model, or language
  combinations produce actionable errors before avoidable processing.
- Installing the core package or Faster-Whisper extra for CPU use does not
  resolve PyTorch or CUDA packages; PyTorch-backed ASRs remain separate extras.
- `--asr qwen` accepts only the 1.7B HF model and resolves it when `--model` is
  omitted; the global ASR default remains WhisperX.
- Installation documentation provides separate actionable CPU and NVIDIA CUDA
  paths for PyTorch-backed ASRs and Faster-Whisper.
- Parakeet and Qwen3-ASR accept local video through a temporary 16 kHz mono WAV
  that is removed after success or failure.
- Parakeet accepts omitted `--lang`; unknown language metadata is null and all
  published artifact names omit the language suffix.
- Retained JSON identifies both backend and model; all other artifact and
  rendering contracts remain compatible.
- Hermetic tests cover adapter conversion and orchestration without network,
  GPU, model downloads, or real FFmpeg execution.
