"""Model interface leveraging LiteLLM providers.

Model calls are wrapped in a bounded, configurable retry policy
(tenacity, exponential backoff with jitter). Only transient provider
failures are retried — rate limits, timeouts, connection drops, and
5xx/internal errors. Deterministic request errors (bad model name, bad
API key, context overflow, malformed request) fail fast so systemic
problems are not hidden behind retries.

Calls also carry serving telemetry: what the request looked like from the
client, as opposed to whether the completion was any good. The split is
deliberate — telemetry is diagnostic and never feeds a score (see
scoring.SCORING_VERSION).

End-to-end latency cannot distinguish time spent before the first answer
content arrives from time spent delivering the answer afterward. Streaming
(``model.stream``) makes those two client-observable phases measurable
separately, as ``ttft_ms`` and ``output_window_ms``. Both are observations
from the request boundary; neither is an inference-engine metric, and the
harness deliberately derives no token rate from them (a client cannot see
token boundaries inside a chunk).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, cast

from litellm import (
    completion,
    completion_cost,
    get_llm_provider,
    get_supported_openai_params,
    stream_chunk_builder,
)
from litellm.exceptions import (
    APIConnectionError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from litellm.utils import ModelResponse
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from .config import ModelConfig

#: Exception types that indicate a transient provider problem.
_TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    RateLimitError,
    Timeout,
    APIConnectionError,
    InternalServerError,
    ServiceUnavailableError,
)


@dataclass
class _AttemptTiming:
    """Serving timings for one provider attempt, not for the retry chain.

    Both fields are None for a non-streamed call, where the client cannot
    see when the answer began arriving.
    """

    ttft_ms: float | None = None
    output_window_ms: float | None = None


@dataclass
class ModelGeneration:
    """A completion plus the call metadata needed for audit and reporting."""

    text: str
    raw_response: ModelResponse | None
    retry_count: int
    latency_ms: float
    provider_response_id: str | None
    temperature_fallback: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    #: Provider call start to the first chunk carrying answer content, on
    #: the attempt that succeeded. Streamed calls only.
    ttft_ms: float | None = None
    #: First content-bearing chunk to the last one, on the attempt that
    #: succeeded. Streamed calls only. Zero is a real measurement — the
    #: whole answer arrived in one chunk. ttft_ms + output_window_ms is
    #: that attempt's observed span, which is below latency_ms whenever a
    #: failed attempt and its backoff preceded it.
    output_window_ms: float | None = None

    def usage_dict(self) -> dict[str, Any]:
        """Usage object in the canonical result-record shape.

        The key set must match records._empty_usage() exactly: every result
        record carries the same usage keys whether or not a provider was
        involved, so consumers never branch on presence.
        """
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "latency_ms": round(self.latency_ms, 1),
            "ttft_ms": round(self.ttft_ms, 1) if self.ttft_ms is not None else None,
            "output_window_ms": (
                round(self.output_window_ms, 1)
                if self.output_window_ms is not None
                else None
            ),
        }


class ModelInterface:
    """Thin wrapper over LiteLLM to keep prompts consistent."""

    def __init__(self, config: ModelConfig):
        self.config = config

    def generate(self, prompt: str) -> str:
        """Generate a completion for the given prompt (text only).

        Compatibility wrapper over generate_with_metadata().
        """
        return self.generate_with_metadata(prompt).text

    def generate_with_metadata(self, prompt: str) -> ModelGeneration:
        """Generate a completion with retry, latency, and call metadata.

        Transient provider errors (rate limit, timeout, connection, 5xx)
        are retried up to ``config.max_retries`` additional attempts with
        exponential backoff and jitter. Non-retryable errors propagate
        immediately, preserving the original exception for the caller.

        Latency covers all attempts, including backoff waits, because that
        is the wall-clock cost of obtaining the completion. The serving
        timings (ttft_ms, output_window_ms) cover only the attempt that
        succeeded: a TTFT inflated by an earlier rate-limit backoff, or an
        output window stitched together from a partial failed stream, would
        describe the harness rather than the request.
        """
        kwargs = self._completion_kwargs(prompt)
        started = time.perf_counter()
        attempt_count = 0
        temperature_fallback = False
        timing = _AttemptTiming()

        def _should_retry(error: BaseException) -> bool:
            if not self._retry_enabled_for(error):
                return False
            return isinstance(error, _TRANSIENT_ERRORS)

        def _before(retry_state: RetryCallState) -> None:
            nonlocal attempt_count
            attempt_count = retry_state.attempt_number

        response: ModelResponse | None = None
        for attempt in Retrying(
            stop=stop_after_attempt(self.config.max_retries + 1),
            wait=wait_random_exponential(
                multiplier=self.config.retry_min_seconds,
                max=self.config.retry_max_seconds,
            ),
            retry=retry_if_exception(_should_retry),
            before=_before,
            reraise=True,
        ):
            with attempt:
                try:
                    response, timing = self._invoke(kwargs)
                except BadRequestError as error:
                    # Deterministic error, except the known deprecated-
                    # temperature case which is fixable by dropping the
                    # parameter. That fallback is intentional behavior,
                    # not a retry, and is flagged separately.
                    if not _is_deprecated_temperature_error(error) or "temperature" not in kwargs:
                        raise
                    kwargs.pop("temperature")
                    temperature_fallback = True
                    response, timing = self._invoke(kwargs)

        assert response is not None  # Retrying(reraise=True) raises otherwise
        latency_ms = (time.perf_counter() - started) * 1000
        choice = response.choices[0]
        usage = _extract_usage(response)
        return ModelGeneration(
            # Providers can return None content (safety block, thinking-only
            # response, truncation). That is a model output, not a harness
            # fault: normalize to "" so it grades as an empty answer.
            text=choice.message["content"] or "",  # type: ignore[union-attr, index]
            raw_response=response,
            retry_count=attempt_count - 1,
            latency_ms=latency_ms,
            provider_response_id=getattr(response, "id", None),
            temperature_fallback=temperature_fallback,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=_estimate_cost_safe(response),
            ttft_ms=timing.ttft_ms,
            output_window_ms=timing.output_window_ms,
        )

    def _invoke(self, kwargs: dict[str, Any]) -> tuple[ModelResponse, _AttemptTiming]:
        """Issue one provider call, streamed or not, with its serving timings."""
        if not self.config.stream:
            return completion(**kwargs), _AttemptTiming()
        return self._invoke_streamed(kwargs)

    def _prepare_stream_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Build the streaming request kwargs, capability lookup included.

        Kept strictly outside the timed section of _invoke_streamed:
        resolving the provider and reading LiteLLM's capability table is
        local harness preparation, not observed serving time, and must
        never land inside ttft_ms.
        """
        stream_kwargs = dict(kwargs, stream=True)
        if _supports_stream_options(self.config.name):
            stream_kwargs["stream_options"] = {"include_usage": True}
        return stream_kwargs

    def _invoke_streamed(self, kwargs: dict[str, Any]) -> tuple[ModelResponse, _AttemptTiming]:
        """Stream one provider call, timing when answer content arrives.

        The chunks are reassembled into an ordinary ModelResponse so the
        rest of the harness — usage extraction, cost estimation, artifact
        parsing — runs the same code path as the non-streamed branch.
        (The same path and response shape, not necessarily identical
        numbers: reconstructed usage can differ from provider-reported
        usage, which is why real usage is requested where supported.)

        Each attempt reassembles only its own chunks, so a failed attempt
        that streamed partial content contributes nothing to the retry
        that succeeds.
        """
        stream_kwargs = self._prepare_stream_kwargs(kwargs)

        # Clock origin is the provider call itself: everything above is
        # local preparation and must not be charged to the backend.
        attempt_started = time.perf_counter()
        first_content_at: float | None = None
        last_content_at: float | None = None
        chunks: list[Any] = []
        for chunk in completion(**stream_kwargs):
            if _chunk_carries_content(chunk):
                arrived = time.perf_counter()
                if first_content_at is None:
                    first_content_at = arrived
                last_content_at = arrived
            chunks.append(chunk)

        if not chunks:
            # Guarded before reassembly so a genuinely empty provider
            # stream gets this stable error rather than whatever a given
            # stream_chunk_builder version happens to do with an empty
            # list. Same class of failure as the None case below: no
            # response object exists, so there is nothing to grade.
            raise ValueError(
                f"Streamed completion produced no response "
                f"(0 chunks received from {self.config.name})."
            )

        built = stream_chunk_builder(chunks, messages=kwargs["messages"])
        if built is None:
            # Distinct from the provider returning None content, which is a
            # model output graded as an empty answer: here there is no
            # response object at all, so there is nothing to grade. Fail
            # loudly rather than invent a completion.
            raise ValueError(
                f"Streamed completion produced no reassemblable response "
                f"({len(chunks)} chunk(s) received from {self.config.name})."
            )
        # The return union also covers TextCompletionResponse, which only
        # arises for text-completion streams; this path always sends
        # `messages`, so the reassembled object is a chat ModelResponse.
        response = cast(ModelResponse, built)
        if first_content_at is None or last_content_at is None:
            # The stream carried a response but no answer content: nothing
            # to time, as opposed to something measured as zero.
            return response, _AttemptTiming()
        return response, _AttemptTiming(
            ttft_ms=(first_content_at - attempt_started) * 1000,
            # Closes on the last content chunk, never on stream exhaustion:
            # the finish/usage trailer arrives after the answer is done and
            # must not be counted as time spent delivering it.
            output_window_ms=(last_content_at - first_content_at) * 1000,
        )

    def _retry_enabled_for(self, error: BaseException) -> bool:
        """Apply per-category retry switches from config."""
        if isinstance(error, RateLimitError):
            return self.config.retry_on_rate_limit
        if isinstance(error, Timeout):
            return self.config.retry_on_timeout
        return True

    @staticmethod
    def estimate_cost(response: ModelResponse) -> float:
        return completion_cost(response)

    def _completion_kwargs(self, prompt: str) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.config.name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "timeout": self.config.request_timeout,
        }
        kwargs["temperature"] = self.config.temperature
        return kwargs


def _is_deprecated_temperature_error(error: BadRequestError) -> bool:
    return "`temperature` is deprecated" in str(error)


def _supports_stream_options(model: str) -> bool:
    """Whether the provider accepts ``stream_options={"include_usage": True}``.

    LiteLLM raises on parameters a provider does not support rather than
    dropping them, so the option cannot be sent blind.

    LiteLLM 1.37 required ``custom_llm_provider``; it is optional from
    1.41, which is this package's corrected dependency floor. Resolving
    and passing the provider explicitly is therefore not a compatibility
    workaround any more — it is compatible with both API shapes and
    avoids relying on implicit provider detection inside the lookup.

    Only the provider-resolution failure is caught: an unknown model
    string (a custom endpoint) legitimately has no capability table,
    whereas a TypeError or AttributeError here means the LiteLLM API
    moved and should fail loudly instead of silently downgrading every
    run's usage to reconstructed estimates.
    """
    try:
        _, provider, *_ = get_llm_provider(model=model)
    except BadRequestError:
        return False
    supported = get_supported_openai_params(model=model, custom_llm_provider=provider) or []
    return "stream_options" in supported


def _chunk_carries_content(chunk: Any) -> bool:
    """Whether a stream chunk carries answer content.

    Only ``delta.content`` counts. The harness grades
    ``choice.message["content"]``, so timing anything else would let a
    model look like it had started answering before a single byte of the
    eventual WordPress artifact had arrived — notably ``reasoning_content``,
    which is why reasoning deltas are excluded here. A reasoning-inclusive
    metric would be a different measurement and would need its own name.

    Content is a *non-empty* string: an empty delta must not open or
    extend the window, while whitespace must, being part of the generated
    answer. Role-only openers and the choice-less usage trailer carry no
    content and move neither boundary.
    """
    for choice in getattr(chunk, "choices", None) or []:
        delta = getattr(choice, "delta", None)
        if delta is None and isinstance(choice, dict):
            delta = choice.get("delta")
        if delta is None:
            continue
        value = getattr(delta, "content", None)
        if value is None and isinstance(delta, dict):
            value = delta.get("content")
        if isinstance(value, str) and value != "":
            return True
    return False


def _extract_usage(response: Any) -> dict[str, int | None]:
    """Read token usage defensively; providers may omit any field."""
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")

    def _read(field: str) -> int | None:
        if usage is None:
            return None
        value = getattr(usage, field, None)
        if value is None and isinstance(usage, dict):
            value = usage.get(field)
        return int(value) if isinstance(value, (int, float)) else None

    return {
        "prompt_tokens": _read("prompt_tokens"),
        "completion_tokens": _read("completion_tokens"),
        "total_tokens": _read("total_tokens"),
    }


def _estimate_cost_safe(response: Any) -> float | None:
    """Best-effort cost estimate via LiteLLM; None when unpriceable.

    Cost is an estimate, not billing truth: unknown models, custom
    endpoints, and local providers have no pricing data, and estimation
    failures must never abort a benchmark run.
    """
    try:
        cost = completion_cost(response)
    except Exception:  # noqa: BLE001 -- best-effort estimate over arbitrary providers
        return None
    return float(cost) if isinstance(cost, (int, float)) else None
