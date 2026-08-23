# WP-Bench Reporting and Repeated-Trial Statistics Design

- Status: Approved
- Date: 2026-08-16; revised 2026-08-22
- Workstream: 2 of 3
- Depends on: `2026-08-16-benchmark-integrity-design.md`
- Contract independence: reporting consumes canonical capabilities and reader
  relations, never branch state or a particular legacy producer shape

## Decision summary

WP-Bench will move result interpretation out of the notebook and into a typed,
headless Python reporting package. The CLI, notebook, and standalone HTML
renderer will consume the same `ReportDocument`; none may parse raw result
shapes or recalculate integrity semantics independently.

The harness will also support explicit repeated trials. Each trial is a
separate run unit in the canonical envelope, over the same sealed selection.
Reports will show individual trials, means, dispersion, named intervals, and
paired skills effects without pooling incompatible or incomplete runs.

## Context and problem

At immutable evidence baseline
`77c98d61b73c6341db2fa5ccb15212867b825eb5`,
`notebooks/results_report.ipynb` predates the
canonical result and scoring contracts:

- It unconditionally reads `data["models"]`, while normal single-model,
  reference, and exploit-audit outputs use different top-level shapes.
- It automatically selects a recent `results_*.json` without validating mode,
  schema, scoring version, completeness, or provenance.
- It foregrounds `correctness` and plots `overall` as an independent metric,
  even though scoring v3 defines strict execution pass rate as primary,
  correctness as legacy, and overall as an alias.
- It has no selected, graded, error, missing, or applicability denominators.
- It has no category, difficulty, or release-focused reporting.
- It treats baseline and skills variants as unrelated model rows rather than a
  paired experiment.
- It cannot report JSONL partials or failed/aborted canonical runs.
- Its exported HTML loads mutable `plotly-latest` from a CDN and omits the run
  provenance needed to audit the report.

The evidence-baseline runner performs one model generation per selected task.
Any seed sealed by a selection algorithm controls task choice, not model
generation, so those artifacts cannot quantify run-to-run stochasticity.

## Goals

1. Report single-model, multi-model, skills A/B, skills-only, reference,
   exploit-audit, completed, ineligible, failed, aborted, and partial inputs.
2. Use the canonical reader and integrity fields from workstream 1 exclusively.
3. Make strict execution pass rate the primary score and show every numerator,
   denominator, completeness state, and eligibility decision.
4. Compare only compatible subjects and never silently pool different datasets,
   selections, scoring contracts, runtimes, or grading policies.
5. Report category, difficulty, release focus, artifact kind, coverage family,
   and runtime profile with explicit sample counts.
6. Add first-class repeated-trial execution and reproducible statistical
   summaries.
7. Formalize paired baseline/skills effects, including fixed, broken, stable,
   excluded, and missing observations.
8. Generate offline, deterministic, escaped, accessible HTML.
9. Keep the notebook as a thin interactive client of the same report engine.
10. Continue reading legacy artifacts with prominent fail-closed warnings.

## Non-goals

- Reimplementing result-shape detection, legacy conversion, completeness,
  eligibility, or provenance inference in reporting.
- Changing WordPress per-test scoring or the eligibility policy.
- A hosted dashboard, results database, or public submission service.
- Claiming that statistical intervals establish general performance across the
  whole WordPress ecosystem.
- Running all pairwise significance tests or manufacturing winner language.
- Restoring legacy correctness as a ranking metric.
- Including raw completions, generated code, exploit code, or provider response
  IDs in default HTML.

## Alternatives considered

### Modernize the notebook only

This is initially quick but leaves parsing, metrics, and statistics in mutable
cells that are hard to test and easy to execute out of order. It is rejected.

### Shared report engine with thin interfaces

A typed report package consumes canonical envelopes and produces one
renderer-neutral model. The CLI, notebook, and HTML renderer share every
semantic decision. This is the selected approach.

### Convert results into a database first

DuckDB or Parquet would help at much larger historical scale, but would add a
second persisted schema and migration surface before it is needed. It is
deferred.

## Dependency contract with workstream 1

Reporting opens input sets only through the canonical reader APIs:
`load_result_envelopes(paths)` and its single-input wrapper
`load_result_envelope(path)`. Workstream 1 owns:

- `RunManifest`, `ResultRecord`, and `ResultEnvelope`.
- Legacy payload detection and `LegacyResultAdapter`.
- JSON/JSONL recovery, sibling precedence, deduplication, and declared
  external-unit resolution.
- Selected-test descriptors and definition hashes.
- Per-unit counts, metric denominators, completeness, and eligibility.
- `contract_fingerprint_sha256`,
  `planned_subject_fingerprint_sha256`, and
  `resolved_subject_fingerprint_sha256`.
- Stable warnings for facts that legacy artifacts cannot prove.

Reporting must not import `json` or `orjson` to inspect an input shape, reopen
the live dataset to invent denominators, infer cross-artifact pairs, or use
`len(records)` as a score denominator.

## Architecture

Add `python/wp_bench/reporting/`:

| Module | Responsibility |
|---|---|
| `api.py` | Public `build_report(load_result: LoadResult, options: ReportOptions) -> ReportDocument`, consuming the canonical reader's multi-input result. |
| `cohorts.py` | Consume reader relation results, form compatibility cohorts, group subjects/trials, and emit warnings. |
| `metrics.py` | Project canonical metrics into scorecards and dimension breakdowns without changing denominators. |
| `statistics.py` | Wilson intervals, repeated-trial summaries, paired skills effects, and deterministic resampling. |
| `models.py` | Versioned renderer-neutral report dataclasses. |
| `html.py` | Escaped, deterministic, standalone HTML rendering. |

`python/wp_bench/cli.py` gains a thin `report` command. The replacement
`notebooks/results_report.ipynb` imports only the public API, chooses inputs,
displays `ReportDocument` tables, and invokes the shared HTML renderer.

Reporting dependencies live in an optional `report` extra. The core loader and
canonical schema remain in the base package. A missing extra produces an
actionable installation message rather than an import traceback.
The extra pins Jinja2 for templating, Plotly plus its inline JavaScript bundle
for charts, and SciPy for Student-t quantiles. Notebook execution dependencies
remain in a separate `notebook` extra.

## Repeated-trial execution

Add `run.trials: int = 1` to `RunConfig`, validated as positive and rejected
for reference-solution and exploit-audit modes. Repeating deterministic
validation/audit is not a model trial. This is an explicit benchmark cost
multiplier and the pre-run plan separately prints:

```text
planned generations = selected tests × models × variants × trials
maximum provider calls = planned generations × (max_retries + 1)
initial planned grader executions = planned generations
maximum grader attempts = initial planned grader executions × (max_test_reattempts + 1)
```

The maximum is reported per retry policy when configured models differ.
Reference mode reports zero model/provider calls, one initial planned grader
execution per selected test, and its recovery-aware maximum. Audit mode
reports zero model/provider calls and the exact required candidate-execution
count from maintainer QA data; its forced `max_test_reattempts=0` makes initial
and maximum grader attempts equal.

Rules:

1. Dataset loading and selection happen once per invocation.
2. Every model × variant × trial receives the identical selected catalog and
   grading contract.
3. Each trial is a distinct manifest run unit with one-based `trial_index` and
   unique `unit_id`.
4. The sealed manifest records requested and effective selection parameters.
   Any seed or nonce used by the selected algorithm governs selection only and
   is never represented as a model-generation seed. A producer that does not
   support a requested selector rejects it before sealing the manifest.
5. WP-Bench does not silently synthesize provider seeds. If a future model
   configuration sends a provider seed, the requested and effective values are
   recorded per attempt and become part of the subject identity.
6. The selected runtime profile's sealed structured isolation identity and
   recovery policy apply to every attempt in every trial exactly as they do for
   a one-trial run.
7. Baseline and skills variants with the same actor and `trial_index` form the
   intended A/B pair only when the manifest assigns the same non-null `pair_id`.
8. Trial failures are recorded independently; one incomplete unit does not
   erase complete sibling trials.

`trial_protocol_fingerprint_sha256` covers declared trial count, generation
seed policy, baseline/treatment pairing layout, and trial scheduling policy.
It excludes actor/model identity, which belongs to the subject fingerprint.
The initial scheduling policy is deterministic model → trial order. For A/B
runs, odd trials execute baseline then treatment and even trials reverse that
order; the policy is recorded because provider-time effects can otherwise be
confounded with a permanently first variant. Task order remains the sealed
selection order within each unit.

Separate CLI invocations can also form repeated model trials. A trial identity is
`(run_id, unit_id)`, not a timestamp or display label. Eligible repeated
grouping requires an identical resolved subject fingerprint; the report can
therefore combine compatible in-run and cross-run trials. If only planned
identity is available, diagnostic grouping is allowed with
`PROVENANCE_UNKNOWN`, but the series is unranked.
Every automatic pair has exactly one sealed owning manifest; ownership is
never inferred jointly from two manifests. The owner may explicitly resolve a
sourced arm whose original `run_id` differs through its declared external-unit
reference. Coincidental cross-input matching never creates a pair. Any other
form of cross-run A/B pairing is deferred; matching actor, trial index, and
test ID is insufficient.

No automatic maximum is imposed because CI and publication profiles may vary,
but documentation defines:

- one trial as exploratory;
- at least three score-complete trials for a dispersion summary;
- at least five score-complete trials for a publication-quality repeated
  interval.

Reports still compute the defined statistics below two or three trials, but
mark them underpowered.

## Report data model

The renderer consumes a versioned `ReportDocument`:

```text
ReportDocument
  report_schema_version
  renderer_version
  input_digest
  options
  warnings[]
  cohorts[]
    contract_fingerprint
    provenance_summary
    series[]
      resolved_subject_fingerprint
      planned_subject_fingerprint
      subject
      trials[]
      repeated_estimate?
      breakdowns[]
    skills_comparisons[]
    reference_checks[]
    exploit_audits[]
```

A `MetricEstimate` contains:

- `metric_id`
- `role`: `primary`, `diagnostic`, or `legacy`
- `value`
- optional `numerator`
- `denominator`
- `denominator_kind`
- `sample_size`
- optional named confidence interval
- notes and coverage warnings

Every breakdown row carries `planned`, `terminal`, `graded`, `passed`,
`failed`, `errored`, `diagnostic`, `missing`, and each applicable score
denominator. Missing metadata is assigned to an explicit `unknown` bucket.

Warnings are structured with `code`, `severity`, affected run/unit IDs,
message, and comparison effect. Required codes include `LEGACY_ADAPTED`,
`PROVENANCE_UNKNOWN`, `PARTIAL_RUN`, `INCOMPATIBLE_SCORING`,
`SELECTION_MISMATCH`, `UNPAIRED_SKILLS_RECORDS`,
`UNBALANCED_TRIAL_COUNTS`, and `TRIAL_COUNT_LOW`.

## Compatibility and cohorting

A comparison cohort key is `(mode, contract_fingerprint_sha256)`. Mode is also
bound into the fingerprint, and the explicit tuple prevents a future adapter
from mixing reference/audit/model semantics. The fingerprint
holds constant the dataset snapshot, selected catalog, scoring contract,
grader/runtime/harness identity, grading dimensions, and isolation while
allowing actor and variant subjects to differ.

Eligible repeated trials require the same
`resolved_subject_fingerprint_sha256`. Diagnostic trials with unresolved model
identity may use the same `planned_subject_fingerprint_sha256`, with a visible
provenance warning and no leaderboard styling. Rules:

- Reporting consumes the reader's relation result and never deduplicates raw
  inputs itself. The reader collapses equivalent canonical siblings and
  applies finalized/partial precedence. Legacy inputs remain distinct when no
  semantic relation can be proved and surface `legacy_possible_double_count`.
- The reader reports the same `run_id` with non-equivalent normalized-envelope
  content as an integrity failure; reporting lists that failure and continues
  with surviving inputs.
- Different contract fingerprints create separate cohorts and are never
  pooled or ranked together.
- Different subject fingerprints may be compared within a compatible cohort,
  but are not repeated trials of one subject.
- Units with `score_complete=false` are displayed and excluded from primary
  repeated estimates even when `record_complete=true`. Score-complete sibling
  units in a `completed_with_errors` envelope remain usable on their own.
- Completed but ineligible trials receive diagnostic summaries without rank or
  leaderboard styling.
- Unequal declared or complete trial counts remain visible but make the series
  comparison diagnostic and unranked.
- Display-name collisions are disambiguated with a short subject fingerprint.

## Mode and status handling

| Input | Primary presentation | Ranking/statistical behavior |
|---|---|---|
| Single model | Scorecard, provenance, completeness, breakdowns, usage | Ranked only with compatible eligible subjects. |
| Multi-model | Comparison table and interval chart, then subject details | Cohorted by contract; no cross-cohort rank. |
| Baseline + skills | Normal series plus paired skill-impact section | Use the owning manifest's pair map; resolve sourced arms only through declared refs. |
| Skills-only | Treatment scorecard and skill provenance | No synthetic baseline; explicit warning. |
| Reference solution | Reference coverage and exact failures | Validation only; target is complete 100% strict pass. |
| Exploit audit | Audit coverage, exploitable and unauditable tests | No model score; exploit denominator is canonical `audited_tests`. |
| Completed but ineligible | Full diagnostics and reasons | No rank or winner language. |
| Completed with errors | Per-unit completeness and failures; complete sibling units remain visible | Score-incomplete units and the repeated series are unranked. |
| Failed/aborted/partial | Status, observed progress, errors, and known missing work | No suite score or repeated estimate. |
| Legacy artifact | Best provable adapted view | Ineligible when completeness/provenance cannot be proved. |

For a legacy record-only partial without a manifest, reporting shows only
observed facts. It may show “pass among observed graded records,” but never
labels that value a suite pass rate.

## Metric definitions

Reporting displays canonical values rather than recomputing their eligibility
semantics.

### Primary and diagnostic metrics

- Strict execution pass rate is primary and always displays
  `passed / graded` with the label “conditional on graded attempts.”
- Selected execution success rate projects the canonical
  `passed / (planned - diagnostic)` metric unchanged, including
  `denominator_kind: gradable_planned`, as an operational
  completeness/reliability diagnostic. The diagnostic count is displayed
  beside it.
- Runtime partial mean displays its non-null applicable count.
- Static-policy pass rate displays its applicable count.
- `overall` is identified as an alias and is never plotted independently.
- `correctness` appears only in a collapsed legacy appendix and cannot affect
  sorting, color, rank, or winner language.
- Unknown usage/cost values remain unknown. Token and cost totals show call
  coverage; latency percentiles show sample count.

A zero denominator renders `N/A`, never zero.

### Dimension breakdowns

Break down each compatible subject by:

- category;
- difficulty;
- canonical selected descriptor `release_focus`;
- artifact kind;
- coverage family;
- runtime profile.

The selected-test catalog is filtered first, then canonical outcome and
applicability rules are projected into that subgroup. Rows reconcile exactly
to parent planned, terminal, graded, error, and missing counts. Reports show
both micro totals and macro category means; macro values are diagnostic and do
not replace the official primary metric.

### Single-trial task-outcome interval

Binary rates may display a Wilson score interval at the report's effective
confidence level. The default is 0.95, which uses `z ≈ 1.96`. It is
labeled a task-outcome interval: it describes dispersion across selected task
outcomes if treated as a sample, not run-to-run model repeatability or
WordPress-universe generalization. Cells with fewer than ten scored tasks
remain visible and receive a low-sample warning.

### Repeated trials

For `R` complete compatible trials, compute each trial metric first and give
each trial equal weight:

```text
mean = sum(trial values) / R
```

Report every trial value, `R`, mean, sample standard deviation, min/max, and a
Student-t interval at effective confidence `C`:

```text
mean ± t((1 + C) / 2, R-1) × sample_sd / sqrt(R)
```

The table retains raw interval bounds even when a t interval extends outside a
rate's natural range; only the chart axis is constrained to `[0,1]` for rates
or `[-1,1]` for deltas. One trial has no repeated standard deviation or
interval. Two score-complete trials may show the formula but are prominently
underpowered. Fewer than five score-complete trials do not receive
publication-quality styling.

The report does not infer a tie from overlapping intervals or superiority from
non-overlap. A repeated series is rankable only when every included unit is
individually eligible and score-complete, the complete-unit count equals its
declared trial count, and compared series share the same
`trial_protocol_fingerprint_sha256` and declared count. This is a report
presentation rule, not a new eligibility policy. Otherwise the repeated
estimate is diagnostic. Eligible ordering uses point estimates and states that
no pairwise hypothesis test determined order.

For `k` from 1 through `min(5, R)`, reports may show task-macro pass@k using the
standard unbiased estimator:

```text
1 - choose(R - task_successes, k) / choose(R, k)
```

pass@k is diagnostic, requires equal trial count for compared subjects, and
never replaces strict pass rate.

### Paired skills comparison

A valid automatic pair is defined solely by one owning sealed manifest's
non-null `pair_id` and its mapping to exactly two compatible unit IDs. An
executed arm is read from that manifest's envelope; a sourced arm is resolved
only after canonical sibling deduplication through its declared
external-unit reference, matching `source_run_id`, `source_unit_id`,
`source_semantic_envelope_sha256`, and contract fingerprint exactly. It retains
its original `run_id`. Actor, `trial_index`, and `test_id` must agree after
that declared join, but matching values never create a pair by themselves.
Sourced pairs are diagnostic and unranked because `unit_sourced_externally`
makes the owning run ineligible. For `n_graded_pairs`:

- `a`: both pass;
- `b`: baseline passes, skills fails (`broken`);
- `c`: baseline fails, skills passes (`fixed`);
- `d`: both fail.

The net strict-pass effect is `(c - b) / n_graded_pairs`. Reports show
`a,b,c,d,n_graded_pairs`, both pass rates, percentage-point delta,
excluded/error/missing pairs, and dimension-level effects.

Resource effects use separate paired populations:

- `n_runtime_pairs`: both records have applicable numeric runtime scores;
- `n_cost_pairs`: both attempts have known cost, including billable errored
  calls;
- `n_latency_pairs`: both attempts have numeric model-call latency, including
  errored calls with measured duration.

Each runtime/cost/latency delta displays its own paired count and known-field
coverage. It never reuses the strict-pass denominator.

For one A/B trial, use a deterministic paired bootstrap over test pairs with
the effective `bootstrap_samples` and confidence options for strict-pass and
runtime deltas. Defaults are 10,000 resamples and 0.95 percentile bounds. Also
show an exact two-sided McNemar p-value from discordant counts as secondary
evidence, without “statistically significant winner” language.

For repeated A/B trials, compute one paired delta per trial and report its
mean, sample standard deviation, and trial-level Student-t interval. Do not
pool repeated observations into one McNemar test. The bootstrap seed derives
from the canonical input digest unless the report option supplies one.

### Reference and exploit metrics

Reference mode reports strict pass plus failure, error, diagnostic, and missing
counts over the explicit denominator.

Exploit mode reports `audit_coverage`, candidate coverage, exploit rate,
audited-safe/exploitable/not-auditable/audit-error test counts, and
required/completed/error candidate counts. It includes a candidate table with
candidate ID, kind, attempted/completed state, outcome, stage, reason, and
assertion IDs. Zero-candidate and candidate-error tests never count as safe or
enter the exploit-rate denominator. `audited_tests` means tests with
`audit_complete`, exactly `exploitable + audited_safe`; reporting projects that
canonical denominator without substituting tests that merely had applicable
candidates.

## CLI, notebook, and HTML

Proposed commands:

```powershell
wp-bench report results_*.json --output report.html
wp-bench report run-a.json run-b.json run-c.json --output repeated.html
wp-bench report results.jsonl.partial --output partial.html
```

The report command resolves explicit files, directories, and glob patterns
itself so behavior is identical in PowerShell and POSIX shells. Directory
inputs include supported canonical/legacy JSON and JSONL artifacts but never
select an input merely because it has the newest timestamp; all resolved inputs
are listed before report generation.

Options are limited to `--confidence`, `--bootstrap-samples`, `--seed`, and
`--strict-compatible`. By default, incompatible inputs form separate warned
cohorts. Strict mode exits nonzero instead.

The report `--seed` controls statistical resampling only. It is unrelated to
run selection parameters or provider generation parameters.

`--confidence` defaults to `0.95` and accepts `0.5 <= C < 1.0`; Wilson,
Student-t, and bootstrap quantiles all derive from the same effective value.
`--bootstrap-samples` defaults to 10,000 and must be at least 1,000. The default
resampling seed derives from the ordered semantic-envelope digests. Every
effective option is recorded in `ReportDocument`.

The notebook has one `INPUTS` parameter cell and contains no parsing,
compatibility, denominator, or statistical formulas. CLI and notebook must
produce the same `ReportDocument` for identical inputs and options.

HTML ordering:

1. Status, completeness, eligibility, and compatibility warnings.
2. Provenance, run IDs, and input content hashes.
3. Primary strict-pass comparison with numerator/denominator and intervals.
4. Repeated-trial summary where available.
5. Category, difficulty, release, artifact, family, and runtime breakdowns.
6. Skills impact, reference validation, or exploit audit as applicable.
7. Usage, latency, cost-coverage, and reliability diagnostics.
8. Error and missing-work details.
9. Methods and legacy-compatibility appendix.

The evidence-baseline radar is removed because it double-counts the primary
metric.
Use dot-and-whisker charts and accessible data tables. HTML has inline CSS and
a pinned inline plotting bundle, stable element IDs, escaped labels, and no
network requests. Default output omits wall-clock report generation time and
absolute input paths. It records report-engine/dependency versions, options,
run IDs, content hashes, and deterministic input digest.
The input digest is computed from normalized semantic-envelope digests and
effective report options, not raw JSON-versus-JSONL bytes.

Given identical canonical inputs, options, report engine, and dependency
versions, output bytes must be identical.

## Failure behavior

- Unsupported future schema major, invalid canonical envelope, conflicting
  run ID, or one invalid input is fatal at that input or run-ID-group scope.
- Contract mismatches split cohorts and explain why comparison changed.
- Unknown legacy provenance or completeness disables eligibility.
- Missing dimension metadata enters `unknown` and emits a warning.
- Failed, aborted, partial, and ineligible inputs cannot display rank, winner
  language, or leaderboard badges.
- Missing one side of a skills pair excludes it from the paired denominator and
  increments a visible excluded count.
- Reference and exploit modes are never compared with model scores.
- Raw model and exploit payloads stay in source artifacts, not default reports.

"Fatal" means the affected input or group is excluded and named with its
stable failure code; surviving inputs still render, and the command exits
nonzero.

## Test strategy

- Unit-test denominator projection for pass, fail, error, diagnostic, missing,
  null applicability, and zero denominator.
- Pin Wilson, Student-t, pass@k, paired bootstrap, McNemar, usage coverage, and
  contingency-table examples.
- Test compatibility keys, duplicate detection, cohort splitting, subject
  grouping, unbalanced trials, and label disambiguation.
- Keep raw JSON/JSONL sibling equivalence, finalized-over-partial preference,
  and conflicting same-run rejection in reader tests. Reporting tests consume
  a pre-related `LoadResult` and verify its chosen representative, collapsed
  path provenance, failures, rendered exclusions, and aggregate nonzero exit.
- Test that unrelated baseline-only and skills-only inputs sharing actor,
  trial index, and test IDs do not pair; only an owning manifest's pair map can
  pair executed units or resolve a sourced unit through its declared external
  reference.
- Test `record_complete=true`/`score_complete=false` exclusion while a complete
  sibling unit remains usable.
- Test separate graded/runtime/cost/latency pair denominators, including
  billable errored attempts.
- Test every dimension bucket and exact reconciliation to parent counts.
- Add canonical fixtures for every mode and terminal status in the mode table.
- Use every entry in workstream 1's additive legacy fixture index; reporting
  receives only adapted envelopes and never branches on legacy version,
  difficulty, telemetry, or producer-specific fields.
- Test record-order invariance and deterministic resampling.
- Snapshot `ReportDocument` before snapshotting HTML.
- Assert two renders are byte-identical, labels are escaped, raw code is absent,
  and no external URL/script dependency exists.
- Exercise `wp-bench report` through Typer for success, warnings, strict
  incompatibility, optional-dependency failure, and fatal input.
- Execute the replacement notebook with small fixtures and compare its
  `ReportDocument` to the CLI result.
- Run `ruff check python`, `mypy python`, and `pytest python`.

## Rollout

1. Activate reporting only when the workstream 1 envelope, selected catalog,
   fingerprints, completeness, and legacy-reader capabilities are available;
   a reporting change that arrives first remains dormant or includes them.
2. Add `run.trials`, manifest unit expansion, planned-call display, and trial
   identity tests.
3. Add report models, cohorting, primary metrics, dimension breakdowns, and
   statistical fixtures.
4. Add deterministic standalone HTML and the CLI command.
5. Replace the notebook with the thin API client.
6. Add reporting projections and compatibility warnings for every indexed
   workstream 1 legacy fixture.
7. Update README metric, trial, reporting, and installation documentation.
8. Validate one real artifact for every mode/status and a five-trial mocked or
   low-cost model matrix before release.

## Acceptance criteria

1. Reporting opens inputs exclusively through canonical reader APIs, using
   `load_result_envelopes()` whenever relations between inputs are possible.
2. Every mode/status in the matrix produces a faithful standalone report.
3. Strict execution pass rate is primary; correctness and overall cannot
   distort ranking or visual emphasis.
4. Every rate displays numerator, denominator, denominator meaning,
   completeness, and eligibility.
5. All dimension rows, including `unknown`, reconcile to parent counts.
6. Benchmark `run.trials` creates distinct units over one frozen selection and
   records planned generations, retry-aware provider-call ceiling, initial
   grader executions, and recovery-aware maximum grader attempts before
   execution; validation/audit reject multiple trials.
7. Compatible score-complete trials show individual values, mean, dispersion,
   and a named interval; score-incomplete trials are excluded visibly.
8. Incompatible inputs are separated and never pooled.
9. Skills reports require an owning manifest pair map; sourced arms resolve
   only through declared external references. Reports include paired counts,
   net effect, uncertainty, fixed/broken tests, field-specific resource
   denominators, and excluded-pair counts.
10. Skills-only inputs never manufacture a baseline comparison.
11. Failed, aborted, partial, and legacy-unknown inputs cannot show rank or
    leaderboard styling.
12. Reference reports identify every failure/error/missing test.
13. Exploit reports expose test and candidate coverage, distinguish audit
    errors from rejected candidates, and use canonical `audited_tests`—tests
    with `audit_complete`, exactly `exploitable + audited_safe`—as the exploit
    denominator.
14. CLI and notebook produce the same report model.
15. HTML is offline, escaped, deterministic, and omits raw code by default.
16. Canonical, legacy, statistics, CLI, notebook, and renderer tests pass with
    repository lint and type checks.

## Risks and fixed assumptions

- Separate trials are treated as independent observations of provider/model
  behavior. The methods section states that provider infrastructure may
  violate that assumption.
- Wilson intervals over one fixed suite describe task-outcome dispersion, not
  repeatability or universal WordPress performance.
- Legacy artifacts cannot recover facts never recorded; the reader and report
  fail closed rather than infer them.
- Repeated trials multiply time and cost. The explicit planned-call display and
  default of one keep that choice visible.
- Byte reproducibility is scoped to pinned report and dependency versions,
  which are recorded in the report.

## Repository evidence

- `notebooks/results_report.ipynb`
- `python/wp_bench/scoring.py::ScoreBreakdown`
- `python/wp_bench/scoring.py::ScoreAggregator`
- `python/wp_bench/core.py::BenchmarkRunner.run`
- `python/wp_bench/core.py::BenchmarkRunner._run_exploit_audit`
- `python/wp_bench/core.py::MultiModelRunner._write_outputs`
- `python/wp_bench/output.py::print_comparison_table`
- `python/wp_bench/output.py::print_skill_impact`
- `python/wp_bench/results_io.py::RecordStream`
- `python/wp_bench/records.py::_base_record`
- `python/tests/test_continue_on_error.py`
- `python/tests/test_skill_variants.py`
- `python/tests/test_result_schema.py`
- `python/tests/test_result_streaming.py`
