# siyuan-mcp

连接 **Claude** 与 **[思源笔记](https://github.com/siyuan-note/siyuan)** 的 MCP 服务。

**v0.1.1 · [PyPI](https://pypi.org/project/siyuan-mcp/)**

## 工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `sy-notebook` | 列出笔记本 | — |
| `sy-list` | 列出文档列表 | `notebook` |
| `sy-save` | 保存文档 | `content`, `notebook` |
| `sy-read` | 读取文档内容 | `id` |
| `sy-delete` | 删除文档 | `id`, `notebook` |
| `sy-find` | 搜索（思源+代码） | `query`, `mode` |

## 安装

```bash
pip install siyuan-mcp
```

### 注册到 Claude（一步）

```bash
siyuan-mcp-install
```

重启 VS Code 即可。

## 使用示例

```
sy-notebook                    → 列出所有笔记本
sy-list 临时使用               → 列出文档（含ID）
sy-save 把这段内容保存到思源    → 直接写入
sy-read siyuan://blocks/xxx    → 读取文档
sy-delete siyuan://blocks/xxx  → 删除文档
sy-find OAuth2                 → 搜索
sy-find fn main mode=code      → 代码搜索
```

## 配置

```bash
cp config.yaml.example config.yaml
# 填入 siyuan.token
```

## 开发

```bash
pip install -e ".[dev]"
pytest -v
python -m siyuan_mcp
```

## 设计原则

参考 obsidian-mcp 的低层级设计哲学：**每个工具只做一件事，不做猜测。** AI 负责内容生成，MCP 负责内容存储。

## 许可证

MIT
