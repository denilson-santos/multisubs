# Consolidate tests and documentation

Status: In review

Depends on: [Plans 0–3](README.md#plans-and-progress).

## Objective

Leave a smaller, intention-revealing test suite and concise documentation with
one source of truth per fact after the structural refactors stabilize.

## Scope

Included: all tests, fixtures, scripts used only for verification, `AGENTS.md`,
`README.md`, and current `docs/*.md` outside completed plan histories; update
the plan catalog only for this active refactor.

Excluded: weakening external-boundary evidence, changing product scope,
rewriting any previously completed plan or dashboard, or introducing
coverage/test-management dependencies.

## Decisions and implementation

- Build a contract-to-test inventory before deleting anything. Merge cases only
  when setup, action, boundary, and assertion intent are the same; parameterize
  stable matrices and keep regression names that explain past failures.
- Keep related animation and word-highlight contracts together in
  `test_animation.py`, as requested. Share a fixture only when at least two
  domains need the same contract; avoid a global fixture or helper dumping
  ground.
- README owns installation, recipes, options, outputs, and limitations. PRD owns
  outcomes and acceptance. Architecture owns current boundaries/contracts.
  Conventions own reusable rules. Delivery owns release operations. Plans own
  decisions and historical evidence.
- Preserve completed plan records unchanged. Remove duplication only from
  current user, architecture, and engineering guidance, keeping one clear
  source for each contract.
- Count active guidance separately from historical plans. The baseline for
  `AGENTS.md`, `README.md`, `docs/prd.md`, `docs/architecture.md`,
  `docs/conventions.md`, and `docs/delivery.md` is 27,448 words; keep this set
  at or below 24,000 without removing required safety, licensing, command, or
  compatibility information.

The repository-wide Markdown total is not an acceptance threshold because it
includes completed plan history that must remain untouched.

## Tasks and verification

- [x] Audit every removed or consolidated test against its surviving contract;
  record deletions and retained word-highlight coverage here.
- [x] Consolidate repeated assertions and remove only the named duplicate cases;
  leave unrelated test files and fixtures unchanged.
- [x] Shorten current guidance while preserving all previously existing plan
  files and dashboards unchanged.
- [x] Check CLI help/README alignment, changed Markdown links and anchors, the
  active plan catalog row, active-guidance word count, and repository diff.

### Test consolidation record

- Removed the nine-case `_ass_alignment_for_position` unit test; serialized
  placement tests retain the private Alignment-code contract.
- Removed the weaker built-in placement/font-size test; the sixteen-template
  exact-baseline test covers typography, layout, and animation together.
- Removed the no-word-timing fallback test; the multilingual fallback
  regression also checks the retained source text and diagnostic reason.
- Removed the duplicate translation assertion from the typed CLI-request test;
  the animation phase matrix still verifies translation rejection.
- Moved the invalid sparse-template case into the broader resource-corruption
  matrix, and kept direct parser rejection coverage for removed
  `--subtitle-template`.
- Folded the word-bounce settle assertion into the parameterized word-motion
  test; cue-emphasis settling remains covered by its cue matrix.
- Moved the former `test_karaoke.py` coverage into `test_animation.py`:
  allocation, lossless fragment mapping, highlight artifacts, and real libass
  color transitions now live with the related phase and motion tests. No test
  coverage was discarded.

Run:

~~~
.venv/bin/python -m compileall multisubs
.venv/bin/multisubs --help
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
.venv/bin/python -m pyright
.venv/bin/python -m pytest
.venv/bin/python -m pytest -m integration tests/test_preview_integration.py tests/test_integration.py tests/test_multilingual_integration.py
git diff --check
~~~

## Delivery

Included on the shared branch: `refactor/simplify-codebase`.
Suggested commits: `test: consolidate behavior-focused coverage` and
`docs: remove duplicated project guidance`; these are commits within the
shared refactor, not a separate pull request.
Use the standard plan status and explicit Git delivery approval lifecycle.

## Acceptance criteria

- Every removed test names an equivalent surviving case or a removed contract;
  no stale skip, xfail, fixture, import, or script remains.
- The default suite stays hermetic and the opt-in suites keep their current
  FFmpeg/libass and multilingual evidence.
- The six active guidance files total at most 24,000 words; changed relative
  links resolve; completed plans and dashboards are unchanged; current behavior
  is stated once in the appropriate document.
- README commands match `multisubs --help`; architecture matches actual module
  ownership; conventions contain rules rather than repeated product prose.
- Full quality checks pass and the final diff contains no generated artifacts or
  unrelated formatting.
