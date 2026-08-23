# WP-Bench Benchmark Integrity Design

- Status: Approved (revision 6)
- Date: 2026-08-16; revised 2026-08-22
- Evidence baseline: observations verified against immutable commit
  `77c98d61b73c6341db2fa5ccb15212867b825eb5` (abbreviated `77c98d6` below)
- Normative independence: branch names, pull-request state, merge order, and
  current implementation symbols are never part of the canonical contract
- Workstream: 1 of 3
- Consumed by: `2026-08-16-reporting-statistics-design.md` and
  `2026-08-16-wordpress-coverage-expansion-design.md`
- Cross-workstream contract: every selected-test descriptor field is present;
  a source that cannot supply one emits null. A validated suite manifest may
  supply declared defaults and smoke strata, but no other workstream or merge
  is a delivery prerequisite.

## Normative independence rule

Canonical requirements are defined only by versioned schemas, enumerated hash
preimages, ordered structural discriminators, and executable invariant tests.
A branch or pull request may motivate a requirement, but its existence, final
shape, merge order, or failure to merge cannot activate, weaken, or invalidate
one. Current code paths and corpus counts are evidence frozen to the commit
that names them, not ambient facts a future implementation must still satisfy.

## Decision summary

WP-Bench will replace its divergent single-model, multi-model, skills,
reference, and exploit-audit payloads with one manifest-driven result
envelope. New writers emit only the canonical format. A read adapter keeps
existing artifacts usable without pretending that missing provenance or
denominators can be reconstructed.

Limited subsets will use a deterministic, order-independent selector, but
will be labeled smoke runs rather than representative benchmark results.
Every metric will carry its denominator, every run unit will carry
completeness and eligibility, and every attempted test will be recorded
before continuation or abort policy is applied.

Because an error is not a grade, a run may re-attempt a bounded number of
ungraded runtime and harness errors, reusing the generation it already paid
for, and record every attempt it made. Without that, one failed database reset
discards a 185-test run. Delivery is split into seven numbered milestones,
each leaving the harness working, because this workstream is about the size of
the harness it is changing.

## Frozen branch evidence (non-normative)

The following reviewed snapshots motivated requirements and regression cases.
They remain evidence even if their branches are rebased, merged in any order,
closed, superseded, or never merged:

- `b0ebf20c773d91847618c0480c5c138d3d9d8842` (#51): cross-artifact
  baseline reuse requires sourced units rather than copied records.
- `9de63f278ef8fd8c8d7796357446f443b00066d2` (#53): reset mechanism is
  part of isolation identity.
- `99e4aa2cc165bbe1bfcd849b4dbd97e429584a94` (#54): generation
  telemetry must describe arbitrary effective and rejected parameters.
- `db308679c5f3704568c91496d0586bef1a564ad2` (#55): worker topology is
  part of isolation identity.
- `d4f8ed70418baf090980bdf150d437d3cb0ce89c` (#56) and
  `587d2aa5a3388018de91411a2e1f86c7b64735f4` (#59): selector requests must affect the sealed
  plan or fail, and canonical descriptors outlive transient runtime-model
  fields.
- `645e7bc76871c98f665945c5499870be2ef0de28` (#58): test-only coverage
  does not create a producer capability or artifact shape.

No requirement below is conditional on these snapshots. They are provenance
for why the invariant exists, not a forecast of repository state.

## Context and problem

Every observation below was verified against `77c98d6` and is stated only as of
that immutable commit. The branch snapshots above are separate evidence. None
of these observations is an input to a canonical digest or an implementation
precondition; regression fixtures and release tests enforce the requirements.

The existing harness has strong per-test grading and durable JSONL streaming,
but its persisted run contract is incomplete:

- `python/wp_bench/core.py` constructs different top-level payloads in
  `BenchmarkRunner.run()`, `BenchmarkRunner._run_exploit_audit()`, and
  `MultiModelRunner._write_outputs()`. The multi-model writer drops selection,
  usage, and error data that `SingleModelRunner.run()` already computed.
- `python/wp_bench/selection.py::select_tests()` sorts strata before draining
  them, so `sorted(groups.keys())` picks the groups and the seed only shuffles
  within them. On the real 185-test corpus this is worse than "biased": the
  corpus has 29 categories and 54 `(category, difficulty)` groups, so at
  `limit=6` every seed returns tests drawn from the same two categories,
  `abilities-api` and `ai-client`, the two that sort first. Seeds 1, 2, and
  1337 differ only in which test they pick inside those six groups. The
  documented promise of a "different deterministic subset" per seed is
  therefore false for any limit below 54, which is every limited run anyone
  performs. `stratified-hash-round-robin/2` is a repair, not a refinement.
- `python/wp_bench/scoring.py::ScoreAggregator` aggregates only graded
  records. A run with passes plus provider errors can therefore display a
  perfect conditional pass rate without a selected or graded denominator.
- With `continue_on_error=false`, the terminal failed attempt is not sent to
  the result callback. A first-call failure can leave no artifact because
  `python/wp_bench/results_io.py::RecordStream` opens lazily on its first
  record.
- `python/wp_bench/core.py::_run_isolated_execution_loop` calls
  `environment.reset()` outside the per-test `try`. A mid-run reset failure
  raises `RuntimeError` or `EnvironmentSetupTimeout`, which neither
  `_graded_run` (TestError and KeyboardInterrupt only) nor the CLI's
  `_run_or_fail` (ValueError only) catches. The run dies on an uncaught
  traceback, writes no results JSON at all, and leaves only a `.partial`. This
  is the most severe artifact-loss path observed at `77c98d6`.
- `python/wp_bench/core.py::_first_passing_exploit` cannot distinguish a
  defeated cheat from a broken verifier. An infrastructure failure returns
  `raw={}`, `_score_execution` reads that as a crash, `execution_pass` is
  false, and the candidate is recorded as rejected. A test whose audit never
  actually ran is reported as not exploitable.
- A post-generation exception loses the completion, usage, response ID,
  retry, and elapsed-time data already captured by `ModelGeneration`.
- Result metadata identifies requested aliases and mutable references. It
  does not record a dataset content digest, harness revision, resolved grader
  image, observed WordPress/PHP/runtime identity, or provider-reported model
  snapshot.
- A partial JSONL stream contains records but no immutable plan, so its exact
  missing tests and subgroup denominators cannot be recovered by itself.

These gaps make reliability telemetry survivorship-biased and prevent a
result artifact from proving that it is complete, comparable, or suitable for
a leaderboard.

## Goals

1. Use one versioned manifest, record, event, and envelope contract for every
   run mode and topology.
2. Freeze the selected tests and behavioral configuration before the first
   graded attempt.
3. Record explicit metric numerators, denominators, applicability, and
   coverage.
4. Compute completeness and leaderboard eligibility mechanically per
   model/variant/trial unit.
5. Preserve every terminal attempt, including the attempt that causes the
   default abort path.
6. Let a run recover from a bounded number of ungraded runtime and harness
   errors without re-sampling the model, without forfeiting completeness, and
   without hiding that the recovery happened.
7. Preserve model-call and stage telemetry monotonically after generation.
8. Content-address dataset, test, prompt rendering, harness, grader, runtime,
   scoring, and skill provenance; record model immutability when the provider
   can prove it.
9. Make partial streams self-describing and recoverable without reopening a
   mutable dataset.
10. Retain append-as-completed streaming, readable partials, atomic final
    writes, and collision-safe filenames.
11. Read legacy artifacts through one fail-closed adapter.
12. Ship as independently reviewable milestones, each of which leaves the
    harness working.

## Non-goals

- Claiming that a small smoke subset estimates full-suite performance.
- Cryptographically signing or attesting result authorship.
- Guaranteeing that estimated cost equals a provider bill.
- Resuming a killed run from its partial stream in a later invocation. This is
  about crash resumption specifically. Bounded in-run recovery of ungraded
  errors is in scope, and so is referencing a previously executed unit as a
  comparison arm; both are specified below. Neither replays a killed run.
- Changing WordPress assertion semantics or the strict per-test pass rule.
- Creating a standard leaderboard for skill-injected variants.
- Storing secrets, request headers, or environment variables as provenance.

## Alternatives considered

### Patch each legacy payload independently

Adding the missing fields independently would be a small change, but it would
preserve multiple shapes, duplicate lifecycle code, and leave consumers to
infer mode and completeness. This is rejected.

### Canonical envelope plus event stream

One typed manifest and ordered list of run units serves single, multi, skills,
reference, and audit runs. An append-only event stream provides recovery;
the final JSON is the normalized projection. A legacy reader adapts old
files. This is the selected approach.

### Event log as the only artifact

An event-sourced-only format is robust, but every consumer would need to fold
the stream before doing basic analysis. WP-Bench will keep both the event log
and a final envelope.

## Architecture

The design introduces focused modules and keeps `core.py` as orchestration:

| Module | Responsibility |
|---|---|
| New `python/wp_bench/schemas.py` | Strict models and version constants for manifests, records, envelopes, counts, metrics, eligibility, provenance, and events. |
| New `python/wp_bench/provenance.py` | Canonical hashing, config redaction, dataset snapshots, source-tree identity, model identity classification, and grader/runtime inspection. |
| `python/wp_bench/datasets.py` | The single normalization boundary: resolve one suite identity and every canonical descriptor identically for local and Hub sources. |
| `datasets/export_dataset.py` | Preserve suite identity and every descriptor the catalog consumes, so an exported suite loads to the same catalog as its source. |
| `python/wp_bench/selection.py` | Build a versioned `SelectionPlan`, selected-test catalog, and catalog digest. |
| New `python/wp_bench/verification.py` | Build the declared and post-policy verification projections once, including the derived gateway, their digests, and divergence classification; execution consumes the same object selection seals. |
| `python/wp_bench/records.py` | Build all terminal records through one base constructor, including exploit assessments. |
| `python/wp_bench/models.py` | Return a success or failure `ModelCallOutcome` with attempt telemetry in either case. |
| `python/wp_bench/environment.py` | Keep execution/reset behavior and expose observed grader/runtime provenance and stage timings. |
| `python/wp_bench/scoring.py` | Produce denominator-aware per-unit metrics. |
| New `python/wp_bench/integrity.py` | Derive completeness and versioned eligibility from the manifest and terminal records. |
| `python/wp_bench/results_io.py` | Own manifest-first event streaming, locking, recovery, and atomic finalization through `RunArtifactWriter`. |
| New `python/wp_bench/results_reader.py` | Expose `load_result_envelope(path)`, `load_result_envelopes(paths)` for the cross-input relations, and the legacy adapter. |
| `python/wp_bench/config.py` | Add `run.max_test_reattempts` and the structured isolation identity; keep rejecting unknown fields. |
| `python/wp_bench/core.py` | Execute a sealed plan through `RunCoordinator`, which owns attempt ordinals, the recovery budget, and the attempt boundary that now contains the runtime reset. It no longer assembles payload dictionaries. |
| `python/wp_bench/output.py` | Render canonical aggregates without recomputing completeness or eligibility. |

Existing runner classes may remain as temporary API adapters during migration,
but they must delegate persistence to the same coordinator and writer.

## Version boundaries

The following versions are independent:

- `RUN_MANIFEST_SCHEMA_VERSION = "1.0"`
- `RESULT_RECORD_SCHEMA_VERSION = "3.0"`
- `RESULT_ENVELOPE_SCHEMA_VERSION = "3.0"`
- `RESULT_EVENT_SCHEMA_VERSION = "1.0"`
- `SCORING_VERSION = "4.0"`
- `ELIGIBILITY_POLICY_VERSION = "wp-bench-leaderboard/1.0"`

Writers reject unknown fields. Readers reject unsupported major versions and
may preserve unknown compatible-minor fields under `extensions` without
interpreting them.

A version string that does not track shape is worse than no version string,
because a reader can branch on it and be wrong. The evidence baseline and
frozen branch snapshots already contain mutually incompatible structures that
use the same advisory legacy version. The legacy fixture index records every
observed structure by its versioned recursive-shape fingerprint,
original-byte digest, and producer commit; no merge outcome is required for an
observed structure to remain part of the compatibility corpus.

Therefore: any canonical change to an emitted record or payload field set bumps
its schema version in the same change, enforced by a versioned recursive-shape
fingerprint test. `LegacyResultAdapter` uses an ordered, mutually exclusive
structural discriminator registry and never branches on a recorded legacy
version string. The version is authoritative for canonical artifacts and
advisory for legacy ones; an unknown or ambiguous legacy structure fails that
input explicitly rather than being guessed.

## Canonical manifest

`RunManifest` is sealed before the first model, reference, or exploit attempt.
Environment setup and provenance resolution happen during preflight. If
preflight raises, the coordinator seals a manifest with explicit unresolved
fields, writes a failed terminal artifact, and does not guess identities.

The manifest contains:

| Field | Contract |
|---|---|
| `schema_version` | Manifest version `1.0`. |
| `run_id` | UUID generated once per CLI invocation. |
| `created_at` | UTC RFC 3339 timestamp captured at invocation start. |
| `mode` | `benchmark`, `reference_solution`, or `exploit_audit`. |
| `topology` | `single`, `multi`, or `matrix`; informational only. |
| `selection` | Requested selection, effective kind, algorithm/version, universe identity, selected catalog, and catalog digest. |
| `run_units` | Ordered actor × variant × trial units. Each has a unique `unit_id`, a `source` discriminator (`executed` or `sourced`), one-based `trial_index`, actor, variant, planned count, planned-subject fingerprint, and optional `pair_id`. |
| `external_unit_refs` | References to run units this run did not execute; empty unless some unit is `sourced`. |
| `trial_protocol` | Declared trial count, generation-seed policy, pairing policy, and `trial_protocol_fingerprint_sha256`; benchmark mode only. |
| `audit_plan` | Sealed candidate plan; non-null if and only if `mode` is `exploit_audit`. |
| `policies` | Continuation, recovery budget, grading dimensions, concurrency, timeouts, and artifact-capture policy. Isolation lives on each runtime profile, not here. |
| `provenance` | Requested/resolved identities, including maps keyed by runtime profile and execution engine. |
| `config_sha256` | Hash of normalized behavior-affecting configuration, excluding output paths and secrets. |
| `contract_fingerprint_sha256` | Comparison contract including mode but excluding run ID, timestamps, topology, actor, variant, and trial count. |
| `extensions` | Empty object in manifest version 1.0. |

The selected-test catalog is authoritative for planned denominators. Every
entry contains:

- `test_id`
- `suite`
- `category`
- `difficulty`
- `artifact_kind`
- `runtime_profile`
- `coverage_family`
- `release_focus`
- `wordpress_target_version`
- `benchmark_definition_sha256`
- `verification_sha256`
- `effective_verification_sha256`
- `verification_divergence`

Nullable dimensions are present as JSON `null`, never omitted.
`test_id`, `suite`, and `category` are nonempty strings.
`artifact_kind` is one of the active cross-workstream contract values
`php_snippet`, `wp_plugin_files`, or `wp_theme_files`; dormant names such as
`block_plugin`, `js_module`, and `patch` are not admitted. `difficulty`,
`runtime_profile`, `coverage_family`, `release_focus`, and
`wordpress_target_version` are `string | null`. The three digest fields match
`^[0-9a-f]{64}$`, and `verification_divergence` is exactly `none`,
`gateway_only`, or `dimension_skipped`.

### Selection-plan fields and digest preimages

`SelectionPlan` version 1 has exactly these fields:

| Field | Contract |
|---|---|
| `requested_limit` | The normalized positive safe-integer limit, or null. |
| `requested_test_ids` | The normalized explicit IDs in first-occurrence request order; empty when the request is not explicit. |
| `requested_seed` | The normalized caller-supplied safe-integer seed, or null when the limited selector uses its built-in seed. |
| `effective_kind` | `full`, `limited_smoke`, or `explicit_smoke`. |
| `algorithm` | `full/1`, `explicit-id-set/1`, or `stratified-hash-round-robin/2`, naming the path actually used. |
| `effective_seed` | The seed consulted by the limited algorithm, including the built-in `1337`; null for full and explicit paths. |
| `smoke_strata` | The validated ordered canonical descriptor fields supplied by the suite or the built-in `category,difficulty` default. |
| `universe_test_count` | Number of unique tests in the resolved suite before selection. |
| `universe_sha256` | Digest of the complete suite-scoped universe preimage below. |
| `selected_catalog` | The selected-test entries above in stable test-ID order. |
| `selected_catalog_sha256` | Digest of the complete selected-catalog preimage below. |

The algorithm records the request path even when the request covers the whole
universe: for example, a limit at or above the universe size has effective kind
`full` and algorithm `stratified-hash-round-robin/2`. That keeps the effective
classification truthful without pretending the requested limit or seed was
ignored. Explicit IDs cannot be combined with a limit or caller-supplied seed,
and a caller-supplied seed requires a limit. These combinations fail before
manifest creation. The built-in seed is applied only to a limited request; a
full or explicit request has no effective seed.
Explicit-ID token normalization splits comma-separated CLI values, trims each
token, rejects any empty token, and retains only the first occurrence of a
repeated ID. It never turns a nonempty explicit request into an empty/full
request. Duplicate IDs in the dataset universe always reject.

Every digest below is the lowercase hexadecimal SHA-256 of the RFC 8785 bytes
for the displayed concrete JSON value, through `canonical_sha256()`. Object
key order is illustrative; array order is normative. The per-test benchmark
definition stored as `SelectedTest.benchmark_definition_sha256` has this exact
preimage:

```json
[
  "wp-bench-benchmark-definition",
  1,
  {
    "test_id": "<canonical test ID>",
    "suite": "<resolved suite ID>",
    "prompt": "<prompt>",
    "expected_behavior": "<expected behavior>",
    "requirements": ["<requirement in authored order>"],
    "test_function": null,
    "artifact_kind": "php_snippet",
    "execution_schema_version": "1.0",
    "execution": {},
    "static_checks": {},
    "runtime_checks": {},
    "category": "general",
    "difficulty": null,
    "runtime_profile": null,
    "coverage_family": null,
    "release_focus": null,
    "wordpress_target_version": null
  }
]
```

Angle-bracket strings above denote the normalized value at that position, not
literal sentinel text. Empty objects and nulls are likewise the normalized
values for the illustrated schema-1 case; populated tests place their complete
concrete JSON trees there. The definition excludes reference solutions/files,
maintainer or generated negative controls, raw metadata,
`metadata.suite_metadata`, `source_document_id`, `source_document_metadata`,
and every source identity.

The dataset-declared verification preimage is exactly:

```json
[
  "wp-bench-verification",
  1,
  {
    "execution_schema_version": "1.0",
    "execution": {},
    "static_checks": {},
    "runtime_checks": {}
  }
]
```

The effective-verification preimage has the same four object keys and the
domain tag `"wp-bench-effective-verification"`. Its `static_checks` and
`runtime_checks` are the post-policy values, including the derived weight-zero
gateway when applicable; its execution fields are the normalized plan actually
sealed for the run. Candidate content, owned-directory tokens, reference data,
negative controls, and verifier transport fields never enter either preimage.

Gateway parsing is intentionally narrower than PHP parsing and is frozen for
digest stability. Strip leading/trailing whitespace from a non-null
`test_function`, match `\A[A-Za-z_][A-Za-z0-9_]*`, and use that leading match
as the function name; the remaining signature text is model-facing and does
not change gateway extraction. No match is a preflight error. A null
`test_function` adds no gateway. The exact prepended assertion is:

```json
{
  "type": "function_exists",
  "target": "<extracted function name>",
  "description": "Defines test function <extracted function name>()",
  "weight": 0
}
```

The angle-bracket portions are replaced by the extracted name with no other
formatting or escaping beyond normal JSON serialization.

For gateway construction, an absent `runtime_checks.assertions` key denotes an
empty authored assertion list. When the key is present its value must be a
concrete JSON array; null, an object, a string, or any non-list concrete type is
a preflight error naming the test and `runtime_checks.assertions`. Existing
array order is preserved after the gateway is prepended. This shape check is
performed even when `test_function` is null, so malformed declared verification
cannot become conditionally executable under a different gateway policy.

The complete resolved-suite universe preimage is:

```json
[
  "wp-bench-selection-universe",
  1,
  "<resolved suite ID>",
  ["<ordered smoke stratum field>"],
  [
    ["<test ID>", "<benchmark_definition_sha256>", "<verification_sha256>"]
  ]
]
```

The innermost test tuples are sorted by test ID and cover every unique test in
the resolved suite, not only selected tests. Binding the declared verification
digest and ordered strata means an unselected assertion or strata change cannot
masquerade as the same smoke universe.

The selected-catalog preimage is:

```json
[
  "wp-bench-selected-catalog",
  1,
  [
    {
      "test_id": "<canonical test ID>",
      "suite": "<resolved suite ID>",
      "category": "general",
      "difficulty": null,
      "artifact_kind": "php_snippet",
      "runtime_profile": null,
      "coverage_family": null,
      "release_focus": null,
      "wordpress_target_version": null,
      "benchmark_definition_sha256": "<lowercase hexadecimal SHA-256>",
      "verification_sha256": "<lowercase hexadecimal SHA-256>",
      "effective_verification_sha256": "<lowercase hexadecimal SHA-256>",
      "verification_divergence": "none"
    }
  ]
]
```

Entries contain exactly the `SelectedTest` fields already enumerated and are
sorted by `test_id`. Every digest field is exactly 64 lowercase hexadecimal
characters with no `sha256:` prefix. `verification_divergence` is
`dimension_skipped` whenever policy empties a nonempty declared grading
dimension, taking precedence over a simultaneously derived gateway; otherwise
it is `gateway_only` when the gateway is the sole semantic difference, and
`none` when the declared and effective verification objects have the same
semantics. Skipping a dimension that was already empty is not itself a
divergence.

This catalog contract is independent of any transient in-memory test model or
legacy result-record field set. Each source adapter must produce the normalized
canonical value, emit null when the contract permits an unknowable value, or
reject the source as not representable. Removing a field from a runner object
or legacy writer therefore cannot remove that dimension from the canonical
catalog or change selection semantics silently.

The dataset loader is the only normalization boundary for selected-test
descriptors, and it must cover every catalog field, not only the dimensions
workstream 3 introduces:

- `suite` is the resolved SUITE identity: the suite directory name for a local
  source, the row's suite column for a Hub source. It is never a source
  document's own `id`. At `77c98d6`,
  `datasets.py::_parse_execution_suite` assigns each
  of 29 execution documents' distinct ids (`wp-core-execution-v1-abilities_api`
  and so on) while `export_dataset.py` writes `wp-core-v1` for all 185 rows, so
  the same content loads under 29 identities locally and one on the Hub. A
  document identifier that is worth keeping becomes a separate
  `source_document_id` that no descriptor, digest, or record consumes.
- `source_document_metadata` preserves the source execution document's
  concrete `metadata` object for transport, inheritance, and legacy adaptation;
  missing or null becomes an empty object. It is audit context only and enters
  no selected-test descriptor, digest, or result record.
- `test_id` and `prompt` are required nonempty strings. `expected_behavior`
  normalizes missing or null to the exact empty string and otherwise requires a
  string; authored strings are not trimmed or case-folded. `requirements`
  normalizes missing to an empty array and otherwise requires an ordered array
  of strings. Duplicate test IDs reject the resolved suite.
- The normalized `execution_schema_version` always comes from the validated
  `SuiteDescriptorPolicy`. A source document's `schema_version`, when present,
  must be a string exactly equal to that policy value; omission is permitted
  only under the built-in schema-1 policy and resolves to `1.0`. The document's
  legacy `version` is a content revision: it never supplies, overrides, or
  enters `execution_schema_version` or its descriptor digest projection.
- `category` defaults to `general` on both paths. Missing, null, empty, or the
  legacy sentinel string `"unknown"` for `difficulty` normalizes to canonical
  JSON null; `unknown` is a reporting label only and is never stored as the
  canonical descriptor.
- `artifact_kind` defaults to `php_snippet`, with absent, null, and empty
  string all coerced identically. At `77c98d6`, the two loaders differ here:
  `.get(key, default)` locally against `or default` for Hub rows.
- `test_function`, `reference_solution`, and `reference_files` normalize absent
  and empty to null on both paths.
- `static_checks`, `runtime_checks`, and `execution` normalize absence to an
  empty object and otherwise require a concrete JSON object; null and malformed
  transport values reject instead of becoming empty checks. Task `metadata`
  normalizes missing or null to an empty object and otherwise requires an
  object. Nested array order is preserved.
- `exploit_solutions` is null for every Hub-sourced test, because the export
  deliberately omits maintainer QA data.
- `execution.profile` becomes `runtime_profile`;
- `metadata.coverage.family` becomes `coverage_family`;
- schema-1 or schema-2 `metadata.release_focus` becomes `release_focus`;
- `metadata.wordpress_target_version`, or the suite's declared inherited
  target, becomes `wordpress_target_version`.

For those four nullable descriptor strings, missing, null, and the exact empty
string mean no value; other strings are preserved byte-for-byte. Release focus
uses the first nonempty task then validated-suite value. WordPress target uses
the first nonempty task, validated-suite, then schema-1 execution-document
`metadata.wp_version` value. A non-string candidate rejects rather than being
coerced.

The stable cross-workstream seam is a validated `SuiteDescriptorPolicy`, not
the raw shape of a future `suite.json`. It contains exactly:

| Field | Contract |
|---|---|
| `suite_id` | Nonempty resolved canonical suite identity. |
| `suite_content_version` | Semantic content version as a string, or null for a schema-1 suite without a manifest. |
| `execution_schema_version` | Schema version as a string; built-in schema-1 policy supplies `1.0`. |
| `smoke_strata` | Nonempty ordered unique fields drawn only from `category`, `difficulty`, `artifact_kind`, `runtime_profile`, `coverage_family`, `release_focus`, and `wordpress_target_version`. |
| `release_focus` | Suite-inherited canonical value, or null. A task value takes precedence. |
| `wordpress_target_version` | Suite-inherited canonical value, or null. A task value takes precedence, followed for schema 1 by the execution document's `metadata.wp_version`. |
| `suite_manifest_json` | The validated concrete canonical manifest object, or null when no manifest exists. |
| `suite_manifest_sha256` | Lowercase 64-hex digest of `["wp-bench-suite-manifest",1,suite_manifest_json]`, or null exactly when the JSON is null. |

WS1.1 owns this normalized capability type and its schema-1 built-in policy;
it does not invent or branch on a workstream identity. A manifest validator,
whenever present, maps its versioned raw envelope to this policy. A checked-out
suite or Hub row that declares a manifest but has no validator for that version
fails as unsupported rather than silently using schema-1 defaults. An absent
manifest uses `category,difficulty`, null manifest identity, and schema version
`1.0`; that is not applicable provenance, not unresolved provenance.
For a present manifest, `suite_content_version` must be a nonempty string. Its
semantic extraction from opaque manifest keys belongs to the resolver; the
local loader validates the returned type/presence but does not independently
reinterpret raw keys. The Hub adapter additionally requires every retained
row's transported content version to equal the resolver result.

The callable seam is `SuitePolicyResolver(*, suite_id, suite_manifest_json,
suite_manifest_sha256) -> SuiteDescriptorPolicy`;
`suite_manifest_sha256` is optional for an unhashed local raw file and required
on manifested Hub transport rows. The keyword-only names deliberately match
the policy and transport fields so independently merged producers and
consumers cannot bind the same values under competing APIs. The loader
discovers the raw manifest, calls an injected resolver when one is present,
and verifies the returned suite, manifest object, and digest before normalizing
any task. No global branch probe or milestone registry participates.

The Parquet transport's canonical compatibility field remains `suite`.
Schema-2 rows may additionally carry `suite_id`; if both are present they must
be equal, and the schema-2 exporter writes both. Every row for a manifested
suite carries the same canonical manifest JSON and digest. The Hub adapter
rejects mixed, missing, noncanonical, or digest-mismatched manifest copies
before normalizing a test. This transport rule lets a schema-2 producer and
WS1.1 arrive in either order without allowing two suite identities.

Canonical descriptors may only be derived from fields the Parquet export
preserves. At `77c98d6`, `datasets.py::_merge_metadata` injects
`metadata.suite_metadata` on every locally loaded test while the export drops
it. WS1.1 preserves document source context so a Hub adapter can reconstruct
legacy metadata for consumers, but that raw nested key remains outside the
descriptor contract. For the same reason `benchmark_definition_sha256` covers
the canonical descriptor projection, never the raw merged metadata dictionary:
otherwise a source-only key could diverge the definition digest on all 185
tests and canonicalizing `suite` alone would not restore comparability.

The loader also retains an internal `DatasetRequestIdentity` containing the
exact configured `source`, `name`, `revision`, and `split`, excluding the cache
directory. A precomputed selection may execute only under an exactly matching
request identity, preventing a Hub selection from repository/revision A being
attributed to B without a reload. This request context is not immutable source
provenance and enters no descriptor, selection preimage, catalog, or contract
fingerprint; WS1.3 resolves and records source provenance separately. Local and
Hub catalog parity therefore does not compare this intentionally source-specific
object.

This is a normative equality clause, not an aspiration. For identical suite
content, local and Hub loading produce byte-identical selected-test catalogs,
identical catalog digests, identical per-test `benchmark_definition_sha256`,
`verification_sha256`, and `effective_verification_sha256`, and an identical
`contract_fingerprint_sha256`. A release test loads real `wp-core-v1` content
both ways and asserts that equality. Source-specific identities, the resolved
Hub commit or the local tree digest, are recorded for audit and excluded from
the contract fingerprint, since binding either one would re-split the cohort
the rest of this rule exists to join.

That equality activates in two capability gates. WS1.1 proves identical
normalized catalog objects, universe/catalog digests, and per-test benchmark,
declared-verification, and effective-verification digests. WS1.3, after it can
resolve the remaining fingerprint inputs, injects identical non-dataset
identities and proves the complete `contract_fingerprint_sha256`. Comparing two
staged null fingerprint fields is never evidence of parity.

The run universe is one resolved suite, not every row a source happens to
contain. A source may contain multiple valid suite identities. The Hub adapter
first discards rows whose `test_kind != "execution"` under the existing
transport discriminator. It validates every remaining candidate execution row's
identity shape (including a required nonempty `suite` and equality with
`suite_id` when both exist), then filters by the requested canonical identity.
Valid unrelated-suite rows are ignored and may not perturb the requested
suite; no matching row fails. After filtering, every retained row must resolve
to exactly the requested suite and agree on that suite's manifest, content
version, and execution schema. Without this order, `full` selection means
different things on the two paths as soon as a second suite is exported.

Schema-2 suites must make release focus and WordPress target non-null through a
task value or suite inheritance. Selection and reporting read only these
canonical descriptor fields; `suite.json.smoke_strata` names only canonical
fields. A missing value normalizes to JSON `null`, and `null` is what enters
every digest preimage, including the selection strata. `unknown` is a display
label reporting may show for the null bucket; it is never a hashed value. The
two produce different canonical bytes and therefore different subsets, so a
published hash vector includes a null stratum value to lock the choice.

At `77c98d6`, no suite manifest exists, but that does not make every dimension
null. For the fingerprinted `wp-core-v1` evidence snapshot:

- `release_focus` is non-null for all 185 tasks, with three distinct values
  (`classic` 126, `7.0` 32, `6.9` 27). It comes from task metadata and must not
  be nulled; doing so would collapse workstream 2's required release-focus
  breakdown into a single `unknown` row and discard the split the data was
  authored to express.
- `wordpress_target_version` resolves from the execution document's declared
  `metadata.wp_version`, present in all 29 documents, until `suite.json`
  supersedes it as the inheritance source.
- `runtime_profile` and `coverage_family` are null, because schema 1 has no
  `execution.profile` and no `metadata.coverage.family` to read.

A null `runtime_profile` selects the built-in default profile, which is a real
pinned manifest entry with a real official isolation policy, not an absence.
Selection likewise uses the built-in default strata. Without the default
profile, every clause requiring a resolved profile reference and a
profile-listed isolation identity would be unsatisfiable for the only suite
that exists, and workstream 1 would ship an eligibility policy that returns
false for every run it can ever be given. An absent suite manifest is
therefore "not applicable" rather than "unresolved", and does not raise
`provenance_unresolved`.

Suite-declared strata, suite-declared profiles, and remaining dimensions become
active whenever a validated manifest supplies them. The manifest overrides
built-in defaults; no named workstream, branch, or merge gates that capability.

Isolation is recorded as a structured identity, never as a configuration enum.
The identity belongs to a runtime profile, because different profiles restore
their baseline by different mechanisms and one run-level value could not
describe them:

| Field | Contract |
|---|---|
| `mechanism` | How the baseline is restored, for example `db_reset_reinstall` or `db_template_restore`. |
| `scope` | `per_test` or `none`. |
| `worker_topology` | What each worker owns, for example `shared_runtime` or `database_per_worker`. |
| `identity_sha256` | Canonical digest of `mechanism`, `scope`, and `worker_topology`. |
| `concurrency` | Observed effective worker count. Recorded, not hashed. |

Concurrency is deliberately outside the digest. Hashing it would make every
worker count a distinct isolation identity, so a profile's official policy
would have to enumerate counts rather than mechanisms. The policy instead
names accepted `identity_sha256` values and an accepted concurrency range.

Each entry in the `runtime_profiles` map carries its own isolation identity,
and each record's `provenance_checks` references the identity it actually used.
The run-level `policies` entry is the digest of that map, not a single
identity.

The frozen `db30867` branch snapshot independently demonstrates an adapter from
flat legacy metadata into this structure:

```json
{"runtime_isolation": "reset_per_test",
 "execution_concurrency": 4,
 "isolation_pooling": "database_per_worker"}
```

The fields above are that legacy object plus a digest: `runtime_isolation` maps
to `scope`, `isolation_pooling` to `worker_topology`, and
`execution_concurrency` to `concurrency`. `mechanism` is separately required
because two runtimes can provide the same scope and topology through different
reset behavior. This mapping is evidence for a legacy adapter, not a required
producer API.

An official runtime profile names the isolation identities it accepts. Changing
the reset mechanism or the worker topology changes the recorded identity by
construction. A run cannot inherit or forfeit official status from the
`run.execution_isolation` value alone, and an unlisted identity is
`isolation_unofficial` rather than a silent pass.

Profile policies are capability registries, not forecasts. `single_site` is
the built-in default profile. Its initial registry may admit the following
identities only when the same revision includes a producing runtime fixture and
the release test proves the stated behavior:

| mechanism | scope | worker_topology | concurrency |
|---|---|---|---|
| `db_reset_reinstall` | `per_test` | `shared_runtime` | 1 |
| `db_template_restore` | `per_test` | `shared_runtime` | 1 |
| `db_template_restore` | `per_test` | `database_per_worker` | 1 to 16 |

Rows unsupported by the checked-out runtime are dormant schema capabilities,
not release obligations and not accepted identities for a run. Pooled
isolation is eligible when activated and proven because handing each
concurrent test a database no other test touches is a stronger guarantee than
time-slicing one database serially, not a weaker one.

A release test asserts both directions for active official capabilities: every
identity produced by an active official profile fixture appears on that
profile's accepted list, and every active accepted identity has an official
producing fixture. The test fails naming either orphan. The harness may produce
and record other structured identities, but they remain ineligible with
`isolation_unofficial`; observing one never expands the accepted registry.
Adding or changing an official reset mechanism or worker topology adds its
fixture and policy entry in the same change. That scoped bidirectional
invariant, not branch state or this illustrative table, is the durable
contract.

`contract_fingerprint_sha256` has an enumerated preimage, not a described one.
It covers exactly: `mode`; the selected catalog and its order; the selected
suite's benchmark snapshot; the record, event, envelope, and scoring contract
versions; the grading-dimension policy; the continuation policy; the
`runtime_profiles` map digest including each profile's isolation identity;
every selected grader, runtime profile, and engine identity; the
behavior-affecting harness digest; the interpreter identity; and the
behavior-affecting resolved dependency map. It excludes reporting code,
notebooks, documentation, and unrelated suites. Listing the members matters
because an earlier draft placed the recovery budget inside `policies` while
enumerating a preimage that omitted the continuation policy, and an
implementer could satisfy both readings with opposite cohort behavior.

`run.max_test_reattempts` is in `config_sha256` and deliberately not in the
contract fingerprint. Under mandatory generation reuse a recovery can only
convert an ungraded error into a grade of the same draw, and standard-track
eligibility already requires `score_complete`, so among eligible units the
budget provably cannot change the set of graded artifacts. That exemption is
conditional on reuse: if recovery ever re-generates, the budget alters the
sampled distribution and must enter the fingerprint.

`config_sha256` is maintained by the same fail-safe rule as the source
allowlist. Any `RunConfig` field not on an explicit exclusion list, which
contains output paths and secrets only, is behavior-affecting and enters the
digest, enforced by a release test.

Exclusions are path-level and whole-file. A path is excludable only if the
entire file is excludable; sub-file or per-function classification is
forbidden, because it cannot be mechanically checked and it invites exactly
the mistake an earlier draft made in calling the CLI presentation-only.
`python/wp_bench/cli.py` is behavior-affecting and is included: it writes
`run.limit`, `run.seed`, `run.test_ids`, `run.suite`, `dataset.name`, and the
skills configuration; `_normalize_test_ids` defines the selected universe; and
it performs mode dispatch, model-set construction, and flag-combination
validation. The spec elsewhere makes the CLI normatively responsible for
deriving no exit code of its own, which it could not be if it were
presentation. It stays included until a real refactor moves rendering into a
separate module, at which point the rendering module, not a region of
`cli.py`, becomes excludable.

Excludability is a testable predicate rather than an editorial judgment. An
excluded module imports nothing from `wp_bench` at runtime, mutates no
configuration object, and calls no selection, dataset, record, writer,
integrity, or provenance API. At `77c98d6`, `output.py` satisfies it and
`cli.py` does not. The release test asserts the predicate for every excluded path in
addition to failing on unclassified ones.

The allowlist is maintained fail-safe rather than best-effort: any source path
that no allowlist entry classifies counts as behavior-affecting, so a new
module splits cohorts until a human decides it should not. Wrongly splitting
two identical cohorts is visible and recoverable; silently merging two cohorts
whose behavior differs is neither.

The digest is computed over a package-relative path and content Merkle of the
importable `wp_bench` package, which is identical whether the package is read
from a checkout or from an installed distribution. The tracked-tree walk is
the release-time completeness test, not the digest input. Defining the digest
over tracked paths alone would leave it without a preimage in exactly the
repository-less installation this spec elsewhere supports.

Each manifest unit also has a
`planned_subject_fingerprint_sha256` that adds requested model configuration,
generation parameters, variant, and skill hashes while excluding `run_id`,
`unit_id`, and `trial_index`.

Provider-resolved model identity may only become known after generation. The
final unit aggregate therefore carries `resolved_subject_fingerprint_sha256`,
computed from the planned subject plus the internally consistent observed
provider/model snapshot and all response-confirmed behavior-affecting effective
parameters. Inconsistent effective parameters or model snapshots within one
unit are an identity failure. The resolved fingerprint is null when no
immutable identity can be proven.
Reporting uses the contract fingerprint for comparability and the resolved
subject fingerprint for eligible repeated-trial grouping. It may group
unresolved diagnostics by planned fingerprint only with a visible warning.

Version 1 manifests reserve `trial_index` even when the only producing
capability sets it to one. A later producer may activate repeated trials
without changing the unit identity contract.
`pair_id` is generated once for each intended baseline/treatment pair and is
shared by exactly those two units. It is never derived from model name or trial
index, and never inferred from two artifacts happening to share a model. A pair
whose baseline arm was executed by an earlier run is expressed by pairing an
`executed` unit with a `sourced` one inside a single sealed manifest, which is
the explicit mapping such a pair requires.

The manifest validator rejects any non-null `pair_id` that does not group
exactly two units with the same actor and `trial_index`, variants
`{baseline, skills}`, and either two executed sources or one executed plus one
sourced unit. Every sourced unit names exactly one external reference, and
every external reference is named by exactly one sourced unit; singleton,
overfull, two-sourced, incompatible, missing-reference, and orphan-reference
groups are invalid before any attempt begins.

## Sourced run units

Cross-artifact baseline reuse, if a producer supports it, saves money and wall
clock only when it preserves the earlier arm's identity. It must never copy the
earlier run's graded records into the new run's artifact. From the moment
records carry a `run_id`, those records are foreign to the artifact holding
them, and the writer's only two copying options are both illegal: keep the
original `run_id`, and the reader rejects the input; rewrite it, and the
artifact asserts a provenance falsehood and breaks `attempt_id`, which is
derived from the run.

A run unit therefore declares a `source`:

- `executed`: this run generated and graded it. The default, and the only kind
  a benchmark run without declared external unit references contains.
- `sourced`: the unit's records live in another artifact and are referenced,
  never copied.

Each `sourced` unit names an `external_unit_refs` entry carrying `ref_id`,
`source_run_id`, `source_unit_id`, `source_semantic_envelope_sha256`, and the
source's `contract_fingerprint_sha256`.
`source_semantic_envelope_sha256` is the exact
`semantic_envelope_sha256` of the normalized sealed source representative; it
is never a raw-file digest.

External-reference resolution is ordered and exact:

1. Parse, detect, version-check, and normalize every input; then apply canonical
   sibling equivalence and prefix supersession to choose one surviving
   representative per semantic source.
2. Match the declared `source_run_id` and
   `source_semantic_envelope_sha256` against those surviving sealed
   representatives. The matched source manifest must contain exactly one unit
   with `source_unit_id`.
3. Require the declared source contract fingerprint to equal the source
   manifest's value. Pair comparability additionally requires that value to
   equal the owning manifest's contract fingerprint.
4. Zero matches, multiple semantic matches, a missing/duplicate unit, or any
   digest/fingerprint mismatch fails the declared relation with a stable code;
   the reader never searches for a substitute arm.

The contract fingerprint is strictly stronger than checking scoring and record
schema versions plus test-id equality, because it also covers the selected
catalog and its order, the harness execution contract, the grader and runtime
identities, and the isolation identity. Two runs that agree on it are
comparable; two that do not are not, whatever their version strings say. A
filesystem path is not a reference: it is not portable, it is not
content-addressed, and it puts a developer's home directory in a file meant to
be shared.

Counts and completeness are computed over `executed` units only. Without that
rule a sourced unit contributes its planned count with no terminal records, so
`missing` equals `planned`, and a successful iteration of the workflow reports
as `completed_with_errors` and exits 1. Sourced units still appear in
`aggregates`, so a reader can see the comparison arm; a run that hides them
would be indistinguishable from a skills-only run, which is exactly the input
reporting may never use to manufacture a comparison.

A run containing any `sourced` unit is never eligible: reason
`unit_sourced_externally`, and a stable warning on the pair. This workstream
introduces `load_result_envelopes(paths)` as the sole place that resolves the
declared relation at read time; no consumer infers a pair from filenames,
actors, test IDs, trial indices, or coincidentally matching inputs.

## Sealed audit plan

Audit denominators cannot be recovered from a partial stream unless they are
sealed. A digest alone yields no candidate count, and a denominator stored only
in a terminal event is absent from an interrupted audit. That contradicts this
workstream's own rule that a partial stream identifies every planned unit and
exact missing count. Reopening the dataset is not a fallback: any source that
lacks the required maintainer-QA capability fails audit preflight rather than
claiming coverage it cannot reconstruct.

`audit_plan` is non-null exactly when `mode` is `exploit_audit`, is sealed
before the first candidate executes, and enters `contract_fingerprint_sha256`
in audit mode. It contains `plan_schema_version`; `candidate_stop_policy`;
`exploit_battery_version` and `exploit_battery_sha256` over the ordered
`(candidate_id, template)` pairs the generic generator produces; the resolved
maintainer-QA source identity and its snapshot digest; and one `tests[]` entry
per selected test, in catalog order.

Each `tests[]` entry carries `test_id`, `gateway_function` (null when the test
declares none), `planned_candidate_count`, `applicable_candidate_count`,
`auditable` (`applicable_candidate_count > 0`), and an ordered `candidates[]`.
Each candidate carries `execution_index`, a `candidate_id` that is stable under
reordering rather than the positional `authored-{i}` label used at `77c98d6`, `source`
(`generic_battery` or `authored`), `artifact_kind`,
`candidate_definition_sha256`, `applicable`, a `not_applicable_reason` that is
null exactly when applicable, and `expected_failure` (null under schema 1).
The plan stores digests of authored candidates and never their source text, so
an audit manifest can be inspected or exported without leaking QA content.

Applicability is decided at seal time from the test definition alone and is
never re-decided during execution. A runtime disagreement with the sealed plan
records `audit_plan_drift`, halts that test, and never silently reclassifies a
candidate.

`candidate_stop_policy` is `exhaustive` by default. Under `first_exploit`,
every candidate after the first `exploitable` is recorded `not_attempted` with
reason `superseded_by_exploit` and is excluded from `required_candidates`, so a
proven-exploitable test still reports full candidate coverage. Exhaustive
auditing costs nothing on a healthy suite, where no cheat passes and every
candidate runs under either policy; it buys a denominator that is static from
seal time and a report of every cheat that works rather than only the first.
The metric is comparable only within one policy, so the policy is reported
beside it.

Audit preflight fails closed. When the QA data the plan requires cannot be
resolved, the run terminates `failed` with `maintainer_qa_unavailable` rather
than sealing a plan with silently missing candidates. Running
`--check-exploits` against a Hub source is exactly this case. A sealed plan in
which every test has zero applicable candidates is likewise a preflight
failure, not a passing zero-coverage audit that exits 0.

`run.max_test_reattempts` is forced to 0 and recorded as such for audit mode.

## Canonical terminal record

Every planned `(unit_id, test_id)` has at most one terminal `ResultRecord`. A
bounded recovery may additionally emit non-terminal attempt records for the
same pair; only the last attempt is terminal.

| Field | Contract |
|---|---|
| `schema_version` | Record version `3.0`. |
| `run_id`, `unit_id`, `attempt_id` | Stable linkage; `attempt_id` is deterministic from run, unit, and test IDs plus a zero-based `attempt_ordinal`, so a recovered error keeps both attempts addressable. |
| `terminal` | Whether this attempt is the pair's terminal record. |
| `test` | Manifest descriptor plus preserved task metadata. |
| `actor` and `variant` | References to the manifest unit. |
| `input` | Prompt hash, prompt-template reference, dataset `verification_sha256`, `effective_verification_sha256`, artifact kind, and normalized execution plan/profile/scope/engines. Both digests are copies of the sealed catalog entry for this `test_id`. |
| `output` | Raw completion, normalized artifact, artifact digest, `generated_by_attempt_ordinal`, and `generation_reused`; null until generation completes. |
| `outcome` | State, stable reason code, failing stage, and sanitized error. |
| `scores` | Execution scores; non-null exactly when the outcome is `passed`, `failed`, or `diagnostic`, and null for every errored and every audit record. |
| `diagnostic_scores` | Scores that were produced but must never be aggregated. Mutually exclusive with `scores`; see the cleanup rule below. |
| `assessment` | Discriminated execution or exploit-audit details, including candidate-level audit outcomes. |
| `grader` | Overall verifier result plus ordered phase results, cleanup outcome, timeout, bounded stdout/stderr, and verifier version. |
| `telemetry` | Model-call outcome, usage, retries, stage timings, and coverage. |
| `provenance_checks` | Per-attempt actor checks and references to the exact manifest runtime-profile and engine identities used. |
| `extensions` | Empty object in record version 3.0. |

Two verification digests are recorded because the dataset contract and the
executed contract are not the same object. `verification_sha256` is the
dataset-declared assertion set and execution plan, and is the comparability
anchor.

`effective_verification_sha256` covers the post-policy verification
specification only, through the exact four-key projection and domain-separated
preimage above. For schema 2 the `execution` and check trees contain the plan,
profile, scope, engines, phases, setup, and teardown. The projection is built
after `run.skip_static` and `run.skip_runtime` are applied and after the
derived weight-0 `function_exists` gateway assertion is prepended. Its preimage
must not include the candidate artifact, the generated code or files, the
candidate directory token, or the verifier transport envelope. An earlier draft
said it covered "the payload the verifier received", which literally includes
the model's own generated code: that digest would change for every model on
every attempt, destroying its purpose as a contract digest and making the
eligibility clause that compares it unsatisfiable by construction. The exact
verifier request can be reconstructed only while the sealed effective
verification specification, retained normalized artifact content, and
verifier `payload_version` are available. Their digests authenticate those
components but cannot reconstruct bytes.

Because it depends only on the sealed test definition and run-level skip
policy, the digest is computed once at manifest seal and stored on the
selected-test catalog entry. It is byte-identical across every unit, variant,
trial, and attempt of a run, and it is non-null on every record regardless of
outcome, including errors at generation, artifact parsing, runtime reset, and
environment setup, because its value never depended on the verifier being
invoked. A record whose value differs from its catalog entry is a reader-level
integrity failure in the same family as a duplicate or foreign record, not a
grading signal.

Divergence is classified at seal time rather than inferred by comparing
digests. Each catalog entry carries `verification_divergence`, one of `none`
(no semantic change), `gateway_only` (gateway assertion added, nothing
dropped), or `dimension_skipped` (run policy emptied a nonempty
dataset-declared dimension). A skip applied to an already empty dimension does
not create divergence. Before each verifier invocation the harness rebuilds the
specification and asserts that it digests to the sealed value; a mismatch is
`errored` at `verification_contract_drift`, halts the affected runtime profile,
and never rewrites the manifest. Without that assertion, structural
impossibility is an aspiration rather than an invariant.

No execution plan, present or future, may derive assertion content, phase
names, phase ordering, setup, or teardown from the candidate artifact. This is
what keeps seal-time determinism true for workstream 3's lifecycle, theme,
multisite, and browser plans, and it is normative rather than an emergent
property of an implementation's plan matrix. An unparseable `test_function` signature
becomes a preflight failure, before any paid call, because the gateway name
must resolve in order to seal the catalog.

Execution outcomes are:

- `passed`: fully graded strict pass.
- `failed`: fully graded strict failure, including invalid model artifacts and
  verifier timeouts.
- `errored`: provider, reset, transport, or harness failure prevented grading.
- `diagnostic`: intentionally skipped grading dimensions prevent a strict
  score.

`passed`, `failed`, and `diagnostic` are terminal on first attempt. Only an
`errored` outcome whose failing stage is on the recoverable list may be
re-attempted; the list is closed and appears under bounded per-test recovery.

Audit records use the same common shape and an audit assessment. An audit with
no applicable negative candidate records `not_auditable` in the assessment,
not as an execution score.

`grader.phases` reserves multi-process execution in record version 3.0. Every
phase contains `phase_id`, lifecycle action, engine/profile references,
fresh-bootstrap identity, start/end timestamps, duration, remaining task
deadline, outcome, assertions, and bounded diagnostics. `grader.cleanup`
contains attempted/succeeded, duration, recovered resources, and any error.
Single-process snippet execution is represented as one `execute` phase, so
consumers never need a second shape when future execution-plan capabilities add
more phases.

An exploit-audit assessment contains one item for every PLANNED candidate,
applicable or not and attempted or not, so a single record yields the
applicable count, the outcome partition, and the test classification without
consulting the manifest. Each item carries a stable `candidate_id`, artifact
kind, candidate-definition digest, the applicable/attempted/completed flags,
an outcome, execution stage, stable reason code, matched and failing assertion
IDs, and a sanitized error.

Candidate outcomes are `rejected`, `exploitable`, `not_applicable`,
`audit_error`, and `not_attempted`. The flags are derived, not independently
authored: `applicable` is false exactly for `not_applicable`, `attempted` is
true exactly for `rejected`, `exploitable`, and `audit_error`, and `completed`
is true exactly for `rejected` and `exploitable`. Every `not_attempted` item
carries a reason: `superseded_by_exploit`, `run_aborted`, or `profile_halted`.

The test-level classification is built from two booleans that are stored
explicitly, never inferred from each other's absence. For a test with
applicable candidate set A:

- `has_exploit` is true when some candidate in A is `exploitable`;
- `audit_complete` is true when `has_exploit` is true, or when A is non-empty,
  every candidate in A is `rejected`, and the record itself did not error.

`has_exploit` therefore implies `audit_complete` unconditionally. That
implication is the entire reason every audit numerator lands inside its
denominator, and the writer rejects any record that violates it. A passing
cheat is a final verdict that no later candidate can overturn, so a proven
exploit discharges completeness under either stop policy.

The test-level outcome is assigned by first match in this exact order:

1. `exploitable`, when `has_exploit`;
2. `audit_error`, when the record errored or any applicable candidate is
   `audit_error` or unresolved `not_attempted`;
3. `not_auditable`, when A is empty;
4. `audited_safe` otherwise.

Equivalently, `audit_complete` is true exactly when the outcome is
`exploitable` or `audited_safe`. Without this precedence a test with one
exploitable candidate and one errored candidate has three admissible
classifications, and the two plausible choices are both wrong: filing it as
`audit_error` hides a proven exploit behind an infrastructure failure, which is
the exact defect observed at `77c98d6`, while filing
it as `exploitable` under the old definition put the numerator outside its
denominator and rendered a proven finding as a null rate.

A rejected candidate is not equivalent to a candidate that failed to execute.
Audit test-level outcomes map to record outcomes as follows: `audited_safe`,
`exploitable`, and `not_auditable` are `diagnostic`; test-level `audit_error`
is `errored`. `passed` and `failed` never occur in audit mode, `graded` is
zero, and `score_complete` is null rather than false.

An audit run may not classify any test `audited_safe` when its
`verification_divergence` is `dimension_skipped`: a cheat that was never
checked against the skipped dimension proves nothing. Either those tests are
`audit_error` with reason `grading_dimension_skipped`, or audit mode rejects
the skip flags at configuration validation. The eligibility-based safeguard
does not apply here, because audit units are never eligible in the first place.

An invalid completion is a model failure, not a harness error. Conversely, a
missing executable, reset failure, or provider exception must not be invented
as a zero execution score.

`scores` and `diagnostic_scores` are mutually exclusive, enforced by the schema
alongside the zero-denominator rule on `Metric`. The second field exists for
one situation: grading produced dimension results and then something
invalidated the environment they were produced in, which is a cleanup failure,
or an identity drift detected after the verifier returned. Those records are
`errored`, so `scores` must be null, yet the assertion outcome is real evidence
and discarding it would lose the only diagnosis of what the artifact did before
cleanup failed. A separate field rather than a `usable=false` flag on `scores`
makes accidental aggregation a typo rather than a missed boolean.
`diagnostic_scores` never contributes to any numerator, denominator, count,
metric, completeness flag, or eligibility-bearing statistic, in this workstream
or any consuming one.

A verifier timeout is not this case: it stays `failed` with ordinary non-null
`scores`, because the runtime returned a structured result and the environment
remained valid. Cleanup precedence is normative in the other direction: a
failed cleanup sets `errored` at `artifact_cleanup` even when every phase
passed and every assertion succeeded.

The record's `outcome` is authoritative for every count and metric. A consumer
may not derive pass or fail from `assessment`, `grader.phases`, or
`grader.success`, and reference-mode failure detection reads `outcome` rather
than looking up a score.

## Canonical envelope

The final `ResultEnvelope` contains:

```json
{
  "schema_version": "3.0",
  "manifest": {},
  "status": {},
  "completeness": {},
  "aggregates": [],
  "records": [],
  "failure": null,
  "extensions": {}
}
```

- `manifest` is canonical-digest equal to the `payload` of the first JSONL
  event. It is not byte-equal: the event wraps the payload in envelope fields,
  so the two objects have different key sets and no serialization can make them
  identical.
- `status` contains state, reason code, start timestamp, and, when the writer
  produced them, end timestamp, duration, and exit code. A reader-produced
  envelope, from an unfinalized stream or a legacy artifact, leaves those three
  null and raises `status_unverifiable`.
- `completeness` contains run-wide counts only; it never averages scores
  across models or variants.
- `aggregates` contains exactly one ordered item per run unit.
- `records` holds every attempt, terminal and superseded, sorted by
  `(unit_id, test_id, attempt_ordinal)`, which is a total order because at most
  one record exists per triple.
- `failure` is reserved for systemic failure or user abort.

Every count, metric, score, completeness flag, and eligibility decision is
computed over TERMINAL records only. Superseded attempts contribute to
`reattempted`, `recovered`, `usage`, and `telemetry`, and to nothing else.
Leaving this unstated would let one implementation count three recovered errors
into `errored` while its own `status.state` reads `completed`, and would break
the completeness identity below.

Each `RunUnitAggregate` has this normative shape:

| Field | Contract |
|---|---|
| `unit_id` | Manifest unit reference. |
| `actor`, `variant`, `trial_index`, `pair_id` | Unit identity fields copied from the manifest, canonical-digest equal to it. |
| `status` | Unit state and stable reason code. |
| `planned_subject_fingerprint_sha256` | Requested subject identity from the manifest. |
| `resolved_subject_fingerprint_sha256` | Post-run immutable subject identity, or null with a warning. |
| `counts` | Planned, terminal, graded, passed, failed, errored, diagnostic, missing, reattempted, recovered, unusable_scored, and audit-candidate counts, all over terminal records. |
| `metrics` | Denominator-bearing execution or audit metric objects. |
| `usage` | Token/cost/latency totals over ALL attempts, plus per-field coverage counts. |
| `telemetry` | Attempted/completed model calls and stage timings over ALL attempts. Attempted calls may exceed `planned` by at most the number of superseded attempts that re-called the provider. |
| `eligibility` | Policy version, track, verification, eligible flag, and stable reasons. |
| `audit` | Null for execution; otherwise required/completed/error candidate counts and test-level audit outcomes. |
| `warnings` | Stable unit-scoped integrity warnings. |

`run_terminal.payload` is exactly `{status, completeness, aggregates,
failure}` using the same objects as the final envelope. Folding a finished
event stream therefore reconstructs the envelope without re-running scoring or
integrity policy.

Writer-produced terminal states are `completed`, `completed_with_errors`,
`failed`, and `aborted`. `interrupted` is reader-synthesized for an open
stream, is never written by any writer, carries a null exit code, and does not
appear below. Reference failures and exploit findings are completed workflows
with nonzero exit codes, not infrastructure failures.

`status.exit_code` is normative, so the CLI derives no exit code
independently. At `77c98d6`, the mapping is scattered across `SystemExit` and
`typer.Exit` call sites. It becomes an ordered precedence list, evaluated
top-down, because a table of independent rows is neither disjoint nor total: a
user interrupt of a run that had already recorded errors matches two rows with
different codes, and a clean reference or audit run matches none.

1. `aborted`, user interrupt: 130.
2. `failed`, preflight or systemic failure: 1.
3. `completed_with_errors`, any terminal errored or missing attempt: 1.
4. `completed` with reference failures or exploit findings: 1.
5. `completed`, no findings: 0.

Rules 4 and 5 are mode-independent: a benchmark run has no findings to report,
so it falls through to 5 by construction.

Three classes of exit are outside the envelope contract, and the spec says so
rather than implying an artifact that cannot exist. Configuration, skills,
dataset, and selection failures occur before the manifest is sealed, so no
envelope and no `status` can describe them; argument-combination validation is
the same. These exit 1 and are CLI-owned. A `--dry-run` invocation seals no
manifest and grades nothing; it exits 0 and is CLI-owned. Automation moving
from exit codes to `status.state` must therefore still treat "no artifact was
written at all" as a distinct outcome. The rule that only an output-directory
failure cannot record itself is scoped to failures occurring after selection
resolves.

`completed_with_errors` exiting 1 is a deliberate behavior change: at
`77c98d6`, a `continue_on_error` run that recorded errors exits 0, so automation cannot
distinguish a fully graded run from a partly graded one without parsing the
artifact.

Run units and their aggregates are always ordered lists. Display names are
labels, never map keys or identifiers. A single run is simply a one-unit list;
skills, trials, and multi-model runs add units without changing shape.

## JSONL event stream and artifact lifecycle

Each JSONL line has `event_schema_version`, `run_id`, a monotonically
increasing `emitted_sequence`, `event_type`, `emitted_at`, and `payload`.

Event types are:

- `manifest`: exactly once and first.
- `attempt`: one superseded non-terminal attempt record, emitted only by
  bounded recovery.
- `result`: one canonical terminal record.
- `run_terminal`: status, per-unit aggregates, completeness, and any systemic
  failure. Per-unit eligibility already travels inside `aggregates`.

Well-formedness, checked by the reader on every stream: `manifest` appears
exactly once and first; `run_terminal` appears at most once and, when present,
last, and any event after it fails the input; `emitted_sequence` is strictly
increasing; a repeated sequence number whose `(emitted_sequence, event_type,
payload digest)` triple is identical collapses to one event, while a repeated
number with a differing triple fails the input; a record whose `run_id` differs
from the manifest's fails the input.

`RunArtifactWriter` owns the sequence counter, and sequence assignment and the
file append happen inside the same critical section. Holding a lock around the
counter alone would let a thread that took a lower number lose the race to
write, producing a file whose sequence numbers decrease while every individual
assignment was correctly serialized. This replaces the `77c98d6` arrangement, where
`MultiModelRunner` shares one `RecordStream` across per-model runners holding
separate locks and is safe only because models happen to run sequentially.
Whenever a run grades more than one test at a time, whether through
`execution_isolation: none` or through a per-worker database pool, the counter
orders events by append time, so `emitted_sequence` is monotonic in the file
while records within a unit may complete out of test order. The writer's
contract does not name a concurrency ceiling and does not assume one: a run
that grades serially is the degenerate case of the same rule.

Lifecycle:

1. Validate config, skills, dataset, IDs, selection, and resolvable provenance.
2. Preflight the runtime and collect observed identities. On a handled
   preflight failure, seal an unresolved manifest and continue directly to a
   failed terminal event.
3. Seal the manifest and append it before the first graded attempt.
4. Build an `AttemptContext` for every planned attempt. It accumulates prompt,
   model response, artifact, reset, grader, score, and timing information.
5. Convert success or exception into a record and append it. An `errored`
   record with recovery budget remaining is appended as a non-terminal
   `attempt` event, and the test returns to step 4.
6. Only after the terminal record is durable, apply continue, abort, or
   systemic-failure policy.
7. Seal and finalize, in this declared order: (7a) compute counts, metrics,
   resolved identities, eligibility, and terminal status, and append that exact
   `run_terminal` payload; (7b) validate the reconstructed envelope; (7c) write
   final JSON atomically; (7d) write final JSONL atomically.
8. Unlink the live stream only after both final artifacts are committed.

Step 7a appends the terminal event to the live stream, so from that moment the
live file is a complete event stream that happens to still be named
`.partial`. This deliberately reverses the `77c98d6`
`RecordStream.finalize`, which unlinks before `os.replace` so that a partial
never sits beside a finished artifact. That order can lose both files if the
process dies between the unlink and the replace, leaving only a `.tmp`. Under
the order above, the states in which a live stream coexists with one or both
final artifacts are expected, not anomalies.

A handled failure produces a finalized artifact with `failed` or
`completed_with_errors`. A hard kill leaves a live `.jsonl.partial`.

Classification is by content, never by filename. A *sealed* stream contains a
`run_terminal` event; an *open* stream does not. A final `.json`, a final
`.jsonl`, and a `.jsonl.partial` may each be sealed or open, so every rule
below is written in those terms rather than in terms of the file suffix.

Torn-line tolerance follows from how the bytes are written, not from the name:
`.jsonl.partial` is the only file appended to in place, by one unbuffered
`os.write` per record, so it is the only file that can be torn. The final
artifacts arrive by `os.replace` and cannot be. At most one malformed FINAL
line may be dropped, and only from a live stream; malformed content anywhere
else, or anywhere but the last line, fails the input. A torn `run_terminal`
line is dropped whole, with no partial-credit parse; the stream is then open
and yields `interrupted`.

Both live and final JSONL preserve append order: manifest first, records in
completion order, terminal last. `emitted_sequence` is therefore monotonic in
every stream, and canonical sorting happens only in `ResultEnvelope.records`.
Records carry no position field: a `canonical_position` would exist only in the
final JSON, which would both fail strict record validation and make a writer's
own JSON and JSONL siblings non-equivalent.

Sealed is a projection property, not an event requirement. A validated final
canonical JSON envelope with a terminal run state is sealed; a canonical JSONL
or live stream proves the equivalent terminal projection with `run_terminal`.
Both receive a non-null `semantic_envelope_sha256`. Only an open projection has
a null semantic digest.

These are the reachable states and what the reader must produce for each:

| State | On disk | Reader output |
|---|---|---|
| Kill before the manifest is appended | Nothing | No artifact exists; nothing to read. |
| Kill after manifest, before or during results | Open stream | `interrupted`; planned units and tests from the manifest; `terminal` = records present; `missing = planned - terminal`; no metrics, no scores, no eligibility. |
| Kill mid-record | Open stream, torn last line | Drop the torn line, then as above. |
| Kill after 7a, before any final write | Sealed live stream, no sibling | Fold to a complete envelope with the written terminal state, never `interrupted`; assign `semantic_envelope_sha256`; warn `artifact_not_finalized`. |
| Kill between 7c and 7d | One final artifact plus a sealed live stream | Both sealed and equivalent; deduplicate to one. A legal state, not an error. |
| Kill after 7d, before unlink | Two final artifacts plus a sealed live stream | All three equivalent; deduplicate to one silently. This is the expected residue of step 8. |
| Live stream strictly extends a final artifact | Both, non-equivalent | Retain as a diagnostic input, warn `finalized_artifact_lost_records`, exclude from scoring and from the group's representative. |

An open stream produces no metrics, no scores, and no eligibility: it fails
closed. A sealed live stream produces a full envelope but is not eligible,
because step 7b never validated it.

Deduplication uses two distinct relations, which are never computed with the
same hash, because prefix-ness is a property of an event sequence while
equivalence is a property of a projection only a sealed stream has.

*Envelope equivalence* applies to every sealed input, including a sealed live
stream. The reader computes `semantic_envelope_sha256` from the normalized
envelope after discarding serialization-only event order and file-format
fields. Sealed inputs sharing `(run_id, semantic_envelope_sha256)` are
equivalent and deduplicate to one. `semantic_envelope_sha256` is non-null for
every sealed input and null for every open one.

*Prefix supersession* applies to open streams. An open stream is superseded and
dropped silently, with no warning, when its ordered `(emitted_sequence,
event_type, payload digest)` triples are a prefix of the sealed
representative's, ignoring that representative's trailing `run_terminal`.
Because an open stream lacks the terminal event it can never equal a sealed
one, so the prefix is necessarily strict.

Failure blast radius is a ladder, and each rung is deliberately narrow:

1. An input that fails to parse, detect, version-check, or satisfy
   well-formedness fails ALONE and never joins a run-ID group. Corrupt is not
   the same as conflicting: a file that cannot be normalized has no envelope to
   be non-equivalent to.
2. An open stream that diverges from a sealed sibling fails ALONE, with
   `partial_diverges_from_finalized`. It never quarantines the sealed sibling.
3. Sealed-versus-sealed non-equivalence within one run ID quarantines every
   sealed input of that group, with `same_run_conflicting_envelopes`. There is
   no first-wins, no majority vote, and no newest-file rule, because no input
   in a symmetric conflict is knowably authoritative and any tie-break would
   make the result depend on argument order.
4. Nothing fails the report. The report renders the surviving inputs, lists
   every failed input by path with a stable code, and exits nonzero.

The open-versus-sealed asymmetry at rung 2 is normative and is why the
quarantine at rung 3 is not applied uniformly. A sealed artifact was validated
before it was written; an open stream is the file the writer intended to
delete. Letting a stale or damaged live stream quarantine a good finalized
artifact would be exactly the "one corrupt file denies a good one" harm the
ladder exists to prevent.

When several sealed inputs in a group are equivalent, the surviving
representative is chosen by fixed precedence, final JSON then final JSONL then
live stream, and both the choice and the collapsed paths are recorded. This
keeps deduplication independent of argument order and directory listing order.

Legacy artifacts carry no `run_id`, no `emitted_sequence`, and no `event_type`,
and their final JSONL is canonically sorted while a legacy partial is in
completion order, so neither relation is computable for them. Legacy inputs
therefore never deduplicate, and supplying both a legacy JSON and its JSONL
sibling raises `legacy_possible_double_count`. The alternative, keying them by
directory and filename timestamp, is the filename heuristic this section
otherwise forbids.

## Limited selection contract

Effective selection kinds are:

- `full`: selected IDs exactly equal the dataset universe.
- `limited_smoke`: `limit` creates a proper subset.
- `explicit_smoke`: explicit IDs create a proper subset.

An explicit list or limit that covers the complete universe is effectively
`full`. Proper subsets are always smoke-only and leaderboard-ineligible.

The selection algorithm is `stratified-hash-round-robin/2`:

1. Reject duplicate test IDs.
2. Read the suite's ordered `smoke_strata` fields when a validated manifest
   supplies them; otherwise use the versioned built-in default
   `category,difficulty`. The strata list is part of both hash preimages, so a
   source that declares different strata produces a different, and correctly
   incomparable, subset without depending on when manifest support lands.
3. Group tests by the normalized values of those fields.
4. Let `strata_pairs` be the ordered JSON array containing one
   `[field_name, normalized_value]` pair per suite-declared stratum. Encode the
   group preimage as RFC 8785 JSON Canonicalization Scheme bytes for
   `["wp-bench-selection-group",2,seed,strata_pairs]`. Rank by SHA-256 bytes,
   with the canonical preimage bytes as a collision tie-breaker.
5. Encode the test preimage as RFC 8785 bytes for
   `["wp-bench-selection-test",2,seed,strata_pairs,test_id]`. Rank by SHA-256
   bytes, with canonical preimage bytes as tie-breaker.
6. Drain ranked groups round-robin until the limit is reached.
7. Store the selected catalog in stable test-ID order.

This is independent of dataset row order, file order, and Python PRNG details.
It improves smoke breadth but makes no statistical representativeness claim.
Documentation and console output must use “smoke,” never “representative.”

`difficulty` earns its place in the built-in default through the immutable
selection regression fixture derived from `77c98d6`: its additional strata
materially broaden small smoke selections. The field remains a nullable
canonical descriptor even when a legacy writer or transient runtime object
omits it. A source lacking the value normalizes it to JSON null, and that null
is included in selection and contract hash preimages; reporting alone displays
the null stratum as `unknown`. The selection vectors include this canonical JCS
preimage and expected SHA-256:

```text
["wp-bench-selection-group",2,0,[["category","plugins"],["difficulty",null]]]
517d5dd0a8909e0bd38dc0f19d3a0362654f107fa7d8882c1cdb1dbf9f35ea02
```

A requested selection option must either affect the sealed selection plan or
be rejected before manifest creation. A producer must never accept, display,
or record a limit or seed that it does not consult. Removing a selector option
therefore removes its config field, CLI surface, and metadata together; keeping
one requires an end-to-end test from request through selected catalog.

## Counts, metrics, and completeness

Per-unit counts are derived from the manifest:

- `planned`
- `terminal`
- `graded = passed + failed`
- `passed`
- `failed`
- `errored`
- `diagnostic`
- `missing = planned - terminal`
- `reattempted`, the number of tests with more than one attempt
- `recovered`, the number of tests whose earlier attempts errored and whose
  terminal attempt graded
- `unusable_scored`, the number of terminal records carrying
  `diagnostic_scores`, reported beside `errored` and never added into `graded`,
  `passed`, `failed`, or any rate
- `record_complete = terminal == planned`
- `score_complete = graded == planned` for benchmark/reference units, and null
  for audit units

Every count above is over terminal records of `executed` units. Two identities
are normative and are checked by the writer and re-checked by the reader:
`passed + failed + errored + diagnostic == terminal`, and
`graded + errored + diagnostic + missing == planned`. A `sourced` unit
contributes to neither side of either identity; its counts are those the
referenced artifact recorded.
- for audits: `required_candidates`, `completed_candidates`,
  `candidate_errors`, `audited_safe`, `exploitable`, `not_auditable`, and
  `audit_error`

Every metric is an object with `value`, `numerator`, `denominator`, and
`denominator_kind`. A zero denominator yields `null`, not zero.

The following execution metrics are required:

- `execution_pass_rate = passed / graded`, explicitly labeled conditional on
  graded attempts.
- `selected_execution_success_rate = passed / (planned - diagnostic)`, with
  `denominator_kind: gradable_planned`, a reliability and completeness
  diagnostic that makes errors and missing work visible. A `diagnostic` outcome
  can never contribute to `passed`, so counting it in the denominator would
  make a policy-skipped run publish a hard 0.0 rather than the null a zero
  denominator requires. The `diagnostic` count is surfaced beside the metric.
- `runtime_mean`, with the count of non-null applicable runtime scores.
- `static_policy_pass_rate`, with its applicable count.
- `overall`, retained as an alias of `execution_pass_rate` for one scoring
  release and carrying the identical denominator.
- `correctness`, retained one scoring release as the legacy compatibility
  metric, carrying its own explicit denominator. Scoring 4.0 still emits it so
  reporting can show it in a legacy appendix; it is never primary and never
  sorts, ranks, colors, or decides a winner.

`overall` and `correctness` are aliases and legacy keys, not
behavior-preserving re-implementations. At `77c98d6`,
`ScoreBreakdown.overall` returns `0.0` when nothing was graded, while envelope
3.0 returns `null` for every
zero denominator, these two included. Consumers that treat `overall` as a
float must handle null. This is the intended fix, not an oversight: a run that
graded nothing scored nothing, and reporting the difference as zero is exactly
the survivorship claim this workstream exists to remove.

An incomplete unit may expose observed conditional metrics, but it has no
eligible leaderboard score. Reporting must never promote
`selected_execution_success_rate` into a new correctness metric; its purpose
is to expose operational coverage.

Metric populations are stated rather than left to the implementer.
`execution_pass_rate` and `selected_execution_success_rate` read the `scores`
of terminal records whose outcome is `passed` or `failed`. `runtime_mean` and
`static_policy_pass_rate` read the non-null applicable dimensions of every
terminal record with a non-null `scores`, which includes `diagnostic` outcomes,
since a run that skipped static checks still measured runtime behavior
honestly. No metric ever reads `diagnostic_scores`.

Exploit audit reports:

- `audit_coverage = audited_tests / planned`, denominator kind `planned_tests`;
- `exploit_rate = exploitable / audited_tests`, denominator kind
  `audited_tests`;
- `candidate_coverage = completed_candidates / required_candidates`,
  denominator kind `required_candidates`.

`audited_tests` is the count of tests with `audit_complete` true, which by the
classification above is exactly `exploitable + audited_safe`. Candidate counts
partition as `completed_candidates + candidate_errors + unresolved_candidates
== required_candidates`, where `required_candidates = planned_candidates -
superseded_candidates`.

The invariants that make these safe: `exploitable <= audited_tests <= terminal
<= planned`; `completed_candidates <= required_candidates <=
planned_candidates`; the four audit outcomes partition `terminal`; and
`audited_tests == 0` implies `exploitable == 0`, so a null `exploit_rate` can
never coexist with an unreported finding. A zero denominator is null.

## Bounded per-test recovery

An error is not a grade. A run that loses one test to a runtime or harness
failure has not measured something different; it has measured less. Requiring
`continue_on_error=false` for official eligibility while offering no recovery
means one failed database reset discards the fingerprinted baseline run, which
at `77c98d6` does not even leave a finalized artifact.

Recovery sits at one layer and one layer only. `model.max_retries` already
owns the provider call and retries transient provider failures with backoff;
recovery owns the stages above it, which that policy structurally cannot see.

The attempt stage order is normative, and the same order defines
`outcome.failing_stage`, the telemetry timing keys, and the replay boundary:

`prompt_render`, `generation`, `artifact_parse`, `runtime_reset`, `grading`,
`artifact_cleanup`.

This moves the runtime reset inside the attempt boundary and after artifact
parsing. At `77c98d6`, `_run_isolated_execution_loop` calls `environment.reset()`
outside the per-test `try`, which is why a reset failure escapes as an uncaught
traceback; placing it here fixes that and makes the replayed suffix contiguous.

`RunConfig` gains `max_test_reattempts: int = 1`, validated as `>= 0`.

1. The recoverable failing stages are exactly `runtime_reset` and `grading`.
   Every other stage is terminal on first attempt. `generation` is terminal
   because `model.max_retries` owns that layer and a fifth call is a retry
   wearing a different name. `prompt_render` is terminal because it re-fails
   deterministically. `artifact_cleanup`, `runtime_identity_drift`, and
   `verification_contract_drift` are terminal because each halts the runtime
   profile, so a re-attempt has nothing to run on and could not restore an
   eligible measurement anyway. None of these consume budget or set
   `recovery_exhausted`.
2. A graded outcome is never re-attempted. Re-attempting one would resample the
   measured distribution, so it is refused by contract rather than by
   configuration. Errors sit outside every score denominator, so recovering one
   restores a measurement that was missing instead of replacing one taken.
3. A re-attempt MUST reuse the generation captured by the earliest attempt of
   the same `(unit_id, test_id)`. It freezes the prefix, meaning prompt, prompt
   hash, raw completion, parsed artifact, artifact digest, usage, retry
   telemetry, and provider response identity, and replays the suffix from
   `runtime_reset`. Re-grading without re-running the reset is forbidden,
   because the failed attempt may have mutated the runtime. Once a generation
   is captured for a test, no later attempt may replace it.
4. Reuse is what makes recovery safe, not merely cheap. The recoverable stages
   consume the candidate artifact, so their failure probability is correlated
   with what the model produced: a cleanup failure is caused by the artifact's
   own files by definition. Re-generating would systematically replace
   artifacts that break the harness with ones that do not, which is a bias in
   the subject's favor. Freezing the generation removes the question entirely.
5. Each re-attempt increments `attempt_ordinal` and emits the superseded
   attempt as a non-terminal `attempt` event before the next attempt begins.
   Only the final attempt produces a `result` event. A record that reuses a
   carried generation records `generation_reused`, the ordinal that produced
   it, zero attempted and zero completed provider calls, and no new tokens or
   cost, so summing telemetry over all attempts equals the true number of
   provider invocations.
6. Counts, metrics, scores, completeness, and eligibility derive from terminal
   records only; `usage` and `telemetry` aggregate over all attempts. Neither
   domain is left to the implementer.
7. The budget is per test, never per run. A test that exhausts it produces a
   terminal `errored` record, after which continuation, abort, and
   systemic-failure policy apply as sealed in the manifest. Superseded attempts do not
   count toward the systemic-failure threshold; only terminal errored outcomes
   do.
8. The grading deadline is scoped per attempt, not per test across attempts.
   Otherwise a grading failure late in the deadline leaves a re-attempt with no
   budget and recovery is unimplementable for the class it exists to serve.
9. Recovery is visible, never silent. Every unit aggregate reports
   `reattempted` and `recovered`, and reporting surfaces both.
10. Audit mode does not recover: `max_test_reattempts` is forced to 0 and
    `audit_error` is terminal.

Setting `max_test_reattempts` to 0 makes every errored outcome terminal on
first attempt, so no `attempt` events are emitted and the sequence of terminal
records matches a pre-recovery run. It does not restore `77c98d6` byte-level
behavior, because the same milestone moves reset inside the attempt
boundary and changes the artifact format.

## Leaderboard eligibility

Eligibility is evaluated per unit under `wp-bench-leaderboard/1.0`. A standard
model unit is eligible only when:

- mode is `benchmark` and variant is `baseline`;
- selection is `full`;
- record and score completeness are true;
- required runtime and static dimensions are enabled;
- every selected test's runtime profile/engine references resolve to the exact
  pinned manifest entries, and its recorded isolation identity is one the
  profile's official policy lists;
- every record's `effective_verification_sha256` differs from its dataset
  `verification_sha256` only by the derived gateway assertion;
- `continue_on_error` is false, so no terminal per-test error was tolerated.
  Bounded recovery of an ungraded error is permitted and recorded, and does
  not by itself make a unit ineligible;
- no duplicate or foreign records exist;
- dataset, model, harness, grader, and runtime identities meet the immutable
  provenance policy;
- response-reported model identities are internally consistent;
- schema, scoring, and eligibility-policy versions are supported.

`eligibility` contains `policy_version`, `track`, `verification`, `eligible`,
and stable reason codes. `track` and `verification` are orthogonal axes, and
neither encodes completeness or is derived from `eligible`. An earlier draft
made them one four-valued enum, which was not a partition: a complete
skill-injected run with an unresolvable model identity matched `skills`,
`unverified`, and `ineligible` at once. No precedence order fixes that, because
every ordering destroys information the other values carried.

`track` is the experiment type, known before the first attempt and derived
solely from the unit's variant: `standard` for a baseline variant, `skills` for
a skills variant, and null for any other variant or for a
`reference_solution` or `exploit_audit` unit. A track value never asserts
completeness, provenance, or a verdict.

`verification` is the model-subject identity axis, derived solely from the
model identity classification: `verified` when the classification is
`provider_snapshot` or `artifact_digest` and
`resolved_subject_fingerprint_sha256` is non-null, `unverified` otherwise. It
is never a function of completeness, selection, isolation, harness, grader,
dataset, or runtime facts. `unverified` exists because a provider can decline
to prove what it served: a mutable alias, a gateway that rewrites the model
field, a self-hosted or local endpoint. Those are legitimate measurements of a
subject nobody else can reconstruct, and filing them as flawed would conflate
"we could not identify this" with "this run was broken." The axis is defined by
what a response proves, never by which provider kinds the configuration happens
to enumerate, so adding or removing a `ModelConfig.kind` value cannot change
what `verification` means.

`eligible` stays boolean and remains the sole publication gate: true only when
every clause above holds, including `mode == benchmark`, `track == standard`,
and `verification == verified`. A consumer filtering on `eligible` alone can
therefore never publish an unidentifiable, skill-injected, reference, or audit
unit. `eligible == false` always carries at least one reason.

Required reason codes: `selection_not_full`, `attempts_errored`,
`attempts_missing`, `recovery_exhausted`, `diagnostic_policy`,
`grading_dimension_skipped`, `isolation_unofficial`, `nonstandard_variant`,
`mode_not_benchmark`, `provenance_unresolved`, `model_identity_unresolved`,
`model_identity_mismatch`, `harness_dirty`, `runtime_identity_drift`,
`unit_sourced_externally`, and `artifact_cleanup_failed`. Two of these are
deliberate splits. `model_identity_unresolved` covers the model subject only,
leaving
`provenance_unresolved` for dataset, harness, grader, and runtime identity, so
`verification` is derivable from one code rather than by arithmetic over an
open vocabulary; `verification == unverified` requires exactly one of
`model_identity_unresolved` or `model_identity_mismatch`, which is what
separates an unidentifiable subject from a lying one.
`artifact_cleanup_failed` exists because a cleanup failure invalidates
eligibility and `attempts_errored` alone loses the fact that a profile was
quarantined.

The presentation groups the old enum tried to encode become derived predicates,
specified here so reporting does not invent its own: the standard leaderboard
is `eligible`; the unverified group is `track == standard && verification ==
unverified` with `model_identity_unresolved` as its only reason; skills
experiments are `track == skills`; everything else that is not eligible is an
ineligible diagnostic. Groups are displayed separately and never ranked against
one another.

Under policy 1.0 a skills unit records `track = skills`, `eligible = false`,
and `nonstandard_variant`; a future policy version may define an eligible
non-baseline track without any schema change. `track` and `verification` are
schema-level facts fixed by the record and aggregate schema versions, while
`eligible` and `reasons` are the only parts governed by
`ELIGIBILITY_POLICY_VERSION`. Consumers fail closed on unknown tracks,
verification values, policy versions, and reasons.

## Telemetry

Monotonicity is defined on the `(unit_id, test_id)` attempt chain, not on a
single `AttemptContext`: once a stage has produced data, no later stage and no
later attempt of the same test may replace it with nulls. Defined per attempt
instead, a terminal record could be strictly poorer than the superseded record
it replaced, which is precisely what carrying the frozen generation forward
prevents.

Per-attempt telemetry records:

- request and effective generation parameters;
- attempt ordinal, and the stable reason code of every superseded attempt for
  this test;
- attempted and completed provider calls;
- retry count, sanitized retry categories, backoff duration, and total call
  duration;
- provider response ID, response-reported provider/model, creation time,
  system fingerprint, service tier, finish reason, and refusal/safety outcome
  when supplied;
- every sampling parameter the provider rejected and the harness dropped, as a
  list of parameter names, together with the number of provider invocations the
  drop-and-resend cost. This is deliberately generic: naming one provider
  parameter or matching one vendor error string makes the contract stale when
  provider behavior changes. A resend that follows a dropped parameter is a
  provider invocation and is counted as one, so `attempted_provider_calls`
  stays truthful and `retry_count`, which counts transient retries, is not
  overloaded to carry it;
- prompt, completion, total, cached, cache-creation, reasoning, and billable
  token details when supplied;
- provider-reported cost separately from local estimated cost, with estimator
  and pricing-data versions;
- timings for prompt rendering, generation, artifact parsing, runtime reset,
  grading, and total test duration;
- coverage booleans and sample counts for every optional measurement.

Terminal provider failures carry attempted-call count and elapsed time.
Aggregate usage never converts wholly missing provider data to zero.

## Immutable provenance

| Component | Required identity |
|---|---|
| Dataset | Requested source/name/revision/split; resolved Hub commit or selected-suite tree digest; suite-manifest digest; benchmark snapshot; reference snapshot; maintainer-QA snapshot; universe ID digest; per-test benchmark, verification, reference, and negative-control hashes. |
| Model | Requested LiteLLM config; response-reported provider/model; identity classification `provider_snapshot`, `artifact_digest`, or `unresolved_alias`; immutable snapshot/hash when available. |
| Harness | Package version, git commit, dirty flag, full source-tree digest for audit, and a separately allowlisted behavior-affecting execution-contract digest used for comparison. Reporting, notebooks, docs, and unrelated suites are excluded from the comparison digest. A distribution installed without repository metadata records its version and wheel digest, resolves commit and dirty flag as null, and is `provenance_unresolved`: official runs come from a clean checkout. |
| Prompt rendering | `prompt_template_sha256` over a concrete canonical object, not "the renderer": `{template_version, requirement_format, gateway_line_format, artifact_instructions: {kind: text}}` covering every artifact kind. Computed once per run, recorded in the manifest, referenced rather than recomputed by records. |
| Interpreter | Implementation name and `major.minor` enter the comparison digest; full version, implementation version, and platform tag are audit-only. Never `sys.executable`, virtualenv paths, or environment variables. |
| Dependencies | Name, resolved version, and installed-metadata hash for every distribution in the runtime import closure, read from installed metadata rather than from declarations. The allowlisted behavior-affecting subset enters the comparison digest. `dependency_lock_sha256` over `python/uv.lock` is audit-only. |
| Grader | A map keyed by grader/profile ID containing requested Docker reference plus actual image ID/repo digest, or CLI executable hash/version. |
| Runtime | `runtime_profiles` and `engines` maps keyed by stable IDs. Entries include WordPress/source, PHP, database, WP-CLI, runtime-plugin, verifier, browser/driver, endpoint, and shared-state identities as applicable. Each record references the entries it actually used. |
| Scoring | Manifest/record/envelope/event, scoring, and eligibility-policy versions. |
| Skills | Skill name, rendered-content digest, system-prompt digest, reference count, and inclusion policy; no absolute source path. |

Dependencies are classified by the same fail-safe rule as source paths: a
distribution in the runtime import closure that the dependency allowlist does
not classify counts as behavior-affecting, and the release test fails on it.
Development-only distributions are excluded by explicit classification. LiteLLM
is named behavior-affecting, and the pricing-data version is derived from its
distribution identity rather than from a second invented identifier: a LiteLLM
upgrade can move a provider exception between the transient and deterministic
sets that recovery depends on, so it changes behavior, not just cost estimates.

The lock file is audit evidence, not the comparison identity. `uv.lock`
resolves per marker across a `>=3.10` interpreter range and several platforms,
so one lock digest corresponds to many installed sets, and an environment
installed from the open ranges in `pyproject.toml` has no lock at all. A
missing lock records `dependency_lock_unverified` and a lock inconsistent with
the resolved versions records `dependency_lock_mismatch`; neither merges
cohorts silently, because the fingerprint binds the resolved set. No importable
distribution metadata at all is a different case and remains
`provenance_unresolved`: not seeing what is installed is not the same as seeing
it without a lock.

Platform identity is audit-only. Binding operating system and architecture into
the comparison digest would split macOS and Linux cohorts permanently; an
official-run platform requirement belongs in a runtime profile's official
policy instead.

Dirty or unresolved components remain recordable but make an official unit
ineligible. Every JSON-derived digest uses RFC 8785 JSON Canonicalization Scheme
bytes and SHA-256; binary/tree digests use a separately versioned path/content
Merkle algorithm. A digest preimage is a recursively validated tree of concrete
JSON types; paths, datetimes, decimals, bytes, tuples, enums, container
subclasses, non-string object keys, and other non-JSON values are rejected
rather than coerced. Canonical integers, including every integer-valued schema
or normalized-config field entering a digest, are restricted to the
interoperable range `-(2**53 - 1)` through `2**53 - 1`; larger integer
semantics use strings. Binary64 floats remain floats for RFC 8785 serialization,
so their Appendix B boundary cases are not reclassified as Python integers.
NaN, infinity, and lone Unicode surrogates are rejected.

Digest domains are explicit:

- `benchmark_definition_sha256` covers canonical test/suite identity, prompt,
  authored expected behavior and requirements, the gateway signature,
  artifact/execution contract, scoring checks, and canonical reporting
  metadata, through the exact projection above. It excludes references and
  maintainer-only negative controls.
- `verification_sha256` covers the dataset-declared static/runtime/phase
  assertions and execution plan.
- `effective_verification_sha256` covers only the post-policy verification
  specification defined above, including the derived gateway assertion and
  any nonempty dimension emptied by `run.skip_runtime` or `run.skip_static`;
  it excludes candidate content, directory tokens, and the verifier transport
  envelope.
- `prompt_template_sha256` covers the prompt scaffolding shared by every task:
  requirement formatting, the gateway-function line, and artifact
  instructions. It is independent of any task's content, so a renderer change
  is distinguishable from a dataset change instead of appearing as 185
  simultaneously changed prompt hashes.
- `reference_sha256` covers the reference solution or files.
- `negative_controls_sha256` covers dataset-declared controls only. Under
  schema 1 that is the ordered raw `exploit_solutions` strings, with candidate
  IDs, rationales, and expected failures null, because schema 1 has none of
  them. It is null for a Hub-sourced suite, where the export omits the field.
- `generated_controls_sha256` covers the harness-synthesized battery and its
  generator version. Most audited candidates are synthesized by harness code
  and fall outside dataset provenance entirely, so folding them into the
  dataset digest would attribute harness behavior to the dataset. The audit
  assessment records which digest each candidate came from.
- the benchmark dataset snapshot uses benchmark definitions; reference and
  audit modes additionally bind their respective reference or QA snapshots.

This separation makes equivalent local and public benchmark rows comparable
while preventing a reference or QA audit from claiming provenance for data it
did not load.

## Error handling

- Provider failure before response: `errored` with attempted-call telemetry.
- Artifact parse/validation failure: graded `failed`, retaining completion and
  usage.
- Environment setup/preflight failure: run-level `failed` at
  `environment_setup`; no nonexistent test attempt is synthesized and all
  planned tests remain missing.
- Per-attempt reset failure: test record `errored` at `runtime_reset`; no
  score is invented. The reset call moves inside the attempt boundary, so this
  failure can no longer escape as an uncaught traceback that discards the run.
  It is recoverable under the recovery budget.
- Observed runtime or profile drift: the identity check runs before each
  attempt and again after grading returns. An identity that no longer matches
  its sealed manifest entry records `errored` at `runtime_identity_drift`,
  halts the affected runtime profile, and makes the unit ineligible; when the
  post-grading check fires, the dimension results already produced are carried
  in `diagnostic_scores` exactly as for a cleanup failure. The manifest is
  never rewritten to match what was observed. Not re-attemptable.
- While a runtime profile is halted, its remaining planned tests are counted
  `missing` and no attempt record is synthesized for them, following the
  environment-setup precedent. If scoped recovery succeeds the run continues;
  if it fails the run terminates `failed`.
- Verifier timeout: graded `failed` with `timeout=true`, preserving the sealed
  scoring semantics.
- Verifier transport/harness exception: `errored`, retaining prior generation
  data.
- Cleanup failure: record outcome `errored` at `artifact_cleanup` with `scores`
  null and the pre-cleanup dimension results carried in `diagnostic_scores`;
  raise `artifact_cleanup_failed`; and halt that runtime profile until scoped
  recovery succeeds. Not re-attemptable.
- Audit candidate execution failure: candidate outcome `audit_error`; it is not
  counted as a rejected exploit or safe test.
- Recoverable per-test error with budget remaining: emit the superseded
  attempt, re-attempt the test, and apply abort or continuation policy only to
  the terminal outcome.
- Default abort: persist the terminal attempt and terminal event first.
- Continue-on-error: finish remaining attempts, but errors prevent eligibility.
- Reference failures and exploit findings: completed envelope, explicit reason,
  nonzero exit.
- Serialization or atomic-replace failure: retain the partial stream.

## Legacy compatibility

`load_result_envelope(path)` recognizes the canonical namespace before it
checks version support. A top-level `schema_version`, or a first JSONL object
whose `event_type` is `manifest`, claims that namespace. A supported major is
parsed canonically; an unsupported major fails that input and never falls
through to legacy detection.

Outside the canonical namespace, the exact discriminator matrix is:

| Parsed shape | Origin |
|---|---|
| Object with `metadata.mode == "exploit_audit"` | `legacy_audit`; this precedence gate ignores incidental `models` or `results` keys |
| Object with `metadata` and `models`, without `results`, and not audit | `legacy_multi` |
| Object with `metadata` and `results`, without `models`, and not audit | `legacy_single` |
| Non-empty JSONL stream whose parsed lines satisfy the registered legacy record predicate and whose first line is not a canonical manifest | `legacy_records` |
| Non-audit object with both `models` and `results`, or anything else | Per-input `LoadFailure` |

These predicates are mutually exclusive after the audit precedence gate. No
match or ambiguous shape yields a per-input `LoadFailure`; the reader never
guesses from a filename or advisory legacy version.

The checked-in legacy fixture index is the authoritative compatibility
inventory. Each entry records original bytes, producer commit, mode, format,
expected origin and warnings, an immutable artifact path, a byte digest, and
the structural-fingerprint algorithm and digest. Algorithm
`wp-bench-legacy-structure/1` maps JSON scalars to one-element type arrays,
objects to `["object", [[key, child_shape], ...]]` in RFC 8785 key order, and
arrays to `["array", [[child_shape, count], ...]]` ordered by the child shape's
canonical bytes, then hashes
`["wp-bench-legacy-structure", 1, recursive_shape]` through
`canonical_sha256()`. For a tolerated live partial, at most one malformed final
line is omitted from `recursive_shape`, while the byte digest still covers the
complete original tail and the index records the omission. A new observation
adds an entry. Existing entries, paths, and bytes are immutable. A generator
defect appends a separate annotation record targeting the old fixture and a
corrected fixture under a new ID; it never edits or replaces the historical
entry, path, or bytes.
The initial source set is an explicit append-only list of immutable evidence
commits with a complete expected-observation array, not the checkout present
during implementation. The source manifest and fixture index join exactly once
in both directions for every `(source_commit, source_observation_id)`.
Historical artifacts are validated from checked-in bytes and digests; a
separate temporary probe of the checked-out writer must match the complete
expected set or add new immutable observations.

`LegacyResultAdapter` normalizes these in memory and preserves source details
under `extensions.legacy`, including unknown fields and the lossless parsed
legacy payload. It never rewrites an input file and never invents planned
attempts, universe identity, immutable provenance, or eligibility. Unknown
facts remain null with stable warnings such as
`legacy_completeness_unverifiable` and `legacy_provenance_unverifiable`.

Specifically: it sets `track` from the legacy record's variant key when present
and null otherwise, always sets `verification = unverified` and `eligible =
false` with the reason `legacy_not_evaluable`, and always sets
`diagnostic_scores` null, since no legacy shape can express it. It does not
retroactively rewrite a legacy record's `suite`; fixtures from `77c98d6` hold a
source document ID rather than a suite identity, so the adapter carries the
recorded value through with `legacy_suite_identity_unverifiable`, and that value is never used to
cohort a legacy artifact against a canonical one.

"Fatal" for a conflicting run ID or an invalid input means that input, or that
run-ID group, is excluded, named, and reported, and the command exits nonzero.
It never means the report is not produced.

Envelope equivalence and prefix supersession are relations between inputs, so
they belong to `load_result_envelopes(paths)` rather than to the single-path
function. It returns the loaded envelopes and the failed inputs separately: a
conflicting or corrupt artifact fails itself, names itself, and never fails
its siblings or the report that included it.

Canonical writers do not emit the old single or multi shapes. The adapter is
retained for at least two major result-envelope releases.

## Security and privacy

- Continue sending generated verifier payloads on stdin, not argv.
- Serialize only allowlisted configuration; exclude credentials, environment
  variables, auth headers, and absolute local paths.
- Sanitize and bound error messages, stdout, and stderr.
- Keep provider response IDs but document them as potentially identifying.
- Raw completions and artifacts remain in audit artifacts; owner-only file
  permissions are used where supported. A later publish/export command may
  strip raw content while retaining hashes.
- Provenance hashes establish sameness, not trust or authorship.

## Test strategy

### Unit tests

- Selection: exact hash vectors, source-order independence, seed behavior,
  explicit-path normalization and conflicting-selector rejection, full
  normalization, default strata for suites with no manifest, custom strata,
  universe duplicates, and selected-catalog digests.
- Recovery: an errored-then-graded test is one terminal record plus one
  superseded attempt; the provider is called exactly once across all attempts
  and the terminal record's completion and artifact digest are byte-identical
  to the superseded attempt's; graded outcomes are never re-attempted; only
  `runtime_reset` and `grading` consume budget; cleanup, drift, generation, and
  prompt-render failures are terminal and leave the budget untouched; budget
  exhaustion produces a terminal error and `recovery_exhausted`;
  `max_test_reattempts=0` emits zero `attempt` events and exactly one terminal
  record per planned test.
- Verification digests: the effective digest is computed at seal time, is
  identical across units, variants, trials, and attempts, is non-null on
  provider-failure and parse-failure records, and excludes the candidate
  artifact; `verification_divergence` classifies gateway injection,
  `skip_runtime`, and `skip_static` correctly; a rebuilt specification that
  disagrees with the sealed digest raises `verification_contract_drift`.
- Loader parity: real `wp-core-v1` content loaded locally and through the
  Parquet export produces byte-identical selected-test catalogs,
  universe/catalog digests, and per-test benchmark and verification digests;
  `release_focus` is non-null for all 185 tasks on both paths. A separate WS1.3
  fixture injects identical non-dataset identities and then asserts equal
  `contract_fingerprint_sha256` values.
- Audit algebra: the full enumeration of applicable-candidate count, exploit,
  candidate error, unresolved candidate, and record error yields exactly one
  classification per cell; `has_exploit` implies `audit_complete`; every audit
  numerator is a subset of its denominator; a test with one exploitable and one
  errored candidate is `exploitable` and is counted in `audited_tests`.
- Eligibility axes: the cross product of variant, mode, identity provability,
  and clause satisfaction yields exactly one `(track, verification, eligible,
  reasons)` tuple per cell, with no cell unrepresentable and no two
  semantically distinct cells collapsing to the same tuple.
- Scores: a cleanup failure has null `scores`, non-null `diagnostic_scores`,
  outcome `errored`, stage `artifact_cleanup`; the mutual-exclusion validator
  rejects a record with both; a verifier timeout keeps ordinary `scores` and
  enters the graded denominator; a `diagnostic` record feeds `runtime_mean` but
  not `execution_pass_rate`; an aggregate over one pass plus one cleanup
  failure reports `graded == 1`, `errored == 1`, and `unusable_scored == 1`.
- Schemas: strict versions, common record keys for all outcomes/modes,
  manifest immutability, fingerprint inclusion/exclusion, and trial identity.
- Completeness: pass/fail/error/diagnostic/missing identities, zero
  denominators, per-candidate audit coverage/errors, multi-unit independence,
  and fail-closed eligibility.
- Telemetry: provider failure, retry exhaustion, parse/reset/verifier failure,
  token-detail coverage, and preservation after generation.
- Provenance: local and Hub digests, config redaction, dirty harness,
  repository-less installation, Docker reference mismatch, profile/engine
  maps, isolation identity changes, prompt-template attribution, selected-suite
  versus unrelated-tree changes, CLI/runtime shared state, and unresolved
  model aliases.
- Comparison allowlist: every tracked source path is classified, and an
  unclassified path fails the test rather than defaulting to excluded.
- Reader: every indexed legacy structure, truncated partial final line,
  duplicate events, foreign run IDs, unsupported canonical major versions that
  never fall through to legacy, semantic JSON/JSONL sibling deduplication,
  prefix versus non-prefix partials, exact external-reference resolution after
  deduplication, the torn-partial byte/structure vector, the bidirectional
  evidence-source join, and no inferred eligibility or pairing.
- Records: ordered lifecycle phases, per-phase deadline/timing/provenance,
  cleanup precedence, and snippet-as-one-phase compatibility.

### Integration tests

- A one-model run and a one-unit multi run produce the same semantic envelope.
- Multi-model/skills units share one selection plan but have independent
  counts, usage, errors, and eligibility.
- First-call and post-generation failures produce durable terminal records.
- Reference failures and exploit findings finalize before exiting nonzero.
- A handled environment setup failure produces a manifest and failed terminal
  event.
- Kill-after-manifest, kill-after-result, and truncated-last-line fixtures
  recover exact missing counts.
- Final JSON and JSONL reconstruct equivalent envelopes.
- Final JSON/JSONL plus an equivalent prefix partial deduplicate to one semantic
  envelope; non-equivalent content with one run ID fails.
- A non-prefix partial beside a finalized sibling fails its own load and leaves
  the finalized artifact loadable and reportable.
- A sourced unit resolves only through its owning manifest's exact external
  reference after canonical siblings collapse; a stale semantic digest,
  missing source unit, or coincidentally matching undeclared input cannot form
  a pair.
- A reset failure that recovers yields one terminal record, one superseded
  attempt event, `record_complete` and `score_complete` true, `reattempted` and
  `recovered` each 1, and neither `attempts_errored` nor `recovery_exhausted`
  among the reasons. It does not assert full eligibility, which depends on the
  harness dirty flag and therefore on the developer's working tree; full
  eligibility is tested separately with provenance injected as fixtures.
- A mid-run reset failure produces a terminal errored record and a finalized
  artifact instead of an uncaught traceback.
- Every required audit candidate records rejected/exploitable/error outcome and
  expected stage/assertion evidence.
- A cleanup failure quarantines the profile and preserves the pre-cleanup score
  only as an unusable diagnostic.
- Simulated serialization and replace failures keep recoverable partials.

### Release checks

Run `ruff check python`, `mypy python`, and `pytest python`; validate local and
Hub dataset identity; exercise Docker and wp-env provenance; run reference and
exploit checks; and perform a controlled interrupted run. Assert that the
comparison allowlist classifies every tracked source path, and measure
preflight wall clock against its budget. No mutable image, dataset, or model
alias may pass official eligibility.

Preflight budgets are per activity, because they differ by two orders of
magnitude. Content hashing and source-tree digests complete within two seconds
for `wp-core-v1` on a warm checkout. Runtime and grader inspection is budgeted
separately, five seconds for the Docker path and thirty for wp-env, and is
gathered by one batched identity probe rather than one shell-out per identity:
on the wp-env path every probe is an `npx wp-env run cli` invocation, so a
per-identity design could not meet any useful budget. Environment setup is
outside both budgets. All of it is paid once per run, before any paid model
call, and is measured rather than assumed.

## Rollout

This workstream is roughly the size of the `77c98d6` harness, so it ships as
seven numbered capability milestones rather than as one flag-guarded change.
Each is independently reviewable and leaves the harness working. The numbers
express activation dependencies, not pull-request or branch order: code for a
later milestone may arrive first only if it remains dormant behind capability
checks or includes the prerequisite capabilities. Each receives its own
implementation plan, matching the milestone discipline workstream 3 uses; a
capability activates only after its predecessor's contract tests pass.

1. **WS1.0 (contracts and reader).** `schemas.py`, canonical RFC 8785 hashing,
   `results_reader.py` with `load_result_envelope()` and
   `LegacyResultAdapter`, and an indexed compatibility corpus for the four
   legacy structural families: single/reference, multi/skills, audit, and
   record-only streams. No writer changes and no behavior changes: every
   existing test passes untouched. It splits into hashing/schema and
   reader/fixture changes, but neither waits for a branch or merge. Every
   fixture records an immutable path, original bytes, producer commit,
   versioned recursive-shape fingerprint, byte digest, and expected adapter
   result. Later producer structures are added as new fixtures; they never
   regenerate or replace historical ones.
2. **WS1.1 (loader canonicalization and selection v2).** One resolved suite
   identity across `datasets.py` and `export_dataset.py`, the full descriptor
   normalization, the local-versus-Hub parity test, the suite-scoped universe,
   then `stratified-hash-round-robin/2`, the selected catalog and its digest,
   published hash vectors, and smoke-only language in documentation and console
   output. The loader work leads because the catalog it feeds is the selection
   plan's own denominator, and it ships together because both change which
   tests a limited run picks.
3. **WS1.2 (durable terminal records).** `RunArtifactWriter`, manifest-first
   streaming, `ModelCallOutcome`, terminal-record-before-abort ordering, the
   reset call moved inside the attempt boundary, and the `audit_error`
   candidate outcome. This milestone alone closes every artifact-loss path in
   the context section and is the highest-value increment in the workstream.
4. **WS1.3 (provenance).** `provenance.py`, the allowlisted comparison digest
   and its completeness test, prompt-template attribution, isolation identity,
   grader and runtime identity maps, and preflight resolution against its
   wall-clock budget.
5. **WS1.4 (counts, metrics, eligibility).** `integrity.py`,
   denominator-bearing metrics, per-unit completeness, scoring 4.0,
   `wp-bench-leaderboard/1.0`, and the track table.
6. **WS1.5 (coordinator cutover).** `RunCoordinator` behind an internal flag;
   compare legacy and canonical artifacts on mocked and reference runs; then
   switch every CLI mode to envelope 3.0 and the normative exit-code table.
   Bounded per-test recovery lands here, with the coordinator that owns
   attempt ordinals.
7. **WS1.6 (legacy write removal).** Remove the mode-specific production
   serializers; retain legacy reads for at least two major envelope releases.

Milestone sequencing requires staged nullability, and the schema says so rather
than leaving an impossible obligation. WS1.2 emits the first `run_terminal`
event while WS1.3 still owns provenance resolution and WS1.4 still owns metrics
and eligibility, so `provenance`, `config_sha256`,
`contract_fingerprint_sha256`, `prompt_template_sha256`, `metrics`, and
`eligibility` are nullable in the 1.0 and 3.0 contracts, and an artifact
carrying nulls in them raises `pending_milestone`. Without that, WS1.2 could
not emit a schema-valid artifact at all and the rollout would have to be
reordered around the writer instead of around the risk.

WS1.0 through WS1.2 are the preferred first activation because they fix data
loss that is happening now and depend on no later-workstream decision.
Workstream 2 or 3 code may arrive independently, but it either includes these
reader/writer capabilities or remains dormant until their contract tests pass;
merge order never changes the resulting contract.

## Acceptance criteria

1. Every run form writes envelope 3.0 and record 3.0 through one writer.
2. The manifest is the first JSONL event and precedes the first graded attempt.
3. A partial stream alone identifies every planned unit/test and exact missing
   count.
4. Proper subsets are labeled smoke and cannot be leaderboard-eligible.
5. Selection is source-order independent and matches published hash vectors.
6. Every metric contains its denominator; a zero denominator is null.
7. Completeness and eligibility are present per unit; there is no cross-model
   aggregate.
8. A one-pass/two-error run cannot appear as an eligible perfect result.
9. The terminal attempt is durable before abort policy runs.
10. Completion and model-call telemetry survive all downstream failures.
11. Reference findings, exploit findings, model failures, and systemic failures
    remain distinguishable.
12. Mutable or unresolved provenance fails official eligibility closed.
13. Canonical artifacts contain no credentials or absolute skill paths.
14. Legacy artifacts remain readable but cannot gain inferred eligibility.
15. Existing streaming recovery and atomic-finalization guarantees still pass.
16. Record 3.0 represents snippet and multi-phase lifecycle/browser execution
    without a second result shape.
17. Audit artifacts prove required/completed/error candidate coverage and never
    count candidate execution errors as safe.
18. Runtime/profile/engine provenance is keyed and every record references the
    exact observed entries it used.
19. Equivalent JSON, JSONL, and partial siblings deduplicate semantically while
    conflicting same-run artifacts fail; a non-prefix partial fails its own
    load without failing its finalized sibling or the report.
20. A test that errors once and grades on a bounded re-attempt yields one
    terminal record, one visible superseded attempt, and a complete unit; the
    provider was called exactly once; a graded outcome is never re-attempted.
21. The effective verification digest is sealed once, excludes the candidate
    artifact, is present on every record including pre-verifier failures, and a
    skipped grading dimension is detectable from the manifest alone.
22. An unclassified source path or runtime distribution fails the
    comparison-digest test.
23. Every writer-produced terminal status maps to exactly one exit code by the
    documented precedence, the CLI derives none of them independently, and the
    CLI-owned exits are enumerated.
24. A mid-run reset failure finalizes an artifact instead of escaping as an
    uncaught traceback.
25. Each milestone in the rollout leaves `pytest python` green on its own.
26. WS1.1 local and Hub loading of identical suite content produces identical
    catalogs, universe/catalog digests, and per-test benchmark and verification
    digests. After WS1.3 resolves identical non-dataset identities, the same
    fixture also produces an identical contract fingerprint.
27. A partial audit recovers every candidate denominator from its manifest
    alone, and an audit against a source lacking QA data fails preflight
    instead of reporting coverage it never had.
28. A test with one exploitable and one errored candidate is classified
    `exploitable` and lies inside the `exploit_rate` denominator.
29. Every unit carries exactly one `(track, verification, eligible)` tuple, and
    `eligible` alone is sufficient to gate standard publication.
30. Counts derive from terminal records only, and both completeness identities
    hold on a run containing recovered errors.
31. A release test drives a clean full suite identified by a pinned
    `wp-core-v1` content digest, with provenance injected as fixtures and a
    resolved provider snapshot, and asserts it is eligible. A second test
    asserts both that every identity produced by an active official profile
    fixture appears on that profile's accepted list and that every active
    accepted identity has an official producing fixture. A third assertion
    proves an otherwise recordable identity remains ineligible with
    `isolation_unofficial`. These are tests rather than sentences because a
    policy that no run can satisfy is a failed policy, while prose about
    ambient harness state cannot detect its own staleness.
32. Unsupported future canonical majors fail as canonical inputs rather than
    falling through to a legacy predicate, and ambiguous legacy objects fail
    without guessing.
33. External units resolve only after semantic sibling deduplication through
    exact declared run, unit, digest, and contract identities; undeclared or
    inferred cross-input pairing is impossible.
34. Every indexed legacy fixture retains its original entry, path, and bytes;
    writer drift and generator corrections add new records rather than replace
    history.
35. Manifest validation rejects singleton, overfull, two-sourced,
    actor/trial-incompatible, duplicate-variant, missing-reference, and
    orphan-reference pair groups while accepting executed/executed and
    executed/sourced pairs.
36. A tolerated torn live partial excludes its one malformed final line from
    the structural shape but includes every original byte in the artifact
    digest; the published vector is stable.
37. Every evidence source declares its complete expected observation set, and
    every `(source_commit, source_observation_id)` joins exactly once to the
    fixture index in both directions.

## Risks and fixed assumptions

- Some providers do not expose immutable snapshots. Those runs remain useful
  measurements but cannot satisfy policy 1.0; they land on the `unverified`
  track rather than being discarded or silently ranked.
- Selected-test catalogs increase artifact size; they are required to recover
  subgroup denominators without mutable dataset access.
- Preflight hashing adds startup time once per run, before paid calls.
- A hard kill during environment setup can occur before the manifest is
  writable; handled setup failures are still finalized. Once the manifest is
  written, all complete events before a torn final line are authoritative.
- Trial independence is an experimental assumption documented by reporting;
  the integrity layer records identity and does not claim independence.
- `max_test_reattempts` defaults to 1, so a recovered run reports fewer errors
  than it encountered. The `reattempted` and `recovered` counts make that
  visible, but a reader who ignores them will overestimate runtime reliability.
  The alternative, discarding the full fingerprinted baseline run over one
  failed reset, is worse and at `77c98d6` produces no finalized artifact to
  read.
- Recovery deliberately does not cover provider failures. A provider error that
  survives `model.max_retries` still ends the run under the default abort
  policy. Extending recovery down to that layer would either duplicate the
  retry policy or re-sample the model, and the second is the bias this design
  exists to exclude.
- Scoping the audit `exhaustive` costs nothing while the suite is healthy and
  becomes visible only once a test is exploitable, which is exactly when the
  extra candidates are worth running. If that assumption stops holding, the
  stop policy is sealed per run and can be switched without a schema change.
- The eligibility axes were split into `track` and `verification` late. Any
  consumer written against the earlier four-value enum reads a field that no
  longer exists, which is the intended failure: silently mapping the old values
  would reintroduce the collision the split removes.
- Isolation is recorded structurally, so a change to reset mechanism or worker
  topology changes the identity by construction. A newly supported identity is
  active only when the same change supplies a producing fixture and profile
  policy entry; unsupported candidate identities create no release obligation.
- Once `identity_sha256` and `contract_fingerprint_sha256` are minted, changing
  an accepted mechanism or topology creates a new comparison cohort. That is
  an explicit compatibility boundary, never a merge-order side effect.
- `completed_with_errors` exits 1 where a `continue_on_error` run at `77c98d6`
  exits 0. Automation reading exit codes must move to `status.state`.
- The comparison allowlist is a live-tree allowlist and will drift; the
  fail-safe default and its release test bound the damage to an over-split
  cohort, never a silently merged one.

## Baseline evidence locations at `77c98d6`

The symbols below locate the historical observations in the evidence baseline.
They are not normative module names and may move or disappear without changing
the canonical contract.

- `python/wp_bench/selection.py::select_tests`
- `python/wp_bench/core.py::BenchmarkRunner.run`
- `python/wp_bench/core.py::BenchmarkRunner._run_exploit_audit`
- `python/wp_bench/core.py::MultiModelRunner._write_outputs`
- `python/wp_bench/core.py::SingleModelRunner.run`
- `python/wp_bench/core.py::_run_isolated_execution_loop`
- `python/wp_bench/core.py::_first_passing_exploit`
- `python/wp_bench/core.py::_build_verification_spec`
- `python/wp_bench/core.py::BenchmarkRunner._render_execution_prompt`
- `python/wp_bench/core.py::_graded_run`
- `python/wp_bench/records.py::_base_record`
- `python/wp_bench/records.py::build_error_record`
- `python/wp_bench/records.py::build_exploit_audit_record`
- `python/wp_bench/scoring.py::ScoreAggregator`
- `python/wp_bench/scoring.py::ScoreBreakdown.overall`
- `python/wp_bench/scoring.py::UsageAggregator`
- `python/wp_bench/results_io.py::RecordStream`
- `python/wp_bench/models.py::ModelGeneration`
- `python/wp_bench/models.py::ModelInterface.generate_with_metadata`
- `python/wp_bench/environment.py::WordPressEnvironment`
- `python/wp_bench/config.py::RunConfig`
- `python/wp_bench/cli.py::_run_or_fail`
- `python/tests/test_continue_on_error.py`
- `python/tests/test_result_streaming.py`
- `python/tests/test_result_schema.py`
