"""测试 MCP 服务器工具注册和处理函数。"""

import pytest
from unittest.mock import AsyncMock

from siyuan_mcp.server import (
    _handle_sy_notebook,
    _handle_sy_save,
    _handle_sy_read,
    _handle_sy_delete,
    _handle_sy_find,
    _extract_title,
    _match_project,
)


# ── 输入验证测试 ───────────────────────────────

@pytest.mark.asyncio
async def test_sy_save_empty_content():
    result = await _handle_sy_save({"content": ""})
    assert "不能为空" in result[0].text


@pytest.mark.asyncio
async def test_sy_read_empty_id():
    result = await _handle_sy_read({"id": ""})
    assert "不能为空" in result[0].text


@pytest.mark.asyncio
async def test_sy_delete_empty_id():
    result = await _handle_sy_delete({"id": ""})
    assert "不能为空" in result[0].text


@pytest.mark.asyncio
async def test_sy_find_empty_query():
    result = await _handle_sy_find({"query": ""})
    assert "不能为空" in result[0].text


# ── sy-notebook 测试 ────────────────────────────

@pytest.mark.asyncio
async def test_sy_notebook_returns_list():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.list_notebooks.return_value = [
        type("NB", (), {"id": "nb-1", "name": "测试笔记本", "closed": False})(),
    ]

    try:
        result = await _handle_sy_notebook({})
        assert "测试笔记本" in result[0].text
    finally:
        srv._siyuan_client = None


@pytest.mark.asyncio
async def test_sy_notebook_connection_error():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.list_notebooks.side_effect = ConnectionError("思源笔记未运行")

    try:
        result = await _handle_sy_notebook({})
        assert "思源笔记未运行" in result[0].text
    finally:
        srv._siyuan_client = None


# ── sy-save 测试 ───────────────────────────────

@pytest.mark.asyncio
async def test_sy_save_success():
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config
    from siyuan_mcp.siyuan.models import NotebookInfo

    srv._config = Config()
    srv._siyuan_client = AsyncMock()
    srv._notebook_mapper._notebooks = [
        NotebookInfo(id="nb-1", name="默认笔记本", closed=False),
    ]
    srv._siyuan_client.create_doc.return_value = type(
        "R", (), {"id": "doc-1", "title": "测试笔记"}
    )()

    try:
        result = await _handle_sy_save({"content": "# 测试笔记\n正文内容", "notebook": "1"})
        assert "已保存" in result[0].text
        assert "doc-1" in result[0].text
        srv._siyuan_client.create_doc.assert_called_once()
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_sy_save_connection_error():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.side_effect = ConnectionError("思源笔记未运行")

    try:
        result = await _handle_sy_save({"content": "# 测试"})
        assert "思源笔记未运行" in result[0].text
    finally:
        srv._siyuan_client = None


# ── sy-read 测试 ───────────────────────────────

@pytest.mark.asyncio
async def test_sy_read_success():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.get_doc.return_value = type(
        "D", (), {"id": "doc-1", "content": "# 文档内容\n正文", "path": "/test", "title": "文档内容"}
    )()

    try:
        result = await _handle_sy_read({"id": "doc-1"})
        assert "文档内容" in result[0].text
    finally:
        srv._siyuan_client = None


@pytest.mark.asyncio
async def test_sy_read_connection_error():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.get_doc.side_effect = ConnectionError("思源笔记未运行")

    try:
        result = await _handle_sy_read({"id": "doc-1"})
        assert "思源笔记未运行" in result[0].text
    finally:
        srv._siyuan_client = None


# ── sy-delete 测试 ─────────────────────────────

@pytest.mark.asyncio
async def test_sy_delete_success():
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config
    from siyuan_mcp.siyuan.models import NotebookInfo

    srv._config = Config()
    srv._siyuan_client = AsyncMock()
    srv._notebook_mapper._notebooks = [
        NotebookInfo(id="nb-1", name="测试笔记本", closed=False),
    ]
    # get_doc returns path
    srv._siyuan_client.get_doc.return_value = type(
        "D", (), {"id": "doc-1", "content": "# 内容", "path": "/待删除", "title": "待删除"}
    )()
    srv._siyuan_client.remove_doc.return_value = True

    try:
        result = await _handle_sy_delete({"id": "doc-1", "notebook": "1"})
        assert "已删除" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


# ── sy-find 测试（保留）───────────────────────

@pytest.mark.asyncio
async def test_sy_find_normal_mode():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.search_notes.return_value = [
        type("R", (), {"id": "1", "title": "结果1", "snippet": "匹配内容", "path": "/路径"})(),
    ]

    try:
        result = await _handle_sy_find({"query": "测试"})
        assert "结果1" in result[0].text
    finally:
        srv._siyuan_client = None


@pytest.mark.asyncio
async def test_sy_find_code_mode():
    import siyuan_mcp.server as srv
    from siyuan_mcp.codebase.search import CodeSearchResult
    from unittest.mock import patch

    with patch("siyuan_mcp.server._code_searcher") as mock_searcher:
        mock_searcher.search.return_value = (
            [CodeSearchResult("myrepo", "src/main.rs", 42, "fn test() {}", "test")],
            [],
        )
        result = await _handle_sy_find({"query": "test", "mode": "code"})
        assert "myrepo" in result[0].text


@pytest.mark.asyncio
async def test_sy_find_connection_error():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.search_notes.side_effect = ConnectionError("思源笔记未运行")

    try:
        result = await _handle_sy_find({"query": "test"})
        assert "思源笔记未运行" in result[0].text
    finally:
        srv._siyuan_client = None


# ── 辅助函数测试 ─────────────────────────────

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
