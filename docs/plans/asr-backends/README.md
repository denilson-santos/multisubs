# Selectable ASR backends roadmap

Status: In review

## Objective and scope

Let users select WhisperX, Faster-Whisper, NVIDIA Parakeet, or Qwen3-ASR while
keeping subtitle construction, rendering, and artifact publication independent
from each runtime. WhisperX remains the default and existing commands retain
their behavior.

## Plans and progress

Progress: 0/1 plans complete. Plan 0 is ready for pull-request review with no
blocking dependencies.

| Plan | Status | Dependencies | Delivery |
| --- | --- | --- | --- |
| [0 — ASR adapter layer](00-selectable-asr-adapters.md) | In review | Current transcription and subtitle contracts | `feat/asr-backends` |

## Delivery strategy

Deliver the adapter contract, four implementations, CLI selection, optional
dependencies, tests, and current documentation in one draft pull request to
`main`. Keep runtime packages lazy so previews and unselected backends do not
import or require them.

## Definition of done

- Existing commands still select WhisperX with the `turbo` model.
- Every backend returns the same validated transcript contract and actionable
  dependency or inference failures.
- Backend-specific task, model, language, and timestamp limits fail early or
  degrade to the existing coarse-timing path without fabricated timestamps.
- The `qwen` selector resolves only the Qwen3-ASR 1.7B model; WhisperX remains
  the global default.
- Default tests remain hermetic and documentation explains CPU and CUDA
  installation, selection, models, language behavior, and hardware costs.
