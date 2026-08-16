# WP-Bench Benchmark Integrity Design

- Status: Draft for user review
- Date: 2026-08-16
- Workstream: 1 of 3

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

## Context and problem

The existing harness has strong per-test grading and durable JSONL streaming,
but its persisted run contract is incomplete:

- `python/wp_bench/core.py` constructs different top-level payloads in
  `BenchmarkRunner.run()`, `BenchmarkRunner._run_exploit_audit()`, and
  `MultiModelRunner._write_outputs()`. The multi-model writer drops selection,
  usage, and error data that `SingleModelRunner.run()` already computed.
- `python/wp_bench/selection.py::select_tests()` sorts strata before draining
  them. When `limit` is smaller than the stratum count, alphabetically early
  categories are always selected even though the subset is documented as
  representative.
- `python/wp_bench/scoring.py::ScoreAggregator` aggregates only graded
  records. A run with passes plus provider errors can therefore display a
  perfect conditional pass rate without a selected or graded denominator.
- With `continue_on_error=false`, the terminal failed attempt is not sent to
  the result callback. A first-call failure can leave no artifact because
  `python/wp_bench/results_io.py::RecordStream` opens lazily on its first
  record.
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
6. Preserve model-call and stage telemetry monotonically after generation.
7. Content-address dataset, test, harness, grader, runtime, scoring, and skill
   provenance; record model immutability when the provider can prove it.
8. Make partial streams self-describing and recoverable without reopening a
   mutable dataset.
9. Retain append-as-completed streaming, readable partials, atomic final
   writes, and collision-safe filenames.
10. Read legacy artifacts through one fail-closed adapter.

## Non-goals

- Claiming that a small smoke subset estimates full-suite performance.
- Cryptographically signing or attesting result authorship.
- Guaranteeing that estimated cost equals a provider bill.
- Resuming paid model calls from a partial stream in this workstream.
- Changing WordPress assertion semantics or the strict per-test pass rule.
- Creating a standard leaderboard for skill-injected variants.
- Storing secrets, request headers, or environment variables as provenance.

## Alternatives considered

### Patch each current payload

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
| `python/wp_bench/selection.py` | Build a versioned `SelectionPlan`, selected-test catalog, and catalog digest. |
| `python/wp_bench/records.py` | Build all terminal records through one base constructor, including exploit assessments. |
| `python/wp_bench/models.py` | Return a success or failure `ModelCallOutcome` with attempt telemetry in either case. |
| `python/wp_bench/environment.py` | Keep execution/reset behavior and expose observed grader/runtime provenance and stage timings. |
| `python/wp_bench/scoring.py` | Produce denominator-aware per-unit metrics. |
| New `python/wp_bench/integrity.py` | Derive completeness and versioned eligibility from the manifest and terminal records. |
| `python/wp_bench/results_io.py` | Own manifest-first event streaming, locking, recovery, and atomic finalization through `RunArtifactWriter`. |
| New `python/wp_bench/results_reader.py` | Expose `load_result_envelope(path)` and the legacy adapter. |
| `python/wp_bench/core.py` | Execute a sealed plan through `RunCoordinator`; it no longer assembles payload dictionaries. |
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
| `run_units` | Ordered actor × variant × trial units. Each has a unique `unit_id`, one-based `trial_index`, actor, variant, planned count, planned-subject fingerprint, and optional `pair_id`. |
| `trial_protocol` | Declared trial count, generation-seed policy, pairing policy, and `trial_protocol_fingerprint_sha256`; benchmark mode only. |
| `policies` | Isolation, concurrency, continuation, grading dimensions, timeouts, and artifact-capture policy. |
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
- `definition_sha256`
- `verification_sha256`

Nullable dimensions are present as JSON `null`, never omitted.

The dataset loader is the only normalization boundary for selected-test
descriptors:

- `execution.profile` becomes `runtime_profile`;
- `metadata.coverage.family` becomes `coverage_family`;
- schema-1 or schema-2 `metadata.release_focus` becomes `release_focus`;
- `metadata.wordpress_target_version`, or the suite's declared inherited
  target, becomes `wordpress_target_version`.

Schema-2 suites must make release focus and WordPress target non-null through a
task value or suite inheritance. Selection and reporting read only these
canonical descriptor fields; `suite.json.smoke_strata` names only canonical
fields. Missing schema-1 values normalize to null and therefore to an explicit
`unknown` reporting/selection bucket.

`contract_fingerprint_sha256` covers mode, the selected catalog and order,
selected-suite benchmark snapshot, record/scoring contracts, grading and
isolation policies, behavior-affecting harness code, and every selected
grader/runtime profile and engine identity. It excludes reporting code,
notebooks, documentation, unrelated suites, and presentation-only CLI/output
code so those changes do not split an otherwise identical benchmark cohort.
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

Workstream 2 may set `run.trials > 1`; version 1 manifests therefore reserve
`trial_index` now even though its initial default is one.
`pair_id` is generated once for each intended baseline/treatment pair within a
run and is shared by exactly those two units. It is never derived from model
name or trial index. Cross-invocation pairs require an explicit external
mapping and are never inferred.

## Canonical terminal record

Every planned `(unit_id, test_id)` has at most one terminal `ResultRecord`:

| Field | Contract |
|---|---|
| `schema_version` | Record version `3.0`. |
| `run_id`, `unit_id`, `attempt_id` | Stable linkage; `attempt_id` is deterministic from run, unit, and test IDs. |
| `test` | Manifest descriptor plus preserved task metadata. |
| `actor` and `variant` | References to the manifest unit. |
| `input` | Prompt hash, verification hash, artifact kind, and normalized execution plan/profile/scope/engines. |
| `output` | Raw completion, normalized artifact, and artifact digest once generation completes; otherwise null. |
| `outcome` | Terminal state, stable reason code, failing stage, and sanitized error. |
| `scores` | Execution scores for graded attempts; null for errors and audits. |
| `assessment` | Discriminated execution or exploit-audit details, including candidate-level audit outcomes. |
| `grader` | Overall verifier result plus ordered phase results, cleanup outcome, timeout, bounded stdout/stderr, and verifier version. |
| `telemetry` | Model-call outcome, usage, retries, stage timings, and coverage. |
| `provenance_checks` | Per-attempt actor checks and references to the exact manifest runtime-profile and engine identities used. |
| `extensions` | Empty object in record version 3.0. |

Execution outcomes are:

- `passed`: fully graded strict pass.
- `failed`: fully graded strict failure, including invalid model artifacts and
  verifier timeouts.
- `errored`: provider, reset, transport, or harness failure prevented grading.
- `diagnostic`: intentionally skipped grading dimensions prevent a strict
  score.

Audit records use the same common shape and an audit assessment. An audit with
no applicable negative candidate records `not_auditable` in the assessment,
not as an execution score.

`grader.phases` reserves multi-process execution in record version 3.0. Every
phase contains `phase_id`, lifecycle action, engine/profile references,
fresh-bootstrap identity, start/end timestamps, duration, remaining task
deadline, outcome, assertions, and bounded diagnostics. `grader.cleanup`
contains attempted/succeeded, duration, recovered resources, and any error.
Single-process snippet execution is represented as one `execute` phase, so
consumers never need a second shape when workstream 3 adds lifecycle, browser,
theme, or multisite phases.

An exploit-audit assessment contains one item for every required candidate:

- stable `candidate_id`, artifact kind, and candidate-definition digest;
- whether it was required, applicable, attempted, and completed;
- outcome `rejected`, `exploitable`, `not_applicable`, or `audit_error`;
- execution stage, stable reason code, matched/failing assertion IDs, and
  sanitized error.

Its test-level outcome is `audited_safe` only when all required applicable
candidates completed and were rejected; otherwise it is `exploitable`,
`not_auditable`, or `audit_error`. A rejected candidate is not equivalent to a
candidate that failed to execute.

An invalid completion is a model failure, not a harness error. Conversely, a
missing executable, reset failure, or provider exception must not be invented
as a zero execution score.

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

- `manifest` is byte-equivalent to the first JSONL event.
- `status` contains state, reason code, start/end timestamps, duration, and
  intended CLI exit code.
- `completeness` contains run-wide counts only; it never averages scores
  across models or variants.
- `aggregates` contains exactly one ordered item per run unit.
- `records` is sorted by `(unit_id, test_id, attempt_id)`.
- `failure` is reserved for systemic failure or user abort.

Each `RunUnitAggregate` has this normative shape:

| Field | Contract |
|---|---|
| `unit_id` | Manifest unit reference. |
| `actor`, `variant`, `trial_index`, `pair_id` | Byte-equivalent unit identity fields from the manifest. |
| `status` | Unit state and stable reason code. |
| `planned_subject_fingerprint_sha256` | Requested subject identity from the manifest. |
| `resolved_subject_fingerprint_sha256` | Post-run immutable subject identity, or null with a warning. |
| `counts` | Planned, terminal, graded, passed, failed, errored, diagnostic, missing, and audit-candidate counts. |
| `metrics` | Denominator-bearing execution or audit metric objects. |
| `usage` | Token/cost/latency totals plus per-field coverage counts. |
| `telemetry` | Attempted/completed model calls and stage timing summaries. |
| `eligibility` | Policy version, track, eligible flag, and stable reasons. |
| `audit` | Null for execution; otherwise required/completed/error candidate counts and test-level audit outcomes. |
| `warnings` | Stable unit-scoped integrity warnings. |

`run_terminal.payload` is exactly `{status, completeness, aggregates,
failure}` using the same objects as the final envelope. Folding a finished
event stream therefore reconstructs the envelope without re-running scoring or
integrity policy.

Terminal states are `completed`, `completed_with_errors`, `failed`, and
`aborted`. The reader synthesizes `interrupted` only when a partial stream has
no terminal event. Reference failures and exploit findings are completed
workflows with nonzero exit codes, not infrastructure failures.

Run units and their aggregates are always ordered lists. Display names are
labels, never map keys or identifiers. A single run is simply a one-unit list;
skills, trials, and multi-model runs add units without changing shape.

## JSONL event stream and artifact lifecycle

Each JSONL line has `event_schema_version`, `run_id`, a monotonically
increasing `emitted_sequence`, `event_type`, `emitted_at`, and `payload`.

Event types are:

- `manifest`: exactly once and first.
- `result`: one canonical terminal record.
- `run_terminal`: status, per-unit aggregates, completeness, eligibility, and
  any systemic failure.

Lifecycle:

1. Validate config, skills, dataset, IDs, selection, and resolvable provenance.
2. Preflight the runtime and collect observed identities. On a handled
   preflight failure, seal an unresolved manifest and continue directly to a
   failed terminal event.
3. Seal the manifest and append it before the first graded attempt.
4. Build an `AttemptContext` for every planned attempt. It accumulates prompt,
   model response, artifact, reset, grader, score, and timing information.
5. Convert success or exception into one terminal record and append it.
6. Only after the record is durable, apply continue, abort, or systemic-failure
   policy.
7. Compute counts, metrics, resolved identities, eligibility, and terminal
   status; append that exact `run_terminal` payload; validate the reconstructed
   envelope; and atomically write final JSON and JSONL.
8. Remove the partial only after both final artifacts are safely committed.

A handled failure produces a finalized artifact with `failed` or
`completed_with_errors`. A hard kill leaves `.jsonl.partial`. The reader may
ignore only a malformed final line in a partial file; malformed content in a
finished artifact is fatal. An output-directory failure is the only failure
that cannot record itself.

Both partial and final JSONL preserve append order: manifest first, results in
completion order, and terminal last. `emitted_sequence` is therefore monotonic
in every stream. Canonical sorting happens only in `ResultEnvelope.records`;
records may additionally carry `canonical_position` in the final projection.

The reader computes `semantic_envelope_sha256` from the normalized envelope
after discarding serialization-only event order and file-format fields. Final
JSON and JSONL siblings with the same `(run_id, semantic_envelope_sha256)` are
equivalent and deduplicate to one input. An equivalent finalized artifact
supersedes its strict-prefix partial. Only non-equivalent normalized envelopes
sharing a run ID are an integrity error.

## Limited selection contract

Effective selection kinds are:

- `full`: selected IDs exactly equal the dataset universe.
- `limited_smoke`: `limit` creates a proper subset.
- `explicit_smoke`: explicit IDs create a proper subset.

An explicit list or limit that covers the complete universe is effectively
`full`. Proper subsets are always smoke-only and leaderboard-ineligible.

The selection algorithm is `stratified-hash-round-robin/2`:

1. Reject duplicate test IDs.
2. Read the suite's ordered `smoke_strata` fields. The default is
   `category,difficulty`; `wp-projects-v1` uses
   `coverage_family,artifact_kind,difficulty,runtime_profile`.
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
- `record_complete = terminal == planned`
- `score_complete = graded == planned` for benchmark/reference units
- for audits: `required_candidates`, `completed_candidates`,
  `candidate_errors`, `audited_safe`, `exploitable`, `not_auditable`, and
  `audit_error`

Every metric is an object with `value`, `numerator`, `denominator`, and
`denominator_kind`. A zero denominator yields `null`, not zero.

The following execution metrics are required:

- `execution_pass_rate = passed / graded`, explicitly labeled conditional on
  graded attempts.
- `selected_execution_success_rate = passed / planned`, a reliability and
  completeness diagnostic that makes errors and missing work visible.
- `runtime_mean`, with the count of non-null applicable runtime scores.
- `static_policy_pass_rate`, with its applicable count.
- `overall`, retained as an alias of `execution_pass_rate` for one scoring
  release and carrying the identical denominator.

An incomplete unit may expose observed conditional metrics, but it has no
eligible leaderboard score. Reporting must never promote
`selected_execution_success_rate` into a new correctness metric; its purpose
is to expose operational coverage.

Exploit audit instead reports `audit_coverage = audited_tests / planned`,
`candidate_coverage = completed_candidates / required_candidates`, and
`exploit_rate = exploitable / audited_tests`. An audited test is one whose
required applicable candidates all completed as either rejected or
exploitable; candidate execution errors and not-auditable tests never count as
safe. A zero denominator is null.

## Leaderboard eligibility

Eligibility is evaluated per unit under `wp-bench-leaderboard/1.0`. A standard
model unit is eligible only when:

- mode is `benchmark` and variant is `baseline`;
- selection is `full`;
- record and score completeness are true;
- required runtime and static dimensions are enabled;
- every selected test's runtime profile/engine references resolve to the exact
  pinned manifest entries, and its isolation matches that profile's official
  policy;
- `continue_on_error` is false;
- no duplicate or foreign records exist;
- dataset, model, harness, grader, and runtime identities meet the immutable
  provenance policy;
- response-reported model identities are internally consistent;
- schema, scoring, and eligibility-policy versions are supported.

`eligibility` contains `eligible`, `track`, `policy_version`, and stable reason
codes. Required codes include `selection_not_full`, `attempts_errored`,
`attempts_missing`, `diagnostic_policy`, `grading_dimension_skipped`,
`isolation_unofficial`, `nonstandard_variant`, `provenance_unresolved`,
`harness_dirty`, and `model_identity_mismatch`.

Skill-injected units may be complete experiments but are ineligible for the
standard track. A future skills track requires a separate policy version.
Consumers fail closed on unknown policy versions or reasons.

## Telemetry

`AttemptContext` is monotonic: once a stage has produced data, a later stage
cannot replace it with nulls.

Per-attempt telemetry records:

- request and effective generation parameters;
- attempted and completed provider calls;
- retry count, sanitized retry categories, backoff duration, and total call
  duration;
- provider response ID, response-reported provider/model, creation time,
  system fingerprint, service tier, finish reason, refusal/safety outcome,
  and temperature fallback when supplied;
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
| Harness | Package version, git commit, dirty flag, full source-tree digest for audit, and a separately allowlisted behavior-affecting execution-contract digest used for comparison. Reporting, notebooks, docs, and unrelated suites are excluded from the comparison digest. |
| Grader | A map keyed by grader/profile ID containing requested Docker reference plus actual image ID/repo digest, or CLI executable hash/version. |
| Runtime | `runtime_profiles` and `engines` maps keyed by stable IDs. Entries include WordPress/source, PHP, database, WP-CLI, runtime-plugin, verifier, browser/driver, endpoint, and shared-state identities as applicable. Each record references the entries it actually used. |
| Scoring | Manifest/record/envelope/event, scoring, and eligibility-policy versions. |
| Skills | Skill name, rendered-content digest, system-prompt digest, reference count, and inclusion policy; no absolute source path. |

Dirty or unresolved components remain recordable but make an official unit
ineligible. Every JSON-derived digest uses RFC 8785 JSON Canonicalization Scheme
bytes and SHA-256; binary/tree digests use a separately versioned path/content
Merkle algorithm. NaN and infinity are rejected.

Digest domains are explicit:

- `benchmark_definition_sha256` covers model-visible prompt/requirements,
  artifact/execution contract, scoring checks, and canonical reporting
  metadata. It excludes references and maintainer-only negative controls.
- `verification_sha256` covers the exact static/runtime/phase assertions and
  execution plan.
- `reference_sha256` covers the reference solution or files.
- `negative_controls_sha256` covers ordered candidate IDs, artifacts,
  rationales, and expected failures.
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
- Per-attempt reset failure: terminal test record `errored` at `runtime_reset`;
  no score is invented.
- Verifier timeout: graded `failed` with `timeout=true`, preserving current
  semantics.
- Verifier transport/harness exception: `errored`, retaining prior generation
  data.
- Cleanup failure: record outcome `errored` at `artifact_cleanup`, preserve the
  pre-cleanup assertion outcome and scores as unusable diagnostics, invalidate
  eligibility, and halt that runtime profile until scoped recovery succeeds.
- Audit candidate execution failure: candidate outcome `audit_error`; it is not
  counted as a rejected exploit or safe test.
- Default abort: persist the terminal attempt and terminal event first.
- Continue-on-error: finish remaining attempts, but errors prevent eligibility.
- Reference failures and exploit findings: completed envelope, explicit reason,
  nonzero exit.
- Serialization or atomic-replace failure: retain the partial stream.

## Legacy compatibility

`load_result_envelope(path)` detects:

1. Existing `metadata + results` single/reference payloads.
2. Existing `metadata + models` multi/skills payloads.
3. Existing exploit-audit payloads.
4. Existing record-only JSONL and `.jsonl.partial` streams.

`LegacyResultAdapter` normalizes these in memory and preserves source details
under `extensions.legacy`. It never rewrites an input file and never invents
planned attempts, universe identity, immutable provenance, or eligibility.
Unknown facts remain null with stable warnings such as
`legacy_completeness_unverifiable` and `legacy_provenance_unverifiable`.

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
  explicit-ID precedence, full normalization, custom strata, duplicates, and
  selected-catalog digests.
- Schemas: strict versions, common record keys for all outcomes/modes,
  manifest immutability, fingerprint inclusion/exclusion, and trial identity.
- Completeness: pass/fail/error/diagnostic/missing identities, zero
  denominators, per-candidate audit coverage/errors, multi-unit independence,
  and fail-closed eligibility.
- Telemetry: provider failure, retry exhaustion, parse/reset/verifier failure,
  token-detail coverage, and preservation after generation.
- Provenance: local and Hub digests, config redaction, dirty harness, Docker
  reference mismatch, profile/engine maps, selected-suite versus unrelated-tree
  changes, CLI/runtime shared state, and unresolved model aliases.
- Reader: every legacy shape, truncated partial final line, duplicate events,
  foreign run IDs, unsupported major versions, semantic JSON/JSONL sibling
  deduplication, and no inferred eligibility.
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
- Every required audit candidate records rejected/exploitable/error outcome and
  expected stage/assertion evidence.
- A cleanup failure quarantines the profile and preserves the pre-cleanup score
  only as an unusable diagnostic.
- Simulated serialization and replace failures keep recoverable partials.

### Release checks

Run `ruff check python`, `mypy python`, and `pytest python`; validate local and
Hub dataset identity; exercise Docker and wp-env provenance; run reference and
exploit checks; and perform a controlled interrupted run. No mutable image,
dataset, or model alias may pass official eligibility.

## Rollout

1. Add strict schema types, canonical hashing, the reader, and golden legacy
   fixtures without changing default writes.
2. Add `SelectionPlan`, manifest-first streaming, terminal records,
   completeness, provenance, and the coordinator behind an internal flag.
3. Compare legacy and canonical results on mocked and reference runs.
4. Switch every CLI mode to envelope 3.0, scoring 4.0, and smoke-only limited
   language.
5. Remove mode-specific production serializers while retaining legacy reads.

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
    conflicting same-run artifacts fail.

## Risks and fixed assumptions

- Some providers do not expose immutable snapshots. Those runs remain useful
  diagnostics but cannot satisfy policy 1.0.
- Selected-test catalogs increase artifact size; they are required to recover
  subgroup denominators without mutable dataset access.
- Preflight hashing adds startup time once per run, before paid calls.
- A hard kill during environment setup can occur before the manifest is
  writable; handled setup failures are still finalized. Once the manifest is
  written, all complete events before a torn final line are authoritative.
- Trial independence is an experimental assumption documented by reporting;
  the integrity layer records identity and does not claim independence.

## Repository evidence

- `python/wp_bench/selection.py::select_tests`
- `python/wp_bench/core.py::BenchmarkRunner.run`
- `python/wp_bench/core.py::BenchmarkRunner._run_exploit_audit`
- `python/wp_bench/core.py::MultiModelRunner._write_outputs`
- `python/wp_bench/core.py::SingleModelRunner.run`
- `python/wp_bench/records.py::_base_record`
- `python/wp_bench/records.py::build_error_record`
- `python/wp_bench/records.py::build_exploit_audit_record`
- `python/wp_bench/scoring.py::ScoreAggregator`
- `python/wp_bench/scoring.py::UsageAggregator`
- `python/wp_bench/results_io.py::RecordStream`
- `python/wp_bench/models.py::ModelGeneration`
- `python/wp_bench/environment.py::WordPressEnvironment`
- `python/tests/test_continue_on_error.py`
- `python/tests/test_result_streaming.py`
- `python/tests/test_result_schema.py`
