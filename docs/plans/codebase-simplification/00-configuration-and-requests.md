# Simplify configuration and request assembly

Status: Done

Depends on: the current CLI, template, and configuration contracts in
`origin/main` at `6b64077`.

## Objective

Make input parsing and configuration resolution readable as a sequence of
small decisions while producing the same typed requests and diagnostics.

## Scope

Included:

- `multisubs/cli.py`, `config.py`, `models.py`, `templates.py`, and
  `custom_templates.py`.
- Parser construction, template/default/CLI precedence, typed validation, and
  early preview/translation/animation conflicts.
- Focused consolidation in `test_cli.py`, `test_config.py`,
  `test_templates.py`, and `test_custom_templates.py`.

Excluded:

- New flags, defaults, template fields, dependencies, or configuration files.
- Changes to rendering, cue construction, persisted JSON, or error wording
  unless a characterization test proves wording is private.

## Decisions and implementation

- Split `build_parser()` into argument-group builders without inventing a
  declarative CLI framework.
- Replace the large `validate_subtitle_config()` branch tree with private
  validators/builders for typography, backdrops, layout, and animation. Keep
  one public compatibility entry point and reject overrides at the same stage.
- Centralize each option/animation choice and default once. Template expansion
  must consume those values rather than maintain a parallel schema model.
- Separate JSON resource decoding, structural validation, semantic expansion,
  and catalog selection. Keep bounded custom-template I/O and contextual
  `TemplateError`/`ValidationError` causes.
- Remove compatibility adapters only when repository references and documented
  public use both prove they are obsolete; otherwise keep a thin tested facade.

## Tasks and verification

- [x] Record parser/help, all 16 built-in configurations, custom inheritance,
  and representative invalid requests before changing structure. The current
  help/actions match `origin/main`; 13 valid/invalid configuration comparisons
  match the baseline; the existing catalog suite covers all built-ins.
- [x] Decompose parser construction and semantic configuration assembly into
  small option-group, layout, style, and animation helpers.
- [x] Decompose template-resource parsing while preserving contextual errors.
- [x] Remove only audited duplicate assertions; retain validation timing and
  template-corruption coverage. The case-by-case record is in Plan 4.
- [x] Confirm that module ownership did not change, so no ownership-document
  update was required; current guidance is covered in Plan 4.

Run:

~~~
.venv/bin/python -m pytest tests/test_cli.py tests/test_config.py tests/test_templates.py tests/test_custom_templates.py
.venv/bin/python -m ruff check multisubs tests
.venv/bin/python -m pyright
.venv/bin/python -m pytest
~~~

## Commit and pull-request plan

Merged in [PR #85](https://github.com/denilson-santos/multisubs/pull/85):
`refactor: simplify codebase, tests, and documentation`.

Suggested commits:

1. `test: characterize configuration and request contracts`
2. `refactor: simplify request and configuration assembly`
3. `refactor: clarify template loading boundaries`

## Acceptance criteria

- Existing invocations build equivalent typed requests and parser help exposes
  the same options, choices, defaults, and exit behavior.
- Built-in and custom template precedence, bounded loading, and error types are
  unchanged; all packaged resources resolve to equivalent immutable configs.
- `build_parser()` and `validate_subtitle_config()` no longer contain multiple
  unrelated construction phases in one function.
- No test removal leaves a CLI, precedence, validation, or corrupted-resource
  branch without direct coverage.
