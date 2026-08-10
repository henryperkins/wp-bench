"""Shared test helpers."""
from __future__ import annotations

from wp_bench.models import ModelGeneration


def fake_generation(
    text: str,
    *,
    ttft_ms: float | None = None,
    output_window_ms: float | None = None,
) -> ModelGeneration:
    """A ModelGeneration for tests that stub out the provider call.

    Serving telemetry defaults to absent, matching an unstreamed call;
    pass it explicitly to stand in for a streamed one.
    """
    return ModelGeneration(
        text=text,
        raw_response=None,
        retry_count=0,
        latency_ms=1.0,
        provider_response_id="test-response",
        ttft_ms=ttft_ms,
        output_window_ms=output_window_ms,
    )
