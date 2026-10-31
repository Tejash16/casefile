"""The one Anthropic client. Every model call in Casefile goes through `call()`.

Three call sites use it: propose, match, critique/write. `call()`:
- marks the static system blocks with `cache_control` so the prefix is cached across calls;
- writes an audit `model_call` pre record (name, model, prompt_sha256) and a post record
  (tokens_in, tokens_out, cache_read, result_sha256) for every attempt;
- with `output_schema`, asks for JSON via `output_config.format` (strict JSON schema derived from
  the Pydantic model), validates with Pydantic plus an optional semantic `validate` hook, and
  retries at most twice with the validation error fed back; then raises `StructuredOutputError`.

Sampling: current models (Opus 5.5, Haiku 5.5) accept only the default temperature and the SDK has
no `temperature` parameter, so `temperature` is recorded in the log as requested and never sent.
Determinism comes from strict schemas, low effort on match, and the coded gate.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from casefile.agents._audit import AuditSink, get_audit
from casefile.audit.log import hash_json

MODEL_STRONG = os.environ.get("CASEFILE_MODEL_STRONG", "claude-opus-5-5")
MODEL_FAST = os.environ.get("CASEFILE_MODEL_FAST", "claude-haiku-5-5")
# Server-side refusal fallback (beta) on strong-model calls; "0" turns it off.
FALLBACKS = os.environ.get("CASEFILE_FALLBACKS", "1") != "0"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}

MAX_RETRIES = 2
PROMPTS_DIR = Path(__file__).parent / "prompts"


class ModelCallError(RuntimeError):
    """A model call failed after the SDK's own transport retries."""


class ModelRefusalError(ModelCallError):
    """The model (and any fallback) declined the request."""


class StructuredOutputError(ModelCallError):
    """Output did not validate after MAX_RETRIES corrective retries."""

    def __init__(self, name: str, attempts: int, last_error: str) -> None:
        super().__init__(f"{name}: output invalid after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


@dataclass
class CallResult:
    output: Any  # validated Pydantic instance when output_schema was given, else None
    text: str  # concatenated text blocks
    message: Any  # raw SDK Message (the writer reads citations from it)
    model: str  # model that served the response
    log_record_id: str  # audit post record of the successful attempt
    attempts: int
    usage: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------- client and metrics

_client: Any = None
_client_lock = threading.Lock()
_totals_lock = threading.Lock()
_totals: dict[str, int] = {}


def _zero_totals() -> dict[str, int]:
    return {"model_calls": 0, "tokens_in": 0, "tokens_out": 0, "cache_read": 0, "cache_write": 0}


_totals = _zero_totals()


def get_client() -> Any:
    global _client
    with _client_lock:
        if _client is None:
            import anthropic

            try:
                from dotenv import load_dotenv

                load_dotenv()
            except ImportError:
                pass
            _client = anthropic.Anthropic(max_retries=4)
        return _client


def set_client(client: Any) -> None:
    """Inject a client (tests pass a fake with `.messages.create` / `.beta.messages.create`)."""
    global _client
    with _client_lock:
        _client = client


def usage_totals() -> dict[str, int]:
    """Running totals for the case-file metrics panel."""
    with _totals_lock:
        return dict(_totals)


def reset_usage_totals() -> None:
    global _totals
    with _totals_lock:
        _totals = _zero_totals()


INSTRUCTIONS_MARKER = "<!-- instructions -->"


def load_prompt(name: str) -> tuple[str, str]:
    """Return (system text, user-turn instructions) from `prompts/<name>.md`.

    The file holds the static system prompt, then a line `<!-- instructions -->`, then the
    instructions that close the user turn (data first, instructions last).
    """
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    system, _, instructions = text.partition(INSTRUCTIONS_MARKER)
    return system.strip(), instructions.strip()


def load_reference(name: str) -> str:
    """Static reference material bundled with the prompts (typology menu, test registry)."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------- schema helpers

_KEEP_KEYS = {"type", "properties", "required", "items", "enum", "anyOf", "description", "const"}


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema for `output_config.format`: refs inlined, every object closed and fully required.

    Range and length constraints are dropped from the wire schema (not all are supported by
    constrained decoding) and enforced by Pydantic on the way back instead.
    """
    raw = model.model_json_schema()
    defs = raw.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return walk(defs[node["$ref"].split("/")[-1]])
        out = {k: walk(v) for k, v in node.items() if k in _KEEP_KEYS}
        if "properties" in node:
            out["properties"] = {k: walk(v) for k, v in node["properties"].items()}
            out["required"] = list(node["properties"].keys())
            out["additionalProperties"] = False
        if "enum" in node and "type" not in out:
            out["type"] = "string"
        return out

    return walk(raw)


def _system_param(system_blocks: Sequence[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [{"type": "text", "text": t} for t in system_blocks if t]
    if blocks:
        # One breakpoint after the last static block caches the whole system prefix.
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def _as_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return list(content)


def _with_feedback(messages: list[dict[str, Any]], bad_output: str, error: str) -> list[dict]:
    """Fresh single-turn retry: the original user turn plus the rejected output and the error.

    A new request rather than an appended assistant turn keeps history append-only for models that
    bind thinking blocks to the conversation, and the cached system prefix still hits.
    """
    msgs = [dict(m) for m in messages]
    last = msgs[-1]
    feedback = (
        f"<previous_output>\n{bad_output[:6000]}\n</previous_output>\n"
        f"<validation_error>\n{error[:3000]}\n</validation_error>\n"
        "Your previous output was rejected for the reason above. Return a corrected JSON object "
        "that satisfies the schema and every instruction."
    )
    last["content"] = _as_blocks(last["content"]) + [{"type": "text", "text": feedback}]
    return msgs


def _usage(message: Any) -> dict[str, int]:
    u = getattr(message, "usage", None)

    def g(attr: str) -> int:
        return int(getattr(u, attr, 0) or 0) if u is not None else 0

    return {
        "tokens_in": g("input_tokens"),
        "tokens_out": g("output_tokens"),
        "cache_read": g("cache_read_input_tokens"),
        "cache_write": g("cache_creation_input_tokens"),
    }


def _text(message: Any) -> str:
    return "".join(
        getattr(b, "text", "") for b in getattr(message, "content", []) if b.type == "text"
    )


# ---------------------------------------------------------------- the call


def call(
    name: str,
    system_blocks: Sequence[str],
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    output_schema: type[BaseModel] | None = None,
    validate: Callable[[Any], None] | None = None,
    temperature: float | None = 0,
    effort: str | None = None,
    max_tokens: int = 16000,
    audit: AuditSink | None = None,
) -> CallResult:
    """One logged model call. See module docstring for the contract."""
    model = model or MODEL_STRONG
    # Per-call-site override for latency tuning, e.g. CASEFILE_EFFORT_PROPOSE=low.
    effort = os.environ.get(f"CASEFILE_EFFORT_{name.upper()}", effort) or None
    client = get_client()
    audit = get_audit(audit)
    system = _system_param(system_blocks)

    params: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "system": system}
    output_config: dict[str, Any] = {}
    if effort:
        output_config["effort"] = effort
    if output_schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": strict_schema(output_schema)}
    if output_config:
        params["output_config"] = output_config
    if tools:
        params["tools"] = [{**t, "strict": True} for t in tools]
    if tool_choice:
        params["tool_choice"] = tool_choice
    use_fallback = FALLBACKS and model in FALLBACK_MODELS

    attempt_messages = messages
    last_error = ""
    for attempt in range(1, MAX_RETRIES + 2):
        params["messages"] = attempt_messages
        prompt_sha = hash_json({k: v for k, v in params.items() if k != "max_tokens"})
        pre_id = audit.pre(
            "model_call",
            {
                "name": name,
                "model": model,
                "prompt_sha256": prompt_sha,
                "attempt": attempt,
                "effort": effort,
                "requested_temperature": temperature,
                "sampling": "api_default",
                "structured": output_schema.__name__ if output_schema else None,
                "fallbacks": use_fallback,
            },
        )
        try:
            if use_fallback:
                message = client.beta.messages.create(
                    **params, betas=[FALLBACK_BETA], fallbacks="default"
                )
            else:
                message = client.messages.create(**params)
        except Exception as e:  # SDK already retried 429/5xx/connection errors
            audit.post(pre_id, {"status": "error", "error": f"{type(e).__name__}: {e}"[:500]})
            raise ModelCallError(f"{name}: {type(e).__name__}: {e}") from e

        usage = _usage(message)
        text = _text(message)
        served_by = getattr(message, "model", model) or model
        stop_reason = getattr(message, "stop_reason", None)
        with _totals_lock:
            _totals["model_calls"] += 1
            for k in ("tokens_in", "tokens_out", "cache_read", "cache_write"):
                _totals[k] += usage[k]
        outcome: dict[str, Any] = {
            "status": "ok",
            **usage,
            "result_sha256": hash_json(text),
            "request_id": getattr(message, "_request_id", None) or getattr(message, "id", None),
            "stop_reason": stop_reason,
            "served_by": served_by,
        }

        if stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            outcome.update(status="refusal", error=str(getattr(details, "category", None)))
            audit.post(pre_id, outcome)
            raise ModelRefusalError(f"{name}: model declined ({outcome['error']})")

        if output_schema is None:
            post_id = audit.post(pre_id, outcome)
            return CallResult(None, text, message, served_by, post_id, attempt, usage)

        try:
            if stop_reason == "max_tokens":
                raise ValueError(f"output truncated at max_tokens={params['max_tokens']}")
            parsed = output_schema.model_validate_json(text)
            if validate is not None:
                validate(parsed)
        except (ValidationError, ValueError) as e:
            last_error = str(e)
            outcome.update(status="invalid_output", error=last_error[:1000])
            audit.post(pre_id, outcome)
            if stop_reason == "max_tokens":
                params["max_tokens"] = min(params["max_tokens"] * 2, 32000)
            attempt_messages = _with_feedback(messages, text, last_error)
            continue

        post_id = audit.post(pre_id, outcome)
        return CallResult(parsed, text, message, served_by, post_id, attempt, usage)

    raise StructuredOutputError(name, MAX_RETRIES + 1, last_error)
