"""MCP 服务主文件。声明所有工具，启动服务。"""

import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

from siyuan_mcp.config.loader import ConfigLoader
from siyuan_mcp.siyuan.client import SiyuanClient
from siyuan_mcp.codebase.search import CodebaseSearcher


# ── 工具函数 ──────────────────────────────────────

def _sanitize_filename(s: str) -> str:
    """清理字符串为安全的文件名部分。"""
    s = re.sub(r'[\\/:*?"<>|#]', '', s)
    s = s.strip()
    return s[:50] if len(s) > 50 else s


def _make_doc_path(markdown: str, name: str = "") -> str:
    """根据 markdown 内容和项目名生成唯一文档路径。

    path 必须唯一，否则思源会复用已有文档。
    """
    title = _extract_title(markdown)
    safe_title = _sanitize_filename(title) if title != "未命名笔记" else "笔记"
    ts = str(int(time.time() * 1000))
    filename = f"{safe_title}-{ts}"

    if name:
        return f"/projects/{name}/{filename}"
    return f"/{filename}"


def _format_doc_result(result, action: str, location: str = "") -> str:
    """格式化保存结果消息，兼容 ID 为空的情况。"""
    lines = [f"✅ 已{action}到思源"]
    if location:
        lines[0] += f"（{location}）"
    if result.id:
        lines.append(f"- 文档 ID：`{result.id}`")
    if result.title:
        lines.append(f"- 标题：{result.title}")
    if result.id:
        lines.append(f"- 链接：siyuan://blocks/{result.id}")
    return "\n".join(lines)

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
            name="sy-notebooks",
            description="列出思源笔记中所有可用的笔记本。保存笔记前先调用此工具让用户选择保存位置。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="sy-save",
            description="保存笔记到思源。name 为空时保存到收集箱，name 有值时保存到对应项目目录。",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "笔记内容（Markdown 格式）",
                    },
                    "notebook": {
                        "type": "string",
                        "description": "可选，笔记本 ID（调用 sy-notebooks 获取）。不指定则用默认笔记本",
                    },
                    "name": {
                        "type": "string",
                        "description": "可选，项目名称，有值时保存到 /projects/{name}/ 目录",
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
            name="sy-auto",
            description="自动分类保存笔记。根据项目名称（匹配 codebase.repos）和内容标题自动归类到思源项目目录。",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "笔记内容（Markdown 格式）",
                    },
                    "notebook": {
                        "type": "string",
                        "description": "可选，笔记本 ID。不指定则用默认笔记本",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选，标签列表",
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
                    "notebook": {
                        "type": "string",
                        "description": "可选，笔记本 ID。不指定则用默认笔记本",
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
        "sy-notebooks": _handle_sy_notebooks,
        "sy-save": _handle_sy_save,
        "sy-today": _handle_sy_today,
        "sy-auto": _handle_sy_auto,
        "sy-find": _handle_sy_find,
        "code-find": _handle_code_find,
    }

    handler = handlers.get(name)
    if not handler:
        raise ValueError(f"未知工具：{name}")

    return await handler(arguments or {})


# ── sy-notebooks ─────────────────────────────────

async def _handle_sy_notebooks(args: dict) -> list[types.TextContent]:
    """列出所有笔记本。"""
    _ensure_initialized()
    try:
        import httpx
        siyuan_cfg = _config.siyuan
        headers = {"Content-Type": "application/json"}
        if siyuan_cfg.token:
            headers["Authorization"] = f"Token {siyuan_cfg.token}"
        async with httpx.AsyncClient(
            base_url=f"http://{siyuan_cfg.host}:{siyuan_cfg.port}",
            headers=headers,
            timeout=15.0,
        ) as c:
            r = await c.post("/api/notebook/lsNotebooks", json={})
            body = r.json()
            if body.get("code") != 0:
                return [types.TextContent(type="text", text=f"获取笔记本列表失败：{body.get('msg')}")]
            notebooks = body["data"]["notebooks"]
            lines = ["📚 可用的笔记本：\n"]
            for nb in notebooks:
                lines.append(f"- `{nb['id']}` — **{nb['name']}**")
                if nb.get("closed"):
                    lines[-1] += " 🔒"
            return [types.TextContent(type="text", text="\n".join(lines))]
    except Exception as e:
        return [types.TextContent(type="text", text=f"获取笔记本列表失败：{e}")]


# ── sy-save ──────────────────────────────────────

async def _handle_sy_save(args: dict) -> list[types.TextContent]:
    content = args.get("content", "")
    if not content.strip():
        return [types.TextContent(type="text", text="❌ 内容不能为空")]

    try:
        tags = args.get("tags")
        name = args.get("name", "")
        notebook = args.get("notebook", "")

        if tags:
            content += "\n\n---\n标签：" + "、".join(tags)

        path = _make_doc_path(content, name=name)
        title = _extract_title(content)
        result = await _siyuan_client.create_doc(
            markdown=content,
            path=path,
            notebook_id=notebook,
        )

        location = f"项目 [{name}]" if name else "收集箱"
        result_text = (
            f"✅ 已保存到思源（{location}）\n"
            f"- 标题：{title}\n"
        )
        if result.id:
            result_text += f"- 链接：siyuan://blocks/{result.id}"
        return [types.TextContent(type="text", text=result_text)]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except ValueError as e:
        if str(e) == "no_notebook":
            return [types.TextContent(
                type="text",
                text="⚠️ 请先调用 `sy-notebooks` 选择笔记本，然后用 `notebook` 参数指定笔记本 ID",
            )]
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]


# ── sy-today ─────────────────────────────────────

async def _handle_sy_today(args: dict) -> list[types.TextContent]:
    content = args.get("content", "")
    if not content.strip():
        return [types.TextContent(type="text", text="❌ 内容不能为空")]

    try:
        notebook = args.get("notebook", "")
        doc_id = await _siyuan_client.get_or_create_daily_note(notebook_id=notebook)
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
    except ValueError as e:
        if str(e) == "no_notebook":
            return [types.TextContent(
                type="text",
                text="⚠️ 请先调用 `sy-notebooks` 选择笔记本，然后用 `notebook` 参数指定笔记本 ID",
            )]
        return [types.TextContent(type="text", text=f"❌ 写入日记失败：{e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 写入日记失败：{e}")]


# ── sy-auto ─────────────────────────────────────

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
    """尝试从 content 和 codebase repos 中匹配项目名称。"""
    repos = _config.codebase.repos
    if not repos:
        return ""
    # 从内容中检查是否提到某个项目名
    title = _extract_title(content).lower()
    for repo in repos:
        if repo.name.lower() in title or repo.name.lower() in content.lower():
            return repo.name
    return ""


def _resolve_content(raw: str) -> tuple[str, str]:
    """解析 content 参数。如果是文件路径则读取文件，返回 (内容, 来源说明)。"""
    text = raw.strip()

    # 去掉 @ 前缀
    if text.startswith("@"):
        text = text[1:].strip()

    # 检查是否是有效文件路径
    if text:
        p = Path(text)
        if not p.is_absolute():
            p = Path.cwd() / text
        if p.exists() and p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
                return content, f"文件 `{p.name}`"
            except Exception as e:
                return raw, f"（读取文件失败：{e}，按原文保存）"

    # 不是路径，原样返回
    return raw, "笔记"


async def _handle_sy_auto(args: dict) -> list[types.TextContent]:
    content_raw = args.get("content", "")
    if not content_raw.strip():
        return [types.TextContent(type="text", text="❌ 内容不能为空")]

    try:
        content, source = _resolve_content(content_raw)
        if not content.strip():
            return [types.TextContent(type="text", text="❌ 内容不能为空")]

        tags = args.get("tags")
        notebook = args.get("notebook", "")
        if tags:
            content += "\n\n---\n标签：" + "、".join(tags)

        name = _match_project(content)
        if not name:
            name = "uncategorized"

        path = _make_doc_path(content, name=name)
        title = _extract_title(content)
        result = await _siyuan_client.create_doc(
            markdown=content,
            path=path,
            notebook_id=notebook,
        )
        link = f"\n- 链接：siyuan://blocks/{result.id}" if result.id else ""
        return [
            types.TextContent(
                type="text",
                text=(
                    f"✅ 已自动保存（来源：{source}）\n"
                    f"- 项目：{name}\n"
                    f"- 标题：{title}"
                    f"{link}"
                ),
            )
        ]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except ValueError as e:
        if str(e) == "no_notebook":
            return [types.TextContent(
                type="text",
                text="⚠️ 请先调用 `sy-notebooks` 选择笔记本，然后用 `notebook` 参数指定笔记本 ID",
            )]
        return [types.TextContent(type="text", text=f"❌ 自动保存失败：{e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 自动保存失败：{e}")]


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
