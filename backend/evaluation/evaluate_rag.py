"""Evaluate RAG routing, retrieval, model isolation and optional citations.

Requires a locally built RAG index and the Ollama embedding model. Add
--with-generation to also call the chat model and verify source-link coverage.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.agent import OLLAMA_MODEL
from backend.app.rag import answer_from_documents, is_rag_question, retrieve

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "data" / "rag_eval.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "rag_eval_report.json"


async def evaluate_case(case: dict, with_generation: bool) -> dict:
    routed_to_rag = is_rag_question(case["question"])
    route_ok = routed_to_rag == (case["expected_route"] == "rag")
    result = {"id": case["id"], "question": case["question"], "route_ok": route_ok}
    if not routed_to_rag:
        return result

    hits = await retrieve(case["question"])
    hit_ids = [hit["document_id"] for hit in hits]
    expected_ids = case.get("expected_document_ids", [])
    if case.get("expect_no_results"):
        retrieval_ok = not hits
    else:
        retrieval_ok = bool(set(expected_ids) & set(hit_ids))
    expected_model = case.get("expected_model", "ALL")
    allowed_models = {"ALL", expected_model}
    model_isolation_ok = all(hit["model"] in allowed_models for hit in hits)
    result.update({
        "retrieval_ok": retrieval_ok,
        "model_isolation_ok": model_isolation_ok,
        "hit_document_ids": hit_ids,
        "scores": [hit["score"] for hit in hits],
    })
    if with_generation:
        reply, _, _ = await answer_from_documents(case["question"], OLLAMA_MODEL)
        
        from backend.app.rag import read_documents
        documents_by_id = {
            document["id"]: document
            for document in read_documents()
        }

        expected_urls = {
            documents_by_id[document_id]["source_url"]
            for document_id in case.get("expected_document_ids", [])
            if document_id in documents_by_id
        }

        result["citation_ok"] = (
            all(url in reply for url in expected_urls)
            if expected_urls
            else True
        )
    return result


async def run(dataset_path: Path, with_generation: bool) -> dict:
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    results = [await evaluate_case(case, with_generation) for case in cases]
    rag_results = [r for r in results if "retrieval_ok" in r]
    generated = [r for r in results if "citation_ok" in r]

    def rate(rows: list[dict], key: str) -> float | None:
        return round(sum(bool(row[key]) for row in rows) / len(rows), 4) if rows else None

    metrics = {
        "case_count": len(results),
        "route_accuracy": rate(results, "route_ok"),
        "retrieval_hit_rate": rate(rag_results, "retrieval_ok"),
        "model_isolation_rate": rate(rag_results, "model_isolation_ok"),
        "citation_coverage_rate": rate(generated, "citation_ok"),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path.relative_to(ROOT)),
        "with_generation": with_generation,
        "metrics": metrics,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate DriveMate RAG")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--with-generation", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run(args.dataset, args.with_generation))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
