# WP-Bench WordPress Coverage Expansion Design

- Status: Approved
- Date: 2026-08-16; revised 2026-08-22
- Workstream: 3 of 3
- Depends on: benchmark-integrity schema, provenance, and selection contracts
- Benefits from: reporting dimension and completeness support
- Contract independence: canonical suite, artifact, and runtime capabilities
  do not depend on a transient runner model, legacy result shape, or PR order

## Decision summary

WP-Bench will add a separate, versioned `wp-projects-v1` suite containing 50
realistic WordPress project tasks. The existing 185-test `wp-core-v1` suite
remains unchanged so historical comparisons are not silently redefined.
Together the repository will contain 235 execution tests, but the two suites
will report separate scores; this workstream does not manufacture a composite
headline.

The expansion uses three artifact kinds—PHP snippets, plugin file bundles, and
theme file bundles—and treats lifecycle, browser/editor behavior, and
multisite as execution plans/profiles rather than inventing a new response
format for every runtime. Delivery is split into small capability and dataset
milestones so each new runtime surface is proven by canaries before broad task
authoring.

## Baseline census (non-normative)

The observations in this section are frozen to evidence commit
`77c98d61b73c6341db2fa5ccb15212867b825eb5` (abbreviated `77c98d6` below).
They motivate the expansion but are not delivery contracts; the versioned
suite and adapter rules below remain authoritative if producer code changes.
At that baseline, the corpus measures isolated PHP implementation much more
than realistic WordPress delivery:

- `wp-core-v1` contains 185 execution tests across 29 category files.
- All 185 omit `artifact_kind` and therefore load as `php_snippet`.
- All use inline `reference_solution`; none uses `reference_files`.
- Difficulty is 49 basic, 125 intermediate, 6 hard, and 5 legacy advanced.
- Of 201 runtime assertions, 198 are `custom_assertion` and 3 are
  `rest_response`; 169 tasks have one assertion.
- Only 17 tests carry authored `exploit_solutions`.
- Gutenberg coverage exercises PHP APIs and serialized markup, but no model
  JavaScript runs in the editor.
- No dataset task verifies real activation, later-request loading,
  deactivation, uninstall, theme switching, or multisite behavior.

There is a partial multi-file plugin path:

- `python/wp_bench/artifacts.py::parse_artifact()` validates
  `wp_plugin_files` with 20-file, 256 KiB-per-file, and 1 MiB-total limits.
- `ExecutionTest` already carries `artifact_kind` and `reference_files`.
- Reference mode knows how to use plugin reference files.
- `runtime/src/class-artifact-installer.php` writes a plugin bundle and
  directly includes its main file.
- `runtime/src/class-verifier.php` asserts against the loaded plugin and
  removes the directory.

That baseline path is not yet an end-to-end dataset capability. Its Python tests
fake `execute_artifact()`, the dataset validator assumes every task has an
inline PHP reference, static analysis loses file identity, and the runtime
does not exercise actual plugin lifecycle or a fresh WordPress bootstrap.
The configured `ArtifactKind` union advertises `block_plugin`, `js_module`,
`wp_theme_files`, and `patch`, but the parser rejects them.

## Goals

1. Add exactly 50 tasks covering multi-file plugins, plugin lifecycle,
   block/editor JavaScript, classic and block themes, and multisite.
2. Keep `wp-core-v1` immutable and release the new tasks as
   `wp-projects-v1` with its own content fingerprint and suite manifest.
3. Make observable WordPress behavior the scoring authority; static checks
   remain diagnostics except genuine forbidden-policy violations.
4. Require every advertised artifact kind to have parsing, installation,
   execution, reference-mode, export/import, cleanup, and negative-control
   support.
5. Use behavioral prompts that do not reveal checker mechanics or incidental
   implementation details.
6. Give every new task pinned WordPress evidence, a passing reference artifact,
   and artifact-aware known-wrong controls.
7. Exercise lifecycle phases in fresh WordPress bootstraps and clean persistent
   state/files even after failure or timeout.
8. Run browser/editor and multisite checks in pinned, explicit runtime profiles
   with no live network dependency.
9. Add dataset quality gates for artifact mix, difficulty balance, assertion
   coverage, and negative-control coverage.

## Non-goals

- Full repositories, arbitrary source patches, or miniature production apps.
- Composer/npm dependency installation or model-supplied build scripts.
- Pixel-perfect screenshot grading.
- Third-party ecosystems such as WooCommerce.
- Subdomain multisite in version 1; the initial network is subdirectory-based.
- A WordPress/PHP version matrix; the initial target is the canonical
  WordPress 7.0/PHP 8.2 runtime.
- Rewriting or relabeling the existing `wp-core-v1` tasks.
- Defining a composite score across `wp-core-v1` and `wp-projects-v1`.

## Alternatives considered

### Add only plugin-file tasks with the evidence-baseline runner

This yields a quick multi-file increment but cannot honestly cover lifecycle,
themes, editor JavaScript, or multisite. It is useful as the first milestone,
not as the complete design.

### Implement an independent artifact runner for every advertised kind

Separate `block_plugin`, `js_module`, theme, and multisite runners make each
branch explicit but duplicate file safety, cleanup, reference handling, and
negative-control logic. This is rejected.

### Shared file artifacts plus execution plans and profiles

Use artifact kinds only where installation semantics differ. Block plugins are
plugin file bundles; editor behavior is an execution engine; multisite is a
runtime profile; activation/deactivation/uninstall are lifecycle plans. This
is the selected approach.

## Suite boundary and manifest

Create:

```text
datasets/suites/wp-projects-v1/
  suite.json
  execution/
    plugin-files.json
    plugin-lifecycle.json
    gb-block-artifacts.json
    themes.json
    multisite.json
  qa/
    negative-controls.json
```

`suite.json` declares:

- suite ID and semantic content version;
- execution schema version `2.0`;
- official WordPress/PHP/runtime profile requirements;
- exact task-family, artifact, and difficulty targets;
- ordered smoke strata:
  `coverage_family,artifact_kind,difficulty,runtime_profile`;
- source/review policy;
- scoring and eligibility profile references.

Every execution category document also declares `"schema_version": "2.0"`
and the suite ID; both must match `suite.json`. Existing documents without a
schema version load as schema 1.0. The document's existing `version` field
continues to mean content revision, not schema version.

The suite manifest and normalized schema-2 rows are the canonical descriptor
source regardless of which fields a transient `ExecutionTest` model or legacy
result writer exposes. Each source adapter must produce the declared value,
emit null only where the canonical contract permits it, or reject the source
as not representable. Removing `difficulty`, artifact metadata, or selection
fields from a legacy producer cannot remove them from this suite contract.

The local loader and Hugging Face export preserve the suite manifest identity.
Every exported row carries the canonical compatibility field `suite` plus
`suite_id`, and those two values must be equal. It also carries
`suite_content_version`,
`execution_schema_version`, `suite_manifest_sha256`, and canonical
`suite_manifest_json`. All rows for one suite must agree; the Hub loader
reconstructs and verifies the manifest before loading tests. This makes local
and Hub catalog inputs identical without relying on mutable external metadata;
with identical remaining provenance/runtime identities, WS1.3 then produces
identical benchmark contract fingerprints.

The schema-2 validator maps that versioned raw envelope through the benchmark
integrity design's exact injected `SuitePolicyResolver(*, suite_id,
suite_manifest_json, suite_manifest_sha256)` callable to a
`SuiteDescriptorPolicy`. WS1.1 consumes that policy and never reaches into raw
manifest keys. The raw manifest schema
therefore remains WS3.0-owned without becoming a merge-order dependency: a
present manifest unsupported by the available validator fails closed, while an
absent manifest uses WS1.1's schema-1 built-in policy.
`wp-core-v1` remains schema 1 and accepts its historical labels. Schema-2
tasks use only `basic`, `intermediate`, and `hard`; the five existing
`advanced` records are not mutated.

Reports display the suites separately. A future composite requires its own
versioned weighting policy and is outside this specification.

## Exact target coverage

The new suite contains exactly 50 tasks:

| Family | Count | Required composition |
|---|---:|---|
| Multi-file plugin integration | 12 | Includes, classes, settings/admin, REST, dependency and registration wiring. |
| Plugin lifecycle | 8 | Activation, later-request bootstrap, deactivation, uninstall, migration, and cleanup. |
| Block/editor artifacts | 12 | Six metadata/server-registration tasks and six browser/editor tasks. |
| Themes | 10 | Four classic-theme and six block-theme tasks. |
| Multisite | 8 | Four API snippets and four multi-file/network-plugin tasks. |

Artifact mix:

- 36 `wp_plugin_files`;
- 10 `wp_theme_files`;
- 4 `php_snippet`.

Difficulty mix:

- 10 basic;
- 30 intermediate;
- 10 hard.

Each family contains at least one basic and one hard task. No family is added
to the suite release until all its reference and negative controls pass in the
real target runtime.

Every new task must:

- observe at least two materially different fixtures, states, or inputs;
- include a happy-path observation and an edge, absence, cleanup, or permission
  observation;
- use at least two artifact-aware negative controls: one omission/trivial case
  and one plausible family-specific mistake;
- avoid live network, uncontrolled time, external providers, and unowned random
  state;
- clean every persistent fixture it creates;
- use a prompt that describes the desired behavior and artifact, not the
  assertion code, exact helper sequence, or arbitrary wrapper name.

An atomic API behavior may use one runtime assertion only when that assertion
directly and completely proves both required observations; the reviewer must
explain this in `expected_behavior`.

## Dataset schema 2.0

The following valid JSON fragment shows the schema-2 fields added to a normal
execution task; the unchanged `id`, prompt, requirements, and static-check
fields are omitted from this illustrative fragment:

```json
{
  "artifact_kind": "wp_plugin_files",
  "execution": {
    "profile": "single_site",
    "plan": "plugin_activate_deactivate",
    "activation_scope": "site",
    "engines": ["wordpress_php"]
  },
  "runtime_checks": {
    "setup": "delete_option( 'wpbp_state' );",
    "phases": {
      "after_activate": {
        "assertions": [
          {
            "id": "state-created",
            "type": "option_value",
            "target": "wpbp_state",
            "expected": "active",
            "description": "Activation creates the owned state"
          }
        ]
      },
      "after_deactivate": {
        "assertions": [
          {
            "id": "state-removed",
            "type": "custom_assertion",
            "code": "return false === get_option( 'wpbp_state', false );",
            "description": "Deactivation removes the owned state"
          }
        ]
      }
    },
    "teardown": "delete_option( 'wpbp_state' );"
  },
  "reference_files": {
    "wpbp-lifecycle.php": "<?php\n/* Plugin Name: WP-Bench Lifecycle */\nregister_activation_hook( __FILE__, function () { update_option( 'wpbp_state', 'active' ); } );\nregister_deactivation_hook( __FILE__, function () { delete_option( 'wpbp_state' ); } );"
  },
  "metadata": {
    "coverage": {
      "family": "plugin_lifecycle",
      "surface": "deactivation",
      "persistence": "database"
    }
  }
}
```

Maintainer negative controls live in
`qa/negative-controls.json`, keyed against immutable task definitions:

```json
{
  "test_id": "e-plugin-lifecycle-001",
  "benchmark_definition_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "verification_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
  "controls": [
    {
      "id": "missing-cleanup",
      "rationale": "Leaves the persistent state that deactivation must remove.",
      "expected_failure": {
        "stage": "after_deactivate",
        "assertion_ids": ["state-removed"]
      },
      "artifact": {
        "kind": "wp_plugin_files",
        "files": {
          "wpbp-lifecycle.php": "<?php\n/* Plugin Name: WP-Bench Lifecycle */\nregister_activation_hook( __FILE__, function () { update_option( 'wpbp_state', 'active' ); } );"
        }
      }
    },
    {
      "id": "no-lifecycle-hooks",
      "rationale": "Loads as a plugin but never creates or removes the required state.",
      "expected_failure": {
        "stage": "after_activate",
        "assertion_ids": ["state-created"]
      },
      "artifact": {
        "kind": "wp_plugin_files",
        "files": {
          "wpbp-lifecycle.php": "<?php\n/* Plugin Name: WP-Bench Lifecycle */"
        }
      }
    }
  ]
}
```

Rules:

- `reference_solution` is required for `php_snippet`.
- `reference_files` is required for file artifacts.
- The two reference forms are mutually exclusive.
- `test_function` is normally absent for file artifacts; observable WordPress
  hooks, state, files, registries, and output are the contract.
- Legacy flat `runtime_checks.assertions` remains valid and maps to the snippet
  execution phase or legacy plugin-load phase.
- The versioned QA sidecar replaces inline `exploit_solutions` for schema 2.
  It is excluded from public Parquet and bound to both benchmark-definition
  and verification digests so stale controls fail preflight.
- `datasets/export_dataset.py` and both dataset loaders preserve schema,
  execution, artifact, reference, suite, and provenance fields consistently.
- The loader projects `execution.profile` to canonical `runtime_profile`,
  `metadata.coverage.family` to `coverage_family`, and metadata/suite release
  fields to canonical `release_focus` and `wordpress_target_version`, exactly
  as defined by workstream 1.
- Every schema-2 assertion has a stable unique ID so QA expectations can name
  the assertion that a negative artifact must fail.
- Schema-2 release focus and WordPress target version are required at task or
  suite level and may not normalize to null.
- Invalid kind/plan/profile/engine combinations fail dataset validation before
  any model call.
- Remove unused `block_plugin`, `js_module`, and `patch` literals from the
  advertised runtime contract until a future implemented schema needs them.

Model and reference runs work from either local or Hub data. Artifact-aware
audit requires the maintainer checkout/QA sidecar; `--check-exploits` against a
Hub-only `wp-projects-v1` source fails preflight with a clear
`maintainer_qa_unavailable` error instead of marking tests unauditable. The
benchmark, reference, and QA snapshot digests are recorded separately as
defined by workstream 1.

## Artifact contracts

### PHP snippet

Keep the schema-1 fenced-PHP response and
`setup → candidate → assertions → teardown` semantics.

### Plugin file bundle

The model returns:

```json
{"files": {"relative/path": "complete UTF-8 contents"}}
```

Requirements:

- Preserve the existing 20-file, 256 KiB-per-file, and 1 MiB-total limits.
- Reject absolute paths, traversal, empty segments, invalid path characters,
  binary content, and duplicate normalized paths.
- Require exactly one top-level PHP file with a valid `Plugin Name:` header.
- Preserve path identity through static and runtime results; a token in the
  wrong file cannot satisfy a file-specific contract.
- Block plugins use this artifact kind and may include `block.json`, PHP,
  JavaScript, CSS, and `.asset.php` files.
- Candidate files must be directly runnable. The grader never installs model
  dependencies or runs a model-supplied build script.

### Theme file bundle

`wp_theme_files` uses the same JSON files envelope and safety limits, with
theme-specific validation:

- exactly one top-level `style.css` contains a valid `Theme Name:` header;
- WordPress recognizes the installed bundle through `WP_Theme`;
- classic tasks contain the files WordPress requires for a valid classic
  theme;
- block-theme tasks contain `theme.json` and `templates/index.html`, plus any
  task-required parts, patterns, or style variations;
- WordPress APIs, not regex alone, decide installed-theme validity.

## Execution plans and profiles

Supported plans in schema 2 are:

- `snippet_execute`
- `plugin_load_legacy`
- `plugin_activate`
- `plugin_activate_deactivate`
- `plugin_full_lifecycle`
- `theme_switch`
- `block_editor_roundtrip`

Supported profiles/scopes are:

- `single_site`, site scope;
- `multisite_subdirectory`, site or network scope.

Supported engines are:

- `wordpress_php`;
- `wordpress_browser`.

Selected tests declare all required capabilities. Preflight fails before paid
calls if the grader cannot provide a selected profile or engine.
Each plan defines an exact ordered set of required and optional phase names;
unknown, duplicate, missing-required, or out-of-order phases fail dataset
validation. Assertions cannot request a phase that the selected plan does not
execute.

Normative plan matrix:

| Plan | Artifact | Valid profile/scope | Engines | Ordered actions and assertion phases |
|---|---|---|---|---|
| `snippet_execute` | `php_snippet` | either profile, site | PHP | fresh bootstrap; optional setup; candidate plus required `execute`; optional teardown |
| `plugin_load_legacy` | `wp_plugin_files` | single site, site | PHP | fresh bootstrap; optional setup; direct legacy load plus required `after_load`; optional teardown |
| `plugin_activate` | `wp_plugin_files` | either profile, site or network | PHP | install inactive; optional setup; activate; fresh bootstrap; required `after_activate`; optional teardown |
| `plugin_activate_deactivate` | `wp_plugin_files` | either profile, site or network | PHP | activate; fresh `after_activate`; deactivate; fresh required `after_deactivate`; optional teardown |
| `plugin_full_lifecycle` | `wp_plugin_files` | either profile, site or network | PHP | activate; fresh `after_activate`; deactivate; fresh `after_deactivate`; uninstall/delete through WordPress; fresh required `after_uninstall`; optional teardown |
| `theme_switch` | `wp_theme_files` | single site, site | PHP | install inactive; optional setup; switch; fresh required `after_switch`; restore original theme; fresh required `after_restore`; optional teardown |
| `block_editor_roundtrip` | `wp_plugin_files` | single site, site | PHP and browser | activate; fresh required PHP `after_activate`; required browser `editor_roundtrip`; optional fresh PHP `after_browser`; optional teardown |

`plugin_load_legacy` exists only to migrate schema-1 behavior; no new
schema-2 task may select it. Setup always runs after safe installation but
before the first lifecycle action. Teardown runs after the final assertion
phase even when an assertion failed. Harness cleanup/deactivation/removal runs
after teardown regardless of test outcome and is not a model-scored phase.
Each action/assertion phase receives a fresh WordPress bootstrap where the
matrix says “fresh.” Browser tasks share the same task-wide deadline as PHP
phases.

## Runtime lifecycle

Each installation/session directory is unique and scoped to
`(run_id, unit_id, test_id, attempt_ordinal)`. Only that exact owned directory
and explicitly tracked fixtures may be removed. A recovered attempt installs
the same frozen normalized artifact into a fresh owned session. The Python
harness performs cleanup in `finally` in addition to PHP cleanup, because a
timeout or killed PHP process can bypass destructors and shutdown hooks.

File-artifact execution is:

1. Reset the declared runtime profile.
2. Validate and install the artifact while inactive.
3. Run setup in a fresh WordPress bootstrap.
4. Execute the declared lifecycle action through WordPress APIs.
5. Run that phase's assertions in another fresh bootstrap.
6. Repeat steps 4–5 for later phases.
7. Run test teardown.
8. Force deactivation or switch back, remove tracked state and files, and
   verify cleanup.
9. Record phase results, durations, bootstrap identity, and cleanup outcome.

These steps describe one canonical attempt. On a recoverable `runtime_reset`
or `grading` error, workstream 1 starts a new attempt at step 1
(`runtime_reset`) and replays the complete runtime sequence using the already
captured normalized artifact; it never grades a retry against residual state,
regenerates, or reparses a model completion. `artifact_cleanup`,
runtime-identity drift, and verification-contract drift are terminal and halt
or quarantine the profile as defined by the canonical integrity contract.

Fresh bootstraps are mandatory after activation and deactivation. Including a
main plugin file in one PHP process does not prove activation hooks,
subsequent-request loading, deactivation, or uninstall behavior.

The active installation/session component therefore separates scoped file
placement and ownership from activation or direct inclusion for every new
lifecycle plan. `plugin_load_legacy` remains an explicit schema-1 compatibility
capability and is removed only through a versioned migration, not implicitly
when implementation symbols or runner internals change.

`grader.timeout_seconds` is the deadline for all phases of one attempt, not a
fresh allowance per phase and not a shared allowance across recovered
attempts.

If assertions finish but cleanup fails, the canonical outcome becomes
`errored` at `artifact_cleanup`; the pre-cleanup score remains diagnostic and
unusable. The environment quarantines that profile, performs scoped recovery,
and does not start another attempt until recovery proves the owned artifact and
fixtures are gone. Failure to recover terminates the run.

## Runtime profiles

Add a profile-aware environment manager. Single-site and multisite runtimes
are isolated instances with pinned equivalent WordPress, PHP, runtime-plugin,
database, and WP-CLI versions. Per-test reset applies inside the selected
profile.

Every profile records and validates workstream 1's structured isolation
identity: `mechanism`, `scope`, `worker_topology`, and `identity_sha256`.
Behavior observed at preflight is authoritative; a flat configuration value or
branch-specific metadata shape is not.

Configuration adds a typed `grader.profiles` map whose keys are runtime-profile
names. Each `GraderProfileConfig` supplies its own grader kind, wp-env path or
container identity, database namespace, CLI endpoint, and optional web base
URL. Existing flat grader fields adapt to a single `single_site` profile for
backward compatibility. A project-suite config must define separate
`single_site` and `multisite_subdirectory` entries; they may not share a
container name, database, or writable WordPress directory.

Browser capability is configured under `grader.browser` with a pinned image
digest, driver version, endpoint, and total timeout. It targets the selected
profile's web base URL. Missing or mutable browser identity fails the browser
preflight and official eligibility.

Every profile declares a `state_identity` for its database and WordPress
artifact filesystem. CLI, web, and browser endpoints used by one task must
report the same WordPress installation ID, database fingerprint, and candidate
artifact-volume identity. Preflight rejects a profile whose processes do not
share that state.

The multisite profile:

- performs a clean deterministic subdirectory network install;
- uses fixed main-site/network IDs and deterministic site paths;
- supports site and network activation;
- verifies behavior against at least two sites for network-scoped tasks;
- records the network/site IDs used in grader diagnostics;
- remains serial under its official profile isolation policy.

`metadata.requires_multisite` becomes a validated mirror of
`execution.profile`, not an informational flag. Profile disagreement fails
dataset validation.

At `77c98d6`, the root `.wp-env.json` and `runtime/.wp-env.json` target
different WordPress/PHP combinations. Official project-suite runs use explicit
runtime profiles and record observed identities through workstream 1; no
ambient workspace default is authoritative.

## Browser/editor engine

Server-side block registration tasks use the plugin runner first. The six
editor tasks use a pinned Playwright/browser sidecar against a web-served
canonical WordPress runtime. Browser and driver versions/digests become grader
provenance.

Each editor task uses a fixed:

- admin account;
- locale and timezone;
- theme and permalink mode;
- viewport;
- post slug;
- external-request blocklist.

A structured editor assertion may insert the candidate block, modify an
attribute, save, reload, confirm block validity and persistence, inspect
front-end rendering, and fail on unexpected console errors. Assertions use
semantic editor/DOM state rather than screenshots; screenshots are diagnostic
only.

The browser image and WordPress/editor assets are pinned. The grader does not
download arbitrary npm packages or contact external sites during a task.
The browser capability canary must prove both directions of visibility: a
candidate installed through CLI is visible to the web/editor process, and
state created in the browser is visible to a later fresh CLI assertion.

## Assertion strategy

Runtime behavior remains authoritative. Add reusable built-ins for common
observations so new tasks do not default to opaque custom predicates:

- path-aware file existence and file-specific matching;
- strict JSON/JSON-path values;
- per-file PHP syntax and deterministic JavaScript syntax/load checks;
- plugin status and activation scope;
- option/site-option and cleanup state;
- theme validity, active template/stylesheet, global settings/styles, template
  discovery, and rendered output;
- multisite site/network state and correct blog restoration;
- structured browser/editor actions and assertions.

Plugin assertions inspect WordPress registries, hooks, options, database
state, REST dispatch, cron, rewrite state, or rendered output rather than
trusting a candidate wrapper return. Lifecycle tasks assert creation and
removal across fresh requests. Multisite tasks own and clean fixed fixtures.

Static analysis runs per file and reports paths. Required patterns remain
diagnostic; only genuine forbidden patterns with `severity: error` can fail a
task. Static tokens never substitute for behavioral assertions.

## Source, reference, and negative-control policy

Every schema-2 task must include:

- structured `metadata.source_refs` entries with `repository`, immutable
  `revision` commit SHA, `path`, and optional `symbol`/`lines`; editor tasks
  also pin the relevant editor repository/package revision;
- `expected_behavior` naming every observable phase and assertion;
- concise model-facing requirements;
- one complete reference artifact that passes the real verifier;
- at least two typed negative controls with rationales and expected failure
  stage;
- review status and reviewer identity in suite-maintainer metadata.

No prompt includes the reference implementation, assertion code, lifecycle
plan name, checker-only helper, or incidental exact API key unless that API
surface is itself the task.

`--check-exploits` is generalized into artifact-aware negative-control
execution. It consumes the sidecar's declared artifact kind through the
canonical normalized-artifact adapter and never assumes a PHP-source artifact
from a legacy producer shape. Unauditable is a release failure for every new
task.

Schema-1 string source references remain readable but do not satisfy the
schema-2 review gate. Schema-2 refs reject branch names, mutable `trunk`, and
unpinned package ranges. Each QA control's `expected_failure` must contain a
valid plan phase and at least one stable assertion ID; the audit verifies the
observed rejection against that expectation rather than accepting any crash.

## Phased milestones

Each milestone introduces at most one runtime capability and no more than
eight tasks. Every capability milestone ends with real-runtime canaries before
the corresponding dataset-only expansion.

WS3.0 validator/schema code may merge as a dormant capability in either order
with WS1.1. A manifest-bearing suite, its runnable example config, or its
export/import path must not activate until the WS1.1-owned
`SuiteDescriptorPolicy`, `SuitePolicyResolver`, and suite-scoped `load_suite()`
capability tests are present and green, or the activating change bundles those
exact capabilities. It must never duplicate the policy type or let a legacy
loader silently ignore `suite.json`.

1. **WS3.0 — Suite schema and gates:** add `suite.json`, a tracked
   `wp-projects.yaml` example config, schema-2 validation, conditional reference
   forms, execution metadata, the digest-bound maintainer QA sidecar,
   export/import parity, and exact balance tests.
2. **WS3.1 — Plugin runner hardening:** real integration, unique sessions,
   path-aware checks, and out-of-process cleanup; add four plugin canaries.
3. **WS3.2 — Plugin dataset:** add eight more plugin-integration tasks.
4. **WS3.3 — Lifecycle engine:** add fresh-process activation,
   deactivation/uninstall, phase results, and two canaries.
5. **WS3.4 — Lifecycle dataset:** add six lifecycle tasks.
6. **WS3.5 — Server block artifacts:** add six block metadata,
   registration, asset, and server-render tasks on the plugin runner.
7. **WS3.6 — Browser/editor engine:** add pinned browser execution and two
   editor canaries.
8. **WS3.7 — Editor dataset:** add four more browser/editor tasks.
9. **WS3.8 — Theme installer/switcher:** add recognition, switch, restore,
   cleanup, and two theme canaries.
10. **WS3.9 — Theme dataset:** add eight more classic/block-theme tasks.
11. **WS3.10 — Multisite profile:** add deterministic network reset/network
    activation and two canaries.
12. **WS3.11 — Multisite dataset:** add six more multisite tasks.
13. **WS3.12 — Release gate:** verify the exact 50-task balance, full
    references, full negative controls, cleanup fault injection, and local/Hub
    export parity.

Each numbered milestone receives its own implementation plan and review. Later
dataset milestones may proceed only after their capability canaries pass.

## Validation

For every changed task on this Windows workspace:

```powershell
$testId = "e-plugin-files-001"
.\.venv\Scripts\python.exe -m pytest python\tests\test_execution_dataset.py
.\.venv\Scripts\wp-bench.exe run --config wp-projects.yaml --dry-run --test-id $testId
.\.venv\Scripts\wp-bench.exe run --config wp-projects.yaml --check-reference-solution --test-id $testId
.\.venv\Scripts\wp-bench.exe run --config wp-projects.yaml --check-exploits --test-id $testId
```

For each milestone and the final suite:

```powershell
.\.venv\Scripts\python.exe -m pytest python
.\.venv\Scripts\wp-bench.exe run --config wp-projects.yaml --dry-run
.\.venv\Scripts\wp-bench.exe run --config wp-projects.yaml --check-reference-solution
.\.venv\Scripts\wp-bench.exe run --config wp-projects.yaml --check-exploits
.\.venv\Scripts\python.exe datasets\export_dataset.py
ruff check python
mypy python
git diff --check
```

Runtime capability changes also require real wp-env and Docker/profile
canaries. Tests that replace `execute_artifact()` with a fake are useful unit
tests but do not satisfy a capability milestone.

## Test strategy

- Dataset schema tests cover conditional fields, exact enums, unsupported
  combinations, suite counts, family/artifact/difficulty balance, source
  identity, reference presence, and negative-control minimums.
- Artifact unit tests cover path normalization, duplicate normalized paths,
  file/type limits, entrypoint ambiguity, UTF-8, plugin headers, theme headers,
  and malformed JSON.
- Export/import tests compare all public schema fields and suite provenance for
  local and Hugging Face-shaped rows, including canonical suite-manifest JSON
  and digest agreement.
- QA tests reject stale definition/verification digests, invalid expected
  phases/assertion IDs, missing candidates, candidate execution errors, and
  rejections at the wrong stage.
- Runtime integration tests cover real install/activate/deactivate/uninstall,
  fresh bootstraps, theme switch/restore, browser round-trip, site/network
  activation, and phase timeout budgeting.
- Profile preflight tests prove CLI/web shared database and filesystem identity
  and bidirectional visibility before browser model calls.
- Cleanup fault injection covers assertion failure, PHP fatal, timeout,
  browser crash, and harness interruption. The next test must see no owned
  candidate directory or persistent fixture.
- Recovery fault injection introduces one recoverable reset or grading error
  and proves the next attempt uses the same artifact digest and generation
  provenance with no additional provider call. A cleanup failure is terminal,
  quarantines the profile, and is never retried as a new candidate.
- Reference tests run every new artifact through its declared profile and
  engines.
- Negative-control tests prove every typed known-wrong artifact fails for the
  intended reason; no new task is unauditable.
- Determinism tests repeat clean runs with external network blocked.

## Acceptance criteria

1. `wp-core-v1` remains byte-for-byte unchanged and continues to contain 185
   tests.
2. `wp-projects-v1` contains exactly 50 tasks with the stated family,
   artifact, and difficulty counts; repository total is 235.
3. Every reference artifact passes all declared phases in the real target
   runtime.
4. Every maintainer-QA negative control completes and is rejected at its
   expected stage/assertion; no new task is unauditable. Hub-only audit fails
   preflight clearly because the QA sidecar is intentionally unavailable.
5. Plugin lifecycle, theme switching, browser editor round-trip, and multisite
   network activation each have a passing real-runtime canary.
6. Deliberate failure and timeout leave no candidate plugin/theme directory or
   persistent state visible to the next test.
7. Exported rows reload with identical public artifact, execution, suite,
   provenance, reference, canonical suite-manifest JSON, and manifest digest.
8. Unsupported kinds, malformed bundles, duplicate entrypoints, invalid or
   out-of-order phases, missing engines, and profile/state mismatches fail
   before model calls.
9. Repeated clean reference/negative runs are deterministic with network
   blocked.
10. Every prompt passes editorial review for behavioral wording and absence of
    checker/reference leakage.
11. Limited smoke selection records the new suite's family/artifact/
    difficulty/profile strata and cannot silently use alphabetical prefixes.
12. Both suites report independently with immutable content fingerprints; no
    composite score is emitted.

## Risks and fixed assumptions

- Browser/editor tests are slower and more failure-prone. Pinned browser and
  WordPress/editor assets, structured assertions, and two canaries precede the
  broader dataset.
- Database reset does not remove candidate files, so out-of-process scoped
  cleanup is mandatory.
- Multisite provisioning is slower and remains serial under official
  isolation.
- Artifact size limits intentionally constrain tasks to focused project slices,
  not full products.
- Official browser checks require a web-served WordPress runtime in addition to
  a CLI verifier capability.
- The plugin-files path at `77c98d6` has not been proven through a real runtime
  integration test; WS3.1 must establish the capability with canaries rather
  than inherit it from ambient code state.

## Baseline evidence locations at `77c98d6`

The symbols below locate non-normative observations and may move without
changing the canonical suite contract.

- `python/wp_bench/config.py::ArtifactKind`
- `python/wp_bench/artifacts.py::parse_artifact`
- `python/wp_bench/artifacts.py::_parse_plugin_files`
- `python/wp_bench/datasets.py::ExecutionTest`
- `python/wp_bench/datasets.py::_parse_execution_suite`
- `python/wp_bench/core.py::BenchmarkRunner._run_reference_solution_tests`
- `python/wp_bench/exploits.py`
- `python/tests/test_artifacts.py`
- `python/tests/test_execution_dataset.py`
- `runtime/src/class-artifact-installer.php`
- `runtime/src/class-verifier.php`
- `runtime/src/class-sandbox.php`
- `runtime/Dockerfile`
- `runtime/.wp-env.json`
- `.wp-env.json`
- `datasets/export_dataset.py`
- `datasets/README.md`
