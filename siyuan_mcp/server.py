"""MCP 服务主文件。声明所有工具，启动服务。"""

import re
import sys
import time
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, ToolsCapability

from siyuan_mcp.config.loader import ConfigLoader
from siyuan_mcp.siyuan.client import SiyuanClient
from siyuan_mcp.codebase.search import CodebaseSearcher
from siyuan_mcp.mapper import NotebookMapper
from siyuan_mcp.tagger import generate_tags


# ── 工具函数 ──────────────────────────────────────

def _sanitize_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|#]', '', s)
    s = s.strip()
    return s[:50] if len(s) > 50 else s


def _make_doc_path(markdown: str, name: str = "") -> str:
    """生成唯一文档路径（path 必须唯一，否则思源会复用已有文档）。"""
    title = _extract_title(markdown)
    safe_title = _sanitize_filename(title) if title != "未命名笔记" else "笔记"
    ts = str(int(time.time() * 1000))
    filename = f"{safe_title}-{ts}"
    if name:
        return f"/projects/{name}/{filename}"
    return f"/{filename}"


def _extract_title(markdown: str) -> str:
    """从 Markdown 内容中提取第一个标题。"""
    for line in markdown.strip().split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line.startswith("## "):
            return line[3:].strip()
    return "未命名笔记"


def _match_project(content: str) -> str:
    """从 content 和 codebase repos 中匹配项目名称。"""
    if _config is None:
        return ""
    repos = _config.codebase.repos
    if not repos:
        return ""
    title = _extract_title(content).lower()
    for repo in repos:
        if repo.name.lower() in title or repo.name.lower() in content.lower():
            return repo.name
    return ""


# ── 全局状态 ──────────────────────────────────────
_config = None
_siyuan_client = None
_code_searcher = None
_notebook_mapper = NotebookMapper()

server = Server("siyuan-mcp")


def _ensure_initialized():
    global _config, _siyuan_client, _code_searcher
    if _config is None:
        loader = ConfigLoader()
        _config = loader.load()
        _siyuan_client = SiyuanClient(_config)
        _code_searcher = CodebaseSearcher(_config)


# ── 工具列表声明 ────────────────────────────────

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="sy-notebook",
            description="列出思源笔记中所有可用笔记本（带编号和名称）。",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="sy-list",
            description="列出指定笔记本下的文档列表。",
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {
                        "type": "string",
                        "description": "笔记本序号或名称",
                    },
                },
            },
        ),
        types.Tool(
            name="sy-save",
            description="保存文档到思源笔记。",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Markdown 笔记内容",
                    },
                    "notebook": {
                        "type": "string",
                        "description": "可选，笔记本序号或名称，不指定则用默认笔记本（索引0）",
                    },
                },
                "required": ["content"],
            },
        ),
        types.Tool(
            name="sy-read",
            description="读取思源笔记文档内容。",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "文档 ID（siyuan://blocks/xxx 中的 xxx）",
                    },
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="sy-delete",
            description="删除思源笔记文档。",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "文档 ID",
                    },
                    "notebook": {
                        "type": "string",
                        "description": "可选，笔记本序号或名称",
                    },
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="sy-find",
            description="统一搜索。mode=normal|ai 搜索思源知识库，mode=code 搜索本地代码库。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "mode": {
                        "type": "string",
                        "enum": ["normal", "ai", "code"],
                        "description": "搜索模式：normal（默认）/ ai（语义搜索）/ code（代码搜索）",
                    },
                    "limit": {"type": "integer", "description": "结果数量上限（默认 10）"},
                    "notebook": {"type": "string", "description": "限定笔记本（仅 normal/ai 模式）"},
                    "path": {"type": "string", "description": "限定项目名（仅 code 模式）"},
                    "file_type": {
                        "type": "string", "enum": ["code", "doc"],
                        "description": "文件类型过滤（仅 code 模式）",
                    },
                    "context_lines": {"type": "integer", "description": "上下文行数（仅 code 模式，默认 3）"},
                },
                "required": ["query"],
            },
        ),
    ]


# ── 工具调用分发 ──────────────────────────────

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    _ensure_initialized()

    handlers = {
        "sy-notebook": _handle_sy_notebook,
        "sy-list": _handle_sy_list,
        "sy-save": _handle_sy_save,
        "sy-read": _handle_sy_read,
        "sy-delete": _handle_sy_delete,
        "sy-find": _handle_sy_find,
    }

    handler = handlers.get(name)
    if not handler:
        raise ValueError(f"未知工具：{name}")

    return await handler(arguments or {})


# ── sy-notebook ──────────────────────────────────

async def _handle_sy_notebook(args: dict) -> list[types.TextContent]:
    """列出笔记本。"""
    try:
        notebooks = await _siyuan_client.list_notebooks()
        _notebook_mapper.set_notebooks(notebooks)
        return [types.TextContent(type="text", text=_notebook_mapper.format_list())]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 获取笔记本列表失败：{e}")]


# ── sy-list ─────────────────────────────────────

async def _handle_sy_list(args: dict) -> list[types.TextContent]:
    """列出笔记本下的文档列表。"""
    notebook_spec = args.get("notebook", "")
    try:
        notebook_id = _notebook_mapper.resolve(notebook_spec)
    except ValueError:
        notebooks = await _siyuan_client.list_notebooks()
        _notebook_mapper.set_notebooks(notebooks)
        notebook_id = _notebook_mapper.resolve(notebook_spec)

    try:
        docs = await _siyuan_client.list_docs(notebook_id)
        if not docs:
            return [types.TextContent(type="text", text="📭 该笔记本下没有文档")]
        lines = ["📄 文档列表：\n"]
        for d in docs:
            title = d.get("name", d.get("title", "未命名"))
            doc_id = d.get("id", "")
            lines.append(f"- {title}  `{doc_id}`")
        return [types.TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 获取文档列表失败：{e}")]


# ── sy-save ──────────────────────────────────────

async def _handle_sy_save(args: dict) -> list[types.TextContent]:
    content = args.get("content", "")
    if not content.strip():
        return [types.TextContent(type="text", text="❌ 内容不能为空")]

    notebook_spec = args.get("notebook", "")

    try:
        # 解析笔记本
        try:
            notebook_id = _notebook_mapper.resolve(notebook_spec)
        except ValueError:
            notebooks = await _siyuan_client.list_notebooks()
            _notebook_mapper.set_notebooks(notebooks)
            notebook_id = _notebook_mapper.resolve(notebook_spec)

        # 取笔记本名称
        notebook_name = notebook_spec
        for nb in _notebook_mapper._notebooks:
            if nb.id == notebook_id:
                notebook_name = nb.name
                break

        # 匹配项目（可选）
        name = _match_project(content)

        # 自动生成路径
        path = _make_doc_path(content, name=name)
        title = _extract_title(content)

        # 直接写入
        result = await _siyuan_client.create_doc(
            markdown=content,
            path=path,
            notebook_id=notebook_id,
            title=title,
        )

        text = f"✅ 已保存\n- 📂 {notebook_name}/{result.title}"
        if result.id:
            text += f"\n- 🔗 siyuan://blocks/{result.id}"
        return [types.TextContent(type="text", text=text)]

    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except ValueError as e:
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]


# ── sy-read ──────────────────────────────────────

async def _handle_sy_read(args: dict) -> list[types.TextContent]:
    doc_id = args.get("id", "")
    if not doc_id.strip():
        return [types.TextContent(type="text", text="❌ 文档 ID 不能为空")]

    try:
        doc = await _siyuan_client.get_doc(doc_id)
        if not doc.content:
            return [types.TextContent(type="text", text="📭 文档内容为空")]
        return [types.TextContent(type="text", text=doc.content)]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 读取失败：{e}")]


# ── sy-delete ────────────────────────────────────

async def _handle_sy_delete(args: dict) -> list[types.TextContent]:
    doc_id = args.get("id", "")
    if not doc_id.strip():
        return [types.TextContent(type="text", text="❌ 文档 ID 不能为空")]

    try:
        # 先获取文档路径和所在笔记本
        doc = await _siyuan_client.get_doc(doc_id)
        if not doc.path:
            return [types.TextContent(type="text", text="❌ 无法确定文档路径")]
        notebook_spec = args.get("notebook", "")
        notebook_id = _notebook_mapper.resolve(notebook_spec)
        await _siyuan_client.remove_doc(notebook_id, doc.path)
        return [types.TextContent(type="text", text=f"✅ 已删除文档 `{doc.path}`")]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except ValueError as e:
        return [types.TextContent(type="text", text=f"❌ 删除失败：{e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 删除失败：{e}")]


# ── sy-find ──────────────────────────────────────

async def _handle_sy_find(args: dict) -> list[types.TextContent]:
    query = args.get("query", "")
    mode = args.get("mode", "normal")
    limit = args.get("limit", 10)
    notebook = args.get("notebook", "")

    if not query.strip():
        return [types.TextContent(type="text", text="❌ 搜索关键词不能为空")]

    if mode == "code":
        path_filter = args.get("path")
        file_type = args.get("file_type", "code")
        context_lines = args.get("context_lines", 3)
        try:
            results, skipped = _code_searcher.search(
                query=query, path_filter=path_filter,
                file_type=file_type, context_lines=context_lines,
            )
            if not results:
                msg = f"📭 代码库中未找到「{query}」"
                if skipped:
                    msg += f"\n⚠️ 以下项目已跳过：{'；'.join(skipped)}"
                return [types.TextContent(type="text", text=msg)]
            lines = [f"🔍 找到 {len(results)} 处代码匹配「{query}」（mode: code）：\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **{r.repo}** — `{r.file}:{r.line}`")
                lines.append(f"```\n{r.snippet}\n```\n")
            if skipped:
                lines.append(f"⚠️ 以下项目已跳过：{'；'.join(skipped)}")
            return [types.TextContent(type="text", text="\n".join(lines))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ 代码搜索失败：{e}")]

    try:
        results = await _siyuan_client.search_notes(
            query=query, mode=mode, limit=limit, notebook=notebook
        )
        if not results:
            return [types.TextContent(type="text", text=f"📭 未找到与「{query}」相关的结果")]
        lines = [f"🔍 找到 {len(results)} 条结果（mode: {mode}）：\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. 📄 **{r.title}**")
            lines.append(f"   > {r.snippet}")
            if r.path:
                lines.append(f"   📁 {r.path}")
            lines.append("")
        return [types.TextContent(type="text", text="\n".join(lines))]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 搜索失败：{e}")]


# ── 入口 ─────────────────────────────────────────

async def amain() -> int:
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream,
                InitializationOptions(
                    server_name="siyuan-mcp",
                    server_version="0.1.0",
                    capabilities=ServerCapabilities(
                        tools=ToolsCapability(listChanged=False),
                    ),
                ),
            )
        return 0
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1


def main() -> int:
    import asyncio
    return asyncio.run(amain())
