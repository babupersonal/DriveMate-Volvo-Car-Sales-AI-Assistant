"""Local offline tests for RAG; HTTP calls are mocked, not real Ollama."""
import asyncio
import json
from pathlib import Path

import httpx

from backend.app import rag


def test_rag_evaluation_dataset_schema():
    path = Path(__file__).resolve().parents[2] / "data" / "rag_eval.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) >= 10
    assert len({case["id"] for case in cases}) == len(cases)
    required = {"id", "question", "expected_route", "expected_document_ids",
                "expected_model", "expect_no_results"}
    assert all(required <= case.keys() for case in cases)
    assert all(case["expected_route"] in {"rag", "non_rag"} for case in cases)


def test_documents_keep_official_provenance():
    docs = rag.read_documents()
    assert len(docs) >= 8
    assert all(d['source_url'].startswith('https://www.volvocars.com/') for d in docs)
    passages = rag.chunk_documents(docs, max_chars=95)
    assert len(passages) > len(docs)  # Real splitting, not hard-coded answers.
    assert all('source_url' in p and 'chunk_id' in p for p in passages)


def test_rag_question_gate():
    assert rag.is_rag_question('EX30 DC 快充要注意什麼？')
    assert rag.is_rag_question('XC60 要怎麼預約保養？')
    assert not rag.is_rag_question('XC40 和 XC60 哪台馬力大？')
    assert not rag.is_rag_question('EX40 有幾台庫存？')


def test_no_index_fails_safely(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, 'INDEX_PATH', tmp_path / 'not-built.json')
    try:
        rag.load_index()
    except rag.RagNotReady as e:
        assert '尚未建立' in str(e)
    else:
        assert False, 'Expected missing-index protection'


def test_embedding_retrieval_and_grounded_reply(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, 'INDEX_PATH', tmp_path / 'rag_index.json')

    def vector_for(text):
        if 'DC' in text or '快充' in text:
            return [1.0, 0.0, 0.0]
        if 'AC' in text or '交流充電' in text:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def fake_http(request):
        payload = json.loads(request.content)
        if request.url.path == '/api/embed':
            xs = payload['input']
            xs = xs if isinstance(xs, list) else [xs]
            return httpx.Response(200, json={'embeddings': [vector_for(x) for x in xs]})
        if request.url.path == '/api/chat':
            assert '檢索到的文件摘要' in payload['messages'][0]['content']
            return httpx.Response(200, json={'message': {'content':'EX30 使用快充前，請確認充電線接頭完整且沒有損壞。'}})
        raise AssertionError('Unexpected URL: ' + str(request.url))

    transport = httpx.MockTransport(fake_http)
    original_client, original_async_client = httpx.Client, httpx.AsyncClient
    monkeypatch.setattr(rag.httpx, 'Client', lambda timeout: original_client(transport=transport, timeout=timeout))
    monkeypatch.setattr(rag.httpx, 'AsyncClient', lambda timeout: original_async_client(transport=transport, timeout=timeout))
    result = rag.build_index()
    assert result['chunk_count'] >= result['document_count']
    hits = asyncio.run(rag.retrieve('EX30 DC 快充要注意什麼？'))
    assert hits and hits[0]['document_id'] == 'ex30-dc-charge'
    assert all(c['model'] in {'EX30', 'ALL'} for c in hits)
    reply, used, mode = asyncio.run(rag.answer_from_documents('EX30 DC 快充要注意什麼？', 'qwen3:1.7b'))
    assert 'Volvo' in reply and 'https://www.volvocars.com/' in reply
    assert used == ['rag_search'] and mode == 'rag_retrieval'
    # A request about another model must not cite EX30 instructions.
    other = asyncio.run(rag.retrieve('XC40 DC 快充'))
    assert all(c['model'] in {'XC40', 'ALL'} for c in other)
