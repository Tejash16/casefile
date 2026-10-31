"""Shared data objects, transcribed from docs/contract.md (a1 owns this file).

Every object that crosses a module boundary is one of these models. Need a field? Message a1.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- enums


class AddressType(StrEnum):
    commercial = "commercial"
    residential = "residential"
    po_box = "po_box"
    virtual = "virtual"
    coworking = "coworking"
    unknown = "unknown"


class ResolutionStatus(StrEnum):
    resolved = "resolved"
    ambiguous = "ambiguous"
    unresolved = "unresolved"
    not_attempted = "not_attempted"


class ResolutionMethod(StrEnum):
    domain = "domain"
    identify_exact = "identify_exact"
    identify_fuzzy = "identify_fuzzy"
    person_identify_email = "person_identify_email"
    linkedin_url = "linkedin_url"
    person_search = "person_search"
    llm_judge = "llm_judge"


class Typology(StrEnum):
    shell_company = "shell_company"
    pass_through = "pass_through"
    conflict_of_interest = "conflict_of_interest"
    kickback = "kickback"
    non_accomplice_vendor = "non_accomplice_vendor"
    duplicate_billing = "duplicate_billing"
    threshold_structuring = "threshold_structuring"
    ghost_vendor = "ghost_vendor"


class Origin(StrEnum):
    tip = "tip"
    screen = "screen"


class Direction(StrEnum):
    supports = "supports"
    refutes = "refutes"
    neutral = "neutral"


class SourceKind(StrEnum):
    ledger_rows = "ledger_rows"
    vendor_master = "vendor_master"
    staff_list = "staff_list"
    crustdata_company = "crustdata_company"
    crustdata_person = "crustdata_person"
    graph = "graph"
    derived_stat = "derived_stat"


class Verdict(StrEnum):
    Substantiated = "Substantiated"
    Unfounded = "Unfounded"
    Unsubstantiated = "Unsubstantiated"


class VerdictBy(StrEnum):
    gate = "gate"
    gate_override_of_model = "gate_override_of_model"


class ActionType(StrEnum):
    file_read = "file_read"
    tool_call = "tool_call"
    model_call = "model_call"
    rule_test = "rule_test"
    gate = "gate"
    render = "render"


class RecordPhase(StrEnum):
    pre_execution = "pre_execution"
    post_execution = "post_execution"


class MatchVerdict(StrEnum):
    yes = "yes"
    no = "no"
    unsure = "unsure"


# ---------------------------------------------------------------- 2. resolution and Crustdata facts


class Resolution(Model):
    status: ResolutionStatus = ResolutionStatus.not_attempted
    method: ResolutionMethod | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    candidates_considered: int = 0
    log_record_id: str | None = None


class PersonBrief(Model):
    name: str
    title: str | None = None
    linkedin_url: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class Employment(Model):
    company_name: str
    crustdata_company_id: str | None = None
    company_domain: str | None = None
    title: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False


class CompanyFacts(Model):
    crustdata_company_id: str
    name: str
    primary_domain: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    year_founded: int | None = None
    status: str | None = None
    employee_count_range: str | None = None
    headcount_total: int | None = None
    headcount_timeseries: list[tuple[date, int]] = Field(default_factory=list)
    hq_city: str | None = None
    hq_country: str | None = None
    street_address: str | None = None
    founders: list[PersonBrief] = Field(default_factory=list)
    decision_makers: list[PersonBrief] = Field(default_factory=list)
    total_funding_usd: Decimal | None = None
    description: str | None = None
    updated_at: str
    source_request_id: str
    cache_hit: bool = False

    @property
    def citation(self) -> str:
        return f"crustdata:company:{self.crustdata_company_id}@{self.updated_at}"


class PersonFacts(Model):
    crustdata_person_id: str
    name: str
    profile_url: str
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    employment: list[Employment] = Field(default_factory=list)
    updated_at: str
    source_request_id: str
    cache_hit: bool = False

    @property
    def citation(self) -> str:
        return f"crustdata:person:{self.crustdata_person_id}@{self.updated_at}"


# ---------------------------------------------------------------- 1. inputs


class Tip(Model):
    text: str
    received_at: str
    sha256: str


class LedgerRow(Model):
    row_id: str
    date: date
    vendor_name_raw: str
    vendor_key: str
    vendor_id: str | None = None
    invoice_no: str | None = None
    amount: Decimal
    currency: str = "INR"
    approver_name_raw: str | None = None
    approver_id: str | None = None
    created_by: str | None = None
    posted_at: datetime | None = None
    description: str | None = None
    po_number: str | None = None
    bank_account: str | None = None
    quality_flags: list[str] = Field(default_factory=list)


class VendorRecord(Model):
    vendor_id: str
    name_raw: str
    name_norm: str
    address: str | None = None
    address_type: AddressType = AddressType.unknown
    city: str | None = None
    state: str | None = None
    country: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    tax_id: str | None = None
    bank_account: str | None = None
    created_on: date | None = None
    created_by: str | None = None
    resolution: Resolution = Field(default_factory=Resolution)
    crustdata: CompanyFacts | None = None


class StaffRecord(Model):
    staff_id: str
    name_raw: str
    name_norm: str
    title: str | None = None
    department: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    bank_account: str | None = None
    joined_on: date | None = None
    approval_limit: Decimal | None = None
    linkedin_url: str | None = None
    resolution: Resolution = Field(default_factory=Resolution)
    crustdata: PersonFacts | None = None


# ---------------------------------------------------------------- 3. hypotheses, evidence, findings


class Hypothesis(Model):
    hypothesis_id: str
    typology: Typology
    statement: str
    subjects: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    tests_to_run: list[str] = Field(default_factory=list)
    prior_score: float = Field(default=0.5, ge=0, le=1)
    origin: Origin = Origin.tip
    rationale: str = ""


class Source(Model):
    kind: SourceKind
    refs: list[str] = Field(default_factory=list)
    as_of: str | None = None


class EvidenceObject(Model):
    evidence_id: str
    test_id: str
    hypothesis_ids: list[str] = Field(default_factory=list)
    subject_ids: list[str] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)
    direction: Direction
    strength: float = Field(ge=0, le=1)
    summary: str
    quote: str
    source: Source
    sha256: str
    log_record_id: str

    @staticmethod
    def compute_sha256(payload: bytes) -> str:
        """Hex SHA-256 of the source payload the quote came from."""
        return hashlib.sha256(payload).hexdigest()


class Sentence(Model):
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    require_citation: bool = False

    @model_validator(mode="after")
    def _cited_when_required(self) -> Sentence:
        if self.require_citation and not self.evidence_ids:
            raise ValueError(f"sentence requires at least one evidence id: {self.text!r}")
        return self


class Finding(Model):
    hypothesis_id: str
    verdict: Verdict
    verdict_by: VerdictBy = VerdictBy.gate
    model_verdict: Verdict | None = None
    supporting_evidence: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    amount_at_issue_inr: Decimal | None = None
    rationale: list[Sentence] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class CaseFile(Model):
    case_id: str
    company_name: str
    generated_at: str
    predication: Sentence
    executive_summary: list[Sentence] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    approach: list[str] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    data_quality: list[str] = Field(default_factory=list)
    assumptions: dict[str, str] = Field(default_factory=dict)
    exhibits: list[EvidenceObject] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    merkle_root: str = ""
    verify_command: str = ""


# ---------------------------------------------------------------- 4. audit log


class LogRecord(Model):
    record_id: str
    seq: int
    timestamp: str
    agent_id: str
    session_id: str
    action_type: ActionType
    action_detail: dict[str, Any] = Field(default_factory=dict)
    outcome: dict[str, Any] | None = None
    record_phase: RecordPhase
    parent_record_id: str | None = None
    prev_hash: str
    record_hash: str


# ---------------------------------------------------------------- 5. objects named in signatures


class IdentifyResult(Model):
    """One query's result from POST /company/identify (b2)."""

    query: str
    crustdata_company_id: str | None = None
    name: str | None = None
    primary_domain: str | None = None
    confidence_score: float | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str | None = None
    cache_hit: bool = False


class PersonCandidate(Model):
    """A person returned by /person/search or /person/identify (b2)."""

    name: str
    profile_url: str
    crustdata_person_id: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    score: float | None = None
    request_id: str | None = None
    cache_hit: bool = False


class MatchDecision(Model):
    """agents.match.judge_candidates output (a2)."""

    decision: MatchVerdict
    index: int | None = None
    reason: str = ""
    log_record_id: str | None = None


class CriticOutput(Model):
    """agents.critique.critique output (a2)."""

    model_verdict: Verdict
    rationale: list[Sentence] = Field(default_factory=list)
    strongest_counter: str | None = None
    missing_tests: list[str] = Field(default_factory=list)
    hypothesis_id: str | None = None
    log_record_id: str | None = None


# ---------------------------------------------------------------- 8. case spec (case.json)


class CaseInputs(Model):
    tip: str
    ledger: str
    vendors: str
    staff: str


class ExpectedFinding(Model):
    typology: Typology
    subjects: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    verdict: Verdict


class CaseSpec(Model):
    name: str
    inputs: CaseInputs
    expected: list[ExpectedFinding] = Field(default_factory=list)
    must_clear: list[str] = Field(default_factory=list)
    notes: str | None = None
