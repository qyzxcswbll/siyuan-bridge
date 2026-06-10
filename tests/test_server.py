"""测试 MCP 服务器工具注册和处理函数。"""

import pytest
from unittest.mock import AsyncMock

from siyuan_mcp.server import (
    _handle_sy_save,
    _handle_sy_today,
    _handle_sy_auto,
    _handle_sy_find,
    _handle_code_find,
    _extract_title,
    _match_project,
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


# ── sy-today 测试 ────────────────────────────

@pytest.mark.asyncio
async def test_sy_today_empty_content():
    result = await _handle_sy_today({"content": ""})
    assert "不能为空" in result[0].text


@pytest.mark.asyncio
async def test_sy_today_success():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.get_or_create_daily_note.return_value = "daily-123"
    srv._siyuan_client.append_block.return_value = [{"id": "block-1"}]

    try:
        result = await _handle_sy_today({"content": "# 今日工作"})
        assert "已追加到今日日记" in result[0].text
        assert "daily-123" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_sy_today_no_daily_note():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.get_or_create_daily_note.return_value = ""

    try:
        result = await _handle_sy_today({"content": "# 测试"})
        assert "无法创建今日日记" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


# ── sy-auto 测试 ─────────────────────────────

def test_extract_title():
    assert _extract_title("# 签名方案\n...") == "签名方案"
    assert _extract_title("## 订单簿\n...") == "订单簿"
    assert _extract_title("普通文本") == "未命名笔记"


def test_match_project_with_repos_in_content():
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config, CodebaseRepo
    srv._config = Config()
    srv._config.codebase.repos = [
        CodebaseRepo(path="/tmp/wallet", name="wallet"),
        CodebaseRepo(path="/tmp/exchange", name="exchange"),
    ]
    try:
        assert _match_project("关于 wallet 的签名方案") == "wallet"
        assert _match_project("# Exchange 订单簿设计") == "exchange"
        assert _match_project("不相关的内容") == ""
    finally:
        srv._config = None


@pytest.mark.asyncio
async def test_sy_auto_empty_content():
    result = await _handle_sy_auto({"content": ""})
    assert "不能为空" in result[0].text


@pytest.mark.asyncio
async def test_sy_auto_saves_with_path():
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config, CodebaseRepo
    srv._config = Config()
    srv._config.codebase.repos = [
        CodebaseRepo(path="/tmp/wallet", name="wallet"),
    ]
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.return_value = type("R", (), {"id": "doc-1", "title": "签名方案"})()

    try:
        result = await _handle_sy_auto({"content": "# wallet 签名方案\n..."})
        call_kwargs = srv._siyuan_client.create_doc.call_args
        # 验证 path 以 /projects/wallet/ 开头且包含文档名
        assert call_kwargs[1]["path"].startswith("/projects/wallet/")
        assert "已自动保存" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


# ── sy-save with name 测试 ───────────────────

@pytest.mark.asyncio
async def test_sy_save_with_name_saves_to_project():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.return_value = type("R", (), {"id": "doc-1", "title": "测试"})()

    try:
        result = await _handle_sy_save({"content": "# 测试", "name": "wallet"})
        call_kwargs = srv._siyuan_client.create_doc.call_args
        # 验证 path 以 /projects/wallet/ 开头（后面有文档名+时间戳）
        assert call_kwargs[1]["path"].startswith("/projects/wallet/")
        assert "项目" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_sy_save_without_name_saves_to_inbox():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.return_value = type("R", (), {"id": "doc-1", "title": "测试"})()

    try:
        result = await _handle_sy_save({"content": "# 测试"})
        call_kwargs = srv._siyuan_client.create_doc.call_args
        # 无 name 时 path 以 / 开头，不以 /projects/ 开头
        assert call_kwargs[1]["path"].startswith("/")
        assert not call_kwargs[1]["path"].startswith("/projects/")
        assert "收集箱" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


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
