"""Tests for serving telemetry: time-to-first-token and the output window.

These cover the diagnostic half of a model call — what the request looked
like from the client, not whether the completion was any good. Nothing
here may influence a score; the assertions guard the measurement's
honesty instead.

Timing is driven by a scripted clock advanced as each chunk is yielded,
never by real sleeps. Sleep-based tests can pass while measuring the wrong
boundary (they only assert "big enough"); a scripted clock makes every
assertion an exact value, so stamping the wrong chunk fails the test.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from litellm.exceptions import RateLimitError

import wp_bench.models as models_module
from wp_bench.config import (
    DatasetConfig,
    GraderConfig,
    HarnessConfig,
    ModelConfig,
    OutputConfig,
    RunConfig,
)
from wp_bench.core import BenchmarkRunner, MultiModelRunner
from wp_bench.datasets import ExecutionTest
from wp_bench.environment import ExecutionResult
from wp_bench.models import ModelInterface, _supports_stream_options
from wp_bench.records import _empty_usage
from wp_bench.scoring import UsageAggregator


def _ms(value: float | None) -> float:
    """Round a measurement to the microsecond for exact comparison.

    The scripted clock accumulates floats, so a value that is exactly
    1500ms by construction can land on 1499.9999999999998. Rounding to
    the microsecond keeps these exact-boundary assertions while dropping
    IEEE754 noise; it also narrows the Optional for the type checker.
    """
    assert value is not None
    return round(value, 3)


class _Clock:
    """A perf_counter stand-in advanced explicitly by the fake stream."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _content(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text, reasoning_content=None))]
    )


def _role_opener() -> SimpleNamespace:
    """The role-only chunk providers send before any content."""
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None, reasoning_content=None))]
    )


def _reasoning(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None, reasoning_content=text))]
    )


def _usage_trailer() -> SimpleNamespace:
    """The choice-less trailer a provider sends with include_usage."""
    return SimpleNamespace(
        choices=[],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )


def _text_of(chunks: list[Any]) -> str:
    """Reassemble content the way stream_chunk_builder would."""
    parts = []
    for chunk in chunks:
        for choice in getattr(chunk, "choices", None) or []:
            value = getattr(getattr(choice, "delta", None), "content", None)
            if isinstance(value, str):
                parts.append(value)
    return "".join(parts)


def _install(
    monkeypatch: pytest.MonkeyPatch,
    clock: _Clock,
    completion: Any,
    *,
    builder: Any = None,
) -> None:
    """Wire the fake clock, provider call, and chunk reassembly into models.

    Only wp_bench.models sees the fake clock — the real time module is
    untouched, so tenacity's backoff and rich's progress keep working.
    """
    monkeypatch.setattr(models_module, "time", SimpleNamespace(perf_counter=clock))
    monkeypatch.setattr(models_module, "completion", completion)
    monkeypatch.setattr(models_module, "completion_cost", lambda response: 0.002)
    monkeypatch.setattr(
        models_module,
        "stream_chunk_builder",
        builder
        or (
            # Rebuild from the chunks actually handed over, so a test can
            # prove which attempt's content survived.
            lambda chunks, messages=None: SimpleNamespace(
                choices=[SimpleNamespace(message={"content": _text_of(chunks)})],
                id="resp-stream",
                usage=SimpleNamespace(
                    prompt_tokens=100, completion_tokens=50, total_tokens=150
                ),
            )
        ),
    )


def _paced(clock: _Clock, script: list[tuple[float, Any]]) -> Any:
    """A fake completion() whose chunks arrive on the scripted clock."""

    def fake_completion(**kwargs: Any) -> Any:
        def stream() -> Any:
            for delay, chunk in script:
                clock.advance(delay)
                yield chunk

        return stream()

    return fake_completion


#: A representative stream: role opener, two content chunks, usage trailer.
#: TTFT = 0.50s, output window = 1.50s, total observed = 2.25s.
_STANDARD_SCRIPT: list[tuple[float, Any]] = [
    (0.00, _role_opener()),
    (0.50, _content("ans")),
    (1.50, _content("wer")),
    (0.25, _usage_trailer()),
]


def _streamed(name: str = "gpt-4o-mini", **overrides: Any) -> ModelInterface:
    defaults: dict[str, Any] = {"name": name, "stream": True}
    defaults.update(overrides)
    return ModelInterface(ModelConfig.model_validate(defaults))


def test_streamed_call_times_content_arrival_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _Clock()
    _install(monkeypatch, clock, _paced(clock, _STANDARD_SCRIPT))

    generation = _streamed().generate_with_metadata("hello")

    # The role opener carries no content, so it moves neither boundary:
    # TTFT is measured to the first content chunk at +0.50s.
    assert _ms(generation.ttft_ms) == 500.0
    # The window closes on the last content chunk at +2.00s, not on stream
    # exhaustion at +2.25s — the usage trailer is not delivery time.
    assert _ms(generation.output_window_ms) == 1500.0
    assert _ms(generation.latency_ms) == 2250.0
    assert generation.text == "answer"


def test_capability_probe_is_outside_the_timed_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider/capability lookup is harness preparation, not serving time."""
    clock = _Clock()
    _install(monkeypatch, clock, _paced(clock, _STANDARD_SCRIPT))

    def slow_probe(model: str) -> bool:
        clock.advance(5.0)  # an expensive local lookup
        return True

    monkeypatch.setattr(models_module, "_supports_stream_options", slow_probe)

    generation = _streamed().generate_with_metadata("hello")

    # Unchanged from the baseline: the 5s probe is charged to latency
    # (it is real wall clock) but never to the backend's TTFT.
    assert _ms(generation.ttft_ms) == 500.0
    assert _ms(generation.output_window_ms) == 1500.0
    assert _ms(generation.latency_ms) == 7250.0


def test_reasoning_deltas_do_not_start_the_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The harness grades `content`, so TTFT must track `content`.

    Counting reasoning would let a model look like it had started
    answering before any byte of the eventual artifact had arrived.
    """
    clock = _Clock()
    script = [
        (0.00, _role_opener()),
        (0.25, _reasoning("thinking hard")),
        (0.75, _content("answer")),
        (0.10, _usage_trailer()),
    ]
    _install(monkeypatch, clock, _paced(clock, script))

    generation = _streamed().generate_with_metadata("hello")

    # First content at +1.00s, not the reasoning delta at +0.25s.
    assert _ms(generation.ttft_ms) == 1000.0
    assert _ms(generation.output_window_ms) == 0.0


def test_empty_content_delta_does_not_establish_the_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """content="" is not content; whitespace is."""
    clock = _Clock()
    script = [
        (0.00, _role_opener()),
        (0.30, _content("")),  # empty: must not open the window
        (0.20, _content(" ")),  # whitespace: part of the answer, must open it
        (0.50, _content("hi")),
        (0.10, _usage_trailer()),
    ]
    _install(monkeypatch, clock, _paced(clock, script))

    generation = _streamed().generate_with_metadata("hello")

    assert _ms(generation.ttft_ms) == 500.0  # the whitespace chunk at +0.50s
    assert _ms(generation.output_window_ms) == 500.0  # to "hi" at +1.00s


def test_single_content_chunk_reports_a_zero_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero is measured, not missing: the whole answer arrived at once."""
    clock = _Clock()
    script = [(0.00, _role_opener()), (0.40, _content("answer")), (0.10, _usage_trailer())]
    _install(monkeypatch, clock, _paced(clock, script))

    generation = _streamed().generate_with_metadata("hello")

    assert _ms(generation.ttft_ms) == 400.0
    assert _ms(generation.output_window_ms) == 0.0
    assert generation.usage_dict()["output_window_ms"] == 0.0


def test_stream_without_content_has_null_timings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing to time, as opposed to something measured as zero.

    The completion still grades, as an empty answer.
    """
    clock = _Clock()
    script = [(0.00, _role_opener()), (0.50, _usage_trailer())]
    _install(monkeypatch, clock, _paced(clock, script))

    generation = _streamed().generate_with_metadata("hello")

    assert generation.ttft_ms is None
    assert generation.output_window_ms is None
    assert generation.text == ""


def test_unreassemblable_stream_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    """No response object at all is a harness failure, not an empty answer."""
    clock = _Clock()
    _install(
        monkeypatch,
        clock,
        _paced(clock, _STANDARD_SCRIPT),
        builder=lambda chunks, messages=None: None,
    )

    with pytest.raises(ValueError, match=r"4 chunk\(s\) received from gpt-4o-mini"):
        _streamed().generate_with_metadata("hello")


def test_empty_stream_fails_with_the_harness_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider stream yielding nothing gets WP-Bench's own error contract.

    The builder is rigged to explode if reached, proving the guard fires
    first: an empty stream must not depend on how a particular
    stream_chunk_builder version treats an empty list.
    """
    clock = _Clock()

    def exploding_builder(chunks: list[Any], messages: Any = None) -> Any:
        raise AssertionError("stream_chunk_builder must not be reached for an empty stream")

    _install(monkeypatch, clock, _paced(clock, []), builder=exploding_builder)

    with pytest.raises(ValueError, match=r"0 chunks received from gpt-4o-mini"):
        _streamed().generate_with_metadata("hello")


def test_non_streamed_call_has_null_serving_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default path is unchanged and reports nothing rather than a guess."""
    clock = _Clock()

    def fake_completion(**kwargs: Any) -> Any:
        clock.advance(1.25)
        return SimpleNamespace(
            choices=[SimpleNamespace(message={"content": "answer"})],
            id="resp-1",
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

    _install(monkeypatch, clock, fake_completion)

    generation = ModelInterface(ModelConfig(name="gpt-4o-mini")).generate_with_metadata("hi")

    assert generation.ttft_ms is None
    assert generation.output_window_ms is None
    assert _ms(generation.latency_ms) == 1250.0
    assert generation.completion_tokens == 50  # usage capture still works


def test_streamed_retry_discards_partial_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stream that fails mid-output must not contaminate the retry.

    Streaming moves most provider interaction into iterator consumption,
    a failure boundary the non-streamed path never had. This proves the
    boundary is still inside the retry scope, that attempt 1's partial
    content is discarded, and that the timings belong to attempt 2 alone
    while latency still spans the whole chain.
    """
    clock = _Clock()
    attempts: list[dict] = []

    def flaky_completion(**kwargs: Any) -> Any:
        attempts.append(kwargs)
        first = len(attempts) == 1

        def stream() -> Any:
            if first:
                clock.advance(0.10)
                yield _role_opener()
                clock.advance(0.20)
                yield _content("par")
                clock.advance(0.30)
                yield _content("tial")
                clock.advance(0.40)
                raise RateLimitError(
                    message="slow down", llm_provider="openai", model="gpt-4o-mini"
                )
            clock.advance(0.05)
            yield _role_opener()
            clock.advance(0.50)
            yield _content("final")
            clock.advance(1.50)
            yield _content(" answer")
            clock.advance(0.25)
            yield _usage_trailer()

        return stream()

    _install(monkeypatch, clock, flaky_completion)

    generation = _streamed(retry_min_seconds=0.01, retry_max_seconds=0.02).generate_with_metadata(
        "hello"
    )

    # The failure surfaced during iteration and was still retried.
    assert len(attempts) == 2
    assert generation.retry_count == 1
    # Attempt 1's partial content is gone; only attempt 2 was reassembled.
    assert generation.text == "final answer"
    assert "par" not in generation.text
    # Attempt 2 began at +1.00s; its first content landed at +1.55s.
    assert _ms(generation.ttft_ms) == 550.0
    assert _ms(generation.output_window_ms) == 1500.0
    # Latency spans both attempts, from the very start.
    assert _ms(generation.latency_ms) == 3300.0


def test_stream_options_requested_only_when_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _Clock()
    seen: list[dict] = []

    def recording_completion(**kwargs: Any) -> Any:
        seen.append(kwargs)
        return _paced(clock, _STANDARD_SCRIPT)(**kwargs)

    _install(monkeypatch, clock, recording_completion)

    monkeypatch.setattr(models_module, "_supports_stream_options", lambda model: True)
    _streamed().generate_with_metadata("hello")
    assert seen[-1]["stream"] is True
    assert seen[-1]["stream_options"] == {"include_usage": True}

    monkeypatch.setattr(models_module, "_supports_stream_options", lambda model: False)
    _streamed().generate_with_metadata("hello")
    assert "stream_options" not in seen[-1]


def test_capability_probe_works_against_the_installed_litellm() -> None:
    """Unmocked, so a LiteLLM signature change breaks CI instead of degrading.

    get_supported_openai_params took custom_llm_provider as a *required*
    argument in 1.37 and optional from 1.41 (this package's floor); the
    probe resolves and passes the provider, which is compatible with both
    shapes and avoids implicit provider detection. Deliberately asserts
    only that the call answers without raising — which providers support
    the option is LiteLLM's to change.
    """
    for model in ("gpt-4o-mini", "claude-sonnet-4-20250514", "ollama/llama3"):
        assert isinstance(_supports_stream_options(model), bool)

    # An unresolvable model (a custom endpoint) is a legitimate "no", not a crash.
    assert _supports_stream_options("totally-unknown-model-xyz") is False


def test_usage_dict_keys_match_the_canonical_record() -> None:
    """Asserted against _empty_usage() so the two cannot drift apart."""
    from wp_bench.models import ModelGeneration

    usage = ModelGeneration(
        text="x", raw_response=None, retry_count=0, latency_ms=1.0, provider_response_id=None
    ).usage_dict()

    assert set(usage.keys()) == set(_empty_usage().keys())


def test_usage_aggregator_reports_a_denominator_per_distribution() -> None:
    aggregator = UsageAggregator()
    for latency in (100.0, 200.0, 300.0, 400.0, 500.0):
        aggregator.add(
            {
                "latency_ms": latency,
                "ttft_ms": latency / 10,
                "output_window_ms": latency * 2,
            }
        )

    summary = aggregator.summary()

    assert summary["median_latency_ms"] == 300.0
    assert summary["p95_latency_ms"] == 500.0
    assert summary["p99_latency_ms"] == 500.0
    assert summary["latency_samples"] == 5
    assert summary["median_ttft_ms"] == 30.0
    assert summary["p99_ttft_ms"] == 50.0
    assert summary["ttft_samples"] == 5
    assert summary["median_output_window_ms"] == 600.0
    assert summary["output_window_samples"] == 5


def test_usage_aggregator_counts_only_real_observations() -> None:
    """Null telemetry reads as "not observed", never as zero.

    Reference-solution records carry an all-null usage object because no
    provider was called; they must not inflate any denominator.
    """
    aggregator = UsageAggregator()
    for _ in range(3):
        aggregator.add(_empty_usage())
    aggregator.add(None)
    aggregator.add({"latency_ms": 100.0})  # streamed off: latency only

    summary = aggregator.summary()

    assert summary["latency_samples"] == 1
    assert summary["ttft_samples"] == 0
    assert summary["output_window_samples"] == 0
    assert summary["median_ttft_ms"] is None
    assert summary["median_output_window_ms"] is None


def _execution_test() -> ExecutionTest:
    return ExecutionTest(
        id="e-one",
        suite="wp-core-v1",
        prompt="Prompt",
        expected_behavior="expected",
        category="hooks",
        difficulty="basic",
        requirements=[],
        test_function=None,
        static_checks={},
        runtime_checks={
            "assertions": [{"type": "custom_assertion", "code": "return true;", "weight": 1}]
        },
        reference_solution=None,
        metadata={},
    )


def test_streamed_run_records_telemetry_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Telemetry reaches both the per-test record and the run metadata."""
    clock = _Clock()
    _install(monkeypatch, clock, _paced(clock, _STANDARD_SCRIPT))
    monkeypatch.setattr("wp_bench.core.load_tests", lambda dataset: [_execution_test()])

    config = HarnessConfig(
        dataset=DatasetConfig(source="local", name="wp-core-v1"),
        model=ModelConfig(name="gpt-4o-mini", stream=True),
        grader=GraderConfig(kind="cli"),
        run=RunConfig(),
        output=OutputConfig(path=tmp_path / "results.json", jsonl_path=None),
    )
    runner = BenchmarkRunner(config)
    runner.environment.setup = lambda: None  # type: ignore[method-assign]
    runner.environment.reset = lambda: None  # type: ignore[method-assign]
    raw = {
        "success": True,
        "static": {"score": 1.0, "details": {"total_weight": 1}},
        "runtime": {"score": 1.0, "details": {"total_weight": 1}},
    }
    runner.environment.execute_artifact = lambda artifact, verification_spec: ExecutionResult(  # type: ignore[method-assign]
        success=True, raw=raw, stdout="", stderr=""
    )

    payload = runner.run()

    record = payload["results"][0]
    assert record["usage"]["ttft_ms"] == 500.0
    assert record["usage"]["output_window_ms"] == 1500.0
    # Whether telemetry was observable travels with the record.
    assert record["model"]["stream"] is True

    run_usage = payload["metadata"]["usage"]
    assert run_usage["median_ttft_ms"] == 500.0
    assert run_usage["ttft_samples"] == 1
    assert run_usage["output_window_samples"] == 1
    # Telemetry is diagnostic: the score keys are untouched by it.
    assert payload["metadata"]["scores"]["execution_pass_rate"] == 1.0


def test_multi_model_artifact_preserves_the_usage_rollup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Telemetry must survive into the combined multi-model file.

    SingleModelRunner returns a per-model usage rollup and the comparison
    table renders it, but the combined artifact used to serialize only
    config/scores/results — so telemetry appeared on screen and vanished
    from disk, which defeats the point of a reproducible artifact.
    """
    from conftest import fake_generation

    monkeypatch.setattr("wp_bench.core.load_tests", lambda dataset: [_execution_test()])
    config = HarnessConfig(
        dataset=DatasetConfig(source="local", name="wp-core-v1"),
        models=[
            ModelConfig(name="model-a", stream=True),
            ModelConfig(name="model-b", stream=True),
        ],
        grader=GraderConfig(kind="cli"),
        run=RunConfig(),
        output=OutputConfig(path=tmp_path / "multi.json", jsonl_path=None),
    )
    monkeypatch.setattr(
        "wp_bench.core.ModelInterface",
        lambda model_config: SimpleNamespace(
            generate_with_metadata=lambda prompt: fake_generation(
                "```php\n<?php\n```", ttft_ms=321.0, output_window_ms=654.0
            )
        ),
    )
    runner = MultiModelRunner(config)
    runner.environment = SimpleNamespace(  # type: ignore[assignment]
        setup=lambda: None,
        reset=lambda: None,
        execute_artifact=lambda artifact, spec: ExecutionResult(
            success=True,
            raw={
                "success": True,
                "static": {"score": 1.0, "details": {"total_weight": 1}},
                "runtime": {"score": 1.0, "details": {"total_weight": 1}},
            },
            stdout="",
            stderr="",
        ),
    )

    runner.run()

    written = sorted(tmp_path.glob("multi_*.json"))
    assert written
    payload = json.loads(written[-1].read_text())
    for name in ("model-a", "model-b"):
        usage = payload["models"][name]["usage"]
        assert usage["median_ttft_ms"] == 321.0
        assert usage["median_output_window_ms"] == 654.0
        assert usage["ttft_samples"] == 1
        assert usage["output_window_samples"] == 1
