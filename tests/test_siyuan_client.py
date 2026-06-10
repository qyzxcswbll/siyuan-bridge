"""测试思源 API 客户端：数据模型 + HTTP 调用。"""

import pytest
from unittest.mock import AsyncMock, patch

from siyuan_mcp.siyuan.models import (
    CreateDocRequest,
    CreateDocResponse,
    SearchNotesRequest,
    SearchNotesResult,
)
from siyuan_mcp.siyuan.client import SiyuanClient
from siyuan_mcp.config.loader import Config, SiyuanConfig


# ── 数据模型测试 ─────────────────────────────────

class TestModels:
    def test_create_doc_request_defaults(self):
        req = CreateDocRequest(markdown="# Hello")
        assert req.markdown == "# Hello"
        assert req.notebook_id == ""

    def test_search_notes_request(self):
        req = SearchNotesRequest(query="test", limit=5)
        assert req.query == "test"
        assert req.limit == 5

    def test_search_notes_result(self):
        data = {
            "id": "abc123",
            "title": "笔记标题",
            "snippet": "匹配片段...",
            "path": "/笔记/文档",
            "score": 0.95,
            "updated": "2026-06-10T12:00:00",
        }
        result = SearchNotesResult(**data)
        assert result.id == "abc123"
        assert result.title == "笔记标题"
        assert result.snippet == "匹配片段..."

    def test_create_doc_response(self):
        resp = CreateDocResponse(id="doc-1", title="测试")
        assert resp.id == "doc-1"
        assert resp.title == "测试"


# ── API 客户端测试 ───────────────────────────────

@pytest.fixture
def config():
    c = Config()
    c.siyuan = SiyuanConfig(host="127.0.0.1", port=6806, token="")
    return c


@pytest.mark.asyncio
async def test_save_note_success(config):
    client = SiyuanClient(config)
    mock_response = {
        "code": 0,
        "msg": "",
        "data": {"id": "20260610123456-abc123", "title": "测试笔记"},
    }

    with patch.object(client._client, "post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = lambda: mock_response

        result = await client.create_doc("# 测试笔记")
        assert result.id == "20260610123456-abc123"
        assert result.title == "测试笔记"


@pytest.mark.asyncio
async def test_search_notes_success(config):
    client = SiyuanClient(config)
    mock_response = {
        "code": 0,
        "msg": "",
        "data": [
            {
                "id": "abc123",
                "title": "搜索结果",
                "snippet": "匹配...",
                "path": "/根/文档",
                "score": 0.95,
                "updated": "2026-06-10T12:00:00",
            }
        ],
    }

    with patch.object(client._client, "post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = lambda: mock_response

        results = await client.search_notes("test keyword")
        assert len(results) == 1
        assert results[0].id == "abc123"
        assert results[0].title == "搜索结果"


@pytest.mark.asyncio
async def test_connection_error_returns_friendly_message(config):
    from httpx import ConnectError

    client = SiyuanClient(config)
    with patch.object(client._client, "post") as mock_post:
        mock_post.side_effect = ConnectError("连接被拒绝")

        with pytest.raises(ConnectionError, match="思源笔记未运行"):
            await client.create_doc("# test")


@pytest.mark.asyncio
async def test_api_error_response(config):
    client = SiyuanClient(config)
    mock_response = {"code": 1, "msg": "Token 无效", "data": {}}

    with patch.object(client._client, "post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = lambda: mock_response

        with pytest.raises(ValueError, match="Token 无效"):
            await client.create_doc("# test")


# ── 日记功能测试 ─────────────────────────────

@pytest.mark.asyncio
async def test_get_or_create_daily_note_success(config):
    client = SiyuanClient(config)
    mock_response = {
        "code": 0,
        "msg": "",
        "data": {"id": "daily-note-123", "title": "2026-06-10"},
    }

    with patch.object(client._client, "post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = lambda: mock_response

        doc_id = await client.get_or_create_daily_note()
        assert doc_id == "daily-note-123"


@pytest.mark.asyncio
async def test_append_block_success(config):
    client = SiyuanClient(config)
    mock_response = {
        "code": 0,
        "msg": "",
        "data": [{"id": "new-block-id"}],
    }

    with patch.object(client._client, "post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = lambda: mock_response

        result = await client.append_block("parent-123", "# 测试内容")
        assert len(result) == 1
        assert result[0]["id"] == "new-block-id"


@pytest.mark.asyncio
async def test_append_block_camelcase_serialization(config):
    """验证 appendBlock 请求使用 camelCase 字段名。"""
    from siyuan_mcp.siyuan.models import AppendBlockRequest
    req = AppendBlockRequest(parent_id="pid", data="content")
    dumped = req.model_dump()
    assert "parentID" in dumped
    assert "parent_id" not in dumped
    assert dumped["parentID"] == "pid"
    assert dumped["domainType"] == 0
