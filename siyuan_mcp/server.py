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

# ── 常量 ──────────────────────────────────────────
SY_CONTENT_FILE = Path(".claude/sy-content.md")


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


# ── 全局状态 ──────────────────────────────────────
_config = None
_siyuan_client = None
_code_searcher = None
_notebook_mapper = NotebookMapper()

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
            name="sy-list",
            description="列出思源笔记中所有笔记本（带编号和名称）。用户可通过序号或名称选择笔记本。",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="sy-last",
            description="保存最后一条对话内容到思源笔记。使用前请先将对话内容写入 .claude/sy-content.md。不传 confirmed 时仅返回预览，传 confirmed=true 才实际写入。",
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {
                        "type": "string",
                        "description": "可选，笔记本序号或名称。不指定则用默认笔记本（索引0）",
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "确认标记。传 true 时实际写入，false 或省略时仅返回预览（默认 false）",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="sy-session",
            description="保存整个会话内容到思源笔记。使用前请先将会话内容写入 .claude/sy-content.md。不传 confirmed 时仅返回预览，传 confirmed=true 才实际写入。",
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {
                        "type": "string",
                        "description": "可选，笔记本序号或名称。不指定则用默认笔记本（索引0）",
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "确认标记。传 true 时实际写入，false 或省略时仅返回预览（默认 false）",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="sy-find",
            description="统一搜索。mode=normal|ai 搜索思源知识库，mode=code 搜索本地代码库。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["normal", "ai", "code"],
                        "description": "搜索模式：normal（默认）/ ai（语义搜索）/ code（代码搜索）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "搜索结果数量上限（默认 10）",
                    },
                    "notebook": {
                        "type": "string",
                        "description": "可选，限定笔记本（仅 normal/ai 模式）",
                    },
                    "path": {
                        "type": "string",
                        "description": "可选，限定项目名（仅 code 模式，匹配 repo name）",
                    },
                    "file_type": {
                        "type": "string",
                        "enum": ["code", "doc"],
                        "description": "文件类型过滤（仅 code 模式）",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "上下文行数（仅 code 模式，默认 3）",
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
        "sy-list": _handle_sy_list,
        "sy-last": _handle_sy_save,
        "sy-session": _handle_sy_save,
        "sy-find": _handle_sy_find,
    }

    handler = handlers.get(name)
    if not handler:
        raise ValueError(f"未知工具：{name}")

    return await handler(arguments or {})


# ── sy-list ─────────────────────────────────────

async def _handle_sy_list(args: dict) -> list[types.TextContent]:
    """列出笔记本（带编号和名称）。"""
    try:
        notebooks = await _siyuan_client.list_notebooks()
        _notebook_mapper.set_notebooks(notebooks)
        return [types.TextContent(type="text", text=_notebook_mapper.format_list())]
    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 获取笔记本列表失败：{e}")]


# ── sy-save ──────────────────────────────────────

async def _handle_sy_save(args: dict) -> list[types.TextContent]:
    content_raw = args.get("content")
    has_explicit_content = "content" in args

    # 未传 content 时从 .claude/sy-content.md 读取
    if not has_explicit_content:
        content_file = SY_CONTENT_FILE
        if not content_file.exists() or not content_file.is_file():
            return [types.TextContent(type="text", text="❌ 内容为空，请先将对话内容写入 .claude/sy-content.md")]
        try:
            content_raw = content_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ 读取 .claude/sy-content.md 失败：{e}")]
        if not content_raw:
            return [types.TextContent(type="text", text="❌ .claude/sy-content.md 为空，请写入内容后重试")]
        source_prefix = "对话文件"
    else:
        source_prefix = ""

    notebook_spec = args.get("notebook", "")
    confirmed = args.get("confirmed", False)

    try:
        # 解析内容来源
        if source_prefix:
            content = content_raw
            source = source_prefix
        else:
            content, source = _resolve_content(content_raw)
        if not content.strip():
            return [types.TextContent(type="text", text="❌ 内容不能为空")]

        # 防止内容太短（< 30 字且无 Markdown 标题）被当作占位指令
        if len(content.strip()) < 30 and not content.strip().startswith("#"):
            return [types.TextContent(type="text", text="⚠️ 内容过短，请提供完整的笔记内容或明确标注「last/最后一次」「session/整个会话」")]

        # 对话真实性校验：预览时检查是否包含对话标记
        _HAS_DIALOG = bool(re.search(r'>\s*\*\*用户.*?\*\*|>\s*\*\*助手.*?\*\*', content))
        if not _HAS_DIALOG:
            source = f"{source}（缺少对话标记）"

        # 提取标题
        title = _extract_title(content)

        # 匹配项目
        name = _match_project(content)

        # 确保笔记本列表已加载
        if not _notebook_mapper._notebooks:
            try:
                notebooks = await _siyuan_client.list_notebooks()
                _notebook_mapper.set_notebooks(notebooks)
            except Exception:
                pass

        # 解析笔记本
        try:
            notebook_id = _notebook_mapper.resolve(notebook_spec)
            notebook_name = ""
            for nb in _notebook_mapper._notebooks:
                if nb.id == notebook_id:
                    notebook_name = nb.name
                    break
        except ValueError as e:
            # 笔记本列表为空时尝试刷新
            if not notebook_spec:
                notebooks = await _siyuan_client.list_notebooks()
                _notebook_mapper.set_notebooks(notebooks)
                notebook_id = _notebook_mapper.resolve(notebook_spec)
                notebook_name = _notebook_mapper._notebooks[0].name if _notebook_mapper._notebooks else ""
            else:
                return [types.TextContent(type="text", text=f"❌ {e}")]

        # 生成标签
        tags = generate_tags(content)

        # 判断是否为整个对话（行数 > 30 或 字符数 > 2000）
        total_lines = content.count("\n")
        is_full_conversation = total_lines > 30 or len(content) > 2000

        if not confirmed:
            # 预览模式：返回确认信息，不写入
            lines = []
            if is_full_conversation:
                lines.append("⚠️ **即将保存整个对话内容**")
            lines.append(f"📄 内容：{len(content)} 字，{total_lines + 1} 行")
            if not _HAS_DIALOG:
                lines.append("⚠️ 缺少对话标记，请确认内容来源完整")
            lines.append("")
            lines.append(f"  📓 笔记本：{notebook_name or '默认'}")
            lines.append(f"  📝 标题：{title}")
            if name:
                lines.append(f"  📎 项目：{name}")
            if tags:
                lines.append(f"  🏷️  标签：{'、'.join(tags)}")
            lines.append("  ─────────────────")
            plain_text = content.replace("```", "").replace("#", "").strip()[:200]
            lines.append(f"  {plain_text}...")
            lines.append("  ─────────────────")
            lines.append("")
            lines.append("确认保存？(y/N)")
            return [types.TextContent(type="text", text="\n".join(lines))]

        # 确认模式：实际写入
        path = _make_doc_path(content, name=name)
        result = await _siyuan_client.create_doc(
            markdown=content,
            path=path,
            notebook_id=notebook_id,
        )

        result_lines = [
            f"✅ 已保存",
            "",
            f"  📓 笔记本：{notebook_name or '默认'}",
            f"  📂 路径：{notebook_name}/{f'项目/{name}/' if name else ''}{title}",
            f"  📝 标题：{title}",
        ]
        if tags:
            result_lines.append(f"  🏷️  标签：{'、'.join(tags)}")
        if result.id:
            result_lines.append(f"  🔗 siyuan://blocks/{result.id}")

        return [types.TextContent(type="text", text="\n".join(result_lines))]

    except ConnectionError as e:
        return [types.TextContent(type="text", text=f"❌ {e}")]
    except ValueError as e:
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ 保存失败：{e}")]


# ── sy-find ──────────────────────────────────────

async def _handle_sy_find(args: dict) -> list[types.TextContent]:
    query = args.get("query", "")
    mode = args.get("mode", "normal")
    limit = args.get("limit", 10)
    notebook = args.get("notebook", "")

    if not query.strip():
        return [types.TextContent(type="text", text="❌ 搜索关键词不能为空")]

    # mode:code → 代码搜索
    if mode == "code":
        path_filter = args.get("path")
        file_type = args.get("file_type", "code")
        context_lines = args.get("context_lines", 3)

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

            lines = [f"🔍 找到 {len(results)} 处代码匹配「{query}」（mode: code）：\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **{r.repo}** — `{r.file}:{r.line}`")
                lines.append(f"```\n{r.snippet}\n```")
                lines.append("")

            if skipped:
                lines.append(f"⚠️ 以下项目已跳过：{'；'.join(skipped)}")

            return [types.TextContent(type="text", text="\n".join(lines))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ 代码搜索失败：{e}")]

    # mode:normal/ai → 思源搜索
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
    """启动 MCP 服务（异步入口）。"""
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
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
    """启动 MCP 服务（同步入口，供 __main__.py 调用）。"""
    import asyncio
    return asyncio.run(amain())
