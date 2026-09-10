# Build readable linguistic boundaries with record-timed highlights

Status: In review

Delivery branch: `fix/linguistic-subtitle-cues`.

Depends on: [Plan 1](01-font-coverage-and-metrics.md) and
[Plan 2](02-text-and-alignment-mapping.md).

## Objective and scope

Prevent Japanese/Chinese character alignment from becoming arbitrary timed-cue
cuts while preserving the established timing granularity of each validated
alignment record for word text and word-backdrop effects. Linguistic groups are
boundary guidance, not replacement timing units. For Japanese input aligned one
character per record, the visible highlight therefore advances one character at
a time while cue construction and wrapping still prefer readable lexical units.

Recognize supported sentence/clause punctuation and apply language-appropriate
cue and line boundaries, including texts with no punctuation. Preserve source
text and every original alignment timestamp.

Do not improve ASR spelling, insert inferred punctuation, change the Whisper
model, add a universal minimum effect duration, expose a public segmentation
control, or claim every dictionary decision matches a human editor. Phrase- or
lexical-group highlighting is not part of this correction and requires a
separate product decision if introduced later.

## Revised product decision

The first Plan 3 implementation coupled lexical display groups to effect timing.
That coupling is rejected. A local replay generated before Plan 3 produced no
word-effect fallback for the same character-aligned Japanese material. The
group-timed implementation produced six static fallbacks among fifteen cues
when visual wrapping split inside a lexical group and the resulting fragment
indexes no longer matched the group timing indexes. The segmentation itself had
succeeded, so a static green backdrop was an integration failure rather than a
language or renderer limitation.

The reviewed CapCut example highlights a single Japanese character while
adjacent characters remain in the normal style. A targeted review found a
[Japanese read-along example](https://www.youtube.com/watch?v=9rwkuj27UyE&t=10s)
that advances multi-character phrase chunks, but it is an audiobook-style use
case and does not establish lexical-group highlighting as the expected default
for short-form Japanese captions. This plan therefore preserves record-timed
effects as the compatible, evidence-backed default. Group/phrase highlighting
remains a possible future mode, not an implicit language rule.

## Boundary and effect-unit contract

The selected linguistic route remains uniseg 0.10.1 plus SudachiPy 0.6.11 with
SudachiDict-small 20260723 in mode B for Japanese, and jieba 0.42.1 with its
packaged dictionary/HMM enabled for Chinese. Versions, resource hashes,
installation costs, and offline evidence are in
[Plan 0](00-regressions-and-decisions.md#selected-backends-and-evidence).
Keep one internal adapter; do not expose backend choice as a new CLI flag.

Maintain four distinct concepts throughout cue building and rendering:

1. An original alignment record owns source identity and, when valid, one timed
   effect interval. The public `word` effect name is retained for compatibility;
   an alignment record is not guaranteed to be a lexical word.
2. A linguistic display group references one or more source spans and supplies
   preferred semantic boundaries. It may expose a derived enclosing interval
   for diagnostics, but does not own word-effect timing.
3. A legal visual line-break opportunity comes from Unicode line rules plus
   language tailoring. It can be finer than a linguistic group.
4. A display fragment carries source-record identity through casing and line
   breaks so rendering can reconstruct text and timed effects losslessly.

Raw Sudachi morphemes require presentation grouping: attach auxiliary verbs and
non-independent predicate suffixes to their preceding predicate without
crossing whitespace, punctuation, or significant source pauses. This prevents
avoidable `なかっ`/`た` cue cuts without hardcoding video text. Reconcile all
lexical boundaries with uniseg graphemes, including jieba's split emoji/ZWJ
output. Use an invocation-scoped temporary dictionary cache for jieba and
remove it afterwards; never persist transcript text or use its default shared
host cache. Unknown words, prefix/counter groups, and morphology remain explicit
regression cases.

- Group Japanese and Chinese using lexical boundaries mapped to source spans.
  Other languages preserve available word boundaries and meaningful separators.
  Keep punctuation attached appropriately for display, with no fabricated
  alignment for untimed punctuation.
- Keep the 6s semantic cue target and 0.45s pause threshold. Prefer sentence,
  clause, pause, then linguistic-group boundaries; retain longest fitting
  prefixes only among equivalent legal choices, with existing orphan and line
  balancing.
- Timed cue splits should remain at linguistic-group boundaries whenever a
  fitting alternative exists. An oversized group may be subdivided only at a
  legal visual/grapheme boundary that maps exactly to existing record timing;
  diagnose the subdivision and do not relabel its pieces as lexical words.
- Wrapping should first score complete linguistic groups as preferred line
  units. When the envelope requires a legal line break inside a group, preserve
  every record-to-fragment mapping. That visual split must not disable otherwise
  valid word text or word-backdrop effects.
- Allocate active-word and progressive intervals from the original validated
  alignment records using the existing centisecond conservation and gap rules.
  Never merge or stretch records solely to make a highlight more visible.
- Short records remain short. A 20ms record can quantize to a very brief or
  zero-centisecond state and may not appear in every video frame. Record exact
  timing behavior in tests and documentation; do not invent a minimum duration.
- Static word-effect fallback is allowed only when source/alignment timing or
  record-to-fragment mapping is incomplete, invalid, nonchronological, or unsafe
  for the shaping capability established by Plan 4. A mismatch between visual
  line groups and linguistic groups is not by itself a fallback reason.
- Report segmentation and effect capability separately. Per-cue additive
  diagnostics must identify the effect strategy and a bounded fallback reason;
  aggregate `fallback_cues` counts only cues that actually suppress requested
  word tracks, once per cue.
- Production preview text selection may use linguistic groups to choose a
  representative fitting cue. Simulated effect timing must use distinct
  script-appropriate display units: grapheme-like units for character-aligned
  CJK samples and whitespace/source-word units where those are available. It
  must remain labeled simulated and must not imply real WhisperX timestamps.

## Ordered reimplementation tasks

The current branch contained a useful segmentation foundation, but its
group-timed effect integration was a rejected spike. The following checkboxes
record the revised implementation and its verification evidence.

- [x] Retain and review the `DisplayGroup` internal model, lazy Sudachi/jieba
  providers, Unicode punctuation classes, source-span provenance, cache
  cleanup, and bounded/nonmonotonic boundary search. Remove fields or APIs whose
  only purpose was treating a group as an effect-timing word.
- [x] Keep linguistic groups in `build_subtitle_cues`,
  `_build_cues_from_words`, `_find_best_cue_break`, and `_append_words_cue` as
  preferred timed-cue boundaries. Preserve unpunctuated-stream behavior,
  significant pauses, duration/width limits, and diagnosed emergency splits.
- [x] Thread linguistic boundary preferences into `split_words_for_layout`,
  `_text_units`, `_partition_text_units`, and `_display_boundary_priority` so a
  fitting group boundary wins over an avoidable intra-group line break.
- [x] Decouple `prepare_karaoke_cues` and ASS interval allocation from
  `_display_groups`. Build durations and active intervals from original valid
  records, while fragments retain explicit record indexes across generated line
  breaks and length-changing display casing.
- [x] Remove the strict group-index equality failure exposed by an intra-group
  line wrap. Validate instead that each required original record has one
  ordered, reconstructable timed identity; separators and untimed punctuation
  remain display-only fragments.
- [x] Preserve active-word/progressive gap semantics, zero-centisecond behavior,
  interval containment, independent text/backdrop modes, and cue/word phase
  normalization. Count a fallback once when both word tracks are suppressed.
- [x] Separate segmentation metadata from effect diagnostics. Keep backend,
  alignment granularity, group count, and emergency subdivisions, and add a
  bounded per-cue effect strategy/status/reason whose aggregate agrees with
  `fallback_cues`. Required schema-3 fields and original `words` remain intact.
- [x] Revise preview preparation so linguistic grouping chooses representative
  content while simulated effect units mirror likely alignment granularity.
  Remove the assumption that one tokenizer must own both semantic grouping and
  animation timing; Plan 4 will apply the shaping-capability decision.
- [x] Replace tests that require complete-group highlighting with record-timed
  assertions. Add synthetic regressions for group-internal line wraps, the six
  observed fallback shapes, Japanese/Chinese character alignment, ordinary
  whitespace-delimited words, invalid mappings, and independent word tracks.
- [x] Re-run the 250-/1000-record benchmarks and all focused, integration,
  packaging, and quality gates. Update current README, PRD, architecture, and
  conventions only after the revised implementation matches this contract.

## Verification and acceptance

Fixtures should include short Japanese clauses containing the reported lexical
units and unrelated examples so success cannot come from a video-specific
dictionary. Under widths/durations that permit complete units, `なかった`,
`デフォルト`, `使用`, and `装置` must not straddle timed cues. A separate narrow
envelope must exercise the documented emergency cue-split policy.

For a character-aligned `装置は` cue, segmentation may derive `装置` as one
linguistic group, but the timed effect sequence remains `装`, `置`, `は`. At a
sample inside the first record only `装` uses the active word text/backdrop
style. Equivalent assertions apply to progressive timing and Chinese
character-aligned input. A normal whitespace-aligned language continues to
advance by its original word records.

Construct a synthetic equivalent of the fifteen-cue local replay. It must
retain requested word effects for all cues, including the six layouts that
previously became static when line wrapping split `ペイン`, `チャクラ`,
`ナナト`, `装置`, or `ナガト`. Avoidable intra-group line breaks fail layout
acceptance; an unavoidable legal intra-group break is accepted only when text,
record indexes, and timed effects remain complete. Do not commit user video,
transcript, generated frames, or absolute local paths.

Cover punctuation-free Japanese, simplified/traditional Chinese, Korean with
spaces, Japanese/Latin/digits, quote pairs, combining clusters, real pauses,
missing alignments, repeated records, 20ms intervals, length-changing casing,
and both independent active/progressive tracks. Assert exact source
reconstruction, unchanged raw times, chronological record intervals, legal cue
boundaries, no duplicated/missing highlight identity, and centisecond
conservation. No assertion may require a fabricated duration or one visible
video frame for an interval shorter than the frame cadence.

Use a pinned covering font and synthetic timeline to render frames around
record transitions, gaps, cue cuts, and group-internal visual wraps. Compare the
pre-Plan3 and revised central-subtitle replays: fallback count returns to zero
for complete aligned input, layouts remain stable, and the highlight advances
by record. Speech accuracy and linguistic naturalness beyond the selected
boundary rules require separate human review.

```sh
python -m pytest tests/test_text_segmentation.py tests/test_multilingual_regressions.py tests/test_wrapping.py tests/test_transcriber.py tests/test_karaoke.py tests/test_animation.py tests/test_preview.py tests/test_ass.py
python -m pytest -m integration tests/test_karaoke.py tests/test_integration.py tests/test_multilingual_integration.py
python -m pytest
python -m compileall multisubs
multisubs --help
python -m ruff format --check .
python -m ruff check .
python -m pyright
git diff --check
```

Benchmark synthetic 250- and 1000-record unpunctuated streams with narrow and
multiline envelopes. Record dictionary initialization, time, peak memory,
candidate count, group count, alignment-record effect count, and ASS event
count against the same baseline. Require bounded growth and no per-frame event
generation. Investigate greater-than-2x same-host regressions rather than
hiding them with a timeout.

## Rework evidence and retained foundation

The first implementation on `fix/linguistic-subtitle-cues` established
immutable display groups, lazy invocation-scoped Sudachi/jieba providers,
Unicode-aware punctuation, legal emergency subdivision diagnostics, shared
preview grouping, and bounded candidate search. Its recorded 250-/1000-record
benchmarks and successful segmentation tests remain useful baseline evidence.

That implementation also fed group-derived intervals into word effects. Local
render review showed this assumption can suppress both requested word tracks
when a legal visual line break duplicates a group identity across lines. The
resulting static green backdrop is the defect that triggers this plan revision.
The earlier passing test totals do not certify the revised acceptance criteria;
all affected tests and verification commands must be rerun after rework.

The revised implementation was verified against the retained fifteen-cue
Japanese replay: all fifteen cues keep alignment-record effects active and the
aggregate `fallback_cues` value is zero. The synthetic benchmark below uses
unpunctuated `装置は` streams with 20px text, a 220px width, and two multiline
height envelopes. `candidate_boundaries` counts the source record boundaries
presented to the bounded search; peak memory is Python allocation traced by
`tracemalloc`, not total process RSS. Segmentation time includes the
invocation-scoped dictionary initialization.

| Records | Envelope | Segmentation | Layout/effects | Peak Python | Candidate boundaries | Groups | Effect units | ASS events | Fallback cues |
| ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 250 | 220x80px | 109.5ms | 2.37s | 1.49MiB | 250 | 167 | 250 | 732 | 0 |
| 250 | 220x160px | 105.3ms | 1.98s | 1.13MiB | 250 | 167 | 250 | 740 | 0 |
| 1000 | 220x80px | 687.0ms | 15.59s | 4.20MiB | 1000 | 667 | 1000 | 2928 | 0 |
| 1000 | 220x160px | 684.1ms | 11.01s | 4.13MiB | 1000 | 667 | 1000 | 2958 | 0 |

Large partitions use bounded line-fill selection above 32 display units;
smaller partitions retain the exact global scoring path. The benchmark emits
no per-frame events and preserves one effect unit per source record.

## Documentation and delivery

Update README cue readability, alignment-record highlight behavior, short-frame
limitation, and fallback diagnostics; PRD FR-7/FR-17 and acceptance criteria;
architecture cue/group/line/effect mapping, preview simulation, and JSON; and
conventions for Unicode boundaries and timing identity. Explicitly state that a
WhisperX record is not necessarily a lexical word while preserving it as the
default effect unit. Do not rewrite completed plan history.

Suggested branch: `fix/linguistic-subtitle-cues`.
Suggested commits: `fix: preserve record-timed word effects`,
`fix: prefer linguistic subtitle boundaries`,
`fix: report timed-effect fallbacks`,
`docs: distinguish subtitle boundaries from highlight units`.
Draft PR title: `fix: separate linguistic boundaries from timed highlights`.
Follow the [shared delivery lifecycle](README.md#delivery-strategy).

Risks include dictionary disagreement on compounds, alignment granularity that
varies by model/language, very short records, installation cost, malformed
offsets, and oversized groups. Freeze dependency/data versions, state frame-rate
limits, and preserve lossless static fallback only for genuinely invalid or
unsupported mappings. Recovery is a focused revert with source records retained
for regeneration; existing ASS/video files do not change automatically.
