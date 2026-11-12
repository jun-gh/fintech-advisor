"""Automated LLM evaluation harness tests (deterministic PR gate + live Gemini evals)."""

from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import close_db, ensure_schema, get_session_factory, init_db
from app.models.compliance import AuditLog
from app.schemas.copilot import Citation, CopilotQueryRequest, CopilotQueryResponse
from app.services.copilot import ComplianceCopilotService
from app.services.embeddings import GeminiEmbeddingProvider
from app.services.evals import (
    BenchmarkCase,
    JudgeEvaluation,
    evaluate_case,
    load_benchmark_cases,
    summarize_eval_reports,
)
from app.services.guardrails import redact_pii
from app.services.ingestion import IngestionService
from app.services.llm import GeminiChatClient
from scripts.seed_sops import SOPS_DIR, parse_sop_markdown

BENCHMARK_PATH = Path(__file__).resolve().parent / "data" / "benchmark.jsonl"


class FakeJudgeLLMClient:
    """Deterministic judge used in PR CI to verify eval harness scoring without API calls."""

    @property
    def model_name(self) -> str:
        return "fake-judge"

    async def generate_structured(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ):
        is_refusal_case = "[Expected Outcome]: refused" in user_prompt
        model_refused = "[Model Outcome]: refused" in user_prompt
        evaluation = JudgeEvaluation(
            faithfulness_score=5,
            relevance_score=5,
            fact_coverage_pass=True,
            negative_test_pass=(model_refused if is_refusal_case else True),
            reasoning="Deterministic mock judge verification.",
        )
        return response_schema.model_validate(evaluation.model_dump())


def _fake_copilot_response(case: BenchmarkCase) -> CopilotQueryResponse:
    redacted = redact_pii(case.query)
    if case.expected_outcome == "refused":
        return CopilotQueryResponse(
            request_id=f"eval-{case.id}",
            sanitized_query=redacted.sanitized_text,
            pii_redacted_count=redacted.redaction_count,
            redacted_types=list(redacted.redacted_types),
            outcome="refused",
            answer="Insufficient policy evidence to answer this question.",
            citations=[],
            confidence=0.0,
            model_name="fake-copilot",
            latency_ms=10,
        )

    assert case.expected_source_id is not None
    return CopilotQueryResponse(
        request_id=f"eval-{case.id}",
        sanitized_query=redacted.sanitized_text,
        pii_redacted_count=redacted.redaction_count,
        redacted_types=list(redacted.redacted_types),
        outcome="answered",
        answer="Grounded policy answer covering: " + "; ".join(case.required_facts),
        citations=[
            Citation(
                chunk_id=f"{case.expected_source_id}:0:abc123",
                source_id=case.expected_source_id,
                document_title=case.expected_source_id,
                document_version="2026.1",
                section_title="Policy Section",
                excerpt="; ".join(case.required_facts),
            )
        ],
        confidence=0.95,
        model_name="fake-copilot",
        latency_ms=15,
    )


def test_benchmark_dataset_schema_and_coverage() -> None:
    cases = load_benchmark_cases(BENCHMARK_PATH)
    assert len(cases) >= 8
    assert any(c.expected_outcome == "answered" for c in cases)
    assert any(c.expected_outcome == "refused" for c in cases)
    assert any(c.expect_pii_redacted for c in cases)


async def test_eval_harness_scoring_deterministic() -> None:
    cases = load_benchmark_cases(BENCHMARK_PATH)
    judge = FakeJudgeLLMClient()

    reports = [
        await evaluate_case(case, _fake_copilot_response(case), judge)
        for case in cases
    ]
    summary = summarize_eval_reports(cases, reports)

    assert summary.total_cases == len(cases)
    assert summary.pass_rate == 1.0
    assert summary.citation_precision_rate == 1.0
    assert summary.negative_refusal_rate == 1.0


@pytest.mark.live_eval
async def test_live_gemini_eval_benchmark() -> None:
    """Run full golden benchmark against pgvector + live Gemini Copilot + Gemini Judge."""
    settings = get_settings().model_copy(update={"debug": False})
    engine = init_db(settings)
    await ensure_schema(engine)
    cases = load_benchmark_cases(BENCHMARK_PATH)

    embedder = GeminiEmbeddingProvider(settings)
    copilot_llm = GeminiChatClient(settings)
    judge_llm = GeminiChatClient(settings)
    session_factory = get_session_factory()

    try:
        async with session_factory() as session:
            # Ensure SOP corpus is seeded idempotently in CI or fresh DBs
            ingestion = IngestionService(session, embedder)
            for sop_path in sorted(SOPS_DIR.glob("*.md")):
                await ingestion.ingest_document(parse_sop_markdown(sop_path))

            copilot = ComplianceCopilotService(session, embedder, copilot_llm)
            reports = []
            for case in cases:
                response = await copilot.ask(
                    CopilotQueryRequest(query=case.query, top_k=5),
                    request_id=f"live-eval-{case.id}",
                )
                reports.append(await evaluate_case(case, response, judge_llm))

            summary = summarize_eval_reports(cases, reports)
            await session.execute(
                delete(AuditLog).where(AuditLog.request_id.like("live-eval-%"))
            )
            await session.commit()
    finally:
        await close_db()

    assert summary.pass_rate >= 0.85, f"Eval pass rate too low: {summary.model_dump_json(indent=2)}"
    assert summary.avg_faithfulness >= 4.0
    assert summary.negative_refusal_rate == 1.0
