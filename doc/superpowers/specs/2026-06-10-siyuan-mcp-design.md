# 思源笔记 MCP 服务 — 设计文档

> 版本: v1
> 日期: 2026-06-10
> 状态: 待审查

---

## 一、项目概述

实现一个 MCP（Model Context Protocol）服务，连接 Claude Code / Claude Desktop 与思源笔记。

用户无需打开思源笔记，即可通过自然语言完成笔记保存、知识检索、代码库搜索。

### 核心原则

- **统一前缀命名** — 所有思源工具使用 `sy-` 前缀，代码库工具使用 `code-` 前缀
- **本地优先** — 默认通过 stdio 传输，依赖思源本地 HTTP API
- **默认可用** — 所有配置项都有合理的默认值，开箱即用
- **开源通用** — 一套代码覆盖本地/远程部署，配置即适配

### MVP 工具列表

| 工具 | 用途 | 分类 |
|------|------|------|
| `sy-save` | 快捷保存到思源收集箱 | 笔记保存 |
| `sy-find` | 搜索思源知识库（普通/AI 模式） | 知识检索 |
| `code-find` | 在关联本地 Git 项目中搜索代码 | 代码检索 |

---

## 二、架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│  Claude Code / Claude Desktop                        │
│  ┌──────────────────────────────────────────────┐   │
│  │  MCP Client (内置)                           │   │
│  └──────────────┬───────────────────────────────┘   │
└─────────────────┼───────────────────────────────────┘
                  │ stdio 传输（JSON-RPC over stdin/stdout）
                  ▼
┌─────────────────────────────────────────────────────┐
│  siyuan-mcp (Python 单体进程)                        │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  server.py — MCP Server (@mcp.tool)          │   │
│  │  ├── sy-save()    → siyuan/client.py         │   │
│  │  ├── sy-find()    → siyuan/client.py         │   │
│  │  └── code-find()  → codebase/search.py       │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────┐  ┌──────────────────┐         │
│  │  config/loader.py │  │  siyuan/client   │         │
│  │  （YAML 配置      │  │  （思源 HTTP API  │         │
│  │   加载/合并/校验） │  │   封装）          │         │
│  └──────────────────┘  └──────────────────┘         │
│                                                      │
│  ┌──────────────────┐                               │
│  │  codebase/       │                               │
│  │  search.py       │  ← ripgrep 搜索本地代码       │
│  │  config.py       │  ← 代码库路径管理             │
│  └──────────────────┘                               │
└─────────────────────┬───────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
┌──────────────────┐     ┌─────────────────────┐
│ 思源笔记 HTTP API  │     │ 本地 Git 仓库        │
│ localhost:6806    │     │ wallet/exchange/im  │
└──────────────────┘     └─────────────────────┘
```

### 通信方式

- **传输协议**: MCP stdio（标准输入输出）
- **消息格式**: JSON-RPC 2.0
- **服务生命周期**: 由 MCP 客户端（Claude）自动启动/停止
- **思源通信**: HTTP 请求到 `http://127.0.0.1:6806`

### 部署形态

| 环境 | 启停方式 |
|------|---------|
| Claude Code (CLI) | 在 `claude.json` 中配置为 MCP server，自动管理 |
| Claude Code (VS Code) | 同上，VS Code 配置共享 |
| Claude Desktop | 在 `claude_desktop_config.json` 中配置 |
| 手动调试 | `python -m siyuan_mcp` 直接运行 |

---

## 三、项目结构

```
d:\Code\siyuan-bridge\
├── siyuan_mcp/                ← Python 包（源码）
│   ├── __init__.py
│   ├── __main__.py            ← python -m siyuan_mcp 入口
│   ├── server.py              ← MCP 服务主文件（工具声明）
│   ├── siyuan/
│   │   ├── __init__.py
│   │   ├── client.py          ← 思源 HTTP API 客户端
│   │   └── models.py          ← 数据模型
│   ├── codebase/
│   │   ├── __init__.py
│   │   ├── search.py          ← ripgrep 代码搜索
│   │   └── config.py          ← 代码库路径配置解析
│   └── config/
│       ├── __init__.py
│       ├── loader.py          ← YAML 加载/合并/校验/环境变量覆盖
│       └── defaults.py        ← 内置默认值常量
├── config.yaml.example        ← 示例配置文件（含注释）
├── pyproject.toml             ← 项目元数据 + 依赖声明
├── README.md                  ← 安装/配置/使用说明
├── doc/
│   ├── 思源笔记与AI集成-需求文档.md
│   └── superpowers/
│       └── specs/
│           └── 2026-06-10-siyuan-mcp-design.md  ← 本文件
└── tests/                     ← 测试（后续阶段）
    ├── test_siyuan_client.py
    ├── test_codebase_search.py
    └── test_config_loader.py
```

---

## 四、MCP 工具详细定义

### 4.1 `sy-save` — 保存笔记

```
@mcp.tool
async def sy_save(
    content: str,        # 笔记内容（Markdown 格式）
    tags: list[str] | None = None,  # 可选，手动指定标签
    source: str | None = None       # 可选，来源标记
) -> SySaveResult
```

**行为**：
1. 接收 Markdown 内容
2. 调用思源 API `createDocWithMd` 创建文档到收集箱
3. 如果提供 `tags`，写入文档标签
4. 返回文档 ID 和思源链接

**返回**：
```json
{
    "id": "20260610123456-abc123",
    "url": "siyuan://blocks/20260610123456-abc123",
    "title": "自动生成或用户指定的标题"
}
```

### 4.2 `sy-find` — 搜索知识库

```
@mcp.tool
async def sy_find(
    query: str,                    # 搜索关键词
    mode: Literal["normal", "ai"] = "normal",  # 搜索模式
    limit: int = 10,               # 结果数上限
    notebook: str | None = None    # 可选，限定笔记本
) -> SyFindResult
```

**行为**：
1. `mode="normal"`: 调用思源 API `searchNotes`（关键词匹配）
2. `mode="ai"`: 调用思源 API `searchFullText`（语义搜索）
3. 格式化返回结果，包含文档标题、摘要片段、路径

**返回**：
```json
{
    "total": 15,
    "results": [
        {
            "id": "20260610123456-abc123",
            "title": "笔记标题",
            "snippet": "匹配内容的上下文片段...",
            "path": "/笔记/分类/文档名",
            "score": 0.95,
            "updated": "2026-06-10T12:00:00"
        }
    ]
}
```

### 4.3 `code-find` — 搜索代码库

```
@mcp.tool
async def code_find(
    query: str,                       # 搜索关键词（支持正则）
    path: str | None = None,          # 可选，限定项目
    file_type: Literal["code", "doc"] = "code",  # 文件类型过滤
    context_lines: int = 3            # 上下文行数
) -> CodeFindResult
```

**行为**：
1. 读取配置中的 `codebase.repos` 列表
2. 如果指定 `path`，只搜索匹配的项目
3. 对每个项目路径执行 `ripgrep` 搜索
4. 过滤结果：`code` 模式排除 `.md`/`.txt`/`.doc` 等文档文件
5. 返回匹配结果

**返回**：
```json
{
    "total": 8,
    "results": [
        {
            "repo": "wallet",
            "file": "src/wallet/transfer.go",
            "line": 42,
            "snippet": "    // 匹配行上下文的代码片段\n    func Transfer(ctx context.Context, req *TransferReq) error {\n        ...",
            "match": "Transfer"
        }
    ],
    "skipped_repos": []  // 搜索失败的路径列表
}
```

---

## 五、配置系统

### 5.1 配置文件

搜索优先级：当前目录 `./config.yaml` → `~/.siyuan-mcp/config.yaml` → 内置默认值

```yaml
# config.yaml
siyuan:
  host: "127.0.0.1"       # 思源 API 地址
  port: 6806               # 思源 API 端口
  token: ""                # API Token（空=不鉴权）
  workspace: ""            # 工作空间路径（留空自动检测）

codebase:
  repos:                   # 关联代码库列表
    - path: "D:/Code/wallet"
      name: "wallet"
    - path: "D:/Code/exchange"
      name: "exchange"
    - path: "D:/Code/im"
      name: "im"

search:
  default_mode: "normal"   # 默认搜索模式: normal | ai
  max_results: 10          # 默认最大返回数
  rg_path: "rg"            # ripgrep 路径

storage:
  default_notebook: ""     # 默认笔记本 ID（空=思源默认）
  inbox_path: "/"          # 收集箱路径
```

### 5.2 配置加载流程

```
启动
  │
  ├─① 加载内置默认值（defaults.py）
  │
  ├─② 尝试读取 ./config.yaml
  │   └─ 不存在 → 尝试读取 ~/.siyuan-mcp/config.yaml
  │       └─ 不存在 → 跳过
  │
  ├─③ 合并配置（用户配置覆盖默认值，深度合并）
  │
  ├─④ 环境变量覆盖
  │   ├─ SIYUAN_HOST      → siyuan.host
  │   ├─ SIYUAN_PORT      → siyuan.port
  │   ├─ SIYUAN_TOKEN     → siyuan.token
  │   ├─ CODEBASE_REPOS   → codebase.repos（JSON 数组字符串）
  │   └─ SEARCH_MAX_RESULTS → search.max_results
  │
  ├─⑤ 校验：siyuan.host 不能为空
  │
  └─⑥ 输出最终 Config 对象
```

### 5.3 所有可配置项及默认值

| 配置路径 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `siyuan.host` | string | `"127.0.0.1"` | 思源 API 主机地址 |
| `siyuan.port` | integer | `6806` | 思源 API 端口 |
| `siyuan.token` | string | `""` | API Token（空=不校验） |
| `siyuan.workspace` | string | `""` | 思源工作空间路径 |
| `codebase.repos` | array | `[]` | 关联代码库列表 |
| `codebase.repos[].path` | string | — | 代码库本地路径 |
| `codebase.repos[].name` | string | — | 代码库别名 |
| `search.default_mode` | enum | `"normal"` | 搜索模式 |
| `search.max_results` | integer | `10` | 搜索结果上限 |
| `search.rg_path` | string | `"rg"` | ripgrep 命令路径 |
| `storage.default_notebook` | string | `""` | 默认笔记本 ID |
| `storage.inbox_path` | string | `"/"` | 收集箱路径 |

---

## 六、错误处理

### 错误分类与处理策略

| 错误类型 | 触发条件 | 处理方式 |
|---------|---------|---------|
| 配置错误 | Token 无效、端口错误 | 启动时抛出详细错误，提示用户检查配置 |
| 思源未启动 | 连接 `127.0.0.1:6806` 失败 | 工具调用时返回 `McpError("思源笔记未运行，请先启动思源笔记")` |
| API 错误 | 思源返回非 200 | 透传思源错误信息 |
| 代码库路径不存在 | `repos[].path` 不可访问 | 跳过该路径，在 `skipped_repos` 字段标记 |
| ripgrep 未安装 | `rg` 命令执行失败 | 返回错误提示安装 ripgrep |
| 网络超时 | 思源请求超时 | 重试 1 次后返回超时错误 |

### 工具返回值约定

**成功**：直接返回数据对象（如 `SySaveResult`、`SyFindResult`）

**错误**：抛出 `McpError`（标准 MCP 错误协议），Claude 会展示错误消息给用户

---

## 七、依赖项

### Python 依赖

```toml
[project]
name = "siyuan-mcp"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",      # MCP Python SDK
    "pyyaml>=6.0",     # YAML 解析
    "httpx>=0.27",     # 异步 HTTP 客户端
]
```

### 系统依赖

- **ripgrep (rg)** — 代码搜索引擎（运行时依赖，非 Python 包）
  - 安装：`winget install BurntSushi.ripgrep` / `apt install ripgrep` / `brew install ripgrep`
  - 可选：未安装时 `code-find` 返回安装提示，不影响其他工具

### 开发依赖

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.4",
]
```

---

## 八、配置示例（MCP 客户端注册）

### Claude Code（CLI） — `claude.json`

```json
{
  "mcpServers": {
    "siyuan-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "D:/Code/siyuan-bridge", "python", "-m", "siyuan_mcp"]
    }
  }
}
```

### Claude Desktop — `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "siyuan-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "D:/Code/siyuan-bridge", "python", "-m", "siyuan_mcp"]
    }
  }
}
```

### 生产部署（pypi 发布后）

```json
{
  "mcpServers": {
    "siyuan-mcp": {
      "command": "uvx",
      "args": ["siyuan-mcp"]
    }
  }
}
```

---

## 九、安全考虑

1. **思源 Token** — 保存在本地 YAML 文件中，不硬编码在代码里
2. **代码库路径** — 只搜索用户明确配置的路径，不扫描全盘
3. **HTTP 连接** — 默认只连 localhost，不泄露到外网
4. **MCP stdio** — 进程隔离，MCP 服务只通过标准输入输出通信，不暴露网络端口

---

## 十、后续扩展（非 V1）

| 功能 | 工具 | 计划阶段 |
|------|------|---------|
| 今日日记 | `sy-today` | Phase 2 |
| 项目笔记 | `sy-project` | Phase 2 |
| 知识问答 | `sy-ask` | Phase 2 |
| 项目总结 | `sy-summarize` | Phase 3 |
| 项目审查 | `sy-review` | Phase 3 |
| 自动分类 | AI 自动判断笔记类型 | Phase 3 |
| 标签系统 | 自动生成标签写入思源 | Phase 3 |
| pypi 发布 | `pip install siyuan-mcp` | Phase 3 |

---

## 十一、规格自检记录

- [x] **占位符扫描** — 所有章节均有实际内容，无 TODO/待定
- [x] **内部一致性** — 架构描述与工具定义匹配，配置项与代码结构一致
- [x] **范围检查** — V1 聚焦 3 个工具+配置系统，可独立发布
- [x] **模糊性检查** — 命名规则(sy-/code-前缀)、搜索模式(normal/ai)、配置优先级均已明确
