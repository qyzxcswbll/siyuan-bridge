"""测试 MCP 服务器工具注册和处理函数（3 工具系统）。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from siyuan_mcp.server import (
    _handle_sy_save,
    _handle_sy_find,
    _handle_sy_list,
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


# ── sy-list 测试 ─────────────────────────────

@pytest.mark.asyncio
async def test_sy_list_returns_notebooks():
    import siyuan_mcp.server as srv
    from siyuan_mcp.siyuan.models import NotebookInfo

    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.list_notebooks.return_value = [
        NotebookInfo(id="nb-1", name="AI知识体系", closed=False),
        NotebookInfo(id="nb-2", name="工作文档", closed=False),
        NotebookInfo(id="nb-3", name="归档", closed=True),
    ]
    # 重置 mapper 状态
    srv._notebook_mapper._notebooks = []

    try:
        result = await _handle_sy_list({})
        assert "AI知识体系" in result[0].text
        assert "工作文档" in result[0].text
        assert "归档" in result[0].text
        assert "当前默认" in result[0].text
    finally:
        srv._siyuan_client = None


@pytest.mark.asyncio
async def test_sy_list_connection_error():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.list_notebooks.side_effect = ConnectionError("思源笔记未运行")

    try:
        result = await _handle_sy_list({})
        assert "思源笔记未运行" in result[0].text
    finally:
        srv._siyuan_client = None


# ── sy-save 确认流程测试 ───────────────────

@pytest.mark.asyncio
async def test_sy_save_preview_no_confirm():
    """不传 confirmed → 返回预览信息。"""
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config
    from siyuan_mcp.siyuan.models import NotebookInfo

    srv._config = Config()
    srv._siyuan_client = AsyncMock()
    srv._notebook_mapper._notebooks = [
        NotebookInfo(id="nb-1", name="默认笔记本", closed=False),
    ]

    try:
        result = await _handle_sy_save({"content": "# 测试标题\n这是测试内容"})
        assert "即将保存笔记" in result[0].text
        assert "测试标题" in result[0].text
        # 不应调用写入
        srv._siyuan_client.create_doc.assert_not_called()
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_sy_save_confirmed_writes():
    """confirmed=true → 调用 create_doc。"""
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config
    from siyuan_mcp.siyuan.models import NotebookInfo

    srv._config = Config()
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.return_value = type("R", (), {"id": "doc-1", "title": "测试标题"})()
    srv._notebook_mapper._notebooks = [
        NotebookInfo(id="nb-1", name="默认笔记本", closed=False),
    ]

    try:
        result = await _handle_sy_save({
            "content": "# 测试标题\n这是测试内容",
            "confirmed": True,
        })
        srv._siyuan_client.create_doc.assert_called_once()
        assert "已保存" in result[0].text
        assert "测试标题" in result[0].text
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_sy_save_with_notebook_index():
    """notebook="2" → 映射到索引 1 的笔记本。"""
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config
    from siyuan_mcp.siyuan.models import NotebookInfo

    srv._config = Config()
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.return_value = type("R", (), {"id": "doc-1", "title": "测试"})()
    srv._notebook_mapper._notebooks = [
        NotebookInfo(id="nb-1", name="默认", closed=False),
        NotebookInfo(id="nb-2", name="工作文档", closed=False),
    ]

    try:
        result = await _handle_sy_save({
            "content": "# 测试",
            "notebook": "2",
            "confirmed": True,
        })
        # 应传到 nb-2
        call_args = srv._siyuan_client.create_doc.call_args
        assert call_args[1]["notebook_id"] == "nb-2"
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_sy_save_with_notebook_name():
    """notebook="AI知识" → 模糊匹配。"""
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config
    from siyuan_mcp.siyuan.models import NotebookInfo

    srv._config = Config()
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.return_value = type("R", (), {"id": "doc-1", "title": "测试"})()
    srv._notebook_mapper._notebooks = [
        NotebookInfo(id="nb-1", name="默认", closed=False),
        NotebookInfo(id="nb-2", name="AI知识体系", closed=False),
    ]

    try:
        result = await _handle_sy_save({
            "content": "# 测试",
            "notebook": "AI知识",
            "confirmed": True,
        })
        call_args = srv._siyuan_client.create_doc.call_args
        assert call_args[1]["notebook_id"] == "nb-2"
    finally:
        srv._siyuan_client = None
        srv._config = None


@pytest.mark.asyncio
async def test_sy_save_default_notebook():
    """notebook="" → 索引0。"""
    import siyuan_mcp.server as srv
    from siyuan_mcp.config.loader import Config
    from siyuan_mcp.siyuan.models import NotebookInfo

    srv._config = Config()
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.create_doc.return_value = type("R", (), {"id": "doc-1", "title": "测试"})()
    srv._notebook_mapper._notebooks = [
        NotebookInfo(id="nb-1", name="默认", closed=False),
        NotebookInfo(id="nb-2", name="工作文档", closed=False),
    ]

    try:
        result = await _handle_sy_save({
            "content": "# 测试",
            "notebook": "",
            "confirmed": True,
        })
        call_args = srv._siyuan_client.create_doc.call_args
        assert call_args[1]["notebook_id"] == "nb-1"
    finally:
        srv._siyuan_client = None
        srv._config = None


# ── sy-find 测试 ─────────────────────────────

@pytest.mark.asyncio
async def test_sy_find_normal_mode():
    import siyuan_mcp.server as srv
    from siyuan_mcp.siyuan.models import SearchNotesResult

    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.search_notes.return_value = [
        SearchNotesResult(
            id="doc-1",
            title="测试文档",
            snippet="这是测试内容",
            path="/测试/测试文档",
            score=0.95,
        ),
    ]

    try:
        result = await _handle_sy_find({"query": "测试", "mode": "normal"})
        assert "测试文档" in result[0].text
        assert "mode: normal" in result[0].text
        srv._siyuan_client.search_notes.assert_called_once_with(
            query="测试", mode="normal", limit=10, notebook=""
        )
    finally:
        srv._siyuan_client = None


@pytest.mark.asyncio
async def test_sy_find_code_mode():
    import siyuan_mcp.server as srv
    from unittest.mock import MagicMock

    srv._code_searcher = MagicMock()
    srv._code_searcher.search.return_value = (
        [
            MagicMock(repo="wallet", file="src/main.py", line=42, snippet="def process(): pass"),
        ],
        [],
    )

    try:
        result = await _handle_sy_find({"query": "def process", "mode": "code"})
        assert "wallet" in result[0].text
        assert "src/main.py" in result[0].text
        assert "mode: code" in result[0].text
    finally:
        srv._code_searcher = None


@pytest.mark.asyncio
async def test_sy_find_code_mode_no_results():
    import siyuan_mcp.server as srv
    from unittest.mock import MagicMock

    srv._code_searcher = MagicMock()
    srv._code_searcher.search.return_value = ([], ["skipped-repo"])

    try:
        result = await _handle_sy_find({"query": "nonexistent", "mode": "code"})
        assert "未找到" in result[0].text
        assert "skipped-repo" in result[0].text
    finally:
        srv._code_searcher = None


# ── 错误处理测试 ─────────────────────────────

@pytest.mark.asyncio
async def test_sy_save_handles_connection_error():
    import siyuan_mcp.server as srv
    srv._siyuan_client = AsyncMock()
    srv._siyuan_client.list_notebooks.side_effect = ConnectionError("思源笔记未运行")
    # 确保 mapper 为空，触发自动刷新（刷新失败 → ConnectionError）
    orig_notebooks = srv._notebook_mapper._notebooks
    srv._notebook_mapper._notebooks = []

    try:
        result = await _handle_sy_save({"content": "# 测试"})
        assert "思源笔记未运行" in result[0].text
    finally:
        # 恢复（以防影响其他测试）
        srv._notebook_mapper._notebooks = orig_notebooks
        srv._siyuan_client = None


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


@pytest.mark.asyncio
async def test_code_find_handles_search_exception():
    import siyuan_mcp.server as srv
    from unittest.mock import MagicMock

    srv._code_searcher = MagicMock()
    srv._code_searcher.search.side_effect = RuntimeError("搜索异常")

    try:
        result = await _handle_sy_find({"query": "test", "mode": "code"})
        assert "代码搜索失败" in result[0].text
    finally:
        srv._code_searcher = None


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


def test_match_project_no_config():
    import siyuan_mcp.server as srv
    srv._config = None
    assert _match_project("anything") == ""
