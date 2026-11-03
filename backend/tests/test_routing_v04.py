"""Regression tests for v0.4 booking intent and retrieval-grounded safety guidance."""
import asyncio
import os
import tempfile
from pathlib import Path

# Isolate from the user's database and existing test suite.
TEST_DIR = tempfile.TemporaryDirectory()
os.environ["DRIVEMATE_DB_PATH"] = str(Path(TEST_DIR.name) / "test.db")

from backend.app.db import init_db  # noqa: E402
from backend.app.agent import chat, is_test_drive_request  # noqa: E402
from backend.app import rag  # noqa: E402


def setup_module():
    init_db()


def test_booking_intent_is_prioritized_over_vehicle_info():
    for q in ('我想預約 EX30 試乘。', '可以幫我安排 XC40 試駕嗎？', '想預約 EX40'):
        assert is_test_drive_request(q)
        reply, used, mode = asyncio.run(chat([{'role':'user', 'content':q}]))
        assert mode == 'booking_guidance'
        assert '模擬試乘預約' in reply
        assert '不會向 Volvo 送出預約' in reply
        assert used == []


def test_booking_unknown_model_and_missing_model():
    reply, used, mode = asyncio.run(chat([{'role':'user','content':'想試乘 XC999'}]))
    assert '沒有收錄' in reply and '無法建立' in reply
    reply, used, mode = asyncio.run(chat([{'role':'user','content':'我想預約試乘'}]))
    assert '先選擇車型' in reply


def test_maintenance_booking_is_not_mistaken_for_test_drive():
    assert not is_test_drive_request('XC60 要如何預約回廠保養？')
    assert not is_test_drive_request('XC60 需要預約維修嗎？')


def test_explicit_charging_safety_warning_is_grounded():
    docs = [d for d in rag.read_documents() if d['id'] in ('ex30-charge-safety', 'ex30-dc-charge')]
    matches = [{'document_id':d['id'], 'title':d['title'], 'source_url':d['source_url'],
                'text':d['summary'], 'model':d['model']} for d in docs]
    answer = rag.charging_safety_answer('EX30 的充電線接頭損壞，可以自己用工具清理嗎？', matches)
    assert answer is not None
    text, evidence = answer
    assert '不可以' in text and '自行' in text and '停止使用' in text
    assert len(evidence) == 2
    assert rag.charging_safety_answer('EX30 使用 DC 快充要注意什麼？', matches) is None
    assert rag.charging_safety_answer('EX30 的充電線接頭損壞，可以自己用工具清理嗎？',
                                      [{'text':'資料不足'}]) is None


def test_safety_rag_reply_does_not_hallucinate_without_evidence(monkeypatch):
    docs = [d for d in rag.read_documents() if d['id'] in ('ex30-charge-safety', 'ex30-dc-charge')]
    matches = [{'document_id':d['id'], 'title':d['title'], 'source_url':d['source_url'],
                'text':d['summary'], 'model':d['model']} for d in docs]
    async def fake_retrieve(q):
        return matches
    monkeypatch.setattr(rag, 'retrieve', fake_retrieve)
    reply, used, mode = asyncio.run(rag.answer_from_documents(
        'EX30 的充電線接頭損壞，可以自己用工具清理嗎？', 'qwen3:1.7b'))
    assert '不可以' in reply and '停止使用' in reply
    assert 'https://www.volvocars.com/' in reply
    assert used == ['rag_search'] and mode == 'rag_retrieval'
