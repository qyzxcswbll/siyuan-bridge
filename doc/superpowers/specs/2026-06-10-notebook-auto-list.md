# 笔记本自动列出 — 设计文档

> 日期: 2026-06-10
> 状态: 待实现

---

## 背景

保存工具（sy-save、sy-today、sy-auto）在未指定 notebook 参数时，
当前返回一句静态提示"请先调用 sy-notebooks 选择笔记本"。
用户需要手动调用 sy-notebooks、记住 ID、再重新调保存——流程断成两步。

## 需求

不传 notebook 时，工具自动把笔记本列表亮出来，让用户在 Claude 里直接选。

## 方案

在保存工具的 ValueError("no_notebook") 处理分支中，
直接调用 `_handle_sy_notebooks` 返回笔记本列表，
Claude 拿到列表后展示给用户，用户选定后 Claude 重新调保存工具带上 notebook ID。

## 改动范围

| 文件 | 改动 |
|------|------|
| `siyuan_mcp/server.py` | 3 个 handler 的 `except ValueError` 分支改为调用 `_handle_sy_notebooks` |
| `siyuan_mcp/server.py` | 移除 `sy-notebooks` 工具声明（不再需要单独注册） |
| `tests/test_server.py` | 更新测试断言 |

## 交互流程

```
用户 → sy-save(content="...")
  → 无 notebook → 自动返回笔记本列表
  → Claude 展示：1. AI知识体系  2. 用户使用 ...
用户 → 第一个
  → Claude 重新调 sy-save(content="...", notebook="202606...")
  → 保存成功
```

## 自检

- [x] 占位符: 无
- [x] 一致性: handler 负责列表拉取，无需新增函数
- [x] 范围: 3 个 handler 改 3 行 + 删 1 个工具声明 + 更新测试
- [x] 模糊性: 无
