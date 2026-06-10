# siyuan-mcp

连接 **Claude** 与 **[思源笔记](https://github.com/siyuan-note/siyuan)** 的 MCP 服务。让你在终端中通过自然语言管理知识库，无需打开思源笔记。

## 功能

| 工具 | 说明 | 分类 |
|------|------|------|
| `sy-save` | 快速保存笔记到思源收集箱 | 笔记保存 |
| `sy-today` | 追加内容到今日日记 | 日记 |
| `sy-find` | 搜索思源知识库（关键词 / AI 语义） | 知识检索 |
| `code-find` | 在关联的本地 Git 项目中搜索代码 | 代码检索 |

## 快速开始

### 前置要求

- **Python 3.10+**
- **思源笔记 v3.6.5+**（运行中，开启网络伺服）
- **ripgrep**（可选，用于 `code-find`）
  ```bash
  # Windows
  winget install BurntSushi.ripgrep
  # macOS
  brew install ripgrep
  # Linux
  apt install ripgrep
  ```

### 安装

```bash
# 克隆仓库
git clone https://github.com/your/siyuan-mcp.git
cd siyuan-mcp

# 安装依赖（推荐使用 uv）
pip install -e .
```

### 配置

```bash
# 复制并编辑配置
cp config.yaml.example config.yaml
# 按需修改——至少配置 codebase.repos 的代码库路径
```

### 注册到 Claude Code

在 `claude.json`（或 VS Code 的 `cline_mcp_settings.json`）中添加：

```json
{
  "mcpServers": {
    "siyuan-mcp": {
      "command": "python",
      "args": ["-m", "siyuan_mcp"],
      "cwd": "D:/Code/siyuan-bridge"
    }
  }
}
```

或者使用 `uv`（推荐）：

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

> **注意**：请将 `D:/Code/siyuan-bridge` 替换为你的实际项目路径。

## 使用示例

```
> 帮我把这段内容保存到思源：JWT 认证的实现思路是...
→ sy-save: ✅ 已保存到思源

> 查一下我关于 OAuth2 的笔记
→ sy-find: 🔍 找到 3 条结果

> 在钱包项目中搜索 Transfer 函数
→ code-find: 🔍 找到 5 处代码匹配
```

## 配置项说明

所有配置项都有合理的默认值，开箱即用。配置加载优先级：

1. `./config.yaml`（当前目录）
2. `~/.siyuan-mcp/config.yaml`（用户目录）
3. 内置默认值
4. 环境变量（最高优先级）

### 思源连接

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `siyuan.host` | string | `127.0.0.1` | 思源 API 地址 |
| `siyuan.port` | int | `6806` | 思源 API 端口 |
| `siyuan.token` | string | `""` | API Token（[获取方式](https://github.com/siyuan-note/siyuan)） |
| `siyuan.workspace` | string | `""` | 工作空间路径（自动检测） |

### 代码库

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `codebase.repos` | array | `[]` | 关联代码库列表 |
| `codebase.repos[].path` | string | — | 本地路径 |
| `codebase.repos[].name` | string | — | 别名（code-find 的 path 参数匹配此项） |

### 搜索

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `search.default_mode` | enum | `normal` | 默认搜索模式：`normal`或`ai` |
| `search.max_results` | int | `10` | 搜索结果数量上限 |
| `search.rg_path` | string | `rg` | ripgrep 命令路径 |

### 存储

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `storage.default_notebook` | string | `""` | 默认笔记本 ID（空=思源默认） |
| `storage.inbox_path` | string | `"/"` | 收集箱路径 |

### 环境变量覆盖

所有配置项均可通过 `{SECTION}_{KEY}` 格式的环境变量覆盖：

```bash
export SIYUAN_HOST="192.168.1.100"
export SIYUAN_TOKEN="your-token-here"
export CODEBASE_REPOS='[{"path": "/projects/wallet", "name": "wallet"}]'
export SEARCH_MAX_RESULTS=20
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest -v

# 代码检查
ruff check siyuan_mcp/
```

## 项目结构

```
siyuan-mcp/
├── siyuan_mcp/
│   ├── server.py          # MCP 服务主文件（工具注册+分发）
│   ├── siyuan/            # 思源 API 客户端
│   │   ├── client.py      # HTTP API 封装
│   │   └── models.py      # 数据模型
│   ├── codebase/          # 代码库搜索
│   │   └── search.py      # ripgrep 封装
│   └── config/            # 配置系统
│       ├── loader.py      # YAML 加载+合并+校验
│       └── defaults.py    # 内置默认值
├── tests/
│   ├── test_config_loader.py
│   ├── test_siyuan_client.py
│   ├── test_codebase_search.py
│   └── test_server.py
├── config.yaml.example
└── pyproject.toml
```

## 许可证

MIT
