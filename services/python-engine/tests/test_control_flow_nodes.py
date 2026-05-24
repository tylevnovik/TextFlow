from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.workflow.nodes.conditional_router import execute_node as execute_conditional_router
from app.workflow.nodes.manual_review_gate import execute_node as execute_manual_review_gate
from app.workflow.nodes.result_gate import execute_node as execute_result_gate


@dataclass
class DummyContext:
    manifest: dict[str, Any] = field(default_factory=dict)
    shared: dict[str, Any] = field(default_factory=dict)
    result_bundle: dict[str, Any] = field(default_factory=dict)
    full_corpus: list[dict[str, Any]] = field(default_factory=list)


def test_conditional_router_routes_records_by_predicate():
    context = DummyContext()
    corpus = [
        {
            "doc_id": "doc-openai",
            "title": "OpenAI paper",
            "raw_text": "Large language models",
            "institution": "OpenAI",
            "year": 2025,
        },
        {
            "doc_id": "doc-anthropic",
            "title": "Anthropic paper",
            "raw_text": "Constitutional AI",
            "institution": "Anthropic",
            "year": 2024,
        },
    ]

    outputs = execute_conditional_router(
        context,
        {
            "config": {
                "source_kind": "corpus_metadata",
                "field": "institution",
                "operator": "in",
                "values": ["OpenAI"],
            }
        },
        {"corpus_in": corpus},
    )

    assert [item["doc_id"] for item in outputs["matched_corpus"]] == ["doc-openai"]
    assert [item["doc_id"] for item in outputs["unmatched_corpus"]] == ["doc-anthropic"]
    assert outputs["route_summary"][0]["matched_count"] == 1
    assert outputs["route_summary"][0]["unmatched_count"] == 1


def test_result_gate_blocks_downstream_when_threshold_not_met():
    context = DummyContext()
    metric_rows = [
        {"metric": "silhouette_score", "value": 0.41},
        {"metric": "davies_bouldin_score", "value": 1.2},
    ]

    blocked_outputs = execute_result_gate(
        context,
        {
            "config": {
                "metric_name": "silhouette_score",
                "metric_name_field": "metric",
                "metric_field": "value",
                "operator": "gte",
                "threshold": 0.5,
            }
        },
        {"metric_table_in": metric_rows},
    )

    assert blocked_outputs["passed"] is False
    assert blocked_outputs["passed_table"] == []
    assert blocked_outputs["blocked_table"] == metric_rows
    assert blocked_outputs["gate_summary"][0]["observed_value"] == 0.41

    passing_outputs = execute_result_gate(
        context,
        {
            "config": {
                "metric_name": "silhouette_score",
                "metric_name_field": "metric",
                "metric_field": "value",
                "operator": "gte",
                "threshold": 0.4,
            }
        },
        {"metric_table_in": metric_rows},
    )

    assert passing_outputs["passed"] is True
    assert passing_outputs["passed_table"] == metric_rows
    assert passing_outputs["blocked_table"] == []


def test_manual_review_gate_waits_for_resolved_review_task():
    context = DummyContext(
        manifest={
            "review_tasks": [
                {"id": "review-topic-model", "status": "open", "title": "Review topics"},
            ]
        }
    )
    payload = [{"topic_id": 1, "label": "AI Safety"}]
    node = {
        "config": {
            "review_id": "review-topic-model",
            "required_status": "resolved",
            "on_missing": "block",
        }
    }

    waiting_outputs = execute_manual_review_gate(context, node, {"payload_in": payload})

    assert waiting_outputs["waiting"] is True
    assert waiting_outputs["approved_payload"] == []
    assert waiting_outputs["blocked_payload"] == payload
    assert waiting_outputs["review_gate_summary"][0]["status"] == "open"

    context.manifest["review_tasks"][0]["status"] = "resolved"
    approved_outputs = execute_manual_review_gate(context, node, {"payload_in": payload})

    assert approved_outputs["waiting"] is False
    assert approved_outputs["approved_payload"] == payload
    assert approved_outputs["blocked_payload"] == []
