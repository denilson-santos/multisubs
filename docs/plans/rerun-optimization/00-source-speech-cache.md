# Persist source speech independently of presentation

Status: In review

Delivery: `feat/reusable-subtitle-runs`

Depends on: the existing [source-speech contract](../../architecture.md#deferred-speech-rendering)
and static backend/model/language validation.

## Objective and decisions

Skip model loading, inference, and alignment when reusing the same source and
recognition request. Cache normalized source speech
before semantic cue construction; preserve original words, missing/null times,
and unknown language. Use `SpeechTranscript` schema 1, not retained display JSON.
This increment supports `transcribe`; existing uncached translation is unchanged.

## Public interface and persistence

CLI transcription automatically uses
`<output-dir>/.multisubs-cache/transcriptions/v1`, including subtitle exports
and real previews. `--cache-dir DIR` overrides that location with
`DIR/transcriptions/v1`; a shared explicit directory also allows reuse across
output roots. The default follows the requested output root, outside
collision-safe retained-run folders; omitting `-o` uses the current directory.
`--refresh-cache` works with the default or custom location and refreshes the
matching entry only after successful recognition. Translation, sample previews,
external subtitles, and Python rendering APIs retain their uncached behavior.
Full source SHA-256, normalized requested language (including automatic mode),
backend, resolved model, task, and an explicit recognition compatibility revision
identify an entry. Presentation, source filename, output path, and encoder do
not identify speech. Installed runtime-version differences invalidate reuse;
absent optional runtimes do not prevent consuming valid speech.
When the current entry is absent, validated legacy `speech-v1` entries remain
reusable. New writes and refreshes use `transcriptions/v1`, leaving old files
untouched. The naming change preserves the identity and JSON schema.

Entries are bounded 16 MiB UTF-8 JSON with validated metadata and source data.
Directories and atomic temporary files restrict access to the owner. Reject
symbolic-link entries; never follow paths embedded in cache data. Invalid entries
trigger visible recomputation; filesystem failures are actionable errors. Detect
source changes during hashing/recognition before writing. Failed refreshes retain
the previous complete entry. Concurrent runs may duplicate recognition but must
never expose partially written JSON.

Retention is indefinite until the user removes the dedicated cache directory.
It is independent of `--keep-transcriptions`, and survives later layout/FFmpeg
failure. Document that model downloads remain managed by each runtime; cache hits
are reused observations, not proof of identical inference on every device.

## Implementation tasks

- [x] Add `speech_cache.py` with streaming identity, bounded validation, version
  metadata without runtime imports, atomic writes, and visible hit/miss progress.
- [x] Add typed request fields and CLI flags; validate combinations before models.
- [x] Default CLI transcription to the output-local cache, support refresh
  without a custom path, and keep the default outside retained-run folders.
- [x] Store entries in `transcriptions/v1` and reuse validated legacy
  `speech-v1` entries when the current entry is absent; preserve old files.
- [x] Rebuild normal semantic cues from cached source through the existing compiler.
- [x] Cover changes to content/configuration, refresh, corrupt/oversized data,
  source mutation, Unicode, unknown language, absent times, and failure recovery.
- [x] Document commands, retention, compatibility, and privacy conventions.

## Verification and acceptance

Run `.venv/bin/python -m pytest tests/test_speech_cache.py tests/test_rerun_cli.py`.
Changing templates or moving identical media must cause zero extra adapter calls.
Content, backend/model/language, compatibility, or installed runtime changes must
miss; forced refresh must call recognition. Cache survives renderer failure.
Default transcription, subtitle exports, and real clips share the output-local
cache; custom paths replace it, and transcription-free modes create none.
No test downloads or initializes a model.

## Commit and pull-request plan

Use the package branch and shared draft PR against `main`. Suggested commit:
`feat: reuse source speech across subtitle runs`, including focused tests.
Run the full hermetic suite, Ruff, Pyright, compileall, and CLI help before
delivery. Follow the package's explicit approval and final pre-PR status rules.
