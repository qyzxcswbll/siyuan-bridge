"""测试 MCP 服务器工具注册和处理函数。"""

import pytest
from unittest.mock import AsyncMock

from siyuan_mcp.server import (
    _handle_sy_save,
    _handle_sy_find,
    _handle_code_find,
)


# ── 输入验证测试 ───────────────────────────────

@pytest.mark.asyncio
async def test_sy_save_empty_content():
    result = await _handle_sy_save({"content": ""})
    assert "不能为空" in result[0].text


@pytest.mark.asyncio
async def test_sy_find_empty_query():
    result = await _handle_sy_find({"query": ""})
    assert "不能为空" in result[0].text


@pytest.mark.asyncio
async def test_code_find_empty_query():
    result = await _handle_code_find({"query": ""})
    assert "不能为空" in result[0].text


# ── 错误处理测试 ─────────────────────────────

@pytest.mark.asyncio
async def test_sy_save_handles_connection_error():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.side_effect = ConnectionError("思源笔记未运行")

    try:
        result = await _handle_sy_save({"content": "# 测试"})
        assert "思源笔记未运行" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_sy_find_handles_connection_error():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.search_notes.side_effect = ConnectionError("思源笔记未运行")

    try:
        result = await _handle_sy_find({"query": "test"})
        assert "思源笔记未运行" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_code_find_handles_search_exception():
    import siyuan_mcp.server as srv
    from siyuan_mcp.codebase.search import CodebaseSearcher
    searcher = AsyncMock() if hasattr(CodebaseSearcher, '__call__') else None
    from unittest.mock import patch

    with patch("siyuan_mcp.server._ensure_initialized"):
        with patch("siyuan_mcp.server._code_searcher") as mock_searcher:
            mock_searcher.search.return_value = ([], ["mock-repo（搜索异常）"])
            result = await _handle_code_find({"query": "test"})
            # 至少返回友好消息而非崩溃
            assert len(result) > 0
