# 工具集重设计 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将现有 5 个 MCP 工具（sy-notebooks/sy-save/sy-auto/sy-find/code-find）精简为 3 个（sy-list/sy-save/sy-find），sy-save 增加确认流程和自动标签，sy-find 吸收 code-find，配置精简。

**架构：** 新增 NotebookMapper（序号/名称→ID 映射）和 AutoTagger（jieba 分词自动标签）两个独立模块，修改 server.py 注册新工具并移除旧工具，修改 config 去掉冗余配置项，修复 SiyuanClient 的 _call_api 响应类型问题。

**技术栈：** Python 3.10+ / MCP SDK / httpx / jieba / pydantic

**参考：** [Redesign Spec](../specs/2026-06-11-redesign-tools.md)

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `pyproject.toml` | 修改 | 添加 jieba 依赖 |
| `siyuan_mcp/config/defaults.py` | 修改 | 删除 workspace、default_mode、default_notebook、inbox_path |
| `siyuan_mcp/config/loader.py` | 修改 | 删除对应 Config 字段和 _ENV_MAP 条目 |
| `siyuan_mcp/siyuan/models.py` | 修改 | 新增 NotebookInfo 模型 |
| `siyuan_mcp/siyuan/client.py` | 修改 | 新增 list_notebooks()，修复 _call_api 的 data 类型兼容 |
| `siyuan_mcp/mapper.py` | **创建** | NotebookMapper — 笔记本序号/名称→ID 映射 |
| `siyuan_mcp/tagger.py` | **创建** | AutoTagger — jieba 分词自动标签 |
| `siyuan_mcp/server.py` | 修改 | 工具注册重构、Handler 重写、集成 Mapper+Tagger |
| `config.yaml.example` | 修改 | 同步精简后的配置项 |
| `tests/test_config_loader.py` | 修改 | 更新测试断言（删除已移除的配置项） |
| `tests/test_siyuan_client.py` | 修改 | 新增 list_notebooks 测试 |
| `tests/test_mapper.py` | **创建** | NotebookMapper 全场景测试 |
| `tests/test_tagger.py` | **创建** | AutoTagger 全场景测试 |
| `tests/test_server.py` | 修改 | 重写：新工具名、新参数、新行为 |

---

## 任务分解

### 任务 1：配置精简

**文件：**
- 修改：`siyuan_mcp/config/defaults.py` — 删除 storage 段和 workspace/default_mode
- 修改：`siyuan_mcp/config/loader.py` — 删除 Config 中对应字段和 _ENV_MAP
- 修改：`tests/test_config_loader.py` — 更新断言
- 修改：`config.yaml.example` — 同步精简

- [ ] **步骤 1：更新 defaults.py**

删除 `workspace`、`default_mode`、`default_notebook`、`inbox_path` 的默认值：

```python
def get_defaults() -> dict[str, Any]:
    return {
        "siyuan": {
            "host": "127.0.0.1",
            "port": 6806,
            "token": "",
        },
        "codebase": {
            "repos": [],
        },
        "search": {
            "max_results": 10,
            "rg_path": "rg",
        },
    }
```

- [ ] **步骤 2：更新 loader.py**

删除 `SiyuanConfig.workspace`、`SearchConfig.default_mode`、`StorageConfig` 整个类、`Config.storage` 字段。
删除 _ENV_MAP 中对应的环境变量。

```python
class SiyuanConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6806
    token: str = ""

class CodebaseConfig(BaseModel):
    repos: list[CodebaseRepo] = []

class SearchConfig(BaseModel):
    max_results: int = 10
    rg_path: str = "rg"

class Config(BaseModel):
    siyuan: SiyuanConfig = SiyuanConfig()
    codebase: CodebaseConfig = CodebaseConfig()
    search: SearchConfig = SearchConfig()

_ENV_MAP: list[tuple[str, tuple[str, str]]] = [
    ("SIYUAN_HOST", ("siyuan", "host")),
    ("SIYUAN_PORT", ("siyuan", "port")),
    ("SIYUAN_TOKEN", ("siyuan", "token")),
    ("CODEBASE_REPOS", ("codebase", "repos")),
    ("SEARCH_MAX_RESULTS", ("search", "max_results")),
]
```

- [ ] **步骤 3：更新测试 test_config_loader.py**

将 `test_get_defaults_returns_expected_structure` 中断言 `"storage" in defaults` 改为 `"storage" not in defaults`。
将 `test_siyuan_defaults` 中断言 `siyuan["workspace"]` 删除。
将 `test_search_defaults` 中断言 `default_mode` 删除。

- [ ] **步骤 4：更新 config.yaml.example**

删除 `siyuan.workspace`、`storage` 段、`search.default_mode`。

- [ ] **步骤 5：运行测试确认通过**

```bash
cd d:/Code/siyuan-bridge && python -m pytest tests/test_config_loader.py -v
```

- [ ] **步骤 6：Commit**

```bash
git add -A
git commit -m "refactor: remove obsolete config fields (workspace, default_mode, storage)"
```

---

### 任务 2：SiyuanClient 新增 list_notebooks + NotebookInfo 模型

**文件：**
- 修改：`siyuan_mcp/siyuan/models.py` — 新增 NotebookInfo
- 修改：`siyuan_mcp/siyuan/client.py` — 新增 list_notebooks()、修复 _call_api
- 修改：`tests/test_siyuan_client.py` — 新增测试

- [ ] **步骤 1：添加 NotebookInfo 模型**

在 `siyuan_mcp/siyuan/models.py` 末尾添加：

```python
class NotebookInfo(BaseModel):
    """笔记本信息（从 lsNotebooks 响应解析）。"""
    id: str
    name: str
    closed: bool = False
```

- [ ] **步骤 2：添加 list_notebooks 方法**

在 `SiyuanClient` 类中添加：

```python
async def list_notebooks(self) -> list[NotebookInfo]:
    """获取笔记本列表。"""
    resp = await self._call_api("/api/notebook/lsNotebooks", {})
    raw = resp if isinstance(resp, list) else resp.get("notebooks", [])
    return [NotebookInfo(**nb) for nb in raw]
```

- [ ] **步骤 3：修复 _call_api 中 data 为字符串时的处理**

当前代码：`return body.get("data") or {}`
问题：当 API 返回 `"data": "文档ID"` 时正常工作，但 `"data": None` 时返回 `{}`。

改为：
```python
data = body.get("data")
if data is None:
    return {}
return data
```

- [ ] **步骤 4：编写 list_notebooks 测试**

在 `tests/test_siyuan_client.py` 中添加：

```python
@pytest.mark.asyncio
async def test_list_notebooks_success(config):
    client = SiyuanClient(config)
    mock_response = {
        "code": 0,
        "msg": "",
        "data": {
            "notebooks": [
                {"id": "nb-1", "name": "AI知识体系", "closed": False},
                {"id": "nb-2", "name": "日记本", "closed": False},
                {"id": "nb-3", "name": "归档", "closed": True},
            ]
        },
    }

    with patch.object(client._client, "post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json = lambda: mock_response

        result = await client.list_notebooks()
        assert len(result) == 3
        assert result[0].name == "AI知识体系"
        assert result[0].id == "nb-1"
        assert result[2].closed is True
```

- [ ] **步骤 5：运行测试确认通过**

```bash
cd d:/Code/siyuan-bridge && python -m pytest tests/test_siyuan_client.py -v
```

- [ ] **步骤 6：Commit**

```bash
git add -A
git commit -m "feat: add list_notebooks to SiyuanClient, add NotebookInfo model"
```

---

### 任务 3：NotebookMapper — 序号/名称→ID 映射

**文件：**
- 创建：`siyuan_mcp/mapper.py`
- 创建：`tests/test_mapper.py`

- [ ] **步骤 1：编写失败测试**

`tests/test_mapper.py`:

```python
"""测试 NotebookMapper 笔记本映射器。"""

import pytest
from siyuan_mcp.mapper import NotebookMapper
from siyuan_mcp.siyuan.models import NotebookInfo


@pytest.fixture
def mapper():
    m = NotebookMapper()
    m._notebooks = [
        NotebookInfo(id="nb-ai", name="AI知识体系", closed=False),
        NotebookInfo(id="nb-diary", name="日记本", closed=False),
        NotebookInfo(id="nb-archive", name="项目归档", closed=True),
    ]
    return m


def test_default_returns_first_notebook(mapper):
    assert mapper.resolve("") == "nb-ai"


def test_index_one_based(mapper):
    assert mapper.resolve("1") == "nb-ai"
    assert mapper.resolve("2") == "nb-diary"
    assert mapper.resolve("3") == "nb-archive"


def test_name_exact_match(mapper):
    assert mapper.resolve("AI知识体系") == "nb-ai"
    assert mapper.resolve("日记本") == "nb-diary"


def test_name_fuzzy_match(mapper):
    """输入包含笔记本名称，或笔记本名称包含输入。"""
    assert mapper.resolve("AI") == "nb-ai"
    assert mapper.resolve("知识") == "nb-ai"


def test_index_out_of_range_raises(mapper):
    with pytest.raises(ValueError, match="超出范围"):
        mapper.resolve("0")
    with pytest.raises(ValueError, match="超出范围"):
        mapper.resolve("4")


def test_name_not_found_raises(mapper):
    with pytest.raises(ValueError, match="未找到"):
        mapper.resolve("不存在的笔记本")


def test_format_list_contains_names_and_default_marker(mapper):
    out = mapper.format_list()
    assert "AI知识体系" in out
    assert "日记本" in out
    assert "项目归档" in out
    assert "当前默认" in out.replace(" ←", "")  # 跳过 unicode 箭头
    assert "🔒" in out  # closed 标记
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd d:/Code/siyuan-bridge && python -m pytest tests/test_mapper.py -v
```
预期：ImportError（mapper.py 不存在）

- [ ] **步骤 3：编写 NotebookMapper 实现**

`siyuan_mcp/mapper.py`:

```python
"""笔记本序号/名称 → notebook_id 映射。"""

from siyuan_mcp.siyuan.models import NotebookInfo


class NotebookMapper:
    """将用户输入的序号或笔记本名称映射为 notebook_id。
    
    用户输入:
        ""       → 索引 0（默认笔记本）
        "2"      → 索引 1（1-based 序号）
        "AI知识" → 模糊匹配笔记本名称
    """

    def __init__(self):
        self._notebooks: list[NotebookInfo] = []

    def set_notebooks(self, notebooks: list[NotebookInfo]):
        self._notebooks = list(notebooks)

    def resolve(self, spec: str = "") -> str:
        if not spec:
            if not self._notebooks:
                raise ValueError("笔记本列表为空，请先调用 sy-list")
            return self._notebooks[0].id

        # 序号模式："1" → 索引 0
        if spec.isdigit():
            idx = int(spec) - 1
            if idx < 0 or idx >= len(self._notebooks):
                raise ValueError(
                    f"笔记本序号超出范围（1-{len(self._notebooks)}）"
                )
            return self._notebooks[idx].id

        # 名称模式："AI知识体系" → 模糊匹配
        for nb in self._notebooks:
            if spec in nb.name or nb.name in spec:
                return nb.id

        raise ValueError(f"未找到笔记本「{spec}」")

    def format_list(self) -> str:
        if not self._notebooks:
            return "📚 笔记本列表为空"
        lines = ["📚 思源笔记本列表：\n"]
        for i, nb in enumerate(self._notebooks, 1):
            marker = " ← 当前默认" if i == 1 else ""
            lock = " 🔒" if nb.closed else ""
            lines.append(f"  {i}. {nb.name}{marker}{lock}")
        lines.append("\n输入序号或笔记名称即可作为 sy-save 的 notebook 参数")
        return "\n".join(lines)
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd d:/Code/siyuan-bridge && python -m pytest tests/test_mapper.py -v
```
预期：7 passed

- [ ] **步骤 5：Commit**

```bash
git add -A
git commit -m "feat: add NotebookMapper with index/name resolution"
```

---

### 任务 4：AutoTagger — jieba 自动标签

**文件：**
- 创建：`siyuan_mcp/tagger.py`
- 创建：`tests/test_tagger.py`

- [ ] **步骤 1：编写失败测试**

`tests/test_tagger.py`:

```python
"""测试自动标签生成。"""

import pytest
from siyuan_mcp.tagger import generate_tags


def test_short_content_returns_empty():
    assert generate_tags("短") == []


def test_normal_content_returns_tags():
    content = (
        "JWT 认证方案\n"
        "JWT 是一种基于 Token 的认证方式。"
        "它使用 RS256 签名算法对 Token 进行签名。"
        "认证流程包括登录、签发 Token、验证 Token 三个步骤。"
    )
    tags = generate_tags(content)
    assert len(tags) <= 6
    assert len(tags) >= 1
    # JWT 应该是高频词
    assert any("JWT" in t for t in tags)


def test_max_six_tags():
    # 生成长内容确保能提取至少 6 个标签候选
    content = (
        "Python Rust Go Java 性能对比\n"
        "Python 在 AI 领域有优势，Rust 在系统编程有优势。"
        "Go 在并发编程方面表现优秀。Java 在企业级应用广泛。"
        "这些语言各有特点，适用于不同场景。"
        "性能方面 Rust 最优，Go 次之。"
        "开发效率 Python 最高。生态系统 Java 最丰富。"
        "选择语言需要根据具体需求。"
    )
    tags = generate_tags(content)
    assert len(tags) <= 6


def test_tags_truncated_to_10_chars():
    content = "这是一个超长标签测试 " * 20
    tags = generate_tags(content)
    for t in tags:
        assert len(t) <= 10


def test_markdown_headers_removed():
    """Markdown 标题不应进入标签。"""
    content = "# 这是一个很长的标题\n\n正文内容是关于认证的话题。认证很重要。"
    tags = generate_tags(content)
    assert "这是一个很长的标题" not in tags
    assert len(tags) > 0
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd d:/Code/siyuan-bridge && python -m pytest tests/test_tagger.py -v
```
预期：ImportError（tagger.py 不存在）

- [ ] **步骤 3：安装 jieba 并编写实现**

先添加依赖：
```bash
cd d:/Code/siyuan-bridge && python -m pip install jieba
```

在 `pyproject.toml` 中添加：
```python
dependencies = [
    "mcp>=1.0.0",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "pydantic>=2.0",
    "jieba>=0.42",
]
```

`siyuan_mcp/tagger.py`:

```python
"""自动标签生成：使用 jieba 分词提取关键词。"""

import re
from typing import Optional

try:
    import jieba
except ImportError:
    jieba = None  # type: ignore


# 通用中文停用词
_STOP_WORDS: set[str] = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "它", "们", "那", "什么", "怎么", "因为", "所以", "可以", "这个",
    "那个", "我们", "他们", "它们", "被", "把", "让", "对", "与",
    "而", "但", "但是", "如果", "虽然", "然后", "或者", "还是",
    "以及", "其中", "其", "之", "为", "所", "能", "于", "及", "等",
    "中", "从", "将", "用", "以", "来", "还", "做", "和", "或",
    "并", "而", "且", "被", "把", "让", "给", "向", "对", "比",
}


def generate_tags(content: str, max_tags: int = 6) -> list[str]:
    """从 Markdown 内容中提取最多 max_tags 个标签。

    规则：
    - 内容 < 20 字 → 返回空列表
    - 去掉 Markdown 标题、代码块、链接
    - jieba 分词 → 过滤停用词+单字 → 按词频排序 → 取 top N
    - 单标签最长 10 字符
    """
    text = content.strip()
    if len(text) < 20:
        return []

    # 去掉 Markdown 元素
    text = re.sub(r'^#+\s.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'\[.+?\]\(.+?\)', '', text)

    if jieba is None:
        # jieba 未安装时使用简单空格/标点分词作为 fallback
        words = re.findall(r'[\w一-鿿]+', text)
    else:
        words = jieba.lcut(text)

    # 过滤：停用词、单字、空白
    filtered = [
        w.strip() for w in words
        if w.strip() and len(w.strip()) > 1 and w.strip() not in _STOP_WORDS
    ]

    # 按词频排序
    freq: dict[str, int] = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1

    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    tags = [w for w, _ in sorted_words[:max_tags]]
    return [t[:10] for t in tags]
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd d:/Code/siyuan-bridge && python -m pytest tests/test_tagger.py -v
```
预期：5 passed

- [ ] **步骤 5：Commit**

```bash
git add -A
git commit -m "feat: add jieba-based auto-tagging (generate_tags)"
```

---

### 任务 5：server.py — 工具注册重构 + Handler 重写

**文件：**
- 修改：`siyuan_mcp/server.py`
- 修改：`tests/test_server.py`

这是最大的任务。server.py 需要：
1. 移除旧工具声明：sy-notebooks、sy-auto、code-find
2. 新增工具声明：sy-list
3. 重写 sy-save：精简参数、增加确认流程、集成 mapper+tagger
4. 重写 sy-find：增加 mode:code 路由
5. 集成 NotebookMapper 和 AutoTagger 到全局状态
6. 更新 handler 分发表

sy-list 和 sy-save 共享 NotebookMapper 实例，so 需要添加到 _ensure_initialized。

- [ ] **步骤 1：更新全局状态和初始化**

在 server.py 顶部添加导入：
```python
from siyuan_mcp.mapper import NotebookMapper
from siyuan_mcp.tagger import generate_tags
```

更新全局状态：
```python
_config = None
_siyuan_client = None
_code_searcher = None
_notebook_mapper = NotebookMapper()
```

更新 `_ensure_initialized`：
```python
def _ensure_initialized():
    global _config, _siyuan_client, _code_searcher
    if _config is None:
        loader = ConfigLoader()
        _config = loader.load()
        _siyuan_client = SiyuanClient(_config)
        _code_searcher = CodebaseSearcher(_config)
```

在 sy-list handler 和 sy-save handler 中调 `_notebook_mapper.set_notebooks()` 确保映射器常新。
在第一次调用时刷新映射器缓存。

- [ ] **步骤 2：重写工具列表**

`handle_list_tools` 返回值改为 3 个工具：sy-list、sy-save、sy-find

**sy-list:**
```python
types.Tool(
    name="sy-list",
    description="列出思源笔记中所有笔记本（带编号）。用户可通过序号或名称选择笔记本。",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": [],
    },
),
```

**sy-save（精简参数）:**
```python
types.Tool(
    name="sy-save",
    description="保存笔记到思源。默认保存到索引0（第一笔记本）。"
               "不传 confirmed 时只返回预览确认信息，传 confirmed=true 才实际写入。"
               "内容以 @ 开头可读取文件。",
    inputSchema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "笔记内容（Markdown）或 @文件路径",
            },
            "notebook": {
                "type": "string",
                "description": "可选，笔记本序号或名称。不指定则用默认笔记本（索引0）",
            },
            "confirmed": {
                "type": "boolean",
                "description": "确认标记。true=实际写入，false=仅返回预览（默认）",
            },
        },
        "required": ["content"],
    },
),
```

**sy-find（增加 mode:code）:**
```python
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
                "description": "搜索条数上限（默认 10）",
            },
            "notebook": {
                "type": "string",
                "description": "限定笔记本（仅 normal/ai 模式）",
            },
            "path": {
                "type": "string",
                "description": "限定项目名（仅 code 模式，匹配 repo name）",
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
```

- [ ] **步骤 3：重写 handler 分发表**

```python
handlers = {
    "sy-list": _handle_sy_list,
    "sy-save": _handle_sy_save,
    "sy-find": _handle_sy_find,
}
```

- [ ] **步骤 4：实现 _handle_sy_list**

```python
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
```

- [ ] **步骤 5：重写 _handle_sy_save（分两段：预览和确认）**

```python
async def _handle_sy_save(args: dict) -> list[types.TextContent]:
    content_raw = args.get("content", "")
    if not content_raw.strip():
        return [types.TextContent(type="text", text="❌ 内容不能为空")]

    notebook_spec = args.get("notebook", "")
    confirmed = args.get("confirmed", False)
    is_full_conversation = False  # 对话内容检测由 MCP 调用端标记，server 端通过长度/特征判断

    try:
        # 1. 解析内容来源
        content, source = _resolve_content(content_raw)
        if not content.strip():
            return [types.TextContent(type="text", text="❌ 内容不能为空")]

        # 2. 提取标题
        title = _extract_title(content)

        # 3. 匹配项目
        name = _match_project(content)

        # 4. 确保笔记本映射器已加载
        if not _notebook_mapper._notebooks:
            try:
                notebooks = await _siyuan_client.list_notebooks()
                _notebook_mapper.set_notebooks(notebooks)
            except Exception:
                pass

        # 5. 解析笔记本
        try:
            notebook_id = _notebook_mapper.resolve(notebook_spec)
            notebook_name = ""
            for nb in _notebook_mapper._notebooks:
                if nb.id == notebook_id:
                    notebook_name = nb.name
                    break
        except ValueError as e:
            # 笔记本解析失败 → 尝试拉取最新笔记本列表后重试
            if not notebook_spec:
                notebooks = await _siyuan_client.list_notebooks()
                _notebook_mapper.set_notebooks(notebooks)
                notebook_id = _notebook_mapper.resolve(notebook_spec)
                notebook_name = _notebook_mapper._notebooks[0].name if _notebook_mapper._notebooks else ""
            else:
                return [types.TextContent(type="text", text=f"❌ {e}")]

        # 6. 生成标签
        tags = generate_tags(content)

        # 7. 判断是否是整个对话
        total_lines = content.count("\n")
        is_full_conversation = total_lines > 30 or len(content) > 2000

        if not confirmed:
            # 预览模式：返回确认信息，不保存
            location_parts = []
            if notebook_name:
                location_parts.append(notebook_name)
            if name:
                location_parts.append(f"项目/{name}")
            location_parts.append(title)
            location_str = " / ".join(location_parts) if location_parts else title

            lines = []
            if is_full_conversation:
                lines.append("⚠️ **即将保存整个对话内容**")
                lines.append(f"（共约 {total_lines + 1} 行，{len(content)} 字符）")
            else:
                lines.append("即将保存笔记：")
            lines.append("")
            lines.append(f"  📓 笔记本：{notebook_name or '默认'}")
            lines.append(f"  📝 标题：{title}")
            if name:
                lines.append(f"  📎 项目：{name}")
            if tags:
                lines.append(f"  🏷️  标签：{'、'.join(tags)}")
            lines.append("  ─────────────────")
            # 摘要：取前 200 字
            plain_text = content.replace("```", "").replace("#", "").strip()[:200]
            lines.append(f"  {plain_text}...")
            lines.append("  ─────────────────")
            lines.append("")
            lines.append('确认保存？请回复「确认保存」或「sy-save 已确认」来实际写入。')
            return [types.TextContent(type="text", text="\n".join(lines))]

        # ---- 确认模式 ----
        path = _make_doc_path(content, name=name)
        result = await _siyuan_client.create_doc(
            markdown=content,
            path=path,
            notebook_id=notebook_id,
        )

        # 拼接位置信息
        location_parts = []
        if notebook_name:
            location_parts.append(notebook_name)
        if name:
            location_parts.append(f"项目/{name}")
        location_parts.append(title)
        location_str = " / ".join(location_parts) if location_parts else title

        result_lines = [
            f"✅ 已保存",
            "",
            f"  📓 笔记本：{notebook_name or '默认'}",
            f"  📂 路径：{location_str}",
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
```

- [ ] **步骤 6：重写 _handle_sy_find（增加 mode:code 路由）**

```python
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

    # mode:normal/ai → 思源知识库搜索
    try:
        results = await _siyuan_client.search_notes(
            query=query, mode=mode, limit=limit, notebook=notebook
        )

        if not results:
            return [types.TextContent(
                type="text", text=f"📭 未找到与「{query}」相关的结果"
            )]

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
```

- [ ] **步骤 7：更新 _resolve_content — 判断是否是对话内容**

在原 `_resolve_content` 函数中添加对对话内容标记的支持。当内容行数多、含有多轮对话特征（含 `> **`、`**说：**` 或大量换行）时，设置清晰来源标记。

- [ ] **步骤 8：编写 tests/test_server.py**

重写测试文件，覆盖：

1. `test_sy_save_empty_content` — 空内容 → ❌
2. `test_sy_save_preview_no_confirm` — 无 confirmed → 返回预览
3. `test_sy_save_confirmed_writes` — confirmed=true → 调用 create_doc
4. `test_sy_save_with_notebook_index` — notebook="2" → 映射到索引 1
5. `test_sy_save_with_notebook_name` — notebook="AI知识" → 模糊匹配
6. `test_sy_save_default_notebook` — notebook="" → 索引 0
7. `test_sy_list_returns_notebooks` — sy-list → 返回列表
8. `test_sy_find_empty_query` — 空 query → ❌
9. `test_sy_find_normal_mode` — mode=normal → 调 search_notes
10. `test_sy_find_code_mode` — mode=code → 调 _code_searcher
11. `test_sy_find_connection_error` — 连接错 → 友好提示
12. `test_auto_tags_in_preview` — 预览中包含标签

注意测试中需要 mock SiyuanClient 的 `list_notebooks` 和 `NotebookMapper`。

- [ ] **步骤 9：运行全部测试确认通过**

```bash
cd d:/Code/siyuan-bridge && python -m pytest -v
```
预期：所有测试通过

- [ ] **步骤 10：Commit**

```bash
git add -A
git commit -m "refactor: redesign tools to 3-tool system (sy-list/sy-save/sy-find)"
```

---

### 任务 6：删除遗留文件 + 最终清理

**文件：**
- 删除：`siyuan_mcp/codebase/search.py`（逻辑已合并到 sy-find mode:code，但搜索器本身仍被 server.py 引用，保留）
- 确认所有旧工具名不再出现在代码中

- [ ] **步骤 1：grep 检查是否有残留**

```bash
cd d:/Code/siyuan-bridge && grep -rn "sy-notebooks\|sy-auto\|code-find\|sy-today" siyuan_mcp/ --include="*.py" 2>/dev/null || echo "clean"
```

- [ ] **步骤 2：删除旧的 sy-today 相关代码（已删除但确认无残留）**

- [ ] **步骤 3：运行全部测试**

```bash
cd d:/Code/siyuan-bridge && python -m pytest -v
```

- [ ] **步骤 4：Commit**

```bash
git add -A
git commit -m "chore: clean up legacy references"
```

---

### 任务 7：端到端测试 — 实际调用验证

**验证目标：** 每个工具每种情况实际调用，观察 Claude 反应，汇总结果。

- [ ] **sy-list 测试：** 调用 sy-list，验证返回格式包含编号和名称
- [ ] **sy-save 预览测试：** sy-save 不带 confirmed，验证返回预览信息（标题、标签、位置）
- [ ] **sy-save 确认测试：** sy-save 带 confirmed=true，验证写入成功并返回位置
- [ ] **sy-save 默认笔记本测试：** 不传 notebook，验证保存到索引 0
- [ ] **sy-save 序号笔记本测试：** notebook="2"，验证保存到第二个笔记本
- [ ] **sy-save 名称笔记本测试：** notebook="AI知识体系"，验证模糊匹配
- [ ] **sy-save 空内容测试：** 空 content，验证错误提示
- [ ] **sy-find normal 测试：** mode=normal，验证思源搜索
- [ ] **sy-find code 测试：** mode=code，验证代码搜索
- [ ] **sy-find 空查询测试：** 空 query，验证错误提示
