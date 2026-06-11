# siyuan-mcp

连接 **Claude** 与 **[思源笔记](https://github.com/siyuan-note/siyuan)** 的 MCP 服务。通过低层级、确定性的工具管理知识库。

## 工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `sy-notebook` | 列出笔记本 | — |
| `sy-list` | 列出文档列表 | `notebook` |
| `sy-save` | 保存文档（直接写入） | `content`, `notebook` |
| `sy-read` | 读取文档内容 | `id` |
| `sy-delete` | 删除文档 | `id`, `notebook` |
| `sy-find` | 统一搜索（思源 + 代码） | `query`, `mode` |

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

## 使用示例

```
sy-notebook                    → 列出所有笔记本
sy-list 临时使用               → 列出笔记本下的文档（含 ID）
sy-save 把这段内容保存到思源    → 直接写入文档
sy-read siyuan://blocks/xxx    → 读取文档内容（含标题）
sy-delete siyuan://blocks/xxx  → 删除文档
sy-find OAuth2                 → 搜索知识库
sy-find fn main mode=code      → 搜索本地代码
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

参考 [obsidian-mcp](https://github.com/newtype-01/obsidian-mcp) 的低层级设计哲学：

> 每个工具只做一件事，不做猜测。

AI 负责内容生成，MCP 负责内容存储。工具不承诺"智能"行为。

## 许可证

MIT
