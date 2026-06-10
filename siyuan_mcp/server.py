"""MCP 服务主文件。声明所有工具，启动服务。"""

import sys
from typing import Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

from siyuan_mcp.config.loader import ConfigLoader
from siyuan_mcp.siyuan.client import SiyuanClient
from siyuan_mcp.codebase.search import CodebaseSearcher

# ── 全局状态 ──────────────────────────────────────
_config = None
_siyuan_client = None
_code_searcher = None

server = Server("siyuan-mcp")


def _ensure_initialized():
    """懒初始化全局依赖（在工具首次调用时）。"""
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
            name="sy-save",
            description="快速保存笔记到思源收集箱。将内容以 Markdown 格式保存到思源笔记的默认笔记本。",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "笔记内容（Markdown 格式）",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选，标签列表",
                    },
                    "source": {
                        "type": "string",
                        "description": "可选，来源标记（如 claude-chat）",
                    },
                },
                "required": ["content"],
            },
        ),
        types.Tool(
            name="sy-today",
            description="保存内容到今日日记。将 Markdown 内容追加到思源笔记当天的日记文档中。",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要追加到日记的内容（Markdown 格式）",
                    },
                },
                "required": ["content"],
            },
        ),
        types.Tool(
            name="sy-find",
            description="搜索思源笔记知识库。支持普通关键词搜索和 AI 语义搜索两种模式。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["normal", "ai"],
                        "description": "搜索模式：normal（关键词匹配）或 ai（语义搜索）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最大返回结果数（默认 10）",
                    },
                    "notebook": {
                        "type": "string",
                        "description": "可选，限定笔记本",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="code-find",
            description="在关联的本地 Git 项目中搜索代码。支持正则表达式，可限定项目范围。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词（支持正则表达式）",
                    },
                    "path": {
                        "type": "string",
                        "description": "可选，限定在特定项目中搜索（匹配 repo name）",
                    },
                    "file_type": {
                        "type": "string",
                        "enum": ["code", "doc"],
                        "description": "文件类型过滤：code（排除文档）或 doc（仅文档）",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "匹配行上下文的行数（默认 3）",
                    },
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
        "sy-save": _handle_sy_save,
        "sy-today": _handle_sy_today,
        "sy-find": _handle_sy_find,
        "code-find": _handle_code_find,
    }

    handler = handlers.get(name)
    if not handler:
        raise ValueError(f"未知工具：{name}")

    return await handler(arguments or {})


# ── sy-save ──────────────────────────────────────

async def _handle_sy_save(args: dict) -> list[types.TextContent]:
    content = args.get("content", "")
    if not content.strip():
        return [types.TextContent(type="text", text="❌ 内容不能为空")]

    try:
        title = args.get("source", "Claude 笔记")
        tags = args.get("tags")

        # 如果有标签，在内容末尾追加
        if tags:
            content += "\n\n---\n标签：" + "、".join(tags)

        result = await _siyuan_client.create_doc(
            markdown=content,
            title=title,
        )
        return [
            types.TextContent(
                type="text",
                text=(
                    f"✅ 已保存到思源\n"
                    f"- 文档 ID：`{result.id}`\n"
                    f"- 标题：{result.title}\n"
                    f"- 链接：siyuan://blocks/{result.id}"
                ),
            )
        ]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]


# ── sy-today ─────────────────────────────────────

async def _handle_sy_today(args: dict) -> list[types.TextContent]:
    content = args.get("content", "")
    if not content.strip():
        return [types.TextContent(type="text", text="❌ 内容不能为空")]

    try:
        doc_id = await _siyuan_client.get_or_create_daily_note()
        if not doc_id:
            return [types.TextContent(
                type="text", text="❌ 无法创建今日日记，请检查思源设置"
            )]

        await _siyuan_client.append_block(doc_id, content)
        return [types.TextContent(
            type="text",
            text=f"✅ 已追加到今日日记\n- 文档 ID：`{doc_id}`\n- 链接：siyuan://blocks/{doc_id}",
        )]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 写入日记失败：{e}")]


# ── sy-find ──────────────────────────────────────

async def _handle_sy_find(args: dict) -> list[types.TextContent]:
    query = args.get("query", "")
    mode = args.get("mode", "normal")
    limit = args.get("limit", 10)
    notebook = args.get("notebook", "")

    if not query.strip():
        return [types.TextContent(type="text", text="❌ 搜索关键词不能为空")]

    try:
        results = await _siyuan_client.search_notes(
            query=query, mode=mode, limit=limit, notebook=notebook
        )

        if not results:
            return [
                types.TextContent(
                    type="text", text=f"📭 未找到与「{query}」相关的结果"
                )
            ]

        lines = [f"🔍 找到 {len(results)} 条结果（模式：{mode}）：\n"]
        for r in results:
            lines.append(f"**{r.title}**")
            lines.append(f"> {r.snippet}")
            if r.path:
                lines.append(f"  📁 {r.path}")
            lines.append("")

        return [types.TextContent(type="text", text="\n".join(lines))]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 搜索失败：{e}")]


# ── code-find ───────────────────────────────────

async def _handle_code_find(args: dict) -> list[types.TextContent]:
    query = args.get("query", "")
    path_filter = args.get("path")
    file_type = args.get("file_type", "code")
    context_lines = args.get("context_lines", 3)

    if not query.strip():
        return [types.TextContent(type="text", text="❌ 搜索关键词不能为空")]

    try:
        results, skipped = _code_searcher.search(
            query=query,
            path_filter=path_filter,
            file_type=file_type,
            context_lines=context_lines,
        )

        if not results:
            msg = f"📭 代码库中未找到「{query}」"
            if skipped:
                msg += f"\n⚠️ 以下项目已跳过：{'；'.join(skipped)}"
            return [types.TextContent(type="text", text=msg)]

        lines = [f"🔍 找到 {len(results)} 处代码匹配「{query}」：\n"]
        for r in results:
            lines.append(f"**{r.repo}** — `{r.file}:{r.line}`")
            lines.append(f"```\n{r.snippet}\n```")
            lines.append("")

        if skipped:
            lines.append(f"⚠️ 以下项目已跳过：{'；'.join(skipped)}")

        return [types.TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 代码搜索失败：{e}")]


# ── 入口 ─────────────────────────────────────────

async def amain() -> int:
    """启动 MCP 服务（异步入口）。"""
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="siyuan-mcp",
                    server_version="0.1.0",
                ),
            )
        return 0
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """启动 MCP 服务（同步入口，供 __main__.py 调用）。"""
    import asyncio
    return asyncio.run(amain())
