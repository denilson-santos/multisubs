# Build readable linguistic groups and derive their timing

Status: Planned

Depends on: [Plan 1](01-font-coverage-and-metrics.md) and
[Plan 2](02-text-and-alignment-mapping.md).

## Objective and scope

Prevent Japanese/Chinese character alignment from becoming arbitrary cue cuts
and excessively fragmented word effects. Recognize supported sentence/clause
punctuation and apply language-appropriate line boundaries, including texts
with no punctuation. Preserve source text and original alignment timestamps.

Do not improve ASR spelling, insert inferred punctuation into the transcript,
change the Whisper model, add a universal minimum reading duration, or pretend
that every segmentation decision matches a human editor. No new language codes
or public segmentation controls are required for this package.

## Boundary and timing contract

The selected route is uniseg 0.10.1 plus SudachiPy 0.6.11 with
SudachiDict-small 20260723 in mode B for Japanese, and jieba 0.42.1 with its
packaged dictionary/HMM enabled for Chinese. Versions, resource hashes,
installation costs, and offline evidence are in
[Plan 0](00-regressions-and-decisions.md#selected-backends-and-evidence).
Keep one internal adapter; do not expose backend choice as a new CLI flag.

Raw Sudachi morphemes require presentation grouping: attach auxiliary verbs
and non-independent predicate suffixes to their preceding predicate without
crossing whitespace, punctuation, or significant source pauses. This prevents
`なかっ`/`た` cuts without hardcoding video text. Reconcile all lexical boundaries
with uniseg graphemes, including jieba's split emoji/ZWJ output. Use an
invocation-scoped temporary dictionary cache for jieba and remove it afterwards;
never persist transcript text or use its default shared host cache. Unknown
words, prefix/counter groups, and morphology remain explicit regression cases.

Maintain three distinct units: original alignment records, derived linguistic
display groups, and legal visual line-break opportunities. Word boundaries,
line boundaries, and grapheme boundaries are not interchangeable. Use the
selected offline adapter from Plan 0 with pinned Unicode/dictionary versions.

- Group Japanese and Chinese using lexical boundaries mapped to source spans.
  Other languages preserve available word boundaries and meaningful separators.
  Keep punctuation attached appropriately for display, with no fabricated
  alignment for untimed punctuation.
- A group's interval is derived from its covered timed records: start at the
  first valid covered start, end at the last valid covered end, subject to
  chronology validation. Preserve all individual records unchanged. If the
  mapping is not complete or a group crosses a significant source pause, split
  at a valid boundary or use the static fallback; never stretch speech times.
- Active-word intervals use group end capped by the next group start;
  progressive activation uses group starts with the existing cue-relative
  conservation rules. Existing animation phase shortening remains unchanged.
- Short groups remain short. A 20ms record is not itself a reason to invent a
  100ms interval. Grouping may remove character-level flicker, but the product
  cannot guarantee every short highlight appears at every video frame rate.
- Keep the 6s semantic cue target and 0.45s pause threshold. Prefer sentence,
  clause, pause, then lexical group boundaries; retain longest fitting prefixes
  only among equivalent legal choices, with existing orphan/line balancing.
- Respect Unicode line-breaking prohibitions and language tailoring, including
  opening/closing punctuation, Japanese small kana/prolonged marks where
  applicable, nonbreaking spaces, combining clusters, and Latin words embedded
  in CJK. Do not forbid every intra-word CJK visual line break.
- Timed cue splits should remain at linguistic group boundaries when feasible.
  An oversized CJK group may be split only at a legal visual/grapheme boundary
  that also maps exactly to existing source timing boundaries; report this
  emergency subdivision and do not label its pieces whole lexical words.
  If no such boundary exists, preserve the documented indivisible-token
  overflow behavior and diagnose it; never truncate or invent timestamps.

## Ordered implementation tasks

- [ ] Add a `DisplayGroup`-style internal model with source span references,
  group identity, source/display text mapping, timing provenance, and boundary
  class. Keep original `words` separate in JSON and runtime preparation.
- [ ] Integrate the Plan 0 segmentation backend in the shared adapter introduced
  by Plan 2. Bound work by cue/window size, cache dictionary objects per run,
  load locally, and avoid import-time heavyweight initialization.
- [ ] Add sentence/clause recognition for `。！？`, `、`, Arabic `؟،؛`, and
  relevant Indic endings, including trailing closing quotes/brackets. Preserve
  periods in decimals/abbreviations and do not treat every Unicode punctuation
  category as a sentence break.
- [ ] Update `build_subtitle_cues`, `_build_cues_from_words`,
  `_find_best_cue_break`, and `_append_words_cue` to retain source hints and
  use group boundaries. Ensure unpunctuated speech still has lexical candidates
  and width/duration constraints rather than waiting indefinitely for `。`.
- [ ] Update `split_words_for_layout`, `_text_units`, `_partition_text_units`,
  and `_display_boundary_priority` in `wrapping.py` to consume legal group/line
  boundary sets and the per-cue real font metrics from Plan 1.
- [ ] Review the current early stop after the first overflowing prefix. Shaping
  and contextual widths are not universally monotonic. Keep that optimization
  only where its assumption is established; otherwise use bounded candidate
  evaluation/dynamic programming and test a nonmonotonic measurement fixture.
- [ ] Feed derived groups into `prepare_karaoke_cues` and the ASS interval
  allocators. Replace the assumption that each displayed timing unit maps to
  exactly one original word index with an explicit group-to-record map.
- [ ] Preserve gap semantics, zero-centisecond behavior, interval containment,
  both independent word modes, and cue/word phase normalization. Count fallback
  once per cue even when multiple tracks are affected.
- [ ] Add additive per-cue segmentation metadata: strategy/backend version,
  alignment granularity, group count, emergency subdivisions, and fallback
  reason/count. Required schema-3 fields and original `words` remain intact.
- [ ] Reuse grouping in preview text selection; Plan 4 completes representative
  highlighting and simulated timing. Avoid a second regex tokenization path.
- [ ] Remove Plan 0 segmentation/timing `xfail` marks and document boundaries
  that remain genuinely ambiguous rather than hardcoding the reported text.

## Verification and acceptance

Fixtures should include short Japanese clauses containing the reported lexical
units and unrelated examples so success cannot come from a video-specific
dictionary. Under widths/durations that permit the complete units,
`なかった`, `デフォルト`, and `使用` must not straddle timed cues. Test a
separate narrow-envelope case that exercises the documented emergency policy.

Cover punctuation-free Japanese, simplified/traditional Chinese, Korean with
spaces, Japanese/Latin/digits, quote pairs, combining clusters, real pauses,
missing alignments, repeated words, 20ms character times, and both independent
active/progressive tracks. Assert exact source reconstruction, unchanged raw
times, derived interval containment, no simultaneous active groups, and
centisecond conservation. No test should demand a fabricated minimum duration.

Use a pinned font and synthetic speech timeline to render frames immediately
before/after group transitions and inside gaps. Highlight the intended complete
group without changing layout. Compare the reported central-subtitle replay
before/after and inspect cue transition contexts, not only isolated stills.
Speech accuracy and naturalness beyond the selected linguistic rules require
separate human language review; do not call synthetic timing speech validation.

```sh
python -m pytest tests/test_wrapping.py tests/test_transcriber.py tests/test_karaoke.py tests/test_animation.py tests/test_preview.py tests/test_ass.py
python -m pytest -m integration tests/test_karaoke.py tests/test_integration.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Add the adapter/group test modules to focused commands. Benchmark synthetic
250- and 1000-record unpunctuated streams with narrow/multiline envelopes;
record time, peak memory, candidate count, and event count against baseline.
Require bounded growth and no per-frame event generation. Investigate any
greater-than-2× regression on the same host; do not disguise it with a larger
arbitrary timeout. First dictionary load is measured separately.

## Documentation and delivery

Update README cue readability and word-effect limitations, PRD FR-7/FR-17 and
their acceptance criteria, architecture cue/group/line mapping and JSON,
conventions for Unicode boundaries and derived timing. Explicitly supersede
the prior assumption that a WhisperX record is always a complete word; do not
rewrite completed plan history.

Suggested branch: `fix/linguistic-subtitle-cues`.
Suggested commits: `fix: group aligned characters into display words`,
`fix: select language-aware subtitle boundaries`,
`fix: derive word effects from linguistic groups`,
`docs: document multilingual cue and timing rules`.
Draft PR title: `fix: preserve linguistic units in subtitle cues and effects`.
Follow the [shared delivery lifecycle](README.md#delivery-strategy).

Risks include dictionary disagreement on compounds, installation cost,
unpunctuated ASR, malformed offsets, and oversize words. Freeze dependency/data
versions, state limits, and preserve lossless fallback. Recovery is a focused
revert with source records retained for regeneration; existing ASS/video files
do not change automatically.
