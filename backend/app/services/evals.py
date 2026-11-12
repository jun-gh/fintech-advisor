"""LLM-as-a-Judge evaluation harness (evalgen pattern) for Compliance Copilot."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.copilot import CopilotQueryResponse
from app.services.llm import StructuredLLMClient

_JUDGE_SYSTEM_INSTRUCTION = """You are an impartial, strict financial compliance evaluation judge.
Evaluate the model's RAG response against the cited policy context and required facts.
Penalize hallucinations, unsupported numbers/timelines, or failing to refuse out-of-scope questions."""


class BenchmarkCase(BaseModel):
    """Single golden benchmark evaluation case loaded from JSONL."""

    id: str
    query: str
    expected_outcome: Literal["answered", "refused"]
    expected_source_id: str | None = None
    required_facts: list[str] = Field(default_factory=list)
    expect_pii_redacted: bool = False


class JudgeEvaluation(BaseModel):
    """Structured rubric scored by the LLM judge."""

    faithfulness_score: int = Field(
        ge=1,
        le=5,
        description="1-5: Is every claim in the answer strictly supported by the cited context?",
    )
    relevance_score: int = Field(
        ge=1,
        le=5,
        description="1-5: Does the answer directly and clearly address the user's question?",
    )
    fact_coverage_pass: bool = Field(
        description="True if the answer accurately covers the required facts (or properly refuses)."
    )
    negative_test_pass: bool = Field(
        description="True if refusal cases actually declined to answer instead of hallucinating."
    )
    reasoning: str = Field(description="Concise rationale explaining the scores.")


class CaseEvalReport(BaseModel):
    """Combined deterministic + LLM-judge report for a single benchmark case."""

    case_id: str
    passed: bool
    outcome_match: bool
    citation_match: bool
    pii_check_pass: bool
    judge: JudgeEvaluation


class SuiteEvalSummary(BaseModel):
    """Aggregate metrics across all benchmark cases."""

    total_cases: int
    passed_cases: int
    pass_rate: float
    avg_faithfulness: float
    avg_relevance: float
    citation_precision_rate: float
    negative_refusal_rate: float
    reports: list[CaseEvalReport]


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    """Load and validate benchmark cases from a JSONL file."""
    cases: list[BenchmarkCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cases.append(BenchmarkCase.model_validate_json(stripped))
    return cases


def _format_judge_prompt(case: BenchmarkCase, response: CopilotQueryResponse) -> str:
    if response.citations:
        context_text = "\n\n".join(
            f"[{c.chunk_id} | {c.section_title}]\n{c.excerpt}"
            for c in response.citations
        )
    else:
        context_text = "(No policy citations attached)"

    facts_text = "\n".join(f"- {fact}" for fact in case.required_facts) or "- None"
    return (
        f"[Expected Outcome]: {case.expected_outcome}\n\n"
        f"[Required Facts / Constraint]:\n{facts_text}\n\n"
        f"[Cited Policy Context]:\n{context_text}\n\n"
        f"[User Query]:\n{case.query}\n\n"
        f"[Model Outcome]: {response.outcome}\n"
        f"[Model Answer]:\n{response.answer}"
    )


async def evaluate_case(
    case: BenchmarkCase,
    response: CopilotQueryResponse,
    judge_llm: StructuredLLMClient,
) -> CaseEvalReport:
    """Evaluate a single Copilot response using deterministic checks + LLM-as-a-Judge."""
    outcome_match = response.outcome == case.expected_outcome

    if case.expected_source_id is not None:
        citation_match = any(
            c.source_id == case.expected_source_id for c in response.citations
        )
    else:
        citation_match = len(response.citations) == 0

    if case.expect_pii_redacted:
        pii_check_pass = (
            response.pii_redacted_count > 0
            and "4111-1111-1111-1111" not in response.sanitized_query
            and "4111-1111-1111-1111" not in response.answer
        )
    else:
        pii_check_pass = True

    judge = await judge_llm.generate_structured(
        system_instruction=_JUDGE_SYSTEM_INSTRUCTION,
        user_prompt=_format_judge_prompt(case, response),
        response_schema=JudgeEvaluation,
    )

    if case.expected_outcome == "answered":
        judge_ok = (
            judge.faithfulness_score >= 4
            and judge.relevance_score >= 4
            and judge.fact_coverage_pass
        )
    else:
        judge_ok = judge.negative_test_pass

    passed = outcome_match and citation_match and pii_check_pass and judge_ok

    return CaseEvalReport(
        case_id=case.id,
        passed=passed,
        outcome_match=outcome_match,
        citation_match=citation_match,
        pii_check_pass=pii_check_pass,
        judge=judge,
    )


def summarize_eval_reports(
    cases: list[BenchmarkCase],
    reports: list[CaseEvalReport],
) -> SuiteEvalSummary:
    """Compute aggregate quality metrics from individual case evaluation reports."""
    total = len(reports)
    passed_count = sum(1 for r in reports if r.passed)

    positive_reports = [
        r for c, r in zip(cases, reports, strict=True) if c.expected_outcome == "answered"
    ]
    negative_reports = [
        r for c, r in zip(cases, reports, strict=True) if c.expected_outcome == "refused"
    ]

    avg_faith = (
        sum(r.judge.faithfulness_score for r in positive_reports) / len(positive_reports)
        if positive_reports
        else 0.0
    )
    avg_rel = (
        sum(r.judge.relevance_score for r in positive_reports) / len(positive_reports)
        if positive_reports
        else 0.0
    )
    cit_rate = (
        sum(1 for r in positive_reports if r.citation_match) / len(positive_reports)
        if positive_reports
        else 0.0
    )
    neg_rate = (
        sum(1 for r in negative_reports if r.outcome_match and r.judge.negative_test_pass)
        / len(negative_reports)
        if negative_reports
        else 1.0
    )

    return SuiteEvalSummary(
        total_cases=total,
        passed_cases=passed_count,
        pass_rate=(passed_count / total) if total else 0.0,
        avg_faithfulness=round(avg_faith, 2),
        avg_relevance=round(avg_rel, 2),
        citation_precision_rate=round(cit_rate, 2),
        negative_refusal_rate=round(neg_rate, 2),
        reports=reports,
    )
