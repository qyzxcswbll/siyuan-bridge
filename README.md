# siyuan-mcp

连接 **Claude** 与 **[思源笔记](https://github.com/siyuan-note/siyuan)** 的 MCP 服务。通过低层级、确定性的工具管理知识库。

## 工具

| 工具 | 功能 | 参数 | 说明 |
|------|------|------|------|
| `sy-notebook` | 列出笔记本 | — | 返回所有笔记本的编号和名称，供其他工具引用 |
| `sy-list` | 列出文档列表 | `notebook`（笔记本序号或名称） | 返回文档标题 + ID，该 ID 用于 `sy-read` / `sy-delete` |
| `sy-save` | 保存文档（直接写入） | `content`（Markdown 内容，**必填**）<br>`notebook`（可选，默认索引 0） | 自动提取标题、生成唯一路径；返回文档链接 |
| `sy-read` | 读取文档内容 | `id`（文档 ID，**必填**） | ID 为 `siyuan://blocks/xxx` 中的 xxx，通过 sy-list 获取 |
| `sy-delete` | 删除文档 | `id`（文档 ID，**必填**）<br>`notebook`（可选） | ID 来源同上；删除前自动解析文档路径 |
| `sy-find` | 统一搜索 | `query`（关键词，**必填**）<br>`mode`：`normal`（默认）/ `ai` / `code`<br>`limit`（上限，默认 10）<br>`notebook`（限定笔记本，仅 normal/ai）<br>`path`（限定项目，仅 code）<br>`file_type`：`code` / `doc`（仅 code）<br>`context_lines`（上下文行数，仅 code，默认 3） | normal 搜思源全文；ai 语义搜索；code 搜索本地关联代码库 |

## 快速开始

### 前置要求

- **Python 3.10+**
- **思源笔记 v3.6.5+**（运行中，开启网络伺服）
- **ripgrep**（可选，用于 `sy-find mode=code`）
  ```bash
  winget install BurntSushi.ripgrep   # Windows
  brew install ripgrep                # macOS
  apt install ripgrep                 # Linux
  ```

### 安装

```bash
git clone https://github.com/your/siyuan-mcp.git
cd siyuan-mcp
pip install -e .
```

### 配置

```bash
cp config.yaml.example config.yaml
# 配置思源 API Token
```

### 注册到 Claude

```json
{
  "mcpServers": {
    "siyuan-mcp": {
      "command": "python",
      "args": ["-m", "siyuan_mcp"]
    }
  }
}
```

## Claude 集成配置

将以下规则追加到 `~/.claude/CLAUDE.md`，让 Claude 正确处理思源笔记的内容保存：

```markdown
# siyuan-mcp 保存规则

## 文件保存

当指定保存具体文件（如 `README.md`、`config.yaml`）时：
- **原文直存**，不做任何修改、总结或精简
- 连代码块带文字，逐字写入

## 知识保存

当只说"保存"、"总结保存"或"把这段内容保存到思源"，未指定具体文件时：
- **可总结**：精简文字内容，保留核心信息
- **代码块不动**：``` 内的内容必须原文保留
- 标题结构保持层级
```

也可通过一条命令自动注入：

```bash
siyuan-mcp init
```

## 使用示例

```
sy-notebook                    → 列出所有笔记本
sy-list 临时使用               → 列出笔记本下的文档（含 ID）
sy-save 把这段内容保存到思源    → 直接写入文档
sy-read <id>                 → 读取文档内容（ID 通过 sy-list 获取）
sy-delete <id>               → 删除文档（ID 通过 sy-list 获取）
sy-find OAuth2               → 搜索知识库
sy-find fn main mode=code    → 搜索本地代码
```

## 配置项

| 配置项 | 说明 |
|--------|------|
| `siyuan.host` | 思源 API 地址（默认 127.0.0.1） |
| `siyuan.port` | 思源 API 端口（默认 6806） |
| `siyuan.token` | API Token |
| `codebase.repos` | 关联代码库列表 |
| `search.max_results` | 搜索结果上限 |
| `search.rg_path` | ripgrep 路径 |

环境变量：`SIYUAN_HOST` `SIYUAN_PORT` `SIYUAN_TOKEN` `CODEBASE_REPOS` `SEARCH_MAX_RESULTS`

## 开发

```bash
pip install -e ".[dev]"
pytest -v      # 60 个测试
python -m siyuan_mcp
```

## 项目结构

```
siyuan-mcp/
├── siyuan_mcp/
│   ├── server.py            # 6 工具注册 + 分发
│   ├── mapper.py            # 笔记本序号/名称映射
│   ├── tagger.py            # jieba 自动标签
│   ├── siyuan/
│   │   ├── client.py        # 思源 HTTP API
│   │   └── models.py        # 数据模型
│   ├── codebase/
│   │   └── search.py        # ripgrep 搜索
│   └── config/
│       ├── defaults.py
│       └── loader.py
├── tests/                   # 6 个测试文件
├── pyproject.toml
├── config.yaml.example
└── .mcp.json
```

## 设计原则

AI 负责内容生成，MCP 负责内容存储。工具不承诺"智能"行为。

## 许可证

MIT
