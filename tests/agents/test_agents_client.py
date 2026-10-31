from __future__ import annotations

import pytest
from agent_fakes import message, read_log
from pydantic import BaseModel, Field

from casefile.agents import client
from casefile.agents.models import CritiqueWire, ProposeOutput


class Out(BaseModel):
    answer: str
    score: float = Field(ge=0, le=1)


def test_strict_schema_closes_objects_and_inlines_refs():
    schema = client.strict_schema(ProposeOutput)
    item = schema["properties"]["hypotheses"]["items"]
    assert schema["additionalProperties"] is False
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    assert "enum" in item["properties"]["typology"]
    assert "$ref" not in str(schema) and "$defs" not in schema
    assert "minimum" not in str(schema)
    crit = client.strict_schema(CritiqueWire)
    assert crit["properties"]["rationale"]["items"]["additionalProperties"] is False


def test_call_marks_cache_logs_and_never_sends_temperature(fake, audit_log):
    fake.responses = [message({"answer": "ok", "score": 0.5}, cache_read=900)]
    res = client.call(
        "unit",
        ["static system", "static ref"],
        [{"role": "user", "content": "q"}],
        model="claude-haiku-5-5",
        output_schema=Out,
        temperature=0,
        effort="low",
    )
    assert res.output == Out(answer="ok", score=0.5)
    sent = fake.calls[0]
    assert "temperature" not in sent
    assert sent["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in sent["system"][0]
    assert sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    recs = read_log(audit_log)
    assert [r["record_phase"] for r in recs] == ["pre_execution", "post_execution"]
    assert recs[0]["action_type"] == "model_call"
    assert recs[0]["action_detail"]["name"] == "unit"
    assert len(recs[0]["action_detail"]["prompt_sha256"]) == 64
    assert recs[1]["outcome"]["cache_read"] == 900
    assert recs[1]["outcome"]["tokens_in"] == 100
    assert client.usage_totals()["model_calls"] == 1


def test_strong_model_uses_fallback_beta(fake):
    fake.responses = [message({"answer": "ok", "score": 1})]
    client.call(
        "unit",
        ["s"],
        [{"role": "user", "content": "q"}],
        model="claude-opus-5-5",
        output_schema=Out,
    )
    assert fake.calls[0]["fallbacks"] == "default"
    assert fake.calls[0]["betas"] == [client.FALLBACK_BETA]


def test_retry_feeds_validation_error_back(fake, audit_log):
    fake.responses = [
        message({"answer": "x", "score": 7}),
        message({"answer": "x", "score": 0.7}),
    ]
    res = client.call(
        "unit",
        ["s"],
        [{"role": "user", "content": "q"}],
        model="claude-haiku-5-5",
        output_schema=Out,
    )
    assert res.attempts == 2 and res.output.score == 0.7
    retry_content = fake.calls[1]["messages"][-1]["content"]
    assert retry_content[0] == {"type": "text", "text": "q"}
    assert "<validation_error>" in retry_content[-1]["text"]
    assert len(fake.calls[1]["messages"]) == 1  # fresh single turn, no assistant turn appended
    outcomes = [r["outcome"]["status"] for r in read_log(audit_log) if r["outcome"]]
    assert outcomes == ["invalid_output", "ok"]


def test_semantic_validator_and_give_up(fake):
    fake.responses = [message({"answer": "bad", "score": 0.1}) for _ in range(3)]

    def validate(o: Out) -> None:
        if o.answer == "bad":
            raise ValueError("answer must not be bad")

    with pytest.raises(client.StructuredOutputError) as ei:
        client.call(
            "unit",
            ["s"],
            [{"role": "user", "content": "q"}],
            model="claude-haiku-5-5",
            output_schema=Out,
            validate=validate,
        )
    assert ei.value.attempts == 3
    assert len(fake.calls) == 3


def test_refusal_raises(fake):
    fake.responses = [message("", stop_reason="refusal")]
    with pytest.raises(client.ModelRefusalError):
        client.call("unit", ["s"], [{"role": "user", "content": "q"}], model="claude-haiku-5-5")


def test_transport_error_is_logged_and_typed(fake, audit_log):
    fake.responses = [RuntimeError("boom")]
    with pytest.raises(client.ModelCallError):
        client.call("unit", ["s"], [{"role": "user", "content": "q"}], model="claude-haiku-5-5")
    assert read_log(audit_log)[-1]["outcome"]["status"] == "error"


def test_prompt_files_have_instructions():
    for name in ("propose", "match", "critique", "write"):
        system, instructions = client.load_prompt(name)
        assert system and instructions.startswith("<instructions>"), name
